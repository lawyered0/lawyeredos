from __future__ import annotations

import argparse
import io
import json
import sqlite3
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from lawyeredos.calendar_plan import plan
from lawyeredos.config import load_config
from lawyeredos.matter_context import orient
from lawyeredos.review_bundle import create_manifest, verify_manifest
from lawyeredos.safe_output import commit as commit_output
from lawyeredos.safe_output import preview as preview_output
from lawyeredos.tracker_cli import (
    commit_mutation,
    initialize,
    main as tracker_main,
    preview_mutation,
    read_show,
    verify,
)


def mutation_args(database: Path, command: str, **values):
    defaults = dict(
        database=str(database), file_number="2030-001", dry_run=True,
        confirm_token=None, client="Northstar Bakery Ltd.",
        description="Fictional supply agreement", matter_folder="2030-001-northstar",
        opposing_party="Harbor Paper Co.", other_parties="", primary_email="",
        set_values=[], event_date="2030-01-05", text="Reviewed fictional source.",
    )
    defaults.update(values)
    return argparse.Namespace(**defaults)


class TrackerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.database = self.root / "matters.sqlite3"
        initialize(self.database)

    def tearDown(self):
        self.temp.cleanup()

    def create_matter(self):
        args = mutation_args(self.database, "create")
        preview = preview_mutation(self.database, "create", args)
        return commit_mutation(self.database, "create", args, preview["confirm_token"])

    def test_create_update_timeline_and_history(self):
        created = self.create_matter()
        self.assertTrue(created["committed"])
        args = mutation_args(self.database, "update", set_values=["next_action=Review clause"])
        preview = preview_mutation(self.database, "update", args)
        commit_mutation(self.database, "update", args, preview["confirm_token"])
        timeline = mutation_args(self.database, "timeline")
        preview = preview_mutation(self.database, "timeline", timeline)
        commit_mutation(self.database, "timeline", timeline, preview["confirm_token"])
        matter = read_show(self.database, "2030-001")
        self.assertEqual(matter["next_action"], "Review clause")
        self.assertEqual(len(matter["timeline"]), 1)
        self.assertTrue(verify(self.database)["ok"])

    def test_stale_token_fails(self):
        self.create_matter()
        first = mutation_args(self.database, "timeline", text="First event")
        first_preview = preview_mutation(self.database, "timeline", first)
        second = mutation_args(self.database, "timeline", text="Second event")
        second_preview = preview_mutation(self.database, "timeline", second)
        commit_mutation(self.database, "timeline", second, second_preview["confirm_token"])
        with self.assertRaises(ValueError):
            commit_mutation(self.database, "timeline", first, first_preview["confirm_token"])

    def test_post_commit_readback_failure_is_not_reported_as_retry_safe(self):
        args = mutation_args(self.database, "create")
        preview = preview_mutation(self.database, "create", args)
        output = io.StringIO()
        with patch(
            "lawyeredos.tracker_cli.read_show",
            side_effect=sqlite3.OperationalError("fictional read failure"),
        ):
            with redirect_stdout(output):
                exit_code = tracker_main([
                    "create", "--database", str(self.database),
                    "--file-number", args.file_number,
                    "--client", args.client,
                    "--description", args.description,
                    "--matter-folder", args.matter_folder,
                    "--opposing-party", args.opposing_party,
                    "--other-parties", args.other_parties,
                    "--primary-email", args.primary_email,
                    "--confirm-token", preview["confirm_token"],
                ])

        result = json.loads(output.getvalue())
        self.assertEqual(exit_code, 3)
        self.assertFalse(result["ok"])
        self.assertTrue(result["committed"])
        self.assertEqual(result["commit_state"], "committed")
        self.assertEqual(result["verification_state"], "readback_failed")
        self.assertEqual(result["audit_verification_state"], "not_performed")
        self.assertIsInstance(result["audit_id"], int)
        self.assertFalse(result["retry_safe"])
        self.assertFalse(result["recovery"]["retry_mutation"])
        self.assertEqual(result["commit_evidence"]["revision"], 1)
        self.assertEqual(read_show(self.database, "2030-001")["client"], args.client)
        with self.assertRaisesRegex(ValueError, "already exists"):
            commit_mutation(self.database, "create", args, preview["confirm_token"])
        with sqlite3.connect(self.database) as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM audit").fetchone()[0], 1)

    def test_successful_commit_only_claims_matter_readback_verification(self):
        result = self.create_matter()
        self.assertEqual(result["verification_state"], "readback_verified")
        self.assertEqual(result["audit_verification_state"], "not_performed")
        self.assertFalse(result["retry_safe"])
        with sqlite3.connect(self.database) as connection:
            audit = connection.execute(
                "SELECT id, revision, action, file_number FROM audit WHERE id=?",
                (result["audit_id"],),
            ).fetchone()
        self.assertEqual(audit, (result["audit_id"], 1, "create", "2030-001"))

    def test_pre_commit_failure_has_canonical_not_committed_receipt(self):
        args = mutation_args(self.database, "create")
        output = io.StringIO()
        with redirect_stdout(output):
            exit_code = tracker_main([
                "create", "--database", str(self.database),
                "--file-number", args.file_number,
                "--client", args.client,
                "--description", args.description,
                "--matter-folder", args.matter_folder,
                "--confirm-token", "wrong-token",
            ])
        result = json.loads(output.getvalue())
        self.assertEqual(exit_code, 2)
        self.assertFalse(result["committed"])
        self.assertEqual(result["commit_state"], "not_committed")
        self.assertIsNone(result["audit_id"])
        self.assertFalse(result["retry_safe"])
        with sqlite3.connect(self.database) as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM audit").fetchone()[0], 0)

    def test_commit_call_error_is_unknown_whether_before_or_after_durability(self):
        for durable in (False, True):
            with self.subTest(durable=durable):
                database = self.root / f"commit-{durable}.sqlite3"
                initialize(database)
                args = mutation_args(database, "create")
                preview = preview_mutation(database, "create", args)

                def ambiguous_commit(connection):
                    if durable:
                        connection.execute("COMMIT")
                    raise sqlite3.OperationalError("fictional COMMIT transport failure")

                with patch("lawyeredos.tracker_cli._commit_transaction", side_effect=ambiguous_commit):
                    result = commit_mutation(database, "create", args, preview["confirm_token"])

                self.assertFalse(result["ok"])
                self.assertIsNone(result["committed"])
                self.assertEqual(result["commit_state"], "outcome_unknown")
                self.assertIsInstance(result["audit_id"], int)
                self.assertFalse(result["retry_safe"])
                self.assertEqual(
                    result["recovery"]["required_inspection"],
                    ["show", "history", "verify"],
                )
                with sqlite3.connect(database) as connection:
                    audit_count = connection.execute("SELECT COUNT(*) FROM audit").fetchone()[0]
                self.assertEqual(audit_count, int(durable))

    def test_conflict_screening_searches_party_fields_and_closed_matters(self):
        args = mutation_args(
            self.database,
            "create",
            other_parties="Café Guarantor Inc.",
            primary_email="fictional.contact@example.invalid",
        )
        preview = preview_mutation(self.database, "create", args)
        commit_mutation(self.database, "create", args, preview["confirm_token"])
        close = mutation_args(self.database, "close")
        preview = preview_mutation(self.database, "close", close)
        commit_mutation(self.database, "close", close, preview["confirm_token"])

        for query in ("northstar", "harbor paper", "café guarantor", "example.invalid"):
            output = io.StringIO()
            with redirect_stdout(output):
                result = tracker_main([
                    "find", "--database", str(self.database),
                    "--query", query, "--status", "all",
                ])
            self.assertEqual(result, 0)
            payload = json.loads(output.getvalue())
            self.assertEqual(payload["query"], query)
            self.assertEqual([row["file_number"] for row in payload["matters"]], ["2030-001"])

        output = io.StringIO()
        with redirect_stdout(output):
            tracker_main([
                "find", "--database", str(self.database),
                "--query", "%", "--status", "all",
            ])
        self.assertEqual(json.loads(output.getvalue())["matters"], [])


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def config(self) -> Path:
        workspace = self.root / "workspace"
        scratch = self.root / "scratch"
        matter = workspace / "2030-001-northstar"
        matter.mkdir(parents=True)
        scratch.mkdir()
        (matter / "_matter-brief.md").write_text("# Fictional matter\n", encoding="utf-8")
        database = workspace / "matters.sqlite3"
        initialize(database)
        with sqlite3.connect(database) as connection:
            connection.execute(
                """INSERT INTO matters(file_number, client, description, matter_folder,
                status, created_at, updated_at) VALUES
                ('2030-001', 'Northstar Bakery Ltd.', 'Fictional agreement',
                '2030-001-northstar', 'open', '2030-01-01', '2030-01-01')"""
            )
        template = self.root / "template.docx"
        template.write_bytes(b"fixture")
        config = self.root / "config.toml"
        config.write_text(f'''schema_version = 1
[workspace]
root = "{workspace}"
scratch = "{scratch}"
timezone = "UTC"
[tracker]
database = "{database}"
[documents]
template = "{template}"
author = "Authorized reviewer"
[jurisdiction]
profile = "none"
[integrations]
mail_adapter = "unavailable"
calendar_adapter = "unavailable"
practice_manager_adapter = "unavailable"
[calendar]
calendar_id = ""
[review]
external_ai = false
''', encoding="utf-8")
        return config

    def test_orientation_is_read_only(self):
        result = orient(self.config(), "2030-001", 10)
        self.assertTrue(result["ok"])
        self.assertEqual(result["status"], "ok_read_only")
        self.assertTrue(result["brief"]["present"])

    def test_orientation_name_resolution_is_unicode_case_insensitive(self):
        config = self.config()
        database = self.root / "workspace" / "matters.sqlite3"
        with sqlite3.connect(database) as connection:
            connection.execute(
                "UPDATE matters SET client='Étoile Foods Ltd.' WHERE file_number='2030-001'"
            )
        result = orient(config, "étoile", 10)
        self.assertTrue(result["ok"])
        self.assertEqual(result["matter"]["file_number"], "2030-001")

    def test_safe_output_refuses_overwrite_and_escape(self):
        matter = self.root / "matter"
        matter.mkdir()
        content = self.root / "draft.txt"
        content.write_text("fictional draft", encoding="utf-8")
        args = argparse.Namespace(
            root=str(self.root), matter_folder="matter", relative_path="draft-v01.txt",
            content_file=str(content), confirm_token=None,
        )
        preview = preview_output(args)
        args.confirm_token = preview["confirm_token"]
        result = commit_output(args)
        self.assertTrue(result["committed"])
        with self.assertRaises(ValueError):
            preview_output(args)
        escaped = argparse.Namespace(
            root=str(self.root), matter_folder="matter", relative_path="../escape.txt",
            content_file=str(content), confirm_token=None,
        )
        with self.assertRaises(ValueError):
            preview_output(escaped)

    def test_matter_and_output_paths_refuse_internal_symlink_aliases(self):
        config = self.config()
        workspace = self.root / "workspace"
        registered = workspace / "2030-001-northstar"
        physical = workspace / "physical-matter-folder"
        registered.rename(physical)
        registered.symlink_to(physical, target_is_directory=True)
        result = orient(config, "2030-001", 10)
        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "folder_unavailable")

        content = self.root / "content.txt"
        content.write_text("fictional", encoding="utf-8")
        alias_args = argparse.Namespace(
            root=str(workspace), matter_folder="2030-001-northstar",
            relative_path="draft.txt", content_file=str(content), confirm_token=None,
        )
        with self.assertRaisesRegex(ValueError, "symlink"):
            preview_output(alias_args)

        matter = workspace / "real-matter"
        matter.mkdir()
        outside_subfolder = workspace / "other-matter-output"
        outside_subfolder.mkdir()
        (matter / "correspondence").symlink_to(outside_subfolder, target_is_directory=True)
        nested_args = argparse.Namespace(
            root=str(workspace), matter_folder="real-matter",
            relative_path="correspondence/draft.txt", content_file=str(content),
            confirm_token=None,
        )
        with self.assertRaisesRegex(ValueError, "symlink"):
            preview_output(nested_args)

    def test_calendar_plan(self):
        desired = [{"sync_key":"x","date":"2030-01-02","title":"X","timezone":"UTC"}]
        existing = [{"sync_key":"x","date":"2030-01-01","title":"X","timezone":"UTC"}]
        result = plan(desired, existing)
        self.assertEqual(len(result["update"]), 1)
        self.assertTrue(result["read_only"])

    def test_review_manifest_detects_change(self):
        source = self.root / "source.txt"
        deliverable = self.root / "draft.txt"
        source.write_text("source", encoding="utf-8")
        deliverable.write_text("draft", encoding="utf-8")
        manifest = create_manifest(deliverable, [source], self.root)
        manifest_path = self.root / "manifest.json"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        self.assertTrue(verify_manifest(manifest_path)["unchanged"])
        source.write_text("changed source", encoding="utf-8")
        source_result = verify_manifest(manifest_path)
        self.assertFalse(source_result["unchanged"])
        self.assertFalse(source_result["sources_unchanged"])
        source.write_text("source", encoding="utf-8")
        deliverable.write_text("changed", encoding="utf-8")
        deliverable_result = verify_manifest(manifest_path)
        self.assertFalse(deliverable_result["unchanged"])
        self.assertFalse(deliverable_result["deliverable_unchanged"])

    def test_config_rejects_external_ai(self):
        config = self.config()
        text = config.read_text(encoding="utf-8").replace("external_ai = false", "external_ai = true")
        config.write_text(text, encoding="utf-8")
        with self.assertRaises(ValueError):
            load_config(config)

    def test_config_rejects_unknown_adapter(self):
        config = self.config()
        text = config.read_text(encoding="utf-8").replace(
            'mail_adapter = "unavailable"', 'mail_adapter = "unknown"'
        )
        config.write_text(text, encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "unsupported mail_adapter"):
            load_config(config)


if __name__ == "__main__":
    unittest.main()
