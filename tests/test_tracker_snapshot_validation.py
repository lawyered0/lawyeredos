"""Fictional snapshot validation and honest projection receipt regressions."""
import io
import json
import sqlite3
import unittest
from contextlib import redirect_stdout

from openpyxl import load_workbook

from lawyeredos.tracker_cli import commit_mutation, preview_mutation, verify
from lawyeredos.tracker_migration import commit_migration, export_tracker, main, migration_plan
from lawyeredos.tracker_xlsx import project
import test_tracker_integrity as fixture


class TrackerSnapshotValidationTests(unittest.TestCase):
    setUp = fixture.TrackerIntegrityTests.setUp
    tearDown = fixture.TrackerIntegrityTests.tearDown
    args = fixture.TrackerIntegrityTests.args
    mutate = fixture.TrackerIntegrityTests.mutate

    def snapshot(self):
        source = self.root / "snapshot.json"
        export_tracker(self.database, source, "json")
        return source, json.loads(source.read_text())

    def test_snapshot_refuses_revision_regression_before_publication(self):
        source, value = self.snapshot()
        for row in value["meta"]:
            if row["key"] == "revision":
                row["value"] = "0"
        source.write_text(json.dumps(value))
        target = self.root / "restored.sqlite3"
        with self.assertRaisesRegex(ValueError, "snapshot.*revision"):
            migration_plan(source, target)
        self.assertFalse(target.exists())
        self.assertEqual(verify(self.database)["revision"], 1)

    def test_snapshot_metadata_types_return_json_refusal(self):
        source, original = self.snapshot()
        for key, invalid in (("key", []), ("key", {}), ("key", None),
                             ("value", []), ("value", 1), ("value", None)):
            with self.subTest(key=key, invalid=invalid):
                value = json.loads(json.dumps(original))
                value["meta"][0][key] = invalid
                source.write_text(json.dumps(value))
                output = io.StringIO()
                target = self.root / "restored.sqlite3"
                with redirect_stdout(output):
                    code = main(["preview", "--source", str(source), "--target", str(target)])
                self.assertEqual(code, 2)
                receipt = json.loads(output.getvalue())
                self.assertFalse(receipt["ok"])
                self.assertFalse(receipt["committed"])
                self.assertIn("metadata", receipt["error"])
                self.assertFalse(target.exists())

    def test_snapshot_refuses_invalid_or_reused_audit_revisions(self):
        source, original = self.snapshot()
        for invalid in (0, -1, "1", True, None):
            with self.subTest(invalid=invalid):
                value = json.loads(json.dumps(original))
                value["audit"][0]["revision"] = invalid
                source.write_text(json.dumps(value))
                with self.assertRaisesRegex(ValueError, "snapshot.*revision"):
                    migration_plan(source, self.root / "restored.sqlite3")
        value = json.loads(json.dumps(original))
        duplicate = dict(value["audit"][0], id=2)
        value["audit"].append(duplicate)
        source.write_text(json.dumps(value))
        with self.assertRaisesRegex(ValueError, "snapshot.*revision"):
            migration_plan(source, self.root / "restored.sqlite3")

    def test_snapshot_preserves_revision_gaps_and_higher_sequences(self):
        source, value = self.snapshot()
        for row in value["meta"]:
            if row["key"] == "revision":
                row["value"] = "10"
        value["sqlite_sequence"] = [{"name": "audit", "seq": 100},
                                    {"name": "timeline", "seq": 50}]
        source.write_text(json.dumps(value))
        target = self.root / "restored.sqlite3"
        preview = migration_plan(source, target)
        receipt = commit_migration(source, target, preview["confirm_token"])
        self.assertTrue(receipt["history_preserved"])
        with sqlite3.connect(target) as connection:
            self.assertEqual(connection.execute("SELECT value FROM meta WHERE key='revision'").fetchone()[0], "10")
            self.assertEqual(connection.execute("SELECT revision FROM audit").fetchall(), [(1,)])
            self.assertEqual(connection.execute("SELECT name,seq FROM sqlite_sequence ORDER BY name").fetchall(),
                             [("audit", 100), ("timeline", 50)])

    def test_snapshot_refuses_invalid_sequence_records(self):
        source, original = self.snapshot()
        invalid_sequences = ([{"name": "audit", "seq": -1}],
                             [{"name": "audit", "seq": "1"}],
                             [{"name": "audit", "seq": True}],
                             [{"name": "audit", "seq": None}],
                             [{"name": "unknown", "seq": 1}],
                             [{"name": [], "seq": 1}],
                             [{"name": "audit", "seq": 1}, {"name": "audit", "seq": 2}],
                             [{"name": "audit", "seq": 0}],
                             [{"name": "audit", "seq": 2 ** 63}])
        for sequences in invalid_sequences:
            with self.subTest(sequences=sequences):
                value = json.loads(json.dumps(original))
                value["sqlite_sequence"] = sequences
                source.write_text(json.dumps(value))
                with self.assertRaisesRegex(ValueError, "snapshot.*sequence"):
                    migration_plan(source, self.root / "restored.sqlite3")

    def test_snapshot_missing_sequences_preserves_rows_and_next_ids(self):
        source, value = self.snapshot()
        value["sqlite_sequence"] = []
        source.write_text(json.dumps(value))
        target = self.root / "restored.sqlite3"
        preview = migration_plan(source, target)
        commit_migration(source, target, preview["confirm_token"])
        args = self.args(database=str(target))
        preview = preview_mutation(target, "timeline", args)
        commit_mutation(target, "timeline", args, preview["confirm_token"])
        with sqlite3.connect(target) as connection:
            self.assertEqual(connection.execute("SELECT id FROM audit ORDER BY id").fetchall(), [(1,), (2,)])
            self.assertEqual(connection.execute("SELECT id FROM timeline").fetchall(), [(1,)])

    def test_legacy_import_without_history_can_roundtrip_as_snapshot(self):
        source = self.root / "legacy.json"
        source.write_text(json.dumps([{"file_number": "2030-002", "client": "Fictional B",
                                      "description": "Fictional imported matter", "matter_folder": "other"}]))
        legacy = self.root / "legacy.sqlite3"
        preview = migration_plan(source, legacy)
        commit_migration(source, legacy, preview["confirm_token"])
        snapshot = self.root / "legacy-snapshot.json"
        export_tracker(legacy, snapshot, "json")
        for source in (legacy, snapshot):
            target = self.root / (source.name + ".restored.sqlite3")
            preview = migration_plan(source, target)
            commit_migration(source, target, preview["confirm_token"])
            self.assertEqual(verify(target)["revision"], 0)
            with sqlite3.connect(target) as connection:
                self.assertEqual(connection.execute("SELECT COUNT(*) FROM audit").fetchone()[0], 0)

    def test_projection_discloses_omitted_deadline_metadata(self):
        deadline = [{"date": "2030-02-01", "description": "Fictional filing",
                     "source": "Fictional order paragraph 4", "unverified": True}]
        self.mutate("update", set_values=["court_deadlines=" + json.dumps(deadline)])
        output = self.root / "projection.xlsx"
        receipt = project(self.database, output)
        self.assertFalse(receipt["lossless_projection"])
        self.assertEqual(receipt["omitted_deadline_fields"], [{"file_number": "2030-001",
                         "field": "court_deadlines", "item_index": 0,
                         "omitted_fields": ["source", "unverified"]}])
        self.assertEqual(load_workbook(output)["Open Matters"]["H2"].value,
                         "2030-02-01 | Fictional filing")
        with sqlite3.connect(self.database) as connection:
            self.assertEqual(json.loads(connection.execute("SELECT court_deadlines FROM matters").fetchone()[0]), deadline)


if __name__ == "__main__":
    unittest.main()
