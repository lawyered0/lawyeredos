from __future__ import annotations

import json
import hashlib
import os
import sqlite3
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from lawyeredos import codex_setup
from lawyeredos.codex_setup import (
    apply_plan,
    build_plan,
    dependency_report,
    normalize_answers,
    rollback_upgrade,
)
from lawyeredos.config import load_config
from lawyeredos.review_orchestrator import prepare
from lawyeredos.review_bundle import create_manifest


class CodexSetupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.workspace = self.root / "fictional-workspace"
        def accepted_dependencies(modules):
            report = dependency_report(modules)
            for item in report:
                if item["name"] == "Codex host":
                    item["available"] = True
                    item["detail"] = "test fixture"
            return report
        self.dependency_patch = patch(
            "lawyeredos.codex_setup.dependency_report",
            side_effect=accepted_dependencies,
        )
        self.dependency_patch.start()
        self.addCleanup(self.dependency_patch.stop)

    def tearDown(self):
        self.temp.cleanup()

    def answers(self, **changes):
        values = dict(
            workspace=self.workspace,
            branding_mode="neutral",
            branding_label="Northstar Legal Lab",
            jurisdiction="none",
            modules_raw="matter,tracker,review",
            mail="skip",
            calendar="off",
            calendar_id="",
            existing="error",
        )
        values.update(changes)
        return normalize_answers(**values)

    def test_workspace_refuses_home_and_home_alias_without_changes(self):
        home = self.root / "fictional-home"
        home.mkdir()
        marker = home / "keep.txt"
        marker.write_text("fictional personal customization", encoding="utf-8")
        alias = self.root / "home-alias"
        alias.symlink_to(home, target_is_directory=True)
        with patch("lawyeredos.codex_setup.Path.home", return_value=home):
            for workspace in (home, alias):
                with self.subTest(workspace=workspace):
                    with self.assertRaisesRegex(ValueError, "home directory"):
                        build_plan(self.answers(workspace=workspace))
        self.assertEqual(marker.read_text(encoding="utf-8"), "fictional personal customization")
        self.assertEqual(list(home.iterdir()), [marker])

    def test_workspace_refuses_every_user_global_host_namespace(self):
        home = self.root / "fictional-home"
        home.mkdir()
        with patch("lawyeredos.codex_setup.Path.home", return_value=home):
            for namespace in (".claude", ".codex", ".agents"):
                for workspace in (home / namespace, home / namespace / "nested"):
                    with self.subTest(workspace=workspace):
                        with self.assertRaisesRegex(ValueError, "user-global"):
                            build_plan(self.answers(workspace=workspace))
        self.assertEqual(list(home.iterdir()), [])

    def test_apply_rechecks_workspace_home_boundary_before_writing(self):
        home = self.root / "fictional-home"
        home.mkdir()
        with patch("lawyeredos.codex_setup.Path.home", return_value=home):
            plan = build_plan(self.answers())
        # A retained plan must not become a global installation in a new host context.
        with patch("lawyeredos.codex_setup.Path.home", return_value=self.workspace):
            with self.assertRaisesRegex(ValueError, "home directory"):
                apply_plan(plan)
        self.assertFalse(self.workspace.exists())

    def test_preview_is_side_effect_free_and_host_scoped(self):
        plan = build_plan(self.answers(), require_new_workspace=True)
        self.assertFalse(self.workspace.exists())
        self.assertEqual(plan["host"], "codex")
        self.assertIn(".agents/skills/lawyeredos-work-on-matter", plan["project_skills"]["matter"])
        self.assertFalse(any(".claude" in value for value in plan["project_skills"].values()))
        self.assertTrue(any("~/.codex" in note for note in plan["notes"]))

    def test_apply_preserves_unrelated_skills_and_codex_config_and_repeats(self):
        private_skill = self.workspace / ".agents" / "skills" / "private-user-skill" / "SKILL.md"
        private_skill.parent.mkdir(parents=True)
        private_skill.write_text("---\nname: private-user-skill\ndescription: private\n---\n", encoding="utf-8")
        codex_config = self.workspace / ".codex" / "config.toml"
        codex_config.parent.mkdir()
        codex_config.write_text('model = "private-choice"\n', encoding="utf-8")
        first = apply_plan(build_plan(self.answers(existing="error")))
        self.assertTrue(first["ok"])
        self.assertEqual(private_skill.read_text(encoding="utf-8"), "---\nname: private-user-skill\ndescription: private\n---\n")
        self.assertEqual(codex_config.read_text(encoding="utf-8"), 'model = "private-choice"\n')
        second = apply_plan(build_plan(self.answers(existing="reuse")))
        self.assertTrue(second["idempotent"])
        config = load_config(first["config"])
        self.assertEqual(config.branding_label, "Northstar Legal Lab")

    def test_collision_fails_closed(self):
        collision = self.workspace / ".agents" / "skills" / "lawyeredos-work-on-matter"
        collision.mkdir(parents=True)
        (collision / "SKILL.md").write_text("private", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "not managed"):
            build_plan(self.answers())
        self.assertEqual((collision / "SKILL.md").read_text(encoding="utf-8"), "private")

    def test_symlinked_project_discovery_and_config_replace_fail_closed(self):
        outside = self.root / "outside"
        outside.mkdir()
        self.workspace.mkdir()
        (self.workspace / ".agents").symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "must not be a symlink"):
            build_plan(self.answers())
        (self.workspace / ".agents").unlink()
        apply_plan(build_plan(self.answers()))
        with self.assertRaisesRegex(ValueError, "does not replace"):
            build_plan(self.answers(existing="replace"))

    def test_apply_rechecks_managed_directories_after_preview_symlink_swap(self):
        plan = build_plan(self.answers())
        outside = self.root / "outside"
        outside.mkdir()
        marker = outside / "keep.txt"
        marker.write_text("preserve", encoding="utf-8")
        self.workspace.mkdir()
        (self.workspace / ".agents").symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "must not be a symlink"):
            apply_plan(plan)
        self.assertEqual(marker.read_text(encoding="utf-8"), "preserve")
        self.assertEqual(list(outside.iterdir()), [marker])

    def test_apply_refuses_leaf_symlinks_created_after_preview(self):
        plan = build_plan(self.answers())
        outside = self.root / "outside.txt"
        outside.write_text("preserve", encoding="utf-8")
        outside.chmod(0o640)
        setup_root = self.workspace / ".lawyeredos"
        setup_root.mkdir(parents=True)
        Path(plan["runner"]).symlink_to(outside)
        with self.assertRaisesRegex(ValueError, "managed file must not be a symlink"):
            apply_plan(plan)
        self.assertEqual(outside.read_text(encoding="utf-8"), "preserve")
        self.assertEqual(outside.stat().st_mode & 0o777, 0o640)

    def test_apply_refuses_valid_discovery_file_that_appears_after_preview(self):
        plan = build_plan(self.answers())
        discovery = Path(plan["discovery"])
        discovery.parent.mkdir(parents=True)
        content = json.dumps({
            "schema_version": 2,
            "host": "codex",
            "package_digest": plan["package_digest"],
            "managed_paths": [],
            "managed_fingerprints": {},
        })
        discovery.write_text(content, encoding="utf-8")
        discovery.chmod(0o640)
        with self.assertRaisesRegex(ValueError, "changed after preview"):
            apply_plan(plan)
        self.assertEqual(discovery.read_text(encoding="utf-8"), content)
        self.assertEqual(discovery.stat().st_mode & 0o777, 0o640)

    def test_apply_refuses_discovery_skill_symlink_created_after_preview(self):
        plan = build_plan(self.answers())
        outside = self.root / "outside-skill"
        outside.mkdir()
        marker = outside / "SKILL.md"
        marker.write_text("private", encoding="utf-8")
        skill = Path(plan["project_skills"]["matter"])
        skill.parent.mkdir(parents=True)
        skill.symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "appeared after preview"):
            apply_plan(plan)
        self.assertEqual(marker.read_text(encoding="utf-8"), "private")

    def test_apply_refuses_tracker_that_appears_after_preview(self):
        plan = build_plan(self.answers())
        tracker = self.workspace / ".lawyeredos" / "data" / "matters.sqlite3"
        tracker.parent.mkdir(parents=True)
        tracker.write_bytes(b"private tracker")
        tracker.chmod(0o640)
        with self.assertRaisesRegex(ValueError, "changed after preview"):
            apply_plan(plan)
        self.assertEqual(tracker.read_bytes(), b"private tracker")
        self.assertEqual(tracker.stat().st_mode & 0o777, 0o640)

    def test_tracker_race_is_never_registered_for_rollback(self):
        plan = build_plan(self.answers())
        tracker = self.workspace / ".lawyeredos" / "data" / "matters.sqlite3"

        def simulate_race(path):
            path.write_bytes(b"concurrent private tracker")
            raise ValueError("tracker path appeared after preview")

        with patch("lawyeredos.codex_setup.initialize_tracker_exclusive", side_effect=simulate_race):
            with self.assertRaisesRegex(RuntimeError, "automatic rollback was incomplete"):
                apply_plan(plan)
        self.assertEqual(tracker.read_bytes(), b"concurrent private tracker")

    def test_installed_skills_use_codex_runtime_and_session_mail_boundary(self):
        result = apply_plan(build_plan(self.answers(mail="session-tools")))
        work_skill = Path(result["skills"]["matter"]) / "SKILL.md"
        text = work_skill.read_text(encoding="utf-8")
        self.assertIn("codex-session-tools", text)
        self.assertIn(".lawyeredos/lawyeredos-run", text)
        self.assertIn(".lawyeredos/config.toml", text)
        self.assertNotIn("Require the `LAWYEREDOS_CONFIG` environment variable", text)
        self.assertNotIn("${LAWYEREDOS_ROOT}", text)
        self.assertIn("A closed matter remains read-only", text)
        self.assertIn("without a preliminary full orientation", text)
        self.assertIn("brief.truncated: true", text)
        self.assertIn("From address alone does not prove", text)
        self.assertEqual(load_config(result["config"]).mail_adapter, "codex-session-tools")

        tracker = (Path(result["skills"]["tracker"]) / "SKILL.md").read_text(encoding="utf-8")
        panel = (Path(result["skills"]["review"]) / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("No located hit in the local register fields", tracker)
        self.assertIn("Disposition every material finding", panel)
        self.assertIn("panel concern alone never", panel)

    def test_installed_codex_skill_tree_projectizes_nested_runtime_references(self):
        result = apply_plan(build_plan(self.answers(
            modules_raw="matter,tracker,letters,redline,calendar,review",
        )))
        installed = Path(result["plugin"]) / ".lawyeredos-codex-project" / "skills"
        unresolved = []
        for path in installed.rglob("*"):
            if not path.is_file():
                continue
            text = path.read_text(encoding="utf-8")
            if any(token in text for token in (
                "LAWYEREDOS_ROOT", "LAWYEREDOS_PYTHON", "LAWYEREDOS_CONFIG",
            )):
                unresolved.append(str(path.relative_to(installed)))
        self.assertEqual(unresolved, [])

        mail_reference = (
            installed / "lawyeredos-work-on-matter" / "references" / "mail-intake.md"
        ).read_text(encoding="utf-8")
        self.assertIn(
            'PYTHONPATH=".lawyeredos/current-codex/src" ".lawyeredos/lawyeredos-run" '
            '-m lawyeredos.mail_intake plan',
            mail_reference,
        )
        tracker_reference = (
            installed / "lawyeredos-matter-tracker" / "SKILL.md"
        ).read_text(encoding="utf-8")
        self.assertIn("database path from `.lawyeredos/config.toml`", tracker_reference)

        matter = self.workspace / "2032-001-northstar"
        matter.mkdir()
        database = self.workspace / ".lawyeredos" / "data" / "matters.sqlite3"
        with sqlite3.connect(database) as connection:
            connection.execute(
                """INSERT INTO matters(file_number, client, description, matter_folder,
                status, opposing_party, primary_email, created_at, updated_at)
                VALUES (?, ?, ?, ?, 'open', ?, ?, ?, ?)""",
                (
                    "2032-001", "Northstar Bakery Ltd.", "Fictional supply dispute",
                    "2032-001-northstar", "Harbor Paper Co.", "client@example.invalid",
                    "2032-01-01", "2032-01-01",
                ),
            )
        completed = subprocess.run(
            [
                str(self.workspace / ".lawyeredos" / "lawyeredos-run"),
                "-m", "lawyeredos.mail_intake", "plan",
                "--config", ".lawyeredos/config.toml", "--identifier", "Northstar",
            ],
            cwd=self.workspace, capture_output=True, text=True, check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        planned = json.loads(completed.stdout)
        self.assertEqual(planned["status"], "mail_unavailable")
        self.assertNotIn("ModuleNotFoundError", completed.stderr)

    def test_codex_setup_maps_portable_imap_without_storing_a_secret(self):
        plan = build_plan(self.answers(mail="gmail-imap"))
        self.assertEqual(plan["answers"]["mail_adapter"], "gmail-imap-readonly")
        self.assertIn("LAWYEREDOS_GMAIL_IMAP_SECRET", plan["config_preview"])
        self.assertNotIn("app-password-fixture", plan["config_preview"])

    def test_review_jobs_are_codex_namespaced_without_changing_sources(self):
        matter = self.root / "matter"
        matter.mkdir()
        deliverable = matter / "draft.txt"
        source = matter / "source.txt"
        deliverable.write_text("Fictional draft", encoding="utf-8")
        source.write_text("Fictional source", encoding="utf-8")
        manifest_path = self.root / "manifest.json"
        tasks_path = self.root / "tasks.json"
        manifest_path.write_text(
            json.dumps(create_manifest(deliverable, [source], matter, host="codex")),
            encoding="utf-8",
        )
        before = {path: path.read_bytes() for path in (deliverable, source)}
        result = prepare(manifest_path, tasks_path, host="codex")
        self.assertEqual(result["task_count"], 4)
        tasks = json.loads(tasks_path.read_text(encoding="utf-8"))
        self.assertEqual(tasks["schema"], "codex-review-tasks-v1")
        self.assertTrue(all(task["read_only"] for task in tasks["tasks"]))
        self.assertEqual(before, {path: path.read_bytes() for path in (deliverable, source)})

    def test_failed_apply_rolls_back_created_paths_and_preserves_private_file(self):
        self.workspace.mkdir()
        private = self.workspace / "private.txt"
        private.write_text("preserve", encoding="utf-8")

        def fail_after_partial_tracker(path):
            path.write_bytes(b"partial")
            raise OSError("simulated interruption")

        with patch("lawyeredos.setup_wizard.initialize", side_effect=fail_after_partial_tracker):
            with self.assertRaisesRegex(OSError, "simulated interruption"):
                apply_plan(build_plan(self.answers()))
        self.assertEqual(private.read_text(encoding="utf-8"), "preserve")
        self.assertFalse((self.workspace / ".lawyeredos").exists())
        self.assertFalse((self.workspace / ".agents").exists())

    def test_cancelled_apply_rolls_back_partial_paths(self):
        def interrupt_after_partial_tracker(path):
            path.write_bytes(b"partial")
            raise KeyboardInterrupt

        with patch("lawyeredos.setup_wizard.initialize", side_effect=interrupt_after_partial_tracker):
            with self.assertRaises(KeyboardInterrupt):
                apply_plan(build_plan(self.answers()))
        self.assertFalse(self.workspace.exists())

    def test_cancelled_apply_preserves_concurrently_created_unrelated_file(self):
        plan = build_plan(self.answers())

        def interrupt_during_plugin_copy(source, destination, *args, **kwargs):
            unrelated = self.workspace / ".agents" / "skills" / "unrelated-concurrent.txt"
            unrelated.write_text("preserve", encoding="utf-8")
            raise KeyboardInterrupt

        with patch("lawyeredos.codex_setup.shutil.copytree", side_effect=interrupt_during_plugin_copy):
            with self.assertRaisesRegex(RuntimeError, "automatic rollback was incomplete"):
                apply_plan(plan)
        unrelated = self.workspace / ".agents" / "skills" / "unrelated-concurrent.txt"
        self.assertEqual(unrelated.read_text(encoding="utf-8"), "preserve")

    def test_runtime_only_upgrade_rewrites_verified_wrapper_and_rolls_back(self):
        first = apply_plan(build_plan(self.answers()))
        runner = self.workspace / ".lawyeredos" / "lawyeredos-run"
        original = runner.read_bytes()
        other_runtime = self.root / "fictional-python"
        other_runtime.symlink_to(codex_setup.sys.executable)
        with patch("lawyeredos.codex_setup.sys.executable", str(other_runtime)):
            plan = build_plan(self.answers(existing="reuse"))
            self.assertTrue(any(item["action"] == "write_runtime_wrapper" for item in plan["operations"]))
            upgraded = apply_plan(plan)
        self.assertNotEqual(runner.read_bytes(), original)
        self.assertIn(str(other_runtime).encode(), runner.read_bytes())
        self.assertTrue(Path(upgraded["upgrade_rollback_state"]).exists())
        self.assertTrue(rollback_upgrade(self.workspace)["ok"])
        self.assertEqual(runner.read_bytes(), original)
        restored = build_plan(self.answers(existing="reuse"))
        self.assertEqual(restored["prior_fingerprints"][str(runner.resolve())], codex_setup.managed_fingerprint(runner))

    def test_runtime_upgrade_rollback_refuses_tampered_wrapper_snapshot(self):
        apply_plan(build_plan(self.answers()))
        runtime = self.root / "fictional-python"
        runtime.symlink_to(codex_setup.sys.executable)
        with patch("lawyeredos.codex_setup.sys.executable", str(runtime)):
            upgraded = apply_plan(build_plan(self.answers(existing="reuse")))
        runner = self.workspace / ".lawyeredos" / "lawyeredos-run"
        applied = runner.read_bytes()
        state = Path(upgraded["upgrade_rollback_state"])
        record = json.loads(state.read_text(encoding="utf-8"))
        record["prior_wrapper_files"][str(runner.resolve())]["content_hex"] = b"fictional tampering".hex()
        state.write_text(json.dumps(record), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "does not match its fingerprint"):
            rollback_upgrade(self.workspace)
        self.assertEqual(runner.read_bytes(), applied)

    def test_runtime_upgrade_rollback_recovers_wrapper_on_discovery_failure(self):
        apply_plan(build_plan(self.answers()))
        runtime = self.root / "fictional-python"
        runtime.symlink_to(codex_setup.sys.executable)
        with patch("lawyeredos.codex_setup.sys.executable", str(runtime)):
            upgraded = apply_plan(build_plan(self.answers(existing="reuse")))
        runner = self.workspace / ".lawyeredos" / "lawyeredos-run"
        applied = runner.read_bytes()
        discovery = Path(upgraded["discovery"])
        original_replace = codex_setup.replace_private_file
        def fail_discovery(path, content):
            if path == discovery:
                raise OSError("fictional discovery failure")
            return original_replace(path, content)
        with patch("lawyeredos.codex_setup.replace_private_file", side_effect=fail_discovery):
            with self.assertRaisesRegex(OSError, "fictional discovery failure"):
                rollback_upgrade(self.workspace)
        self.assertEqual(runner.read_bytes(), applied)
        self.assertEqual(runner.stat().st_mode & 0o777, 0o700)
        self.assertTrue(Path(upgraded["upgrade_rollback_state"]).exists())

    def test_managed_links_upgrade_to_new_versioned_core(self):
        first = apply_plan(build_plan(self.answers()))
        old_plugin = Path(first["plugin"])
        with patch("lawyeredos.codex_setup.package_digest", return_value="a" * 64):
            upgraded = apply_plan(build_plan(self.answers(existing="reuse")))
        new_plugin = Path(upgraded["plugin"])
        self.assertNotEqual(old_plugin, new_plugin)
        self.assertTrue(old_plugin.is_dir())
        self.assertEqual((self.workspace / ".lawyeredos" / "current-codex").resolve(), new_plugin.resolve())
        for path in upgraded["skills"].values():
            self.assertTrue(Path(path).resolve().is_relative_to(new_plugin.resolve()))

    def test_successful_upgrade_can_roll_back_links_without_touching_matter_data(self):
        first = apply_plan(build_plan(self.answers()))
        old_plugin = Path(first["plugin"])
        tracker = self.workspace / ".lawyeredos" / "data" / "matters.sqlite3"
        with sqlite3.connect(tracker) as connection:
            connection.execute("UPDATE meta SET value='17' WHERE key='revision'")
        unrelated = self.workspace / "fictional-client-note.txt"
        unrelated.write_text("preserve", encoding="utf-8")
        with patch("lawyeredos.codex_setup.package_digest", return_value="b" * 64):
            upgraded = apply_plan(build_plan(self.answers(existing="reuse")))
        new_plugin = Path(upgraded["plugin"])
        self.assertTrue(Path(upgraded["upgrade_rollback_state"]).is_file())

        result = rollback_upgrade(self.workspace)

        self.assertTrue(result["ok"])
        self.assertEqual((self.workspace / ".lawyeredos" / "current-codex").resolve(), old_plugin.resolve())
        for path in first["skills"].values():
            self.assertTrue(Path(path).resolve().is_relative_to(old_plugin.resolve()))
        with sqlite3.connect(tracker) as connection:
            self.assertEqual(connection.execute(
                "SELECT value FROM meta WHERE key='revision'"
            ).fetchone()[0], "17")
        self.assertEqual(unrelated.read_text(encoding="utf-8"), "preserve")
        self.assertTrue(new_plugin.is_dir())
        self.assertFalse(Path(upgraded["upgrade_rollback_state"]).exists())

    def test_upgrade_rollback_refuses_managed_core_drift_without_mutation(self):
        first = apply_plan(build_plan(self.answers()))
        old_plugin = Path(first["plugin"])
        with patch("lawyeredos.codex_setup.package_digest", return_value="c" * 64):
            upgraded = apply_plan(build_plan(self.answers(existing="reuse")))
        new_plugin = Path(upgraded["plugin"])
        changed = new_plugin / "src" / "lawyeredos" / "config.py"
        changed.write_text(changed.read_text(encoding="utf-8") + "\n# fictional drift\n", encoding="utf-8")

        with self.assertRaisesRegex(ValueError, "applied Codex core changed"):
            rollback_upgrade(self.workspace)

        self.assertEqual((self.workspace / ".lawyeredos" / "current-codex").resolve(), new_plugin.resolve())
        self.assertNotEqual((self.workspace / ".lawyeredos" / "current-codex").resolve(), old_plugin.resolve())
        self.assertTrue(Path(upgraded["upgrade_rollback_state"]).is_file())

    def test_upgrade_rollback_refuses_retained_prior_core_drift_without_mutation(self):
        first = apply_plan(build_plan(self.answers()))
        old_plugin = Path(first["plugin"])
        with patch("lawyeredos.codex_setup.package_digest", return_value="e" * 64):
            upgraded = apply_plan(build_plan(self.answers(existing="reuse")))
        new_plugin = Path(upgraded["plugin"])
        changed = old_plugin / "src" / "lawyeredos" / "config.py"
        changed.write_text(changed.read_text(encoding="utf-8") + "\n# fictional retained drift\n", encoding="utf-8")

        with self.assertRaisesRegex(ValueError, "retained prior Codex core changed"):
            rollback_upgrade(self.workspace)

        self.assertEqual(
            (self.workspace / ".lawyeredos" / "current-codex").resolve(),
            new_plugin.resolve(),
        )
        self.assertTrue(Path(upgraded["upgrade_rollback_state"]).is_file())

    def test_upgrade_apply_rechecks_retained_prior_core_after_preview(self):
        first = apply_plan(build_plan(self.answers()))
        old_plugin = Path(first["plugin"])
        with patch("lawyeredos.codex_setup.package_digest", return_value="9" * 64):
            plan = build_plan(self.answers(existing="reuse"))
        changed = old_plugin / "src" / "lawyeredos" / "config.py"
        changed.write_text(changed.read_text(encoding="utf-8") + "\n# post-preview retained drift\n", encoding="utf-8")

        with self.assertRaisesRegex(ValueError, "retained prior Codex core changed after preview"):
            apply_plan(plan)

        self.assertEqual(
            (self.workspace / ".lawyeredos" / "current-codex").resolve(),
            old_plugin.resolve(),
        )
        self.assertFalse(Path(plan["plugin"]).exists())

    def test_upgrade_rollback_recovers_applied_links_if_discovery_restore_fails(self):
        apply_plan(build_plan(self.answers()))
        with patch("lawyeredos.codex_setup.package_digest", return_value="d" * 64):
            upgraded = apply_plan(build_plan(self.answers(existing="reuse")))
        new_plugin = Path(upgraded["plugin"])
        discovery = Path(upgraded["discovery"])
        original_replace = codex_setup.replace_private_file

        def fail_discovery(path, content):
            if path == discovery:
                raise OSError("fictional discovery write failure")
            return original_replace(path, content)

        with patch("lawyeredos.codex_setup.replace_private_file", side_effect=fail_discovery):
            with self.assertRaisesRegex(OSError, "fictional discovery write failure"):
                rollback_upgrade(self.workspace)

        self.assertEqual((self.workspace / ".lawyeredos" / "current-codex").resolve(), new_plugin.resolve())
        for path in upgraded["skills"].values():
            self.assertTrue(Path(path).resolve().is_relative_to(new_plugin.resolve()))
        self.assertTrue(Path(upgraded["upgrade_rollback_state"]).is_file())

    def test_installed_codex_core_has_bound_template_manifest(self):
        result = apply_plan(build_plan(self.answers()))
        config = load_config(result["config"])
        self.assertIsNotNone(config.document_template_manifest)
        manifest = json.loads(config.document_template_manifest.read_text(encoding="utf-8"))
        self.assertEqual(manifest["template"], "assets/neutral-letterhead.docx")
        self.assertEqual(
            manifest["sha256"],
            hashlib.sha256(config.document_template.read_bytes()).hexdigest(),
        )

    def test_repeat_install_rejects_tampered_versioned_core(self):
        first = apply_plan(build_plan(self.answers()))
        skill = Path(first["plugin"]) / "skills" / "practice-work-on-matter" / "SKILL.md"
        skill.write_text(skill.read_text(encoding="utf-8") + "\nprivate tamper\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "versioned Codex core content changed"):
            build_plan(self.answers(existing="reuse"))
        self.assertIn("private tamper", skill.read_text(encoding="utf-8"))

    def test_apply_rechecks_versioned_core_after_preview(self):
        first = apply_plan(build_plan(self.answers()))
        plan = build_plan(self.answers(existing="reuse"))
        skill = Path(first["plugin"]) / "skills" / "practice-work-on-matter" / "SKILL.md"
        skill.write_text(skill.read_text(encoding="utf-8") + "\npost-preview tamper\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "changed after preview"):
            apply_plan(plan)
        self.assertIn("post-preview tamper", skill.read_text(encoding="utf-8"))

    def test_repeat_preview_rejects_empty_directory_and_special_entry_in_core(self):
        first = apply_plan(build_plan(self.answers()))
        plugin = Path(first["plugin"])
        empty = plugin / "PRIVATE-EMPTY"
        empty.mkdir()
        with self.assertRaisesRegex(ValueError, "versioned Codex core content changed"):
            build_plan(self.answers(existing="reuse"))
        empty.rmdir()
        fifo = plugin / "PRIVATE-FIFO"
        os.mkfifo(fifo)
        with self.assertRaisesRegex(ValueError, "unsupported filesystem entry"):
            build_plan(self.answers(existing="reuse"))
        fifo.unlink()

    def test_apply_rejects_post_preview_empty_directory_and_special_entry_in_core(self):
        first = apply_plan(build_plan(self.answers()))
        plugin = Path(first["plugin"])
        plan = build_plan(self.answers(existing="reuse"))
        empty = plugin / "PRIVATE-EMPTY"
        empty.mkdir()
        with self.assertRaisesRegex(ValueError, "changed after preview"):
            apply_plan(plan)
        empty.rmdir()
        plan = build_plan(self.answers(existing="reuse"))
        fifo = plugin / "PRIVATE-FIFO"
        os.mkfifo(fifo)
        with self.assertRaisesRegex(ValueError, "unsupported filesystem entry"):
            apply_plan(plan)
        fifo.unlink()

    def test_schema_one_discovery_migrates_without_broadening_ownership(self):
        first = apply_plan(build_plan(self.answers()))
        discovery_path = Path(first["discovery"])
        discovery = json.loads(discovery_path.read_text(encoding="utf-8"))
        discovery["schema_version"] = 1
        discovery.pop("managed_fingerprints")
        discovery_path.write_text(json.dumps(discovery), encoding="utf-8")
        repeated = apply_plan(build_plan(self.answers(existing="reuse")))
        self.assertTrue(repeated["ok"])
        migrated = json.loads(discovery_path.read_text(encoding="utf-8"))
        self.assertEqual(migrated["schema_version"], 2)
        self.assertEqual(set(migrated["managed_paths"]), set(migrated["managed_fingerprints"]))


if __name__ == "__main__":
    unittest.main()
