from __future__ import annotations

import base64
import io
import json
import sqlite3
import tempfile
import unittest
import zipfile
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from lawyeredos.integrations import GmailReadonlyAdapter
from lawyeredos.mail_intake import main, plan, process_bundle
from lawyeredos.tracker_cli import initialize


class MailIntakeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.workspace = self.root / "workspace"
        self.matter = self.workspace / "2032-001-northstar"
        self.matter.mkdir(parents=True)
        (self.matter / "_matter-brief.md").write_text("# Fictional matter\n", encoding="utf-8")
        self.database = self.workspace / "matters.sqlite3"
        initialize(self.database)
        with sqlite3.connect(self.database) as connection:
            connection.execute(
                """INSERT INTO matters(file_number, client, description, matter_folder,
                status, opposing_party, primary_email, created_at, updated_at)
                VALUES (?, ?, ?, ?, 'open', ?, ?, ?, ?)""",
                (
                    "2032-001", "Northstar Bakery Ltd.", "Fictional supply dispute",
                    "2032-001-northstar", "Harbor Paper Co.",
                    "client@example.invalid", "2032-01-01", "2032-01-01",
                ),
            )
        self.template = self.root / "template.docx"
        self.template.write_bytes(b"fixture")
        self.config = self.root / "config.toml"
        self.write_config("fixture-json")

    def tearDown(self):
        self.temp.cleanup()

    def write_config(self, adapter: str) -> None:
        self.config.write_text(f'''schema_version = 1
[workspace]
root = "{self.workspace}"
scratch = "{self.workspace / '.lawyeredos' / 'scratch'}"
timezone = "UTC"
[tracker]
database = "{self.database}"
[documents]
template = "{self.template}"
author = "Authorized reviewer"
[jurisdiction]
profile = "none"
[integrations]
mail_adapter = "{adapter}"
calendar_adapter = "unavailable"
practice_manager_adapter = "unavailable"
[calendar]
calendar_id = ""
[review]
external_ai = false
''', encoding="utf-8")

    def message(self, message_id: str = "m1", *, attachment: dict | None = None) -> dict:
        return {
            "id": message_id, "thread_id": "thread-1", "received_at": "2032-02-01T12:00:00+00:00",
            "from": "client@example.invalid", "to": "lawyer@example.invalid", "cc": "",
            "subject": "Fictional supply dispute", "snippet": "Please review the attached note.",
            "body": "Northstar Bakery asks counsel to review the attached fictional note.",
            "body_complete": True, "attachments": [] if attachment is None else [attachment],
        }

    def attachment(self, content: bytes = b"Fictional attachment text.\n", **changes) -> dict:
        value = {
            "id": "a1", "filename": "../client-note.txt", "mime_type": "text/plain",
            "size": len(content), "content_base64": base64.b64encode(content).decode("ascii"),
        }
        value.update(changes)
        return value

    def bundle(self, planned: dict, messages: list[dict], *, complete: bool = True) -> dict:
        return {
            "schema": "lawyeredos-mail-bundle-v1", "source": "fixture",
            "query": planned["query"], "messages": messages,
            "coverage": {"complete": complete, "completed_at": "2032-02-01T13:00:00+00:00"},
        }

    def test_complete_repeat_and_new_message_flow(self):
        first_plan = plan(self.config, "Northstar")
        result = process_bundle(
            self.config, "Northstar",
            self.bundle(first_plan, [self.message(attachment=self.attachment())]),
        )
        self.assertEqual(result["status"], "complete")
        self.assertTrue(result["checkpoint_advanced"])
        reviewed = result["messages"][0]
        self.assertEqual(reviewed["status"], "reviewed")
        self.assertTrue(reviewed["untrusted_evidence"])
        saved = Path(reviewed["attachments"][0]["saved_path"])
        self.assertEqual(saved.name, "client-note.txt")
        self.assertEqual(saved.read_bytes(), b"Fictional attachment text.\n")

        second_plan = plan(self.config, "2032-001")
        self.assertIn("newer_than:30d", second_plan["query"])
        repeated = process_bundle(
            self.config, "2032-001",
            self.bundle(second_plan, [self.message(attachment=self.attachment())]),
        )
        self.assertEqual(repeated["messages"], [{"message_id": "m1", "status": "already_reviewed"}])
        self.assertEqual(len(list((self.matter / "email-attachments").iterdir())), 1)

        third_plan = plan(self.config, "Northstar")
        new_message = self.message("m2")
        new_message["thread_id"] = "thread-2"
        new_message["body"] = "A new Northstar update with no attachment."
        newest = process_bundle(self.config, "Northstar", self.bundle(third_plan, [new_message]))
        self.assertEqual(newest["messages"][0]["status"], "reviewed")

    def test_partial_attachment_retry_does_not_advance_checkpoint(self):
        first_plan = plan(self.config, "Northstar")
        missing = self.attachment()
        missing.pop("content_base64")
        partial = process_bundle(
            self.config, "Northstar", self.bundle(first_plan, [self.message(attachment=missing)]),
        )
        self.assertEqual(partial["status"], "partial")
        self.assertFalse(partial["checkpoint_advanced"])
        self.assertEqual(partial["messages"][0]["attachments"][0]["status"], "deferred")
        self.assertIsNone(plan(self.config, "Northstar")["checkpoint"])

        retry_plan = plan(self.config, "Northstar")
        retried = process_bundle(
            self.config, "Northstar",
            self.bundle(retry_plan, [self.message(attachment=self.attachment())]),
        )
        self.assertEqual(retried["status"], "complete")
        self.assertIsNotNone(plan(self.config, "Northstar")["checkpoint"])

    def test_docx_is_reviewed_and_existing_different_file_is_not_overwritten(self):
        from docx import Document

        buffer = io.BytesIO()
        document = Document()
        document.add_paragraph("Northstar fictional document evidence.")
        document.save(buffer)
        existing = self.matter / "email-attachments"
        existing.mkdir()
        (existing / "client-note.docx").write_bytes(b"pre-existing user file")

        planned = plan(self.config, "Northstar")
        attachment = self.attachment(
            buffer.getvalue(), filename="client-note.docx",
            mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
        result = process_bundle(
            self.config, "Northstar", self.bundle(planned, [self.message(attachment=attachment)]),
        )
        reviewed = result["messages"][0]["attachments"][0]
        self.assertEqual(reviewed["status"], "reviewed")
        self.assertIn("Northstar fictional document evidence", reviewed["review"]["text"])
        self.assertNotEqual(Path(reviewed["saved_path"]).name, "client-note.docx")
        self.assertEqual((existing / "client-note.docx").read_bytes(), b"pre-existing user file")

    def test_incomplete_coverage_holds_checkpoint_but_dedupes_review(self):
        first_plan = plan(self.config, "Northstar")
        partial = process_bundle(
            self.config, "Northstar", self.bundle(first_plan, [self.message()], complete=False),
        )
        self.assertEqual(partial["messages"][0]["status"], "reviewed")
        self.assertFalse(partial["checkpoint_advanced"])
        self.assertIsNone(plan(self.config, "Northstar")["checkpoint"])

        retry_plan = plan(self.config, "Northstar")
        completed = process_bundle(
            self.config, "Northstar", self.bundle(retry_plan, [self.message()], complete=True),
        )
        self.assertEqual(completed["messages"][0]["status"], "already_reviewed")
        self.assertTrue(completed["checkpoint_advanced"])

    def test_incomplete_body_and_missing_attachment_bytes_remain_retryable(self):
        planned = plan(self.config, "Northstar")
        message = self.message(attachment=self.attachment())
        message["body_complete"] = False
        message["attachments"][0].pop("content_base64")
        result = process_bundle(self.config, "Northstar", self.bundle(planned, [message]))
        self.assertEqual(result["status"], "partial")
        self.assertIn("body retrieval was incomplete", result["messages"][0]["problems"][0])
        self.assertEqual(result["messages"][0]["attachments"][0]["status"], "deferred")
        self.assertIsNone(plan(self.config, "Northstar")["checkpoint"])

    def test_long_body_and_attachment_review_windows_hold_checkpoint(self):
        planned = plan(self.config, "Northstar")
        message = self.message(attachment=self.attachment(b"x" * 12_001))
        message["body"] = "Fictional supply dispute " + ("y" * 12_001)
        result = process_bundle(self.config, "Northstar", self.bundle(planned, [message]))
        self.assertEqual(result["status"], "partial")
        self.assertFalse(result["checkpoint_advanced"])
        self.assertIn("review window", " ".join(result["messages"][0]["problems"]))
        self.assertEqual(
            result["messages"][0]["attachments"][0]["status"], "review_truncated"
        )

    def test_query_result_without_exact_matter_pair_is_held(self):
        planned = plan(self.config, "Northstar")
        message = self.message()
        message["from"] = "unrelated@example.invalid"
        message["subject"] = "Northstar Bakery Ltd."
        message["body"] = "A party-only match without a matter discriminator."
        result = process_bundle(self.config, "Northstar", self.bundle(planned, [message]))
        self.assertEqual(result["messages"][0]["status"], "held_ambiguous")
        self.assertFalse(result["checkpoint_advanced"])

    def test_bundle_source_query_and_timestamp_are_verified(self):
        planned = plan(self.config, "Northstar")
        wrong_source = self.bundle(planned, [self.message()])
        wrong_source["source"] = "codex-session-tool"
        with self.assertRaisesRegex(ValueError, "source"):
            process_bundle(self.config, "Northstar", wrong_source)

        wrong_query = self.bundle(planned, [self.message()])
        wrong_query["query"] = "newer_than:999d"
        with self.assertRaisesRegex(ValueError, "query"):
            process_bundle(self.config, "Northstar", wrong_query)

        bad_timestamp = self.message()
        bad_timestamp["received_at"] = "2032-02-01 12:00:00"
        with self.assertRaisesRegex(ValueError, "UTC offset"):
            process_bundle(self.config, "Northstar", self.bundle(planned, [bad_timestamp]))

    def test_checkpoints_are_scoped_to_the_configured_mail_source(self):
        fixture_plan = plan(self.config, "Northstar")
        result = process_bundle(
            self.config, "Northstar", self.bundle(fixture_plan, [self.message()]),
        )
        self.assertTrue(result["checkpoint_advanced"])

        self.write_config("codex-session-tools")
        codex_plan = plan(self.config, "Northstar")
        self.assertEqual(codex_plan["source"], "codex-session-tool")
        self.assertIsNone(codex_plan["checkpoint"])
        self.assertIn("newer_than:30d", codex_plan["query"])

        self.write_config("unavailable")
        unavailable_plan = plan(self.config, "Northstar")
        self.assertIsNone(unavailable_plan["source"])
        self.assertIsNone(unavailable_plan["checkpoint"])

    def test_unsafe_oversized_and_executable_attachments_are_deferred(self):
        planned = plan(self.config, "Northstar")
        executable = self.attachment(
            b"MZfake", filename="invoice.exe", mime_type="application/octet-stream",
        )
        result = process_bundle(
            self.config, "Northstar", self.bundle(planned, [self.message(attachment=executable)]),
        )
        self.assertEqual(result["status"], "partial")
        self.assertIn("blocked", result["messages"][0]["attachments"][0]["error"])

        with patch("lawyeredos.mail_intake.MAX_ATTACHMENT_BYTES", 3):
            planned = plan(self.config, "Northstar")
            oversized = process_bundle(
                self.config, "Northstar",
                self.bundle(planned, [self.message(attachment=self.attachment(b"four"))]),
            )
        self.assertEqual(oversized["status"], "partial")
        self.assertIn("exceeds", oversized["messages"][0]["attachments"][0]["error"])

        archive = io.BytesIO()
        with zipfile.ZipFile(archive, "w") as output:
            output.writestr("word/document.xml", "<document/>")
            output.writestr("word/embeddings/oleObject1.bin", b"payload")
        planned = plan(self.config, "Northstar")
        active_docx = self.attachment(
            archive.getvalue(), filename="active.docx",
            mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
        active = process_bundle(
            self.config, "Northstar", self.bundle(planned, [self.message(attachment=active_docx)]),
        )
        self.assertIn("active content", active["messages"][0]["attachments"][0]["error"])

    def test_managed_private_session_bundle_is_deleted_after_processing(self):
        planned = plan(self.config, "Northstar")
        folder = self.workspace / ".lawyeredos" / "scratch" / "mail-intake-session"
        folder.mkdir(parents=True)
        folder.chmod(0o700)
        bundle_path = folder / "one-run.json"
        bundle_path.write_text(json.dumps(self.bundle(planned, [self.message()])), encoding="utf-8")
        bundle_path.chmod(0o600)
        output = io.StringIO()
        with redirect_stdout(output):
            status = main([
                "process", "--config", str(self.config), "--identifier", "Northstar",
                "--bundle", str(bundle_path), "--delete-bundle",
            ])
        self.assertEqual(status, 0)
        self.assertFalse(bundle_path.exists())

    def test_symlink_destination_and_ambiguous_matter_fail_closed(self):
        outside = self.root / "outside"
        outside.mkdir()
        (self.matter / "email-attachments").symlink_to(outside, target_is_directory=True)
        planned = plan(self.config, "2032-001")
        with self.assertRaisesRegex(ValueError, "symlink|unsafe"):
            process_bundle(self.config, "2032-001", self.bundle(planned, [self.message()]))
        (self.matter / "email-attachments").unlink()

        second = self.workspace / "2032-002-northstar"
        second.mkdir()
        with sqlite3.connect(self.database) as connection:
            connection.execute(
                """INSERT INTO matters(file_number, client, description, matter_folder,
                status, created_at, updated_at) VALUES
                ('2032-002', 'Northstar Holdings Ltd.', 'Other fictional matter',
                '2032-002-northstar', 'open', '2032-01-01', '2032-01-01')"""
            )
        ambiguous = plan(self.config, "Northstar")
        self.assertFalse(ambiguous["ok"])
        self.assertEqual(ambiguous["status"], "ambiguous")

    def test_unavailable_adapter_reports_without_creating_state(self):
        self.write_config("unavailable")
        result = plan(self.config, "Northstar")
        self.assertEqual(result["status"], "mail_unavailable")
        self.assertEqual(result["route"], "unavailable")
        self.assertFalse((self.workspace / ".lawyeredos" / "data" / "mail-intake.sqlite3").exists())


class GmailIntakeTransportTests(unittest.TestCase):
    def test_full_message_and_attachment_use_read_only_fake_transport(self):
        calls = []
        body = base64.urlsafe_b64encode(b"Northstar body").decode("ascii").rstrip("=")
        attachment = base64.urlsafe_b64encode(b"fictional text").decode("ascii").rstrip("=")

        def transport(method, url, headers, request_body):
            calls.append((method, url, request_body))
            if url.endswith("/profile"):
                return 200, b'{"emailAddress":"fictional@example.invalid"}'
            if "/attachments/" in url:
                return 200, json.dumps({"data": attachment}).encode()
            if "format=full" in url:
                return 200, json.dumps({
                    "id": "m1", "threadId": "t1", "internalDate": "1950000000000",
                    "snippet": "Northstar", "payload": {
                        "headers": [
                            {"name": "From", "value": "client@example.invalid"},
                            {"name": "Subject", "value": "Northstar update"},
                        ],
                        "parts": [
                            {"mimeType": "text/plain", "body": {"data": body}},
                            {"mimeType": "text/plain", "filename": "note.txt",
                             "body": {"attachmentId": "a1", "size": 14}},
                        ],
                    },
                }).encode()
            return 200, b'{"messages":[{"id":"m1"}]}'

        result = GmailReadonlyAdapter("fake-token", transport).intake("Northstar newer_than:30d", 5)
        self.assertTrue(result["coverage"]["complete"])
        self.assertEqual(result["messages"][0]["body"], "Northstar body")
        self.assertEqual(
            base64.b64decode(result["messages"][0]["attachments"][0]["content_base64"]),
            b"fictional text",
        )
        self.assertTrue(all(method == "GET" and request_body is None for method, _url, request_body in calls))

    def test_oversized_body_is_marked_incomplete(self):
        body = base64.urlsafe_b64encode(b"Northstar body").decode("ascii").rstrip("=")

        def transport(method, url, headers, request_body):
            if url.endswith("/profile"):
                return 200, b'{"emailAddress":"fictional@example.invalid"}'
            if "format=full" in url:
                return 200, json.dumps({
                    "id": "m1", "threadId": "t1", "internalDate": "1950000000000",
                    "payload": {"headers": [], "mimeType": "text/plain", "body": {"data": body}},
                }).encode()
            return 200, b'{"messages":[{"id":"m1"}]}'

        with patch("lawyeredos.integrations.MAX_MAIL_BODY_CHARS", 5):
            result = GmailReadonlyAdapter("fake-token", transport).intake("Northstar", 5)
        self.assertEqual(result["messages"][0]["body"], "North")
        self.assertFalse(result["messages"][0]["body_complete"])

    def test_attachment_backed_body_inline_image_and_aggregate_limit_are_explicit(self):
        encoded_body = base64.urlsafe_b64encode(b"Northstar fetched body").decode("ascii").rstrip("=")
        encoded_image = base64.urlsafe_b64encode(b"image-bytes").decode("ascii").rstrip("=")
        calls = []

        def transport(method, url, headers, request_body):
            calls.append(url)
            if url.endswith("/profile"):
                return 200, b'{"emailAddress":"fictional@example.invalid"}'
            if "/attachments/body-1" in url:
                return 200, json.dumps({"data": encoded_body}).encode()
            if "/attachments/image-1" in url:
                return 200, json.dumps({"data": encoded_image}).encode()
            if "format=full" in url:
                return 200, json.dumps({
                    "id": "m1", "threadId": "t1", "internalDate": "1950000000000",
                    "payload": {"headers": [], "parts": [
                        {"mimeType": "text/plain", "body": {"attachmentId": "body-1", "size": 22}},
                        {"mimeType": "image/png", "filename": "signature.png",
                         "headers": [{"name": "Content-Disposition", "value": "inline"}],
                         "body": {"attachmentId": "image-1", "size": 11}},
                    ]},
                }).encode()
            return 200, b'{"messages":[{"id":"m1"}]}'

        with patch("lawyeredos.integrations.MAX_MAIL_RUN_ATTACHMENT_BYTES", 5):
            result = GmailReadonlyAdapter("fake-token", transport).intake("Northstar", 5)
        message = result["messages"][0]
        self.assertEqual(message["body"], "Northstar fetched body")
        self.assertTrue(message["body_complete"])
        self.assertEqual(message["attachments"][0]["filename"], "signature.png")
        self.assertTrue(message["attachments"][0]["inline"])
        self.assertIn("bounded", message["attachments"][0]["retrieval_error"])
        self.assertFalse(any("/attachments/image-1" in url for url in calls))


if __name__ == "__main__":
    unittest.main()
