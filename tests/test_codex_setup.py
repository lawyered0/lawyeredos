from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from lawyeredos.codex_setup import apply_plan, build_plan, normalize_answers
from lawyeredos.config import load_config
from lawyeredos.review_orchestrator import prepare
from lawyeredos.review_bundle import create_manifest


class CodexSetupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.workspace = self.root / "fictional-workspace"

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

    def test_installed_skills_use_codex_runtime_and_session_mail_boundary(self):
        result = apply_plan(build_plan(self.answers(mail="session-tools")))
        work_skill = Path(result["skills"]["matter"]) / "SKILL.md"
        text = work_skill.read_text(encoding="utf-8")
        self.assertIn("codex-session-tools", text)
        self.assertIn(".lawyeredos/lawyeredos-run", text)
        self.assertIn(".lawyeredos/config.toml", text)
        self.assertNotIn("Require the `LAWYEREDOS_CONFIG` environment variable", text)
        self.assertNotIn("${LAWYEREDOS_ROOT}", text)
        self.assertEqual(load_config(result["config"]).mail_adapter, "codex-session-tools")

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


if __name__ == "__main__":
    unittest.main()
