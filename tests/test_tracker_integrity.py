from __future__ import annotations

import argparse
import csv
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from openpyxl import load_workbook

from lawyeredos.tracker_cli import commit_mutation, initialize, preview_mutation, verify
from lawyeredos.tracker_migration import commit_migration, export_tracker, migration_plan
from lawyeredos.tracker_xlsx import project


class TrackerIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.database = self.root / "fictional.sqlite3"
        initialize(self.database)
        self.mutate("create")

    def tearDown(self):
        self.temp.cleanup()

    def args(self, **changes):
        values = dict(database=str(self.database), file_number="2030-001",
                      client="Fictional Bakery", description="Fictional agreement",
                      matter_folder="fictional/matter", opposing_party="", other_parties="",
                      primary_email="", set_values=[], event_date="2030-01-01",
                      text="Fictional event")
        values.update(changes)
        return argparse.Namespace(**values)

    def mutate(self, action, **changes):
        args = self.args(**changes)
        plan = preview_mutation(self.database, action, args)
        return commit_mutation(self.database, action, args, plan["confirm_token"])

    def test_create_rejects_equivalent_folder_spellings(self):
        for folder in ("fictional/./matter", "fictional/matter/", "FICTIONAL/MATTER"):
            with self.subTest(folder=folder), self.assertRaisesRegex(ValueError, "already assigned"):
                preview_mutation(self.database, "create", self.args(
                    file_number="2030-002", matter_folder=folder))

    def test_update_rejects_unsafe_and_duplicate_folders(self):
        self.mutate("create", file_number="2030-002", matter_folder="other")
        for folder in ("../escape", "/absolute", ".", "FICTIONAL/./MATTER"):
            with self.subTest(folder=folder), self.assertRaises(ValueError):
                preview_mutation(self.database, "update", self.args(
                    file_number="2030-002", set_values=[f"matter_folder={folder}"]))

    def test_verify_detects_equivalent_legacy_folder_assignments(self):
        self.mutate("create", file_number="2030-002", matter_folder="other")
        with sqlite3.connect(self.database) as connection:
            connection.execute("UPDATE matters SET matter_folder='FICTIONAL/./MATTER' WHERE file_number='2030-002'")
        self.assertIn("duplicate matter folders", verify(self.database)["problems"])

    def test_legacy_migration_rejects_equivalent_folder_assignments(self):
        source = self.root / "legacy.json"
        source.write_text(json.dumps([
            {"file_number": "2030-001", "client": "Fictional A", "description": "Example", "matter_folder": "a/b"},
            {"file_number": "2030-002", "client": "Fictional B", "description": "Example", "matter_folder": "A/./B"},
        ]))
        with self.assertRaisesRegex(ValueError, "duplicate matter folders"):
            migration_plan(source, self.root / "new.sqlite3")

    def test_xlsx_preserves_formula_like_text_without_formula_cells(self):
        self.mutate("update", set_values=["client==1+1", "description=+1+1", "next_action=@SUM(1,1)"])
        output = self.root / "projection.xlsx"
        project(self.database, output)
        workbook = load_workbook(output, data_only=False)
        sheet = workbook["Open Matters"]
        self.assertEqual(sheet["B2"].value, "=1+1")
        self.assertEqual(sheet["B2"].data_type, "s")
        self.assertFalse(any(cell.data_type == "f" for row in sheet for cell in row))

    def test_csv_neutralizes_formula_like_text(self):
        self.mutate("update", set_values=["client==1+1", "description=+1+1", "next_action=@SUM(1,1)"])
        output = self.root / "projection.csv"
        export_tracker(self.database, output, "csv")
        with output.open(newline="") as handle:
            row = next(csv.DictReader(handle))
        self.assertEqual(row["client"], "'=1+1")
        self.assertEqual(row["description"], "'+1+1")
        self.assertEqual(row["next_action"], "'@SUM(1,1)")

    def test_canonical_snapshot_roundtrip_preserves_history_and_revision(self):
        self.mutate("timeline")
        for source_kind in ("json", "sqlite"):
            with self.subTest(source_kind=source_kind):
                source = self.database
                if source_kind == "json":
                    source = self.root / "snapshot.json"
                    export_tracker(self.database, source, "json")
                target = self.root / f"restored-{source_kind}.sqlite3"
                plan = migration_plan(source, target)
                commit_migration(source, target, plan["confirm_token"])
                with sqlite3.connect(self.database) as before, sqlite3.connect(target) as after:
                    for table in ("meta", "matters", "timeline", "audit", "sqlite_sequence"):
                        self.assertEqual(before.execute(f"SELECT * FROM {table} ORDER BY 1").fetchall(),
                                         after.execute(f"SELECT * FROM {table} ORDER BY 1").fetchall())

    def test_snapshot_confirmation_binds_history_and_rejects_incomplete_history(self):
        source = self.root / "snapshot.json"
        export_tracker(self.database, source, "json")
        target = self.root / "restored.sqlite3"
        plan = migration_plan(source, target)
        value = json.loads(source.read_text())
        value["audit"][0]["payload_json"] = "{}"
        source.write_text(json.dumps(value))
        with self.assertRaisesRegex(ValueError, "stale"):
            commit_migration(source, target, plan["confirm_token"])
        del value["timeline"]
        source.write_text(json.dumps(value))
        with self.assertRaisesRegex(ValueError, "snapshot table"):
            migration_plan(source, target)
        self.assertFalse(target.exists())

    def test_export_failure_does_not_change_successful_commit_receipt(self):
        receipt = self.mutate("timeline")
        with patch("openpyxl.workbook.workbook.Workbook.save", side_effect=OSError("fictional export failure")):
            with self.assertRaisesRegex(OSError, "fictional export failure"):
                project(self.database, self.root / "failed.xlsx")
        self.assertTrue(receipt["committed"])
        self.assertFalse(receipt["retry_safe"])
        with sqlite3.connect(self.database) as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM timeline").fetchone()[0], 1)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM audit").fetchone()[0], 2)


if __name__ == "__main__":
    unittest.main()
