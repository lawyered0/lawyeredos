"""Fictional regressions for report memory-search-1 and memory-search-2."""
import os
import json
import io
from contextlib import redirect_stdout
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor
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

    def test_install_sync_failure_keeps_uncertain_nonretry_receipt(self):
        module, args, target = self.memory_cli()
        original_fsync = module.os.fsync
        def fsync(descriptor):
            if stat.S_ISDIR(os.fstat(descriptor).st_mode) and target.exists():
                raise OSError("fictional post-link sync failure")
            return original_fsync(descriptor)
        output = io.StringIO()
        with patch.object(module.os, "fsync", side_effect=fsync), redirect_stdout(output):
            rc = module.main(args)
        receipt = json.loads(output.getvalue())
        self.assertEqual(target.read_text(), "Fictional durable note")
        self.assertEqual(rc, 2)
        self.assertIsNone(receipt["committed"])
        self.assertEqual(receipt["commit_state"], "outcome_unknown")
        self.assertFalse(receipt["retry_safe"])

    def test_install_stage_cleanup_failure_keeps_uncertain_nonretry_receipt(self):
        module, args, target = self.memory_cli()
        original_unlink = module.os.unlink
        def unlink(path, *values, **kwargs):
            if str(path).startswith(".memory-stage-") and target.exists():
                raise OSError("fictional installed stage cleanup failure")
            return original_unlink(path, *values, **kwargs)
        output = io.StringIO()
        with patch.object(module.os, "unlink", side_effect=unlink), redirect_stdout(output):
            rc = module.main(args)
        receipt = json.loads(output.getvalue())
        self.assertEqual(target.read_text(), "Fictional durable note")
        self.assertEqual(rc, 2)
        self.assertIsNone(receipt["committed"])
        self.assertTrue(receipt["published"])
        self.assertFalse(receipt["retry_safe"])
        self.assertIn("cleanup_errors", receipt)
        self.assertTrue(any(Path(path).name.startswith(".memory-stage-")
                            for path in receipt["recovery_artifacts"]))

    def replacement_cli(self):
        module, args, target = self.memory_cli()
        target.write_text("Fictional old note")
        digest = sha256_file(target)
        args.extend(["--expect-sha256", digest])
        args[args.index("--confirm-token") + 1] = memory_preview(
            self.root, "A/_matter-brief.md", b"Fictional durable note", digest,
            self.root / "tracker.sqlite3", "2035-001",
        )["confirm_token"]
        return module, args, target

    def test_replace_new_link_failure_keeps_displaced_bytes_and_uncertain_receipt(self):
        module, args, target = self.replacement_cli()
        original_link = module.os.link
        def link(source, destination, *values, **kwargs):
            if str(source).startswith(".memory-stage-"):
                raise OSError("fictional new target link failure")
            return original_link(source, destination, *values, **kwargs)
        output = io.StringIO()
        with patch.object(module.os, "link", side_effect=link), redirect_stdout(output):
            rc = module.main(args)
        receipt = json.loads(output.getvalue())
        self.assertEqual(rc, 2)
        self.assertFalse(target.exists())
        displaced = list(target.parent.glob(".matter-write-*.displaced"))
        self.assertEqual(len(displaced), 1)
        self.assertEqual(displaced[0].read_text(), "Fictional old note")
        self.assertIsNone(receipt["committed"])
        self.assertEqual(receipt["commit_state"], "outcome_unknown")
        self.assertFalse(receipt["retry_safe"])
        self.assertEqual(receipt["recovery_artifacts"], [str(displaced[0].resolve())])

    def test_replace_displaced_cleanup_failure_keeps_uncertain_receipt(self):
        module, args, target = self.replacement_cli()
        original_unlink = module.os.unlink
        def unlink(path, *values, **kwargs):
            if str(path).endswith(".displaced"):
                raise OSError("fictional displaced cleanup failure")
            return original_unlink(path, *values, **kwargs)
        output = io.StringIO()
        with patch.object(module.os, "unlink", side_effect=unlink), redirect_stdout(output):
            rc = module.main(args)
        receipt = json.loads(output.getvalue())
        self.assertEqual(rc, 2)
        self.assertEqual(target.read_text(), "Fictional durable note")
        self.assertIsNone(receipt["committed"])
        self.assertFalse(receipt["retry_safe"])
        self.assertEqual(len(list(target.parent.glob(".matter-write-*.displaced"))), 1)

    def test_tracker_close_waits_until_approved_memory_publication(self):
        module, args, target = self.memory_cli()
        database = self.root / "tracker.sqlite3"
        close_args = tracker_args(database, "close")
        close_token = preview_mutation(database, "close", close_args)["confirm_token"]
        original_verify = module._verify_parent_binding
        closed_before_install = []
        futures = []
        with ThreadPoolExecutor(max_workers=1) as pool:
            def verify_then_start_close(*values):
                original_verify(*values)
                future = pool.submit(commit_mutation, database, "close", close_args, close_token)
                futures.append(future)
                # A real second tracker writer must be blocked during publication.
                from concurrent.futures import TimeoutError
                try:
                    future.result(timeout=0.2)
                    closed_before_install.append(True)
                except TimeoutError:
                    closed_before_install.append(False)
            output = io.StringIO()
            with patch.object(module, "_verify_parent_binding", side_effect=verify_then_start_close), redirect_stdout(output):
                rc = module.main(args)
            self.assertTrue(futures[0].result(timeout=6)["committed"])
        receipt = json.loads(output.getvalue())
        self.assertEqual(closed_before_install, [False])
        self.assertEqual(rc, 0)
        self.assertTrue(receipt["committed"])
        self.assertEqual(target.read_text(), "Fictional durable note")
