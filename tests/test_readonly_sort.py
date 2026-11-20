from __future__ import annotations

import hashlib
import sqlite3
import tempfile
import unittest
from pathlib import Path

from lawyeredos.tracker_cli import connect, initialize


class ReadOnlySortTests(unittest.TestCase):
    def test_large_sort_is_connection_local_readonly_and_preserves_database(self):
        with tempfile.TemporaryDirectory() as folder:
            database = Path(folder) / "fictional # tracker?.sqlite3"
            initialize(database)
            before = hashlib.sha256(database.read_bytes()).hexdigest()
            files = sorted(p.name for p in Path(folder).iterdir())
            with connect(database) as connection:
                self.assertEqual(connection.execute("PRAGMA temp_store").fetchone()[0], 2)
                rows = connection.execute(
                    "WITH RECURSIVE n(x) AS (VALUES(1) UNION ALL SELECT x+1 FROM n WHERE x<20000) "
                    "SELECT printf('%08d',20001-x) || replace(hex(zeroblob(128)), '0', 'F') AS value "
                    "FROM n ORDER BY value"
                ).fetchall()
                self.assertEqual(len(rows), 20000)
                self.assertTrue(rows[0][0].startswith("00000001"))
                self.assertTrue(rows[-1][0].startswith("00020000"))
                with self.assertRaises(sqlite3.OperationalError):
                    connection.execute("INSERT INTO meta VALUES ('fictional','blocked')")
            self.assertEqual(hashlib.sha256(database.read_bytes()).hexdigest(), before)
            self.assertEqual(sorted(p.name for p in Path(folder).iterdir()), files)
            with sqlite3.connect(database) as separate:
                self.assertEqual(separate.execute("PRAGMA temp_store").fetchone()[0], 0)

    def test_missing_database_is_not_created(self):
        with tempfile.TemporaryDirectory() as folder:
            database = Path(folder) / "absent.sqlite3"
            with self.assertRaises(ValueError):
                with connect(database):
                    self.fail("missing database opened")
            self.assertFalse(database.exists())
