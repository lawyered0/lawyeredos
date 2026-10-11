from __future__ import annotations

import os
import stat
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from lawyeredos import codex_setup, setup_wizard
from lawyeredos.common import sha256_file
from lawyeredos.content_review import _pdf_units
from lawyeredos.private_fs import (
    assert_private_file,
    create_private_file,
    ensure_private_directory,
    replace_private_file,
)
from lawyeredos.tracker_cli import initialize


def mode(path: Path) -> int:
    return stat.S_IMODE(path.lstat().st_mode)


class PrivateFilesystemPrimitiveTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)

    def tearDown(self):
        self.temporary.cleanup()

    @contextmanager
    def umask(self, value: int):
        previous = os.umask(value)
        try:
            yield
        finally:
            os.umask(previous)

    def test_new_confidential_tree_and_tracker_are_private_at_creation(self):
        managed = self.root / ".lawyeredos"
        ensure_private_directory(managed)
        data = managed / "data"
        ensure_private_directory(data)
        config = managed / "config.toml"
        create_private_file(config, b"fictional=true\n")
        tracker = data / "matters.sqlite3"
        initialize(tracker)
        self.assertEqual(mode(managed), 0o700)
        self.assertEqual(mode(data), 0o700)
        self.assertEqual(mode(config), 0o600)
        self.assertEqual(mode(tracker), 0o600)

    def test_restrictive_umask_still_creates_exact_private_modes(self):
        directory = self.root / "private"
        file = directory / "state.json"
        with self.umask(0o777):
            ensure_private_directory(directory)
            create_private_file(file, b"fictional")
        self.assertEqual(mode(directory), 0o700)
        self.assertEqual(mode(file), 0o600)

    def test_failed_directory_mode_binding_removes_only_created_directory(self):
        directory = self.root / "private"
        with patch("lawyeredos.private_fs.os.chmod", side_effect=OSError("fictional failure")):
            with self.assertRaisesRegex(OSError, "fictional failure"):
                ensure_private_directory(directory)
        self.assertFalse(directory.exists())

    def test_existing_insecure_file_requires_migration_and_is_not_changed(self):
        path = self.root / "legacy-state.json"
        path.write_text("private fictional state", encoding="utf-8")
        path.chmod(0o640)
        with self.assertRaisesRegex(ValueError, "migrate this existing path explicitly"):
            replace_private_file(path, b"replacement")
        self.assertEqual(path.read_text(encoding="utf-8"), "private fictional state")
        self.assertEqual(mode(path), 0o640)

    def test_links_and_special_files_fail_closed(self):
        private = self.root / "private"
        create_private_file(private, b"fixture")
        hardlink = self.root / "hardlink"
        os.link(private, hardlink)
        with self.assertRaisesRegex(ValueError, "multiple hard links"):
            assert_private_file(private)
        symlink = self.root / "symlink"
        symlink.symlink_to(private)
        with self.assertRaisesRegex(ValueError, "symlink"):
            assert_private_file(symlink)
        fifo = self.root / "fifo"
        os.mkfifo(fifo, 0o600)
        with self.assertRaisesRegex(ValueError, "not a regular file"):
            assert_private_file(fifo)

    def test_cached_pdf_scratch_rejects_unsafe_modes_and_aliases(self):
        source = self.root / "fictional.pdf"
        source.write_bytes(b"not a real PDF; cached path test only")
        scratch = self.root / "scratch"
        scratch.mkdir(mode=0o700)
        output = scratch / f"{sha256_file(source)}.txt"
        output.write_text("fictional extracted text " * 4, encoding="utf-8")
        output.chmod(0o644)
        with self.assertRaisesRegex(ValueError, "migrate this existing path explicitly"):
            _pdf_units(source, scratch)
        output.chmod(0o600)
        alias = self.root / "scratch-alias.txt"
        os.link(output, alias)
        with self.assertRaisesRegex(ValueError, "multiple hard links"):
            _pdf_units(source, scratch)


class SetupPrivateModeTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)

    def tearDown(self):
        self.temporary.cleanup()

    @staticmethod
    def _available(report):
        for item in report:
            if item["required"]:
                item["available"] = True
                item["detail"] = "fictional test fixture"
        return report

    def test_fresh_claude_and_codex_confidential_artifacts_are_private(self):
        claude_workspace = self.root / "claude-workspace"
        claude_answers = setup_wizard.Answers(
            workspace=claude_workspace, branding_mode="neutral", branding_label="Organization",
            jurisdiction="none", modules=("matter", "tracker"), mail_adapter="unavailable",
            calendar_adapter="unavailable", calendar_id="", existing_config="reuse",
        )
        original_claude_report = setup_wizard.dependency_report
        with patch(
            "lawyeredos.setup_wizard.dependency_report",
            side_effect=lambda modules=(): self._available(original_claude_report(modules)),
        ):
            claude_result = setup_wizard.apply_plan(setup_wizard.build_plan(claude_answers))
        codex_workspace = self.root / "codex-workspace"
        codex_answers = codex_setup.normalize_answers(
            codex_workspace, "neutral", "Organization", "none", "matter,tracker",
            "skip", "off", "", "error",
        )
        original_report = codex_setup.dependency_report
        with patch(
            "lawyeredos.codex_setup.dependency_report",
            side_effect=lambda modules: self._available(original_report(modules)),
        ):
            codex_result = codex_setup.apply_plan(codex_setup.build_plan(codex_answers))
        for workspace, result, discovery_name in (
            (claude_workspace, claude_result, "project-discovery.json"),
            (codex_workspace, codex_result, codex_setup.DISCOVERY_FILE),
        ):
            setup = workspace / ".lawyeredos"
            self.assertEqual(mode(setup), 0o700)
            self.assertEqual(mode(setup / "data"), 0o700)
            self.assertEqual(mode(Path(result["config"])), 0o600)
            self.assertEqual(mode(setup / "data" / "matters.sqlite3"), 0o600)
            discovery = setup / discovery_name
            self.assertEqual(mode(discovery), 0o600)
        self.assertEqual(mode(claude_workspace / ".lawyeredos" / "setup-state.json"), 0o600)

    def test_upgrade_from_legacy_insecure_config_reports_migration_without_chmod(self):
        workspace = self.root / "codex-upgrade"
        answers = codex_setup.normalize_answers(
            workspace, "neutral", "Organization", "none", "matter,tracker",
            "skip", "off", "", "error",
        )
        original_report = codex_setup.dependency_report
        with patch(
            "lawyeredos.codex_setup.dependency_report",
            side_effect=lambda modules: self._available(original_report(modules)),
        ):
            first = codex_setup.apply_plan(codex_setup.build_plan(answers))
            config = Path(first["config"])
            original = config.read_bytes()
            config.chmod(0o640)
            reuse = codex_setup.normalize_answers(
                workspace, "neutral", "Organization", "none", "matter,tracker",
                "skip", "off", "", "reuse",
            )
            plan = codex_setup.build_plan(reuse)
            with self.assertRaisesRegex(ValueError, "migrate this existing path explicitly"):
                codex_setup.apply_plan(plan)
        self.assertEqual(config.read_bytes(), original)
        self.assertEqual(mode(config), 0o640)

    def test_upgrade_preview_rejects_insecure_existing_tracker_without_change(self):
        workspace = self.root / "codex-tracker-upgrade"
        answers = codex_setup.normalize_answers(
            workspace, "neutral", "Organization", "none", "matter,tracker",
            "skip", "off", "", "error",
        )
        original_report = codex_setup.dependency_report
        with patch(
            "lawyeredos.codex_setup.dependency_report",
            side_effect=lambda modules: self._available(original_report(modules)),
        ):
            result = codex_setup.apply_plan(codex_setup.build_plan(answers))
            tracker = workspace / ".lawyeredos" / "data" / "matters.sqlite3"
            original = tracker.read_bytes()
            tracker.chmod(0o640)
            reuse = codex_setup.normalize_answers(
                workspace, "neutral", "Organization", "none", "matter,tracker",
                "skip", "off", "", "reuse",
            )
            with self.assertRaisesRegex(ValueError, "migrate this existing path explicitly"):
                codex_setup.build_plan(reuse)
        self.assertEqual(tracker.read_bytes(), original)
        self.assertEqual(mode(tracker), 0o640)

        claude_workspace = self.root / "claude-tracker-upgrade"
        claude_answers = setup_wizard.Answers(
            workspace=claude_workspace, branding_mode="neutral", branding_label="Organization",
            jurisdiction="none", modules=("matter", "tracker"), mail_adapter="unavailable",
            calendar_adapter="unavailable", calendar_id="", existing_config="reuse",
        )
        original_claude_report = setup_wizard.dependency_report
        with patch(
            "lawyeredos.setup_wizard.dependency_report",
            side_effect=lambda modules=(): self._available(original_claude_report(modules)),
        ):
            setup_wizard.apply_plan(setup_wizard.build_plan(claude_answers))
            claude_tracker = claude_workspace / ".lawyeredos" / "data" / "matters.sqlite3"
            claude_original = claude_tracker.read_bytes()
            claude_tracker.chmod(0o640)
            with self.assertRaisesRegex(ValueError, "migrate this existing path explicitly"):
                setup_wizard.build_plan(claude_answers)
        self.assertEqual(claude_tracker.read_bytes(), claude_original)
        self.assertEqual(mode(claude_tracker), 0o640)

    def test_both_hosts_reject_hardlinked_existing_tracker_without_change(self):
        codex_workspace = self.root / "codex-hardlink"
        codex_answers = codex_setup.normalize_answers(
            codex_workspace, "neutral", "Organization", "none", "matter,tracker",
            "skip", "off", "", "error",
        )
        original_codex_report = codex_setup.dependency_report
        with patch(
            "lawyeredos.codex_setup.dependency_report",
            side_effect=lambda modules: self._available(original_codex_report(modules)),
        ):
            codex_setup.apply_plan(codex_setup.build_plan(codex_answers))
            codex_tracker = codex_workspace / ".lawyeredos" / "data" / "matters.sqlite3"
            codex_original = codex_tracker.read_bytes()
            os.link(codex_tracker, self.root / "codex-tracker-alias")
            codex_reuse = codex_setup.normalize_answers(
                codex_workspace, "neutral", "Organization", "none", "matter,tracker",
                "skip", "off", "", "reuse",
            )
            with self.assertRaisesRegex(ValueError, "multiple hard links"):
                codex_setup.build_plan(codex_reuse)
        self.assertEqual(codex_tracker.read_bytes(), codex_original)
        self.assertEqual(mode(codex_tracker), 0o600)

        claude_workspace = self.root / "claude-hardlink"
        claude_answers = setup_wizard.Answers(
            workspace=claude_workspace, branding_mode="neutral", branding_label="Organization",
            jurisdiction="none", modules=("matter", "tracker"), mail_adapter="unavailable",
            calendar_adapter="unavailable", calendar_id="", existing_config="reuse",
        )
        original_claude_report = setup_wizard.dependency_report
        with patch(
            "lawyeredos.setup_wizard.dependency_report",
            side_effect=lambda modules=(): self._available(original_claude_report(modules)),
        ):
            setup_wizard.apply_plan(setup_wizard.build_plan(claude_answers))
            claude_tracker = claude_workspace / ".lawyeredos" / "data" / "matters.sqlite3"
            claude_original = claude_tracker.read_bytes()
            os.link(claude_tracker, self.root / "claude-tracker-alias")
            with self.assertRaisesRegex(ValueError, "multiple hard links"):
                setup_wizard.build_plan(claude_answers)
        self.assertEqual(claude_tracker.read_bytes(), claude_original)
        self.assertEqual(mode(claude_tracker), 0o600)


if __name__ == "__main__":
    unittest.main()
