"""Fictional regressions for report memory-search-1 and memory-search-2."""
import os
import json
import io
from contextlib import redirect_stdout
from unittest.mock import patch
import stat
import tempfile
import unittest
from pathlib import Path

from lawyeredos.common import sha256_file
from lawyeredos.memory_search import build_index, memory_preview, memory_commit, search
from lawyeredos.tracker_cli import initialize, preview_mutation, commit_mutation
from test_matter_write import tracker_args


class ScopedMemoryReportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_ordinary_punctuation_search_and_private_index(self):
        matter = self.root / "fictional"; matter.mkdir()
        (matter / "_matter-brief.md").write_text("# Fictional\n2035-017 Smith-Jones O'Brien Re: settlement")
        index = self.root / "index?fictional#brief.sqlite3"
        build_index(matter, index)
        self.assertEqual(stat.S_IMODE(index.stat().st_mode), 0o600)
        for query in ["2035-017", "Smith-Jones", "O'Brien", "Re: settlement"]:
            with self.subTest(query=query):
                self.assertEqual(len(search(index, query)["results"]), 1)

    def test_ordinary_punctuation_is_literal_search_text(self):
        matter = self.root / "fictional"; matter.mkdir()
        (matter / "_matter-brief.md").write_text("# Fictional\n2035-017 Smith-Jones O'Brien Re: settlement")
        index = self.root / "index.sqlite3"
        build_index(matter, index)
        for query in ["2035-017", "Smith-Jones", "O'Brien", "Re: settlement"]:
            with self.subTest(query=query):
                self.assertEqual(len(search(index, query)["results"]), 1)

    def test_memory_cannot_follow_sibling_symlink(self):
        (self.root / "A").mkdir(); (self.root / "B").mkdir()
        other = self.root / "B/_matter-decisions.md"; other.write_text("B note")
        (self.root / "A/_matter-decisions.md").symlink_to(other)
        with self.assertRaisesRegex(ValueError, "symlink|registered"):
            memory_preview(self.root, "A/_matter-decisions.md", b"A note", sha256_file(other))
        self.assertEqual(other.read_text(), "B note")

    def test_memory_requires_registered_matter_without_creating_parent(self):
        with self.assertRaisesRegex(ValueError, "registered"):
            memory_preview(self.root, "NotAMatter/_matter-brief.md", b"fictional")
        self.assertFalse((self.root / "NotAMatter").exists())

    def register(self, folder="A"):
        from test_matter_write import tracker_args
        database = self.root / "tracker.sqlite3"
        initialize(database)
        args = tracker_args(database, "create", matter_folder=folder)
        approved = preview_mutation(database, "create", args)
        commit_mutation(database, "create", args, approved["confirm_token"])
        return database

    def test_registered_memory_writes_reject_closed_wrong_folder_and_hardlinks(self):
        (self.root / "A").mkdir(); (self.root / "B").mkdir()
        database = self.register()
        kwargs = {"database": database, "file_number": "2035-001"}
        with self.assertRaisesRegex(ValueError, "registered"):
            memory_preview(self.root, "B/_matter-brief.md", b"Fictional", **kwargs)
        approved = memory_preview(self.root, "A/_matter-brief.md", b"Fictional", **kwargs)
        result = memory_commit(self.root, "A/_matter-brief.md", b"Fictional", "", approved["confirm_token"], **kwargs)
        self.assertTrue(result["committed"])
        target = self.root / "A/_matter-brief.md"
        digest = sha256_file(target)
        approved = memory_preview(self.root, "A/_matter-brief.md", b"Changed", digest, **kwargs)
        memory_commit(self.root, "A/_matter-brief.md", b"Changed", digest, approved["confirm_token"], **kwargs)
        os.link(target, self.root / "alias.md")
        with self.assertRaisesRegex(ValueError, "hard links|single-link"):
            memory_preview(self.root, "A/_matter-brief.md", b"Later", sha256_file(target), **kwargs)
        (self.root / "alias.md").unlink()
        close_args = tracker_args(database, "close")
        close_preview = preview_mutation(database, "close", close_args)
        commit_mutation(database, "close", close_args, close_preview["confirm_token"])
        with self.assertRaisesRegex(ValueError, "closed"):
            memory_preview(self.root, "A/_matter-brief.md", b"Later", sha256_file(target), **kwargs)

    def test_memory_tracker_change_stales_approval(self):
        (self.root / "A").mkdir()
        database = self.register()
        kwargs = {"database": database, "file_number": "2035-001"}
        approved = memory_preview(self.root, "A/_matter-brief.md", b"Fictional", **kwargs)
        args = tracker_args(database, "timeline", text="Fictional concurrent edit")
        action = preview_mutation(database, "timeline", args)
        commit_mutation(database, "timeline", args, action["confirm_token"])
        with self.assertRaisesRegex(ValueError, "stale"):
            memory_commit(self.root, "A/_matter-brief.md", b"Fictional", "", approved["confirm_token"], **kwargs)
        self.assertFalse((self.root / "A/_matter-brief.md").exists())

    def memory_cli(self):
        from lawyeredos import memory_search
        (self.root / "A").mkdir()
        database = self.register()
        content = self.root / "fictional-note.txt"; content.write_text("Fictional durable note")
        approved = memory_preview(self.root, "A/_matter-brief.md", content.read_bytes(),
                                  database=database, file_number="2035-001")
        args = ["commit-write", "--root", str(self.root), "--relative", "A/_matter-brief.md",
                "--content-file", str(content), "--database", str(database),
                "--file-number", "2035-001", "--confirm-token", approved["confirm_token"]]
        return memory_search, args, self.root / "A/_matter-brief.md"

    def test_post_install_readback_failure_reports_committed_not_retryable(self):
        module, args, target = self.memory_cli()
        original_install = module._install_file
        original_digest = module._target_digest
        installed = False
        def install(*values, **kwargs):
            nonlocal installed
            result = original_install(*values, **kwargs)
            installed = True
            return result
        def digest(*values, **kwargs):
            if installed:
                raise OSError("fictional readback failure")
            return original_digest(*values, **kwargs)
        output = io.StringIO()
        with patch.object(module, "_install_file", side_effect=install), patch.object(module, "_target_digest", side_effect=digest):
            with redirect_stdout(output):
                rc = module.main(args)
        result = json.loads(output.getvalue())
        self.assertEqual(target.read_text(), "Fictional durable note")
        self.assertEqual(rc, 2)
        self.assertTrue(result["committed"])
        self.assertFalse(result["retry_safe"])
        self.assertEqual(result["verification_state"], "readback_failed")

    def test_post_install_cleanup_failure_preserves_committed_receipt(self):
        module, args, target = self.memory_cli()
        original_install = module._install_file
        original_unlink = module.os.unlink
        installed = False
        def install(*values, **kwargs):
            nonlocal installed
            result = original_install(*values, **kwargs)
            installed = True
            return result
        def unlink(path, *values, **kwargs):
            if installed and str(path).startswith(".memory-stage-"):
                raise OSError("fictional cleanup failure")
            return original_unlink(path, *values, **kwargs)
        output = io.StringIO()
        with patch.object(module, "_install_file", side_effect=install), patch.object(module.os, "unlink", side_effect=unlink):
            with redirect_stdout(output):
                rc = module.main(args)
        result = json.loads(output.getvalue())
        self.assertEqual(target.read_text(), "Fictional durable note")
        self.assertEqual(rc, 2)
        self.assertTrue(result["committed"])
        self.assertFalse(result["retry_safe"])
        self.assertEqual(result["verification_state"], "readback_verified")
        self.assertIn("fictional cleanup failure", result["cleanup_errors"][0])

    def test_nonprivate_existing_memory_lock_refused_without_mode_change(self):
        module, args, target = self.memory_cli()
        lock = self.root / "A/.lawyeredos-memory.lock"
        lock.write_text(""); lock.chmod(0o644)
        output = io.StringIO()
        with redirect_stdout(output):
            rc = module.main(args)
        result = json.loads(output.getvalue())
        self.assertEqual(rc, 2)
        self.assertFalse(result["committed"])
        self.assertIn("private", result["error"])
        self.assertFalse(target.exists())
        self.assertEqual(stat.S_IMODE(lock.stat().st_mode), 0o644)

    def test_prepublication_failure_still_reports_not_committed(self):
        module, args, target = self.memory_cli()
        output = io.StringIO()
        with patch.object(module, "_install_file", side_effect=OSError("fictional prepublication failure")):
            with redirect_stdout(output):
                rc = module.main(args)
        result = json.loads(output.getvalue())
        self.assertEqual(rc, 2)
        self.assertFalse(result["committed"])
        self.assertFalse(target.exists())
