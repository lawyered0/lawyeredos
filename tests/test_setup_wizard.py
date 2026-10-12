from __future__ import annotations

import json
import hashlib
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from lawyeredos.config import load_config
from lawyeredos.setup_wizard import (
    Answers,
    apply_plan,
    build_plan,
    dependency_report,
    main,
    normalize_answers,
    render_launcher,
    render_terminal_launcher,
    rollback,
    _backup,
    _undo_failed_apply,
)


class SetupWizardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.workspace = self.root / "fictional-workspace"
        def accepted_dependencies(modules=()):
            report = dependency_report(modules)
            for item in report:
                if item["name"] == "Claude Desktop":
                    item["available"] = True
                    item["detail"] = "test fixture"
            return report
        self.dependency_patch = patch(
            "lawyeredos.setup_wizard.dependency_report",
            side_effect=accepted_dependencies,
        )
        self.dependency_patch.start()
        self.addCleanup(self.dependency_patch.stop)

    def tearDown(self):
        self.temp.cleanup()

    def answers(self, **changes) -> Answers:
        values = dict(
            workspace=self.workspace,
            branding_mode="firm",
            branding_label="Northstar Legal Lab",
            jurisdiction="none",
            modules=("matter", "tracker", "letters", "redline", "review"),
            mail_adapter="unavailable",
            calendar_adapter="unavailable",
            calendar_id="",
            existing_config="reuse",
        )
        values.update(changes)
        return Answers(**values)

    def test_workspace_refuses_home_and_home_alias_without_changes(self):
        home = self.root / "fictional-home"
        home.mkdir()
        marker = home / "keep.txt"
        marker.write_text("fictional personal customization", encoding="utf-8")
        alias = self.root / "home-alias"
        alias.symlink_to(home, target_is_directory=True)
        with patch("lawyeredos.setup_wizard.Path.home", return_value=home):
            for workspace in (home, alias):
                with self.subTest(workspace=workspace):
                    with self.assertRaisesRegex(ValueError, "home directory"):
                        build_plan(self.answers(workspace=workspace))
        self.assertEqual(marker.read_text(encoding="utf-8"), "fictional personal customization")
        self.assertEqual(list(home.iterdir()), [marker])

    def test_workspace_refuses_every_user_global_host_namespace(self):
        home = self.root / "fictional-home"
        home.mkdir()
        with patch("lawyeredos.setup_wizard.Path.home", return_value=home):
            for namespace in (".claude", ".codex", ".agents"):
                for workspace in (home / namespace, home / namespace / "nested"):
                    with self.subTest(workspace=workspace):
                        with self.assertRaisesRegex(ValueError, "user-global"):
                            build_plan(self.answers(workspace=workspace))
        self.assertEqual(list(home.iterdir()), [])

    def test_apply_rechecks_workspace_home_boundary_before_writing(self):
        home = self.root / "fictional-home"
        home.mkdir()
        with patch("lawyeredos.setup_wizard.Path.home", return_value=home):
            plan = build_plan(self.answers())
        # A retained plan must not become a global installation in a new host context.
        with patch("lawyeredos.setup_wizard.Path.home", return_value=self.workspace):
            with self.assertRaisesRegex(ValueError, "home directory"):
                apply_plan(plan)
        self.assertFalse(self.workspace.exists())

    def test_rollback_cli_refusal_exits_nonzero(self):
        apply_plan(build_plan(self.answers()))
        config = self.workspace / ".lawyeredos" / "config.toml"
        config.write_text(config.read_text(encoding="utf-8") + "\n# fictional user modification\n", encoding="utf-8")
        self.assertEqual(main(["--workspace", str(self.workspace), "--rollback"]), 2)

    def test_interactive_eof_cancels_without_traceback(self):
        with patch("builtins.input", side_effect=EOFError):
            self.assertEqual(main([]), 1)
        self.assertFalse(self.workspace.exists())

    def test_preview_has_no_side_effects_or_secret_values(self):
        plan = build_plan(self.answers())
        self.assertFalse(self.workspace.exists())
        self.assertIn("Northstar Legal Lab", plan["config_preview"])
        self.assertNotIn("password", plan["config_preview"].lower())
        self.assertNotIn("api_key", plan["config_preview"].lower())
        self.assertIn("LAWYEREDOS_GMAIL_TOKEN", plan["config_preview"])
        self.assertIn("LAWYEREDOS_GMAIL_IMAP_ACCOUNT", plan["config_preview"])
        self.assertIn("LAWYEREDOS_GMAIL_IMAP_SECRET", plan["config_preview"])
        self.assertIn('gmail_imap_keychain_service = ""', plan["config_preview"])
        self.assertEqual(plan["runtime_python"], os.path.abspath(sys.executable))
        launcher = render_launcher(plan)
        self.assertIn("exec open -a Claude", launcher)
        self.assertNotIn("exec claude", launcher)
        self.assertNotIn("--plugin-dir", launcher)
        terminal = render_terminal_launcher(plan)
        self.assertIn("exec claude", terminal)
        self.assertNotIn("--desktop", terminal)

    def test_mail_choice_maps_connector_skip_and_experimental_routes(self):
        common = dict(
            workspace=self.workspace, branding_mode="neutral",
            branding_label="Organization", jurisdiction="none",
            modules_raw="matter,tracker", calendar="off", calendar_id="",
            existing="reuse",
        )
        connector = normalize_answers(mail="claude-gmail", **common)
        skipped = normalize_answers(mail="skip", **common)
        experimental = normalize_answers(mail="gmail-readonly", **common)
        imap = normalize_answers(mail="gmail-imap", **common)
        self.assertEqual(connector.mail_adapter, "claude-gmail-connector")
        self.assertEqual(skipped.mail_adapter, "unavailable")
        self.assertEqual(experimental.mail_adapter, "gmail-api-readonly")
        self.assertEqual(imap.mail_adapter, "gmail-imap-readonly")
        connector_plan = build_plan(connector)
        self.assertTrue(any("Gmail connector selected" in note for note in connector_plan["notes"]))
        self.assertTrue(any("never treats mail access" in note for note in connector_plan["notes"]))

    def test_experimental_mail_route_fails_validation_without_credential(self):
        result = apply_plan(build_plan(self.answers(mail_adapter="gmail-api-readonly")))
        environment = os.environ.copy()
        environment.pop("LAWYEREDOS_GMAIL_TOKEN", None)
        validation = subprocess.run(
            [
                sys.executable,
                str(Path(__file__).resolve().parents[1] / "scripts" / "validate_setup.py"),
                "--config", result["config"],
            ],
            capture_output=True, text=True, check=False, env=environment,
        )
        self.assertEqual(validation.returncode, 2)
        self.assertIn("Gmail token environment variable is not set", validation.stdout)

    def test_imap_route_requires_user_configured_credential_source(self):
        result = apply_plan(build_plan(self.answers(mail_adapter="gmail-imap-readonly")))
        environment = os.environ.copy()
        environment.pop("LAWYEREDOS_GMAIL_IMAP_ACCOUNT", None)
        environment.pop("LAWYEREDOS_GMAIL_IMAP_SECRET", None)
        validation = subprocess.run(
            [
                sys.executable,
                str(Path(__file__).resolve().parents[1] / "scripts" / "validate_setup.py"),
                "--config", result["config"],
            ],
            capture_output=True, text=True, check=False, env=environment,
        )
        self.assertEqual(validation.returncode, 2)
        self.assertIn("user-created macOS Keychain service", validation.stdout)

    def test_dependency_requirements_follow_selected_modules(self):
        core = {item["name"]: item for item in dependency_report(("matter", "tracker"))}
        self.assertFalse(core["openpyxl"]["required"])
        self.assertFalse(core["python-docx"]["required"])
        self.assertFalse(core["lxml"]["required"])
        self.assertFalse(core["fpdf2"]["required"])

        letters = {item["name"]: item for item in dependency_report(("matter", "tracker", "letters"))}
        self.assertTrue(letters["python-docx"]["required"])
        self.assertFalse(letters["lxml"]["required"])
        self.assertFalse(letters["fpdf2"]["required"])

        redline = {item["name"]: item for item in dependency_report(("matter", "tracker", "redline"))}
        self.assertTrue(redline["python-docx"]["required"])
        self.assertTrue(redline["lxml"]["required"])
        self.assertTrue(redline["fpdf2"]["required"])

    def test_launcher_stops_if_retained_runtime_is_missing(self):
        plan = build_plan(self.answers())
        missing = self.root / "removed-runtime" / "bin" / "python"
        plan["runtime_python"] = str(missing)
        launcher = self.root / "launch-lawyeredos.sh"
        launcher.write_text(render_launcher(plan), encoding="utf-8")
        launcher.chmod(0o700)
        result = subprocess.run(
            [str(launcher)], capture_output=True, text=True, check=False,
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("runtime is unavailable", result.stderr)

    def test_apply_repeat_preserves_existing_config(self):
        first = apply_plan(build_plan(self.answers()))
        self.assertTrue(first["ok"])
        config_path = Path(first["config"])
        original = config_path.read_bytes()
        loaded = load_config(config_path)
        self.assertEqual(loaded.branding_label, "Northstar Legal Lab")
        self.assertFalse(loaded.modules["calendar"])
        plugin = Path(first["plugin"])
        self.assertFalse((plugin / "skills" / "practice-calendar-sync").exists())
        self.assertTrue((plugin / "skills" / "practice-contract-redline").is_dir())
        project_skill = self.workspace / ".claude" / "skills" / "lawyeredos-contract-redline"
        self.assertTrue(project_skill.is_symlink())
        skill_text = (project_skill / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("name: lawyeredos-contract-redline", skill_text)
        self.assertIn("${LAWYEREDOS_ROOT}", skill_text)
        matter_text = (
            self.workspace / ".claude" / "skills" / "lawyeredos-work-on-matter" / "SKILL.md"
        ).read_text(encoding="utf-8")
        self.assertIn("A closed matter remains read-only", matter_text)
        self.assertIn("without a preliminary full orientation", matter_text)
        self.assertIn("brief.truncated: true", matter_text)
        self.assertIn("From address alone does not prove", matter_text)
        settings = json.loads((self.workspace / ".claude" / "settings.local.json").read_text(encoding="utf-8"))
        self.assertEqual(settings["env"]["LAWYEREDOS_ROOT"], str(plugin))
        agent = self.workspace / ".claude" / "agents" / "lawyeredos-legal-review-lens.md"
        self.assertIn("name: lawyeredos-legal-review-lens", agent.read_text(encoding="utf-8"))
        second = apply_plan(build_plan(self.answers(branding_label="Ignored on reuse")))
        self.assertTrue(second["idempotent"])
        self.assertEqual(config_path.read_bytes(), original)

    def test_failed_apply_removes_partial_install_and_preserves_unrelated_file(self):
        self.workspace.mkdir()
        private = self.workspace / "private-user-file.txt"
        private.write_text("preserve", encoding="utf-8")

        def fail_after_partial_tracker(path):
            path.write_bytes(b"partial tracker")
            raise OSError("simulated tracker interruption")

        with patch("lawyeredos.setup_wizard.initialize", side_effect=fail_after_partial_tracker):
            with self.assertRaisesRegex(OSError, "simulated tracker interruption"):
                apply_plan(build_plan(self.answers(existing_config="error")))
        self.assertEqual(private.read_text(encoding="utf-8"), "preserve")
        self.assertFalse((self.workspace / ".lawyeredos").exists())
        self.assertFalse((self.workspace / ".claude").exists())

    def test_cancelled_apply_removes_partial_install(self):
        def interrupt_after_partial_tracker(path):
            path.write_bytes(b"partial tracker")
            raise KeyboardInterrupt

        with patch("lawyeredos.setup_wizard.initialize", side_effect=interrupt_after_partial_tracker):
            with self.assertRaises(KeyboardInterrupt):
                apply_plan(build_plan(self.answers(existing_config="error")))
        self.assertFalse(self.workspace.exists())

    def test_failed_first_apply_after_state_write_removes_all_created_paths(self):
        plan = build_plan(self.answers(existing_config="error"))
        with patch(
            "lawyeredos.setup_wizard.load_config",
            side_effect=OSError("simulated late verification failure"),
        ):
            with self.assertRaisesRegex(OSError, "simulated late verification failure"):
                apply_plan(plan)
        self.assertFalse(self.workspace.exists())

    def test_failed_restore_preserves_recovery_backup(self):
        first = apply_plan(build_plan(self.answers()))
        launcher = Path(first["launcher"])
        launcher.write_text("private launcher modification\n", encoding="utf-8")
        loaded = load_config(Path(first["config"]))
        plan = build_plan(self.answers())
        real_copy2 = shutil.copy2

        def fail_only_during_restore(source, destination, *args, **kwargs):
            if "backups" in Path(source).parts:
                raise OSError("simulated restore copy failure")
            return real_copy2(source, destination, *args, **kwargs)

        with patch(
            "lawyeredos.setup_wizard.load_config",
            side_effect=[loaded, OSError("simulated final verification interruption")],
        ), patch("lawyeredos.setup_wizard.shutil.copy2", side_effect=fail_only_during_restore):
            with self.assertRaisesRegex(RuntimeError, "recovery backups preserved at"):
                apply_plan(plan)
        backups = list((self.workspace / ".lawyeredos" / "backups").glob("*/launch-lawyeredos.sh"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_text(encoding="utf-8"), "private launcher modification\n")

    def test_failed_reapply_restores_replaced_file_and_previous_state(self):
        first = apply_plan(build_plan(self.answers()))
        launcher = Path(first["launcher"])
        state = Path(first["rollback_state"])
        launcher.write_text("private launcher modification\n", encoding="utf-8")
        state_before = state.read_bytes()
        loaded = load_config(Path(first["config"]))
        plan = build_plan(self.answers())
        with patch(
            "lawyeredos.setup_wizard.load_config",
            side_effect=[loaded, OSError("simulated final verification interruption")],
        ):
            with self.assertRaisesRegex(OSError, "simulated final verification interruption"):
                apply_plan(plan)
        self.assertEqual(launcher.read_text(encoding="utf-8"), "private launcher modification\n")
        self.assertEqual(state.read_bytes(), state_before)

    def test_projectized_skills_use_only_project_names(self):
        apply_plan(build_plan(self.answers()))
        skills_root = self.workspace / ".claude" / "skills"
        texts = {
            path.parent.name: path.read_text(encoding="utf-8")
            for path in skills_root.glob("*/SKILL.md")
        }
        self.assertEqual(set(texts), {
            "lawyeredos-work-on-matter",
            "lawyeredos-matter-tracker",
            "lawyeredos-letterhead",
            "lawyeredos-contract-redline",
            "lawyeredos-adversarial-panel",
        })
        combined = "\n".join(texts.values())
        self.assertNotIn("lawyeredos:practice-", combined)
        self.assertNotIn("lawyeredos:legal-review-lens", combined)
        self.assertNotIn("panel-lens", combined)
        self.assertIn("lawyeredos-matter-tracker", texts["lawyeredos-work-on-matter"])
        self.assertIn("lawyeredos-adversarial-panel", texts["lawyeredos-letterhead"])
        self.assertIn("lawyeredos-legal-review-lens", texts["lawyeredos-adversarial-panel"])

    def test_apply_merges_unrelated_project_local_settings(self):
        settings_path = self.workspace / ".claude" / "settings.local.json"
        settings_path.parent.mkdir(parents=True)
        settings_path.write_text(json.dumps({"theme": "dark", "env": {"EXAMPLE": "kept"}}), encoding="utf-8")
        apply_plan(build_plan(self.answers()))
        settings = json.loads(settings_path.read_text(encoding="utf-8"))
        self.assertEqual(settings["theme"], "dark")
        self.assertEqual(settings["env"]["EXAMPLE"], "kept")
        self.assertIn("LAWYEREDOS_CONFIG", settings["env"])

    def test_rollback_restores_preexisting_settings_bytes_and_mode(self):
        settings_path = self.workspace / ".claude" / "settings.local.json"
        settings_path.parent.mkdir(parents=True)
        original = json.dumps({"theme": "dark", "env": {"EXAMPLE": "kept"}}).encode()
        settings_path.write_bytes(original)
        settings_path.chmod(0o644)
        apply_plan(build_plan(self.answers()))
        rollback(self.workspace)
        self.assertEqual(settings_path.read_bytes(), original)
        self.assertEqual(settings_path.stat().st_mode & 0o777, 0o644)

    def test_rollback_rejects_insecure_state_before_any_mutation(self):
        result = apply_plan(build_plan(self.answers()))
        state = Path(result["rollback_state"])
        config = Path(result["config"])
        config_before = config.read_bytes()
        state.chmod(0o644)
        with self.assertRaisesRegex(ValueError, "migrate this existing path explicitly"):
            rollback(self.workspace)
        self.assertEqual(config.read_bytes(), config_before)
        self.assertTrue(Path(result["plugin"]).exists())
        self.assertEqual(state.stat().st_mode & 0o777, 0o644)

    def test_rollback_rejects_special_backup_before_any_mutation(self):
        first = apply_plan(build_plan(self.answers()))
        launcher = Path(first["launcher"])
        launcher.write_text("private launcher content\n", encoding="utf-8")
        result = apply_plan(build_plan(self.answers()))
        state_path = Path(result["rollback_state"])
        state = json.loads(state_path.read_text(encoding="utf-8"))
        record = next(item for item in state["backups"] if item["original"] == str(launcher))
        backup = Path(record["backup"])
        backup.unlink()
        os.mkfifo(backup, 0o600)
        launcher_before = launcher.read_bytes()
        with self.assertRaisesRegex(ValueError, "not a regular file"):
            rollback(self.workspace)
        self.assertEqual(launcher.read_bytes(), launcher_before)
        self.assertTrue(Path(result["plugin"]).exists())

    def test_rollback_rejects_corrupt_mode_metadata_before_any_mutation(self):
        first = apply_plan(build_plan(self.answers()))
        launcher = Path(first["launcher"])
        launcher.write_text("private launcher content\n", encoding="utf-8")
        result = apply_plan(build_plan(self.answers()))
        state_path = Path(result["rollback_state"])
        state = json.loads(state_path.read_text(encoding="utf-8"))
        record = next(item for item in state["backups"] if item["original"] == str(launcher))
        record["original_modes"]["."]["mode"] = 0o7777
        state_path.write_text(json.dumps(state), encoding="utf-8")
        launcher_before = launcher.read_bytes()
        with self.assertRaisesRegex(ValueError, "mode metadata is invalid"):
            rollback(self.workspace)
        self.assertEqual(launcher.read_bytes(), launcher_before)
        self.assertTrue(Path(result["plugin"]).exists())

    def test_failed_apply_recovery_restores_file_and_skill_tree_modes(self):
        setup_root = self.workspace / ".lawyeredos"
        setup_root.mkdir(parents=True)
        setup_root.chmod(0o700)
        backup_root = setup_root / "backups" / "fictional-transaction"
        backup_root.parent.mkdir(mode=0o700)
        settings = self.workspace / ".claude" / "settings.local.json"
        settings.parent.mkdir(parents=True)
        settings.write_bytes(b'{"theme":"dark"}\n')
        settings.chmod(0o644)
        skill = self.workspace / ".claude" / "skills" / "managed-fictional"
        skill.mkdir(parents=True)
        skill.chmod(0o750)
        skill_file = skill / "SKILL.md"
        skill_file.write_text("fictional managed skill\n", encoding="utf-8")
        skill_file.chmod(0o640)
        backups = []
        _backup(settings, backup_root, backups)
        _backup(skill, backup_root, backups)
        settings.write_text("changed\n", encoding="utf-8")
        settings.chmod(0o600)
        skill_file.write_text("changed\n", encoding="utf-8")
        skill.chmod(0o700)
        skill_file.chmod(0o600)
        plan = {
            "setup_root": str(setup_root),
            "plugin": str(setup_root / "plugins" / "unused"),
            "_active_transaction": {
                "created": [], "backups": backups, "backup_root": str(backup_root),
                "previous_state": None,
            },
        }
        self.assertEqual(_undo_failed_apply(plan), [])
        self.assertEqual(settings.read_bytes(), b'{"theme":"dark"}\n')
        self.assertEqual(settings.stat().st_mode & 0o777, 0o644)
        self.assertEqual(skill.stat().st_mode & 0o777, 0o750)
        self.assertEqual(skill_file.read_text(encoding="utf-8"), "fictional managed skill\n")
        self.assertEqual(skill_file.stat().st_mode & 0o777, 0o640)

    def test_apply_preserves_unrelated_private_skill_and_settings(self):
        private_skill = self.workspace / ".claude" / "skills" / "private-existing-skill"
        private_skill.mkdir(parents=True)
        skill_file = private_skill / "SKILL.md"
        skill_file.write_text("private user skill", encoding="utf-8")
        settings_path = self.workspace / ".claude" / "settings.local.json"
        settings_path.write_text(
            json.dumps({"permissions": {"allow": ["Read"]}, "env": {"PRIVATE_SETTING": "kept"}}),
            encoding="utf-8",
        )
        apply_plan(build_plan(self.answers(mail_adapter="claude-gmail-connector")))
        self.assertEqual(skill_file.read_text(encoding="utf-8"), "private user skill")
        settings = json.loads(settings_path.read_text(encoding="utf-8"))
        self.assertEqual(settings["permissions"], {"allow": ["Read"]})
        self.assertEqual(settings["env"]["PRIVATE_SETTING"], "kept")

    def test_preflight_refuses_symlinked_managed_directory(self):
        outside = self.root / "outside"
        outside.mkdir()
        self.workspace.mkdir()
        (self.workspace / ".claude").symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "must not be a symlink"):
            build_plan(self.answers())

    def test_apply_rechecks_managed_directories_after_preview_symlink_swap(self):
        plan = build_plan(self.answers(existing_config="error"))
        outside = self.root / "outside"
        outside.mkdir()
        marker = outside / "keep.txt"
        marker.write_text("preserve", encoding="utf-8")
        self.workspace.mkdir()
        (self.workspace / ".claude").symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "must not be a symlink"):
            apply_plan(plan)
        self.assertEqual(marker.read_text(encoding="utf-8"), "preserve")
        self.assertEqual(list(outside.iterdir()), [marker])

    def test_apply_rejects_setup_root_swap_before_transaction_state_read(self):
        plan = build_plan(self.answers(existing_config="error"))
        outside = self.root / "outside-state"
        outside.mkdir()
        marker = outside / "setup-state.json"
        marker.write_text("private", encoding="utf-8")
        self.workspace.mkdir()
        (self.workspace / ".lawyeredos").symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "must not be a symlink"):
            apply_plan(plan)
        self.assertEqual(marker.read_text(encoding="utf-8"), "private")
        self.assertEqual(list(outside.iterdir()), [marker])

    def test_apply_refuses_discovery_skill_symlink_created_after_preview(self):
        plan = build_plan(self.answers(existing_config="error"))
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

    def test_apply_refuses_private_files_that_appear_after_preview(self):
        plan = build_plan(self.answers(existing_config="error"))
        config = Path(plan["config"])
        launcher = Path(plan["launcher"])
        config.parent.mkdir(parents=True)
        config.write_text("private config", encoding="utf-8")
        launcher.write_text("private launcher", encoding="utf-8")
        launcher.chmod(0o640)
        with self.assertRaisesRegex(ValueError, "changed after preview"):
            apply_plan(plan)
        self.assertEqual(config.read_text(encoding="utf-8"), "private config")
        self.assertEqual(launcher.read_text(encoding="utf-8"), "private launcher")
        self.assertEqual(launcher.stat().st_mode & 0o777, 0o640)

    def test_apply_refuses_valid_discovery_file_that_appears_after_preview(self):
        plan = build_plan(self.answers(existing_config="error"))
        discovery = Path(plan["discovery_state"])
        discovery.parent.mkdir(parents=True)
        content = json.dumps({
            "schema_version": 2,
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

    def test_apply_refuses_setup_state_that_appears_before_transaction_read(self):
        plan = build_plan(self.answers(existing_config="error"))
        state = self.workspace / ".lawyeredos" / "setup-state.json"
        state.parent.mkdir(parents=True)
        content = json.dumps({"schema_version": 1, "private": True})
        state.write_text(content, encoding="utf-8")
        state.chmod(0o640)
        with self.assertRaisesRegex(ValueError, "changed after preview"):
            apply_plan(plan)
        self.assertEqual(state.read_text(encoding="utf-8"), content)
        self.assertEqual(state.stat().st_mode & 0o777, 0o640)

    def test_malicious_discovery_cannot_claim_or_delete_external_path(self):
        external = self.root / "external-private.txt"
        external.write_text("preserve", encoding="utf-8")
        external.chmod(0o640)
        discovery = self.workspace / ".lawyeredos" / "project-discovery.json"
        discovery.parent.mkdir(parents=True)
        discovery.write_text(json.dumps({
            "schema_version": 2,
            "package_digest": "0" * 64,
            "managed_paths": [str(external)],
            "managed_fingerprints": {},
        }), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "outside the LawyeredOS Claude namespace"):
            build_plan(self.answers(existing_config="error"))
        self.assertEqual(external.read_text(encoding="utf-8"), "preserve")
        self.assertEqual(external.stat().st_mode & 0o777, 0o640)

    def test_discovery_fingerprint_change_fails_closed(self):
        first = apply_plan(build_plan(self.answers()))
        agent = self.workspace / ".claude" / "agents" / "lawyeredos-legal-review-lens.md"
        agent.write_text("private replacement", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "fingerprint changed"):
            build_plan(self.answers())
        self.assertEqual(agent.read_text(encoding="utf-8"), "private replacement")
        self.assertTrue(Path(first["plugin"]).is_dir())

    def test_schema_one_discovery_uses_setup_state_fingerprints_and_migrates(self):
        first = apply_plan(build_plan(self.answers()))
        discovery_path = self.workspace / ".lawyeredos" / "project-discovery.json"
        discovery = json.loads(discovery_path.read_text(encoding="utf-8"))
        discovery["schema_version"] = 1
        discovery.pop("managed_fingerprints")
        discovery_path.write_text(json.dumps(discovery), encoding="utf-8")
        # Faithful released sequence: a later config-only replacement rewrote
        # setup-state.json without retaining unchanged project-artifact hashes.
        state_path = Path(first["rollback_state"])
        state = json.loads(state_path.read_text(encoding="utf-8"))
        project_prefixes = (
            str(self.workspace / ".claude" / "skills"),
            str(self.workspace / ".claude" / "agents"),
        )
        state["managed_fingerprints"] = {
            path: value for path, value in state["managed_fingerprints"].items()
            if not path.startswith(project_prefixes)
        }
        state_path.write_text(json.dumps(state), encoding="utf-8")
        repeated = apply_plan(build_plan(self.answers()))
        self.assertTrue(repeated["ok"])
        migrated = json.loads(discovery_path.read_text(encoding="utf-8"))
        self.assertEqual(migrated["schema_version"], 2)
        self.assertEqual(set(migrated["managed_paths"]), set(migrated["managed_fingerprints"]))
        self.assertTrue(Path(first["plugin"]).is_dir())

    def test_rollback_refuses_setup_root_symlink_swap(self):
        result = apply_plan(build_plan(self.answers()))
        setup_root = self.workspace / ".lawyeredos"
        state_text = Path(result["rollback_state"]).read_text(encoding="utf-8")
        retained = self.root / "retained-setup"
        setup_root.rename(retained)
        outside = self.root / "outside-rollback"
        outside.mkdir()
        marker = outside / "private.txt"
        marker.write_text("preserve", encoding="utf-8")
        (outside / "setup-state.json").write_text(
            state_text, encoding="utf-8"
        )
        setup_root.symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "must not be a symlink"):
            rollback(self.workspace)
        self.assertEqual(marker.read_text(encoding="utf-8"), "preserve")

    def test_rollback_rejects_external_state_paths_before_deletion(self):
        result = apply_plan(build_plan(self.answers()))
        external = self.root / "external-rollback.txt"
        external.write_text("preserve", encoding="utf-8")
        state_path = Path(result["rollback_state"])
        state = json.loads(state_path.read_text(encoding="utf-8"))
        state["created"].append(str(external))
        state["managed_fingerprints"][str(external)] = "0" * 64
        state_path.write_text(json.dumps(state), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "outside the managed namespace"):
            rollback(self.workspace)
        self.assertEqual(external.read_text(encoding="utf-8"), "preserve")

    def test_trial_requires_new_or_empty_workspace(self):
        self.workspace.mkdir()
        (self.workspace / "existing-skill.txt").write_text("keep", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "must be new or empty"):
            build_plan(self.answers(existing_config="error"), require_new_workspace=True)

    def test_trial_rechecks_empty_workspace_before_apply(self):
        plan = build_plan(self.answers(existing_config="error"), require_new_workspace=True)
        self.workspace.mkdir()
        keep = self.workspace / "existing-skill.txt"
        keep.write_text("keep", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "no longer empty"):
            apply_plan(plan)
        self.assertEqual(keep.read_text(encoding="utf-8"), "keep")
        self.assertEqual(list(self.workspace.iterdir()), [keep])

    def test_workspace_refuses_global_claude_and_package_descendants(self):
        with self.assertRaisesRegex(ValueError, "user-global"):
            build_plan(self.answers(workspace=Path.home() / ".claude" / "skills"))
        package_child = Path(__file__).resolve().parents[1] / "unsafe-workspace"
        with self.assertRaisesRegex(ValueError, "inside the source package|outside the extracted"):
            build_plan(self.answers(workspace=package_child))

    def test_preflight_refuses_unowned_project_skill_collision(self):
        skill = self.workspace / ".claude" / "skills" / "lawyeredos-work-on-matter"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text("user-owned", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "not managed by LawyeredOS"):
            build_plan(self.answers())
        self.assertEqual((skill / "SKILL.md").read_text(encoding="utf-8"), "user-owned")

    def test_preflight_refuses_non_object_settings_env(self):
        settings_path = self.workspace / ".claude" / "settings.local.json"
        settings_path.parent.mkdir(parents=True)
        settings_path.write_text(json.dumps({"env": []}), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "env must contain a JSON object"):
            build_plan(self.answers())

    def test_existing_config_replace_is_backed_up_and_rollback_restores(self):
        first = apply_plan(build_plan(self.answers()))
        config_path = Path(first["config"])
        original = config_path.read_bytes()
        replacement = self.answers(
            branding_mode="individual", branding_label="Example Independent Practice",
            jurisdiction="ontario", existing_config="replace",
        )
        changed = apply_plan(build_plan(replacement))
        self.assertIn(str(config_path), changed["changed"])
        self.assertIn("Example Independent Practice", config_path.read_text(encoding="utf-8"))
        result = rollback(self.workspace)
        self.assertIn(str(config_path), result["restored"])
        self.assertEqual(config_path.read_bytes(), original)

    def test_upgrade_keeps_old_plugin_and_updates_launcher(self):
        first = apply_plan(build_plan(self.answers()))
        old_plugin = Path(first["plugin"])
        with patch("lawyeredos.setup_wizard.package_digest", return_value="f" * 64):
            plan = build_plan(self.answers())
        new_plugin = Path(plan["plugin"])
        upgraded = apply_plan(plan)
        self.assertTrue(old_plugin.is_dir())
        self.assertTrue(new_plugin.is_dir())
        settings = json.loads((self.workspace / ".claude" / "settings.local.json").read_text(encoding="utf-8"))
        self.assertEqual(settings["env"]["LAWYEREDOS_ROOT"], str(new_plugin))
        project_skill = self.workspace / ".claude" / "skills" / "lawyeredos-work-on-matter"
        self.assertTrue(project_skill.is_symlink())
        self.assertTrue(str(project_skill.resolve()).startswith(str(new_plugin)))

    def test_installed_claude_core_has_bound_template_manifest(self):
        result = apply_plan(build_plan(self.answers()))
        config = load_config(result["config"])
        self.assertIsNotNone(config.document_template_manifest)
        manifest = json.loads(config.document_template_manifest.read_text(encoding="utf-8"))
        self.assertEqual(manifest["template"], "assets/neutral-letterhead.docx")
        self.assertEqual(
            manifest["sha256"],
            hashlib.sha256(config.document_template.read_bytes()).hexdigest(),
        )

    def test_validation_fails_when_template_manifest_binding_is_removed(self):
        result = apply_plan(build_plan(self.answers()))
        config_path = Path(result["config"])
        config_path.write_text(
            "\n".join(
                line for line in config_path.read_text(encoding="utf-8").splitlines()
                if not line.startswith("template_manifest =")
            ) + "\n",
            encoding="utf-8",
        )
        validation = subprocess.run(
            [
                sys.executable,
                str(Path(__file__).resolve().parents[1] / "scripts" / "validate_setup.py"),
                "--config", str(config_path),
            ],
            capture_output=True, text=True, check=False,
        )
        self.assertEqual(validation.returncode, 2)
        self.assertIn("document template manifest is not configured", validation.stdout)

    def test_repeat_install_rejects_tampered_versioned_plugin(self):
        first = apply_plan(build_plan(self.answers()))
        skill = Path(first["plugin"]) / "skills" / "practice-work-on-matter" / "SKILL.md"
        skill.write_text(skill.read_text(encoding="utf-8") + "\nprivate tamper\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "versioned plugin content changed"):
            build_plan(self.answers())
        self.assertIn("private tamper", skill.read_text(encoding="utf-8"))

    def test_apply_rechecks_versioned_plugin_after_preview(self):
        first = apply_plan(build_plan(self.answers()))
        plan = build_plan(self.answers())
        skill = Path(first["plugin"]) / "skills" / "practice-work-on-matter" / "SKILL.md"
        skill.write_text(skill.read_text(encoding="utf-8") + "\npost-preview tamper\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "changed after preview"):
            apply_plan(plan)
        self.assertIn("post-preview tamper", skill.read_text(encoding="utf-8"))

    def test_repeat_preview_rejects_empty_directory_and_special_entry_in_plugin(self):
        first = apply_plan(build_plan(self.answers()))
        plugin = Path(first["plugin"])
        empty = plugin / "PRIVATE-EMPTY"
        empty.mkdir()
        with self.assertRaisesRegex(ValueError, "versioned plugin content changed"):
            build_plan(self.answers())
        empty.rmdir()
        fifo = plugin / "PRIVATE-FIFO"
        os.mkfifo(fifo)
        with self.assertRaisesRegex(ValueError, "unsupported filesystem entry"):
            build_plan(self.answers())
        fifo.unlink()

    def test_apply_rejects_post_preview_empty_directory_and_special_entry_in_plugin(self):
        first = apply_plan(build_plan(self.answers()))
        plugin = Path(first["plugin"])
        plan = build_plan(self.answers())
        empty = plugin / "PRIVATE-EMPTY"
        empty.mkdir()
        with self.assertRaisesRegex(ValueError, "changed after preview"):
            apply_plan(plan)
        empty.rmdir()
        plan = build_plan(self.answers())
        fifo = plugin / "PRIVATE-FIFO"
        os.mkfifo(fifo)
        with self.assertRaisesRegex(ValueError, "unsupported filesystem entry"):
            apply_plan(plan)
        fifo.unlink()

    def test_cancelled_apply_has_no_side_effects(self):
        argv = [
            "--workspace", str(self.workspace), "--branding-mode", "neutral",
            "--branding-label", "Organization", "--jurisdiction", "none",
            "--modules", "matter,tracker", "--mail", "skip", "--calendar", "off",
            "--existing-config", "reuse", "--apply",
        ]
        with patch("builtins.input", return_value=""):
            self.assertEqual(main(argv), 1)
        self.assertFalse(self.workspace.exists())

    def test_invalid_paths_existing_policy_and_calendar_are_rejected(self):
        self.workspace.write_text("not a directory", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "not a directory"):
            build_plan(self.answers())
        self.workspace.unlink()
        apply_plan(build_plan(self.answers()))
        with self.assertRaisesRegex(ValueError, "already exists"):
            build_plan(self.answers(existing_config="error"))
        with self.assertRaisesRegex(ValueError, "dedicated calendar ID"):
            build_plan(self.answers(
                modules=("matter", "tracker", "calendar"),
                calendar_adapter="google-calendar-api", calendar_id="primary",
            ))

    def test_first_install_rollback_removes_managed_files_only(self):
        self.workspace.mkdir()
        keep = self.workspace / "keep.txt"
        keep.write_text("user file", encoding="utf-8")
        result = apply_plan(build_plan(self.answers()))
        self.assertTrue(Path(result["plugin"]).exists())
        rollback(self.workspace)
        self.assertTrue(keep.is_file())
        self.assertFalse(Path(result["plugin"]).exists())
        self.assertFalse(Path(result["config"]).exists())
        self.assertEqual(keep.read_text(encoding="utf-8"), "user file")

    def test_rollback_ignores_python_runtime_cache_in_plugin(self):
        result = apply_plan(build_plan(self.answers()))
        cache = Path(result["plugin"]) / "src" / "lawyeredos" / "__pycache__"
        cache.mkdir(parents=True, exist_ok=True)
        (cache / "runtime.cpython-312.pyc").write_bytes(b"runtime cache")
        rolled_back = rollback(self.workspace)
        self.assertTrue(rolled_back["ok"])
        self.assertFalse(Path(result["plugin"]).exists())

    def test_rollback_still_detects_plugin_source_changes(self):
        result = apply_plan(build_plan(self.answers()))
        source = Path(result["plugin"]) / "src" / "lawyeredos" / "config.py"
        source.write_text(source.read_text(encoding="utf-8") + "\n# changed\n", encoding="utf-8")
        rolled_back = rollback(self.workspace)
        self.assertFalse(rolled_back["ok"])
        self.assertIn(str(Path(result["plugin"])), rolled_back["preserved_modified"])

    def test_rollback_preserves_tracker_after_matter_activity(self):
        result = apply_plan(build_plan(self.answers()))
        tracker = self.workspace / ".lawyeredos" / "data" / "matters.sqlite3"
        with sqlite3.connect(tracker) as connection:
            connection.execute("UPDATE meta SET value='1' WHERE key='revision'")
        rolled_back = rollback(self.workspace)
        self.assertFalse(rolled_back["ok"])
        self.assertEqual(rolled_back["status"], "modified_managed_state")
        self.assertTrue(tracker.is_file())
        self.assertIn(str(tracker.resolve()), rolled_back["preserved_modified"])
        self.assertTrue(Path(result["plugin"]).exists())
        self.assertTrue(Path(result["config"]).exists())

    def test_rollback_without_fingerprints_fails_safe(self):
        result = apply_plan(build_plan(self.answers()))
        state_path = Path(result["rollback_state"])
        state = json.loads(state_path.read_text(encoding="utf-8"))
        state.pop("managed_fingerprints")
        state_path.write_text(json.dumps(state), encoding="utf-8")
        rolled_back = rollback(self.workspace)
        self.assertFalse(rolled_back["ok"])
        self.assertTrue(Path(result["plugin"]).is_dir())
        self.assertTrue(Path(result["config"]).is_file())
        self.assertIn(str(Path(result["plugin"])), rolled_back["preserved_modified"])

    def test_rollback_preserves_modified_replacement(self):
        first = apply_plan(build_plan(self.answers()))
        config = Path(first["config"])
        replacement = self.answers(
            branding_mode="individual",
            branding_label="Example Independent Practice",
            existing_config="replace",
        )
        apply_plan(build_plan(replacement))
        config.write_text(config.read_text(encoding="utf-8") + "\n# user edit\n", encoding="utf-8")
        rolled_back = rollback(self.workspace)
        self.assertFalse(rolled_back["ok"])
        self.assertIn(str(config), rolled_back["preserved_modified"])
        self.assertIn("# user edit", config.read_text(encoding="utf-8"))

    def test_state_contains_no_credentials(self):
        result = apply_plan(build_plan(self.answers()))
        state = json.loads(Path(result["rollback_state"]).read_text(encoding="utf-8"))
        serialized = json.dumps(state).lower()
        self.assertNotIn("token", serialized)
        self.assertNotIn("password", serialized)


if __name__ == "__main__":
    unittest.main()
