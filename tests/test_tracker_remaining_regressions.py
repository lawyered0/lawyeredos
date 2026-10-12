"""Recovered-report tracker claims verified only with fictional isolated data."""
import csv
import io
import json
import os
import sqlite3
import stat
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from openpyxl import load_workbook

from lawyeredos.tracker_cli import initialize, preview_mutation, verify
from lawyeredos.tracker_migration import commit_migration, export_tracker, migration_plan
from lawyeredos.tracker_xlsx import main as xlsx_main, project
from test_tracker_integrity import TrackerIntegrityTests


class TrackerRemainingRegressions(unittest.TestCase):
    setUp = TrackerIntegrityTests.setUp
    tearDown = TrackerIntegrityTests.tearDown
    args = TrackerIntegrityTests.args
    mutate = TrackerIntegrityTests.mutate
    def test_blank_required_update_refused_and_existing_damage_detected(self):
        for field in ("client", "description"):
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "required"):
                preview_mutation(self.database, "update", self.args(set_values=[field + "="]))
        with sqlite3.connect(self.database) as connection:
            connection.execute("UPDATE matters SET client='', description=' '")
        self.assertIn("blank required matter fields", verify(self.database)["problems"])

    def test_update_cannot_clear_next_action_or_operate_on_closed_matter(self):
        self.mutate("update", set_values=["next_action=Fictional follow-up", "next_action_date=2030-01-02"])
        for field in ("next_action", "next_action_date"):
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "workflow"):
                preview_mutation(self.database, "update", self.args(set_values=[field + "="]))
        self.mutate("close")
        for action, changes in (("update", {"set_values": ["next_action=New obligation"]}), ("timeline", {})):
            with self.subTest(action=action), self.assertRaisesRegex(ValueError, "closed"):
                preview_mutation(self.database, action, self.args(**changes))
        self.mutate("update", set_values=["primary_email=fictional@example.invalid"])

    def test_mutations_reject_illegal_xml_control_characters(self):
        for action, changes in (("create", {"file_number": "2030-002", "matter_folder": "other", "client": "a\x0bb"}),
                                ("update", {"set_values": ["description=a\x0bb"]}),
                                ("timeline", {"text": "a\x0bb"}),
                                ("update", {"set_values": ['court_deadlines=[{"description":"a\\u000bb"}]']})):
            with self.subTest(action=action, changes=changes), self.assertRaisesRegex(ValueError, "control character"):
                preview_mutation(self.database, action, self.args(**changes))

    def test_projection_reports_legacy_controls_and_long_fields_without_changing_source(self):
        with sqlite3.connect(self.database) as connection:
            connection.execute("UPDATE matters SET description=?, next_action=?", ("a\x0bb", "x" * 40000))
        before = self.database.read_bytes()
        output = self.root / "legacy.xlsx"
        result = project(self.database, output)
        self.assertEqual(result["sanitized"], [{"file_number": "2030-001", "field": "description", "removed_characters": 1}])
        self.assertEqual(result["truncated"], [{"file_number": "2030-001", "field": "next_action", "original_characters": 40000}])
        book = load_workbook(output)
        self.assertEqual(book["Open Matters"]["C2"].value, "a\ufffdb")
        self.assertTrue(book["Open Matters"]["E2"].value.endswith("[truncated; full text in tracker DB]"))
        self.assertEqual(len(book["Open Matters"]["E2"].value), 32767)
        self.assertEqual(self.database.read_bytes(), before)

    def test_xlsx_unexpected_export_error_has_structured_failure(self):
        output = io.StringIO()
        with patch("openpyxl.workbook.workbook.Workbook.save", side_effect=RuntimeError("fictional save failure")), redirect_stdout(output):
            result = xlsx_main(["--database", str(self.database), "--output", str(self.root / "failed.xlsx")])
        self.assertEqual(result, 2)
        receipt = json.loads(output.getvalue())
        self.assertFalse(receipt["ok"])
        self.assertTrue(receipt["read_only_source"])

    def test_all_fresh_exports_are_private_under_permissive_umask(self):
        old = os.umask(0)
        try:
            for fmt in ("csv", "json", "xlsx"):
                output = self.root / ("private." + fmt)
                if fmt == "xlsx":
                    project(self.database, output)
                else:
                    export_tracker(self.database, output, fmt)
                self.assertEqual(stat.S_IMODE(output.stat().st_mode), 0o600)
        finally:
            os.umask(old)

    def test_migration_destination_appearing_at_publish_is_not_overwritten(self):
        source = self.root / "source.json"
        export_tracker(self.database, source, "json")
        target = self.root / "restore.sqlite3"
        plan = migration_plan(source, target)
        original_link = os.link
        original_replace = os.replace

        def collide(publish, source_path, target_path, *args, **kwargs):
            if Path(target_path) == target:
                target.write_bytes(b"fictional competing destination")
            return publish(source_path, target_path, *args, **kwargs)

        with patch("lawyeredos.tracker_migration.os.link", side_effect=lambda *args, **kwargs: collide(original_link, *args, **kwargs)), \
             patch("lawyeredos.tracker_migration.os.replace", side_effect=lambda *args, **kwargs: collide(original_replace, *args, **kwargs)):
            with self.assertRaises(FileExistsError):
                commit_migration(source, target, plan["confirm_token"])
        self.assertEqual(target.read_bytes(), b"fictional competing destination")

    def test_xlsx_destination_appearing_during_save_is_not_overwritten(self):
        from openpyxl.workbook.workbook import Workbook
        output = self.root / "collision.xlsx"
        original = Workbook.save

        def collide(book, target):
            output.write_bytes(b"fictional competing destination")
            return original(book, target)

        with patch.object(Workbook, "save", collide), self.assertRaises(FileExistsError):
            project(self.database, output)
        self.assertEqual(output.read_bytes(), b"fictional competing destination")

    def test_migration_cleanup_failure_after_publish_reports_committed(self):
        source = self.root / "snapshot.json"
        export_tracker(self.database, source, "json")
        target = self.root / "restore.sqlite3"
        plan = migration_plan(source, target)
        original = Path.unlink

        def fail_after_publication(path, *args, **kwargs):
            if target.exists() and path.name.startswith(".restore.sqlite3."):
                raise OSError("fictional temporary cleanup failure")
            return original(path, *args, **kwargs)

        with patch.object(Path, "unlink", fail_after_publication):
            result = commit_migration(source, target, plan["confirm_token"])
        self.assertFalse(result["ok"])
        self.assertTrue(result["committed"])
        self.assertFalse(result["retry_safe"])
        self.assertEqual(result["verification_state"], "temporary_cleanup_failed")
        self.assertTrue(target.is_file())

    def test_reserved_uri_characters_access_only_the_existing_fictional_database(self):
        folder = self.root / "a#b?c%20d"
        folder.mkdir()
        # Copy an already-created fictional tracker, never invoke missing-DB recovery.
        database = folder / "existing.sqlite3"
        database.write_bytes(self.database.read_bytes())
        database.chmod(0o600)
        before = sorted(path.name for path in self.root.iterdir())
        self.assertTrue(verify(database)["ok"])
        source = folder / "snapshot.json"
        export_tracker(database, source, "json")
        project(database, folder / "projection.xlsx")
        self.assertEqual(migration_plan(database, folder / "restored.sqlite3")["matter_count"], 1)
        self.assertEqual(sorted(path.name for path in self.root.iterdir()), before)


if __name__ == "__main__":
    unittest.main()
