from __future__ import annotations

import base64
import json
import sqlite3
import unittest
from datetime import UTC, datetime
from email.message import EmailMessage
from unittest.mock import patch

from lawyeredos.integrations import GmailReadonlyAdapter
from lawyeredos.mail_intake import plan, process_bundle
import test_mail_intake as mail_fixtures


class IntakeRegressionTests(unittest.TestCase):
    def setUp(self):
        self.fixture = mail_fixtures.MailIntakeTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)

    def test_opening_date_bound_includes_untracked_mail_older_than_30_days(self):
        with patch('lawyeredos.mail_intake.datetime') as clock:
            clock.now.return_value = datetime(2032, 6, 1, tzinfo=UTC)
            clock.fromisoformat.side_effect = datetime.fromisoformat
            planned = plan(self.fixture.config, '2032-001')
        self.assertEqual(planned['time_bound'], 'after:2031/12/31')
        self.assertNotIn('newer_than:30d', planned['query'])

    def sibling(self):
        with sqlite3.connect(self.fixture.database) as connection:
            connection.execute(
                "INSERT INTO matters(file_number, client, description, matter_folder, status, "
                "opposing_party, primary_email, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, 'open', ?, ?, ?, ?)",
                ('2032-0010', 'Northstar Bakery Ltd.', 'Fictional packaging dispute',
                 '2032-0010-other', 'Harbor Paper Co.', 'client@example.invalid',
                 '2032-01-01', '2032-01-01'),
            )

    def held(self, message):
        planned = plan(self.fixture.config, '2032-001')
        result = process_bundle(self.fixture.config, '2032-001', self.fixture.bundle(planned, [message]))
        self.assertEqual(result['messages'][0]['status'], 'held_ambiguous')
        self.assertEqual(result['thread_states'], [])
        self.assertEqual(list((self.fixture.matter / 'email-attachments').iterdir()), [])

    def test_sibling_file_number_prefix_is_not_an_exact_matter_match(self):
        self.sibling()
        message = self.fixture.message(attachment=self.fixture.attachment())
        message.update(subject='2032-0010', body='Documents for file 2032-0010.', snippet='Other file')
        self.held(message)

    def test_shared_client_and_opponent_cannot_disambiguate_sibling_matters(self):
        self.sibling()
        message = self.fixture.message(attachment=self.fixture.attachment())
        message.update(subject='Harbor Paper Co.', body='Northstar Bakery Ltd. update concerning Harbor Paper Co.')
        self.held(message)


    def test_invalid_opening_date_reports_limited_history(self):
        with sqlite3.connect(self.fixture.database) as connection:
            connection.execute("UPDATE matters SET created_at='not-a-date' WHERE file_number='2032-001'")
        planned = plan(self.fixture.config, '2032-001')
        self.assertEqual(planned['time_bound'], 'newer_than:30d')
        self.assertIn('Historical coverage is unverified', planned['history_bound_limitation'])
        result = process_bundle(self.fixture.config, '2032-001', self.fixture.bundle(planned, []))
        self.assertEqual(result['history_bound_limitation'], planned['history_bound_limitation'])

    def test_exact_file_number_disambiguates_shared_parties(self):
        self.sibling()
        message = self.fixture.message()
        message['body'] = '2032-001 Northstar Bakery Ltd. update concerning Harbor Paper Co.'
        planned = plan(self.fixture.config, '2032-001')
        result = process_bundle(self.fixture.config, '2032-001', self.fixture.bundle(planned, [message]))
        self.assertEqual(result['messages'][0]['status'], 'partial')
        self.assertIn('body_review', result['messages'][0])

    def test_tracked_thread_does_not_override_explicit_other_file_number(self):
        initial = plan(self.fixture.config, '2032-001')
        process_bundle(self.fixture.config, '2032-001', self.fixture.bundle(initial, [self.fixture.message()]))
        self.fixture.acknowledge_all('2032-001')
        process_bundle(self.fixture.config, '2032-001', self.fixture.bundle(initial, [self.fixture.message()]))
        self.sibling()
        planned = plan(self.fixture.config, '2032-001')
        other = self.fixture.message('m2', attachment=self.fixture.attachment())
        other.update(subject='2032-0010', body='Documents for file 2032-0010.', snippet='Other file')
        result = process_bundle(self.fixture.config, '2032-001', self.fixture.bundle(planned, [other]))
        self.assertEqual(result['messages'][0]['status'], 'held_ambiguous')
        self.assertEqual(list((self.fixture.matter / 'email-attachments').iterdir()), [])



class MimeRegressionTests(unittest.TestCase):
    def test_unnamed_calendar_mime_leaf_is_preserved_by_imap(self):
        message = EmailMessage()
        message.set_content('Fictional covering note.')
        message.add_alternative('BEGIN:VCALENDAR\nEND:VCALENDAR\n', subtype='calendar')
        adapter, _client = mail_fixtures.GmailImapTransportTests().adapter(message.as_bytes())
        result = adapter.intake('"2032-001" newer_than:30d -in:spam -in:trash')
        attachments = result['messages'][0]['attachments']
        self.assertEqual(len(attachments), 1)
        self.assertEqual(attachments[0]['mime_type'], 'text/calendar')
        self.assertIn(b'BEGIN:VCALENDAR', base64.b64decode(attachments[0]['content_base64']))

    def test_unknown_filename_charset_has_safe_fallback(self):
        # The outer valid encoded word exposes a literal encoded filename to
        # the helper after policy.default's first decoding pass.
        nested = base64.b64encode(b'=?x-fictional?b?ZXZpZGVuY2UudHh0?=')
        raw = (
            b'Content-Type: multipart/mixed; boundary=fictional\n\n'
            b'--fictional\nContent-Type: text/plain\n\nCover note.\n'
            b'--fictional\nContent-Type: text/plain\n'
            b'Content-Disposition: attachment; filename="=?utf-8?b?'
            + nested + b'?="\n\nFictional evidence.\n--fictional--\n'
        )
        adapter, _client = mail_fixtures.GmailImapTransportTests().adapter(raw)
        result = adapter.intake('"2032-001" newer_than:30d -in:spam -in:trash')
        self.assertEqual(result['messages'][0]['attachments'][0]['filename'], 'evidence.txt')

    def test_unknown_body_charset_does_not_abort_imap_message(self):
        raw = b'Content-Type: text/plain; charset=x-fictional\n\nFictional note.'
        adapter, _client = mail_fixtures.GmailImapTransportTests().adapter(raw)
        result = adapter.intake('"2032-001" newer_than:30d -in:spam -in:trash')
        self.assertTrue(result['coverage']['complete'])
        self.assertEqual(result['messages'][0]['body'], 'Fictional note.')

    def test_unnamed_calendar_inline_data_is_preserved_by_rest(self):
        calendar = b'BEGIN:VCALENDAR\nEND:VCALENDAR\n'
        encoded = base64.urlsafe_b64encode(calendar).decode().rstrip('=')
        def transport(method, url, headers, request_body):
            if url.endswith('/profile'):
                return 200, b'{"emailAddress":"fictional@example.invalid"}'
            if 'format=full' in url:
                return 200, json.dumps({
                    'id': 'm1', 'threadId': 't1', 'internalDate': '1950000000000',
                    'payload': {'headers': [], 'mimeType': 'text/calendar', 'body': {'data': encoded}},
                }).encode()
            return 200, b'{"messages":[{"id":"m1"}]}'
        result = GmailReadonlyAdapter('fictional-token', transport).intake('Northstar newer_than:30d')
        attachments = result['messages'][0]['attachments']
        self.assertEqual(len(attachments), 1)
        self.assertEqual(base64.b64decode(attachments[0]['content_base64']), calendar)

    def test_opening_date_bound_is_accepted_by_imap_adapter(self):
        message = EmailMessage()
        message.set_content('Fictional note.')
        adapter, _client = mail_fixtures.GmailImapTransportTests().adapter(message.as_bytes())
        result = adapter.intake('"2032-001" after:2031/12/31 -in:spam -in:trash')
        self.assertTrue(result['coverage']['complete'])
