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
        self.assertNotIn('competing_profiles', planned['match_profile'])
        self.assertNotIn('2032-0010', json.dumps(planned))
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



    def test_recent_matter_query_remains_stable_across_utc_midnight(self):
        with sqlite3.connect(self.fixture.database) as connection:
            connection.execute("UPDATE matters SET created_at='2032-06-01' WHERE file_number='2032-001'")
        with patch('lawyeredos.mail_intake.datetime') as clock:
            clock.now.return_value = datetime(2032, 6, 1, 23, 59, tzinfo=UTC)
            clock.fromisoformat.side_effect = datetime.fromisoformat
            planned = plan(self.fixture.config, '2032-001')
            clock.now.return_value = datetime(2032, 6, 2, 0, 1, tzinfo=UTC)
            result = process_bundle(self.fixture.config, '2032-001', self.fixture.bundle(planned, []))
        self.assertTrue(result['checkpoint_advanced'])

    def test_vanished_reviewed_marker_can_rebase_after_survivors_are_reviewed(self):
        self.fixture.write_config('gmail-imap-readonly')
        def fetch(messages, planned):
            client = mail_fixtures.FakeImapClient(messages)
            adapter = mail_fixtures.GmailImapReadonlyAdapter(
                'fictional@example.invalid', 'fictional-secret', lambda _host: client,
            )
            return adapter.intake(planned['query'], 5, planned['tracked_threads'])
        initial = plan(self.fixture.config, '2032-001')
        first_bundle = fetch({101: (1, 16, mail_fixtures.imap_message())}, initial)
        process_bundle(self.fixture.config, '2032-001', first_bundle)
        self.fixture.acknowledge_all('2032-001')
        process_bundle(self.fixture.config, '2032-001', first_bundle)
        tracked = plan(self.fixture.config, '2032-001')
        replay = fetch({101: (1, 16, mail_fixtures.imap_message())}, tracked)
        process_bundle(self.fixture.config, '2032-001', replay)
        tracked = plan(self.fixture.config, '2032-001')
        self.assertEqual(tracked['tracked_threads'][0]['marker_message_id'], '1')
        survivors = fetch({102: (2, 16, mail_fixtures.imap_message())}, tracked)
        result = process_bundle(self.fixture.config, '2032-001', survivors)
        self.assertFalse(result['checkpoint_advanced'])
        self.fixture.acknowledge_all('2032-001')
        result = process_bundle(self.fixture.config, '2032-001', survivors)
        self.assertTrue(result['checkpoint_advanced'])
        self.assertEqual(plan(self.fixture.config, '2032-001')['tracked_threads'][0]['marker_message_id'], '2')



    def test_recovery_handles_deleted_order_gaps_and_retains_pending_vanished_evidence(self):
        self.fixture.write_config('gmail-imap-readonly')
        def fetch(ids, planned):
            client = mail_fixtures.FakeImapClient({
                100 + number: (number, 16, mail_fixtures.imap_message()) for number in ids
            })
            adapter = mail_fixtures.GmailImapReadonlyAdapter(
                'fictional@example.invalid', 'fictional-secret', lambda _host: client,
            )
            return adapter.intake(planned['query'], 10, planned['tracked_threads'])
        initial = plan(self.fixture.config, '2032-001')
        first = fetch([1, 2, 3, 4], initial)
        process_bundle(self.fixture.config, '2032-001', first)
        self.fixture.acknowledge_all('2032-001')
        process_bundle(self.fixture.config, '2032-001', first)
        tracked = plan(self.fixture.config, '2032-001')
        process_bundle(self.fixture.config, '2032-001', fetch([1, 2, 3, 4], tracked))
        tracked = plan(self.fixture.config, '2032-001')
        self.assertEqual(tracked['tracked_threads'][0]['marker_message_id'], '4')
        pending_bundle = fetch([1, 2, 3, 4, 5], tracked)
        process_bundle(self.fixture.config, '2032-001', pending_bundle)
        retained = mail_fixtures.next_review_chunk(self.fixture.config, '2032-001')
        self.assertEqual(retained['status'], 'review_required')
        tracked = plan(self.fixture.config, '2032-001')
        result = process_bundle(self.fixture.config, '2032-001', fetch([1, 3], tracked))
        self.assertFalse(result['checkpoint_advanced'])
        self.assertEqual(result['status'], 'partial')
        self.assertGreater(result['outstanding_review_items'], 0)
        self.assertEqual(plan(self.fixture.config, '2032-001')['tracked_threads'][0]['marker_message_id'], '3')
        pending = mail_fixtures.next_review_chunk(self.fixture.config, '2032-001')
        self.assertEqual(pending['review_id'], retained['review_id'])
        self.assertEqual(pending['text_sha256'], retained['text_sha256'])
        self.assertEqual(pending['pending'], retained['pending'])
        with sqlite3.connect(self.fixture.workspace / '.lawyeredos/data/mail-intake.sqlite3') as connection:
            self.assertEqual(connection.execute('SELECT COUNT(*) FROM message_reviews').fetchone()[0], 4)
            self.assertEqual(connection.execute(
                "SELECT status FROM content_review_items WHERE message_id='5' AND content_kind='message-body'"
            ).fetchone()[0], 'pending')
        self.fixture.acknowledge_all('2032-001')
        next_plan = plan(self.fixture.config, '2032-001')
        completed = process_bundle(self.fixture.config, '2032-001', fetch([1, 3], next_plan))
        self.assertTrue(completed['checkpoint_advanced'])
        self.assertEqual(completed['outstanding_review_items'], 0)



    def test_recovery_preserves_known_delivery_order_when_provider_timestamps_tie(self):
        initial = plan(self.fixture.config, '2032-001')
        messages = []
        for number in range(1, 5):
            message = self.fixture.message(str(number))
            message.update(provider_labels_known=True, from_account=number == 4,
                provider_labels=['SENT'] if number == 4 else [], acquisition_basis='thread_probe')
            messages.append(message)
        bundle = self.fixture.bundle(initial, messages)
        process_bundle(self.fixture.config, '2032-001', bundle)
        self.fixture.acknowledge_all('2032-001')
        process_bundle(self.fixture.config, '2032-001', bundle)
        tracked = plan(self.fixture.config, '2032-001')
        ordered = self.fixture.bundle(tracked, messages)
        process_bundle(self.fixture.config, '2032-001', ordered)
        tracked = plan(self.fixture.config, '2032-001')
        self.assertEqual(tracked['tracked_threads'][0]['marker_message_id'], '4')
        recovered = self.fixture.bundle(tracked, [messages[0], messages[2]])
        detail = recovered['coverage']['tracked_threads']['details'][0]
        detail.update(marker_missing=True, recovery='missing-marker-surviving-thread-replay')
        result = process_bundle(self.fixture.config, '2032-001', recovered)
        self.assertEqual(result['thread_states'][0]['verdict'], 'we_sent_last_delivery_unproven')
        self.assertEqual(result['thread_states'][0]['last_message_id'], '4')
        next_plan = plan(self.fixture.config, '2032-001')
        tail = self.fixture.bundle(next_plan, [messages[0], messages[2]])
        repeated = process_bundle(self.fixture.config, '2032-001', tail)
        self.assertEqual(repeated['thread_states'][0]['last_message_id'], '4')



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

    def test_vanished_marker_replays_surviving_thread_with_explicit_recovery_imap(self):
        message = EmailMessage()
        message.set_content('Surviving fictional message.')
        adapter, _client = mail_fixtures.GmailImapTransportTests().adapter(message.as_bytes())
        result = adapter.intake(
            '"2032-001" newer_than:30d -in:spam -in:trash', 5,
            [{'thread_id': '4d5e6f', 'marker_message_id': 'dead'}],
        )
        tracked = result['coverage']['tracked_threads']
        self.assertTrue(tracked['complete'])
        self.assertEqual(tracked['details'][0]['recovery'], 'missing-marker-surviving-thread-replay')
        self.assertTrue(tracked['details'][0]['marker_missing'])
        self.assertEqual(tracked['details'][0]['ordered_candidate_ids'], ['1a2b3c'])

    def test_vanished_marker_replays_surviving_thread_with_explicit_recovery_rest(self):
        encoded = base64.urlsafe_b64encode(b'Surviving fictional message.').decode().rstrip('=')
        def transport(method, url, headers, request_body):
            if url.endswith('/profile'):
                return 200, b'{"emailAddress":"fictional@example.invalid"}'
            if '/threads/' in url:
                return 200, b'{"messages":[{"id":"survivor"}]}'
            if 'format=full' in url:
                return 200, json.dumps({
                    'id': 'survivor', 'threadId': 't1', 'internalDate': '1950000000000',
                    'payload': {'headers': [], 'mimeType': 'text/plain', 'body': {'data': encoded}},
                }).encode()
            return 200, b'{"messages":[]}'
        result = GmailReadonlyAdapter('fictional-token', transport).intake(
            'Northstar newer_than:30d', 5,
            [{'thread_id': 't1', 'marker_message_id': 'vanished'}],
        )
        tracked = result['coverage']['tracked_threads']
        self.assertTrue(tracked['complete'])
        self.assertEqual(tracked['details'][0]['recovery'], 'missing-marker-surviving-thread-replay')
        self.assertTrue(tracked['details'][0]['marker_missing'])
        self.assertEqual(tracked['details'][0]['ordered_candidate_ids'], ['survivor'])

    def test_missing_marker_recovery_remains_incomplete_under_caps_and_empty_threads(self):
        message = EmailMessage()
        message.set_content('Fictional note.')
        for ids, cap in (([1, 2], 1), ([], 100)):
            with self.subTest(ids=ids, cap=cap):
                client = mail_fixtures.FakeImapClient({
                    100 + number: (number, 16, message.as_bytes()) for number in ids
                })
                adapter = mail_fixtures.GmailImapReadonlyAdapter(
                    'fictional@example.invalid', 'fictional-secret', lambda _host: client,
                )
                with patch('lawyeredos.imap_mail.MAX_MESSAGES_PER_TRACKED_THREAD', cap):
                    result = adapter.intake('Northstar newer_than:30d -in:spam -in:trash', 5,
                        [{'thread_id': '10', 'marker_message_id': 'dead'}])
                self.assertFalse(result['coverage']['tracked_threads']['complete'])
                self.assertFalse(result['coverage']['tracked_threads']['details'][0]['complete'])
