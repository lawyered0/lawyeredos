from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from lawyeredos.audience_reconciliation import main, reconcile


class AudienceReconciliationTests(unittest.TestCase):
    def test_verified_ignores_display_names_case_order_and_duplicates(self):
        result = reconcile(
            {
                "id": "fictional-message-1",
                "thread_id": "fictional-thread-1",
                "from": "Fictional Client <CLIENT@example.invalid>",
                "to": (
                    "Counsel One <one@example.invalid>, ONE@example.invalid, "
                    "Counsel Two <two@example.invalid>"
                ),
                "cc": "Observer <observer@example.invalid>",
                "body": "Do not add body-only@example.invalid to the audience.",
                "provider_labels": ["sent"],
            },
            {
                "from": ["client@example.invalid"],
                "to": ["two@example.invalid", "one@example.invalid"],
                "cc": ["observer@example.invalid", "OBSERVER@example.invalid"],
            },
        )
        self.assertEqual(result["state"], "verified")
        self.assertTrue(result["comparison"]["exact_role_match"])
        self.assertEqual(result["authorization"]["state"], "not_established")
        self.assertEqual(result["delivery_state"], "not_established")
        self.assertNotIn("body-only@example.invalid", json.dumps(result))

    def test_mismatch_preserves_roles_and_exact_differences(self):
        result = reconcile(
            {
                "id": "fictional-message-2", "thread_id": "fictional-thread-2",
                "from": "client@example.invalid", "to": "one@example.invalid",
                "cc": "observer@example.invalid",
            },
            {
                "from": "client@example.invalid",
                "to": "one@example.invalid, two@example.invalid", "cc": "",
            },
        )
        self.assertEqual(result["state"], "mismatch")
        self.assertEqual(set(result["comparison"]["mismatches"]), {"to", "cc"})
        self.assertEqual(
            result["comparison"]["mismatches"]["to"]["only_proposed"],
            ["two@example.invalid"],
        )

    def test_absent_or_declared_incomplete_headers_are_unknown(self):
        expected = {
            "from": "client@example.invalid", "to": "lawyer@example.invalid", "cc": "",
        }
        absent = reconcile(
            {"id": "fictional-message-3", "from": "client@example.invalid", "to": "lawyer@example.invalid"},
            expected,
        )
        self.assertEqual(absent["state"], "unknown")
        self.assertIn("cc header is absent", absent["retrieved_audience_evidence"]["limitations"])
        incomplete = reconcile(
            {
                "id": "fictional-message-4", "from": "client@example.invalid",
                "to": "lawyer@example.invalid", "cc": "", "headers_complete": False,
            },
            expected,
        )
        self.assertEqual(incomplete["state"], "unknown")
        self.assertIn(
            "headers_complete is false", incomplete["retrieved_audience_evidence"]["limitations"],
        )
        complete = reconcile(
            {
                "id": "fictional-message-4", "from": "client@example.invalid",
                "to": "lawyer@example.invalid", "cc": "", "headers_complete": True,
            },
            expected,
        )
        self.assertNotEqual(
            incomplete["retrieved_audience_evidence"]["sha256"],
            complete["retrieved_audience_evidence"]["sha256"],
        )

    def test_empty_required_or_unparseable_header_is_ambiguous(self):
        expected = {
            "from": "client@example.invalid", "to": "lawyer@example.invalid", "cc": "",
        }
        for bad_from in ("", "Undisclosed recipients:;", "not-an-address"):
            with self.subTest(bad_from=bad_from):
                result = reconcile(
                    {"from": bad_from, "to": "lawyer@example.invalid", "cc": ""}, expected,
                )
                self.assertEqual(result["state"], "ambiguous")
                self.assertIn("from", result["retrieved_audience_evidence"]["ambiguities"])

    def test_bad_proposal_is_ambiguous_not_verified(self):
        result = reconcile(
            {"from": "client@example.invalid", "to": "lawyer@example.invalid", "cc": ""},
            {"from": "client@example.invalid", "to": "lawyer@example.invalid"},
        )
        self.assertEqual(result["state"], "ambiguous")
        self.assertIn("audience", result["proposed_audience"]["ambiguities"])

    def test_cli_selects_exact_message_from_normalized_bundle(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            bundle = root / "bundle.json"
            expected = root / "expected.json"
            bundle.write_text(json.dumps({
                "schema": "lawyeredos-mail-bundle-v1",
                "source": "fictional-session-tool",
                "account_fingerprint": "a" * 64,
                "query": "fictional exact query",
                "messages": [
                    {"id": "m-1", "from": "other@example.invalid", "to": "lawyer@example.invalid", "cc": ""},
                    {"id": "m-2", "from": "client@example.invalid", "to": "lawyer@example.invalid", "cc": ""},
                ],
            }), encoding="utf-8")
            expected.write_text(json.dumps({
                "from": "CLIENT@example.invalid",
                "to": "Fictional Lawyer <lawyer@example.invalid>", "cc": [],
            }), encoding="utf-8")
            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main([
                    "--message", str(bundle), "--message-id", "m-2",
                    "--expected", str(expected),
                ])
            result = json.loads(output.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertTrue(result["ok"])
        self.assertEqual(result["state"], "verified")
        self.assertEqual(result["retrieved_audience_evidence"]["message_id"], "m-2")
        self.assertEqual(
            result["retrieved_audience_evidence"]["provenance"],
            {
                "input_kind": "normalized_bundle",
                "schema": "lawyeredos-mail-bundle-v1",
                "source": "fictional-session-tool",
                "account_fingerprint": "a" * 64,
                "query": "fictional exact query",
            },
        )

    def test_cli_refuses_standalone_message_id_mismatch(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            message = root / "message.json"
            expected = root / "expected.json"
            message.write_text(json.dumps({
                "id": "m-1", "from": "client@example.invalid",
                "to": "lawyer@example.invalid", "cc": "",
            }), encoding="utf-8")
            expected.write_text(json.dumps({
                "from": "client@example.invalid",
                "to": "lawyer@example.invalid", "cc": "",
            }), encoding="utf-8")
            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main([
                    "--message", str(message), "--message-id", "m-2",
                    "--expected", str(expected),
                ])
            result = json.loads(output.getvalue())
        self.assertEqual(exit_code, 2)
        self.assertFalse(result["ok"])
        self.assertIn("does not match", result["error"])


if __name__ == "__main__":
    unittest.main()
