"""Regression fixtures for report matter-write-1; no live tracker data."""
import json
import sqlite3
import unittest
from pathlib import Path
from unittest.mock import patch

import test_matter_write as matter_tests
from lawyeredos.matter_write import preview, commit, inspect_recovery, recover
from lawyeredos.tracker_cli import connect


class RetryReportTests(unittest.TestCase):
    setUp = matter_tests.GuardedMatterWriteTests.setUp
    tearDown = matter_tests.GuardedMatterWriteTests.tearDown
    args = matter_tests.GuardedMatterWriteTests.args
    def test_terminal_rollback_allows_identical_approved_attempt(self):
        args = self.args(next_action="Review fictional note")
        args.confirm_token = preview(args)["confirm_token"]
        def quick_connect(database):
            connection = connect(database)
            connection.execute("PRAGMA busy_timeout=10")
            return connection
        with sqlite3.connect(self.database) as locker:
            locker.execute("BEGIN IMMEDIATE")
            with patch("lawyeredos.tracker_cli.connect", side_effect=quick_connect):
                before = commit(args)
            locker.rollback()
        self.assertEqual(before["tracker_receipt"]["error"], "database is locked")
        self.assertEqual(before["verification_state"], "rollback_verified")
        inspected = inspect_recovery(self.root, before["transaction_id"])
        recover(self.root, before["transaction_id"], inspected["confirm_token"])
        self.assertEqual(args.confirm_token, preview(args)["confirm_token"])
        after = commit(args)
        self.assertTrue(after["committed"])
        self.assertNotEqual(before["transaction_id"], after["transaction_id"])
        self.assertTrue(Path(before["journal"]).is_file())

    def test_unresolved_attempt_remains_nonreplayable(self):
        args = self.args(next_action="Review fictional note")
        args.confirm_token = preview(args)["confirm_token"]
        failed = {"ok": False, "committed": False, "commit_state": "not_committed",
                  "verification_state": "not_performed", "error": "fictional transient failure"}
        with patch("lawyeredos.matter_write._commit_workflow", return_value=failed):
            result = commit(args)
        journal = Path(result["journal"])
        receipt = json.loads(journal.read_text())
        receipt["verification_state"] = "not_performed"
        journal.write_text(json.dumps(receipt))
        with self.assertRaisesRegex(ValueError, "already has a journal"):
            commit(args)
