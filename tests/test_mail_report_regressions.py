from __future__ import annotations

import ast
import base64
import inspect
import sqlite3
import json
import unittest
from datetime import UTC, datetime
from email.message import EmailMessage
from unittest.mock import patch

from lawyeredos.audience_reconciliation import reconcile
from lawyeredos.imap_mail import GmailImapReadonlyAdapter
from lawyeredos.integrations import GmailReadonlyAdapter
from lawyeredos.mail_intake import plan, process_bundle, _relevant, _search_profile
import lawyeredos.mail_intake as mail_api
import test_mail_intake as fixtures


class ExactReportIntakeTests(unittest.TestCase):
    def frozen_legacy_partial(self, positions):
        """Reconstruct old-head persisted state without requiring Git in CI.

        The standalone saved-state upgrade reproduction verifies that old 9cc
        retains successful body rows at these positions but no position table.
        """
        fixture = fixtures.MailIntakeTests()
        fixture.setUp()
        self.addCleanup(fixture.tearDown)
        initial = plan(fixture.config, '2032-001')
        seed = fixture.bundle(initial, [fixture.message('seed')])
        process_bundle(fixture.config, '2032-001', seed)
        fixture.acknowledge_all('2032-001')
        process_bundle(fixture.config, '2032-001', seed)
        tracked = plan(fixture.config, '2032-001')
        names = {position: message_id for message_id, position in positions.items()}
        listed = [names.get(position, f'old-unretrieved-{position}')
            for position in range(max(names) + 1)]
        partial = fixture.bundle(tracked, [fixture.message(value) for value in positions])
        partial['coverage']['tracked_threads']['details'][0].update(
            ordered_candidate_ids=listed, complete=False)
        partial['coverage']['tracked_threads']['complete'] = False
        process_bundle(fixture.config, '2032-001', partial)
        fixture.acknowledge_all('2032-001')
        state = fixture.workspace / '.lawyeredos/data/mail-intake.sqlite3'
        with sqlite3.connect(state) as connection:
            connection.execute('DROP TABLE provider_thread_positions')
            self.assertEqual(dict(connection.execute(
                "SELECT message_id,provider_thread_order FROM message_mail_state "
                "WHERE provider_thread_order IS NOT NULL").fetchall()), positions)
        return fixture, tracked, state

    def test_legacy_partial_upgrade_recovers_only_the_unique_unoccupied_gap(self):
        fixture, tracked, state = self.frozen_legacy_partial({'a': 0, 'c': 2})
        retry = fixture.bundle(tracked, [fixture.message(value) for value in ('a', 'b', 'c')])
        resumed = process_bundle(fixture.config, '2032-001', retry)
        self.assertEqual(resumed['messages'][1]['body_review']['status'], 'pending')
        self.assertFalse(resumed['checkpoint_advanced'])
        fixture.acknowledge_all('2032-001')
        completed = process_bundle(fixture.config, '2032-001', retry)
        self.assertTrue(completed['checkpoint_advanced'])
        with sqlite3.connect(state) as connection:
            self.assertEqual(connection.execute(
                'SELECT message_id,provider_thread_order FROM provider_thread_positions '
                'ORDER BY provider_thread_order').fetchall(), [('a', 0), ('b', 1), ('c', 2)])
            self.assertIsNone(connection.execute(
                "SELECT message_id FROM message_reviews WHERE message_id='old-unretrieved-1'").fetchone())

    def test_legacy_partial_upgrade_refuses_a_known_vanished_id_gap(self):
        fixture, tracked, state = self.frozen_legacy_partial({'a': 0, 'vanished': 1, 'c': 2})
        retry = fixture.bundle(tracked, [fixture.message(value) for value in ('a', 'b', 'c')])
        with self.assertRaisesRegex(ValueError, 'cannot place a new message before known history'):
            process_bundle(fixture.config, '2032-001', retry)
        with sqlite3.connect(state) as connection:
            self.assertEqual(connection.execute(
                "SELECT provider_thread_order FROM message_mail_state WHERE message_id='vanished'"
            ).fetchone()[0], 1)
            self.assertIsNone(connection.execute(
                "SELECT message_id FROM content_review_items WHERE message_id='b'").fetchone())

    def test_legacy_partial_upgrade_refuses_ambiguous_insufficient_or_contradictory_gaps(self):
        for positions, candidates, reason in (
            ({'a': 0, 'c': 3}, ('a', 'b', 'c'), 'cannot place a new message before known history'),
            ({'a': 0, 'c': 1}, ('a', 'b', 'c'), 'cannot place a new message before known history'),
            ({'a': 0, 'c': 2}, ('c', 'b', 'a'), 'conflicts with persisted chronology'),
        ):
            with self.subTest(positions=positions, candidates=candidates):
                fixture, tracked, _state = self.frozen_legacy_partial(positions)
                retry = fixture.bundle(tracked, [fixture.message(value) for value in candidates])
                with self.assertRaisesRegex(ValueError, reason):
                    process_bundle(fixture.config, '2032-001', retry)

    def test_partial_thread_body_retry_uses_enumerated_provider_position(self):
        fixture = fixtures.MailIntakeTests()
        fixture.setUp()
        self.addCleanup(fixture.tearDown)
        initial = plan(fixture.config, '2032-001')
        first = fixture.bundle(initial, [fixture.message('seed')])
        process_bundle(fixture.config, '2032-001', first)
        fixture.acknowledge_all('2032-001')
        process_bundle(fixture.config, '2032-001', first)
        tracked = plan(fixture.config, '2032-001')
        partial = fixture.bundle(tracked, [fixture.message('a'), fixture.message('c')])
        detail = partial['coverage']['tracked_threads']['details'][0]
        detail.update(ordered_candidate_ids=['a', 'b', 'c'], complete=False)
        partial['coverage']['tracked_threads']['complete'] = False
        acquired = process_bundle(fixture.config, '2032-001', partial)
        self.assertFalse(acquired['checkpoint_advanced'])
        state = fixture.workspace / '.lawyeredos/data/mail-intake.sqlite3'
        with sqlite3.connect(state) as connection:
            self.assertEqual(connection.execute(
                "SELECT message_id,provider_thread_order FROM provider_thread_positions "
                "ORDER BY provider_thread_order").fetchall(), [('a', 0), ('b', 1), ('c', 2)])
            self.assertIsNone(connection.execute(
                "SELECT message_id FROM message_mail_state WHERE message_id='b'").fetchone())
        fixture.acknowledge_all('2032-001')
        retry = fixture.bundle(tracked, [fixture.message(value) for value in ('a', 'b', 'c')])
        resumed = process_bundle(fixture.config, '2032-001', retry)
        self.assertEqual(resumed['messages'][1]['body_review']['status'], 'pending')
        fixture.acknowledge_all('2032-001')
        completed = process_bundle(fixture.config, '2032-001', retry)
        self.assertTrue(completed['checkpoint_advanced'])
        with sqlite3.connect(state) as connection:
            self.assertEqual(connection.execute(
                "SELECT message_id,provider_thread_order FROM message_mail_state "
                "WHERE provider_thread_order IS NOT NULL ORDER BY provider_thread_order"
            ).fetchall(), [('a', 0), ('b', 1), ('c', 2)])

    def test_provider_retry_does_not_reuse_a_vanished_id_position(self):
        fixture = fixtures.MailIntakeTests()
        fixture.setUp()
        self.addCleanup(fixture.tearDown)
        initial = plan(fixture.config, '2032-001')
        first = fixture.bundle(initial, [fixture.message('seed')])
        process_bundle(fixture.config, '2032-001', first)
        fixture.acknowledge_all('2032-001')
        process_bundle(fixture.config, '2032-001', first)
        tracked = plan(fixture.config, '2032-001')
        partial = fixture.bundle(tracked, [fixture.message('a'), fixture.message('c')])
        detail = partial['coverage']['tracked_threads']['details'][0]
        detail.update(ordered_candidate_ids=['a', 'vanished', 'c'], complete=False)
        partial['coverage']['tracked_threads']['complete'] = False
        process_bundle(fixture.config, '2032-001', partial)
        # A different, unrecorded ID cannot be guessed into vanished's slot.
        changed = fixture.bundle(tracked, [fixture.message(value) for value in ('a', 'new', 'c')])
        with self.assertRaisesRegex(ValueError, 'cannot place a new message before known history'):
            process_bundle(fixture.config, '2032-001', changed)
        surviving = fixture.bundle(tracked, [fixture.message(value) for value in ('a', 'c', 'new')])
        process_bundle(fixture.config, '2032-001', surviving)
        state = fixture.workspace / '.lawyeredos/data/mail-intake.sqlite3'
        with sqlite3.connect(state) as connection:
            self.assertEqual(connection.execute(
                "SELECT message_id,provider_thread_order FROM provider_thread_positions "
                "ORDER BY provider_thread_order"
            ).fetchall(), [('a', 0), ('vanished', 1), ('c', 2), ('new', 3)])

    def test_enumerated_missing_body_remains_an_account_scoped_acquisition_gap(self):
        fixture = fixtures.MailIntakeTests()
        fixture.setUp()
        self.addCleanup(fixture.tearDown)
        initial = plan(fixture.config, '2032-001')
        first = fixture.bundle(initial, [fixture.message('seed')])
        process_bundle(fixture.config, '2032-001', first)
        fixture.acknowledge_all('2032-001')
        process_bundle(fixture.config, '2032-001', first)
        tracked = plan(fixture.config, '2032-001')
        partial = fixture.bundle(tracked, [fixture.message('a'), fixture.message('c')])
        detail = partial['coverage']['tracked_threads']['details'][0]
        detail.update(ordered_candidate_ids=['a', 'missing', 'c'], complete=False)
        partial['coverage']['tracked_threads']['complete'] = False
        process_bundle(fixture.config, '2032-001', partial)
        fixture.acknowledge_all('2032-001')
        surviving = fixture.bundle(tracked, [fixture.message('a'), fixture.message('c')])
        incomplete = process_bundle(fixture.config, '2032-001', surviving)
        self.assertFalse(incomplete['checkpoint_advanced'])
        self.assertEqual(incomplete['outstanding_unreviewed_messages'], 1)
        current = plan(fixture.config, '2032-001')
        other_account = fixture.bundle(current, [fixture.message('c'), fixture.message('a')])
        other_account['account_fingerprint'] = 'a' * 64
        acquired = process_bundle(fixture.config, '2032-001', other_account)
        self.assertEqual(acquired['outstanding_unreviewed_messages'], 2)
        fixture.acknowledge_all('2032-001')
        completed = process_bundle(fixture.config, '2032-001', other_account)
        self.assertTrue(completed['checkpoint_advanced'])
        state = fixture.workspace / '.lawyeredos/data/mail-intake.sqlite3'
        with sqlite3.connect(state) as connection:
            self.assertEqual(connection.execute(
                "SELECT message_id,provider_thread_order FROM provider_thread_positions "
                "WHERE account_fingerprint=? ORDER BY provider_thread_order", ('a' * 64,)
            ).fetchall(), [('c', 0), ('a', 1)])

    def test_missing_middle_draft_with_new_tail_does_not_deadlock_partial_frontier(self):
        fixture = fixtures.MailIntakeTests()
        fixture.setUp()
        self.addCleanup(fixture.tearDown)
        initial = plan(fixture.config, '2032-001')
        first = fixture.bundle(initial, [fixture.message('a0')])
        process_bundle(fixture.config, '2032-001', first)
        fixture.acknowledge_all('2032-001')
        process_bundle(fixture.config, '2032-001', first)
        tracked = plan(fixture.config, '2032-001')
        old = [fixture.message(value) for value in ('a0', 'd1', 'x2', 'f3')]
        old[2].update(provider_labels=['DRAFT'], provider_labels_known=True, from_account=True)
        partial = process_bundle(fixture.config, '2032-001', fixture.bundle(tracked, old))
        self.assertEqual(partial['status'], 'partial')
        self.assertEqual(plan(fixture.config, '2032-001')['tracked_threads'], tracked['tracked_threads'])
        changed = fixture.bundle(tracked, [old[0], old[1], old[3], fixture.message('g4')])
        result = process_bundle(fixture.config, '2032-001', changed)
        self.assertEqual(result['status'], 'partial')
        self.assertGreater(result['outstanding_review_items'], 0)
        fixture.acknowledge_all('2032-001')
        completed = process_bundle(fixture.config, '2032-001', changed)
        self.assertTrue(completed['checkpoint_advanced'])
        self.assertEqual(plan(fixture.config, '2032-001')['tracked_threads'][0]['marker_message_id'], 'g4')


    def test_known_deferred_attachment_does_not_disappear_from_completion_gate(self):
        fixture = fixtures.MailIntakeTests()
        fixture.setUp()
        self.addCleanup(fixture.tearDown)
        initial = plan(fixture.config, '2032-001')
        message = fixture.message('gap1', attachment=fixture.attachment(
            b'fictional-image', filename='signature.png', mime_type='image/png'))
        result = process_bundle(fixture.config, '2032-001', fixture.bundle(initial, [message]))
        self.assertEqual(result['status'], 'partial')
        self.assertEqual(result['messages'][0]['attachments'][0]['status'], 'deferred')
        fixture.acknowledge_all('2032-001')
        current = plan(fixture.config, '2032-001')
        missing = process_bundle(fixture.config, '2032-001', fixture.bundle(current, []))
        self.assertEqual(missing['status'], 'partial')
        self.assertFalse(missing['checkpoint_advanced'])
        self.assertEqual(missing['outstanding_unreviewed_messages'], 1)



    def test_retained_acquisition_checks_saved_hash_before_completion(self):
        fixture = fixtures.MailIntakeTests()
        fixture.setUp()
        self.addCleanup(fixture.tearDown)
        initial = plan(fixture.config, '2032-001')
        first = process_bundle(fixture.config, '2032-001', fixture.bundle(initial, [
            fixture.message('retained', attachment=fixture.attachment())]))
        fixture.acknowledge_all('2032-001')
        saved = fixtures.Path(first['messages'][0]['attachments'][0]['saved_path'])
        original = saved.read_bytes()
        saved.write_bytes(b'Changed fictional cache content.')
        current = plan(fixture.config, '2032-001')
        corrupted = process_bundle(fixture.config, '2032-001', fixture.bundle(current, []))
        self.assertEqual(corrupted['status'], 'partial')
        self.assertEqual(corrupted['outstanding_unreviewed_messages'], 1)
        saved.write_bytes(original)
        state = fixture.workspace / '.lawyeredos/data/mail-intake.sqlite3'
        with sqlite3.connect(state) as connection:
            body_hash = connection.execute("SELECT content_sha256 FROM content_review_items WHERE content_kind='message-body'").fetchone()[0]
            connection.execute("UPDATE content_review_items SET content_sha256=? WHERE content_kind='message-body'", ('0' * 64,))
        invalid_body = process_bundle(fixture.config, '2032-001', fixture.bundle(current, []))
        self.assertEqual(invalid_body['outstanding_unreviewed_messages'], 1)
        with sqlite3.connect(state) as connection:
            connection.execute("UPDATE content_review_items SET content_sha256=? WHERE content_kind='message-body'", (body_hash,))
        completed = process_bundle(fixture.config, '2032-001', fixture.bundle(current, []))
        self.assertTrue(completed['checkpoint_advanced'])
        self.assertEqual(completed['outstanding_unreviewed_messages'], 0)
        with sqlite3.connect(state) as connection:
            reviewed_hash, provenance = connection.execute("SELECT body_sha256, provenance_json FROM message_reviews WHERE message_id='retained'").fetchone()
        self.assertEqual(reviewed_hash, body_hash)
        self.assertEqual(json.loads(provenance)['query'], initial['query'])

    def test_retained_attachment_privacy_is_required_before_finalization(self):
        for unsafe in ('mode', 'hardlink'):
            with self.subTest(unsafe=unsafe):
                fixture = fixtures.MailIntakeTests()
                fixture.setUp()
                try:
                    planned = plan(fixture.config, '2032-001')
                    acquired = process_bundle(fixture.config, '2032-001', fixture.bundle(planned, [
                        fixture.message('retained', attachment=fixture.attachment())]))
                    self.assertEqual(acquired['status'], 'partial')
                    saved = fixtures.Path(acquired['messages'][0]['attachments'][0]['saved_path'])
                    extra_link = fixture.root / 'fictional-extra-hardlink.txt'
                    if unsafe == 'mode':
                        saved.chmod(0o644)
                    else:
                        extra_link.hardlink_to(saved)
                    fixture.acknowledge_all('2032-001')
                    current = plan(fixture.config, '2032-001')
                    retained = process_bundle(fixture.config, '2032-001', fixture.bundle(current, []))
                    self.assertEqual(retained['status'], 'partial')
                    self.assertEqual(retained['outstanding_unreviewed_messages'], 1)
                    if unsafe == 'mode':
                        saved.chmod(0o600)
                    else:
                        extra_link.unlink()
                    restored = process_bundle(fixture.config, '2032-001', fixture.bundle(current, []))
                    self.assertTrue(restored['checkpoint_advanced'])
                    self.assertEqual(restored['outstanding_unreviewed_messages'], 0)
                finally:
                    fixture.tearDown()

    def test_outstanding_acquisitions_are_source_and_account_scoped(self):
        fixture = fixtures.MailIntakeTests()
        fixture.setUp()
        self.addCleanup(fixture.tearDown)
        planned = plan(fixture.config, '2032-001')
        unsupported = fixture.message('gap1', attachment=fixture.attachment(
            b'fictional-image', filename='signature.png', mime_type='image/png'))
        process_bundle(fixture.config, '2032-001', fixture.bundle(planned, [unsupported]))
        fixture.acknowledge_all('2032-001')
        other_account = fixture.bundle(planned, [])
        other_account['account_fingerprint'] = 'a' * 64
        result = process_bundle(fixture.config, '2032-001', other_account)
        self.assertTrue(result['checkpoint_advanced'])
        self.assertEqual(result['outstanding_unreviewed_messages'], 0)
        fixture.write_config('codex-session-tools')
        other_source_plan = plan(fixture.config, '2032-001')
        other_source = fixture.bundle(other_source_plan, [])
        other_source.update(source='codex-session-tool', account_fingerprint='b' * 64)
        result = process_bundle(fixture.config, '2032-001', other_source)
        self.assertTrue(result['checkpoint_advanced'])
        self.assertEqual(result['outstanding_unreviewed_messages'], 0)

    def test_held_ambiguous_hits_do_not_create_persistent_acquisition_blockers(self):
        fixture = fixtures.MailIntakeTests()
        fixture.setUp()
        self.addCleanup(fixture.tearDown)
        planned = plan(fixture.config, '2032-001')
        other = fixture.message('unrelated')
        other.update(subject='Other subject', body='Other content.', snippet='Other', **{'from': 'other@example.invalid'})
        held = process_bundle(fixture.config, '2032-001', fixture.bundle(planned, [other]))
        self.assertEqual(held['messages'][0]['status'], 'held_ambiguous')
        empty = process_bundle(fixture.config, '2032-001', fixture.bundle(planned, []))
        self.assertTrue(empty['checkpoint_advanced'])
        self.assertEqual(empty['outstanding_unreviewed_messages'], 0)

    def test_acquisition_receipt_migration_is_additive_and_idempotent(self):
        fixture = fixtures.MailIntakeTests()
        fixture.setUp()
        self.addCleanup(fixture.tearDown)
        state = fixture.workspace / '.lawyeredos/data/mail-intake.sqlite3'
        state.parent.parent.mkdir(mode=0o700)
        state.parent.mkdir(mode=0o700)
        state.touch(mode=0o600)
        node = ast.parse(inspect.getsource(mail_api._state_connection))
        schema = next(call.args[0].value for call in ast.walk(node) if isinstance(call, ast.Call)
            and isinstance(call.func, ast.Attribute) and call.func.attr == 'executescript')
        legacy_schema = schema.replace("            acquisition_receipt_json TEXT NOT NULL DEFAULT '{}',\n", '')
        with sqlite3.connect(state) as connection:
            connection.executescript(legacy_schema)
            connection.execute("INSERT INTO state_meta VALUES ('review_protocol', ?)", (mail_api.STATE_REVIEW_PROTOCOL,))
            connection.execute("INSERT INTO message_mail_state(file_number,source,account_fingerprint,message_id,thread_id,"
                "received_at,transmission_state,state_known,observed_at) VALUES "
                "('2032-001','fixture','fixture','legacy','t1','2032-01-01','unknown',0,'2032-01-01')")
        for _ in range(2):
            with mail_api._state_connection(state) as connection:
                self.assertEqual(connection.execute('SELECT acquisition_receipt_json FROM message_mail_state').fetchone()[0], '{}')
                self.assertEqual(connection.execute('SELECT message_id FROM message_mail_state').fetchone()[0], 'legacy')
                self.assertEqual(sum(row[1] == 'acquisition_receipt_json' for row in connection.execute('PRAGMA table_info(message_mail_state)')), 1)



class ReportTransportTests(unittest.TestCase):
    def test_unicode_display_name_remains_matter_identity_evidence(self):
        fixture = fixtures.MailIntakeTests()
        fixture.setUp()
        self.addCleanup(fixture.tearDown)
        fixture.write_config('gmail-imap-readonly')
        with sqlite3.connect(fixture.database) as connection:
            connection.execute("UPDATE matters SET client=?,description=?,primary_email=?,opposing_party=''",
                ('Société Fictionnelle', 'Bail commercial', 'primary@example.invalid'))
        (fixture.matter / '_matter-brief.md').write_text(
            '# Société Fictionnelle\n\n## Status\n\nFictional matter.\n', encoding='utf-8')
        message = EmailMessage()
        message['From'] = '"Société Fictionnelle" <alternate@example.invalid>'
        message['To'] = 'lawyer@example.invalid'
        message['Subject'] = 'Bail commercial'
        message.set_content('Veuillez répondre à la question.')
        client = fixtures.FakeImapClient({101: (1, 16, message.as_bytes())})
        adapter = GmailImapReadonlyAdapter(
            'fictional@example.invalid', 'fictional-secret', lambda _host: client)
        planned = plan(fixture.config, '2032-001')
        bundle = adapter.intake(planned['query'], 5, planned['tracked_threads'])
        self.assertIn('=?utf-8?', bundle['messages'][0]['from'])
        result = process_bundle(fixture.config, '2032-001', bundle)
        self.assertIn('body_review', result['messages'][0])
        self.assertEqual(result['messages'][0]['body_review']['status'], 'pending')
        audience = reconcile(bundle['messages'][0], {
            'from': 'alternate@example.invalid', 'to': 'lawyer@example.invalid', 'cc': '',
        })
        self.assertEqual(audience['state'], 'verified')

    def test_non_ascii_query_uses_utf8_literal_on_real_imap_command_formatter(self):
        class SearchWireClient(fixtures.WireRecordingImapClient):
            def uid(self, command, *args):
                self._command('UID', command, *args)
                return 'OK', [b'']
            def _get_response(self):
                return None
        client = SearchWireClient(b'(\\HasNoChildren \\All) "/" "All Mail"')
        adapter = GmailImapReadonlyAdapter('fictional@example.invalid', 'fictional-secret', lambda _host: client)
        query = '("Société Fictionnelle" "Bail commercial") newer_than:30d -in:spam -in:trash'
        result = adapter.intake(query)
        self.assertTrue(result['coverage']['complete'])
        self.assertIn(b'UID SEARCH CHARSET UTF-8 X-GM-RAW {', client.sent[1])
        self.assertEqual(client.sent[2], query.encode('utf-8'))
        self.assertIsNone(client.literal)

    def test_rest_body_charsets_preserve_accented_matter_evidence(self):
        for charset, text in (
            ('iso-8859-1', 'Société Fictionnelle — bail commercial.'.replace('—', '-')),
            ('windows-1252', 'Société Fictionnelle — bail commercial €100.'),
            ('x-fictional', 'Fictional UTF-8 fallback.'),
        ):
            with self.subTest(charset=charset):
                raw = text.encode('utf-8' if charset == 'x-fictional' else charset)
                encoded = base64.urlsafe_b64encode(raw).decode().rstrip('=')
                def transport(method, url, headers, request_body):
                    if url.endswith('/profile'):
                        return 200, b'{"emailAddress":"fictional@example.invalid"}'
                    if 'format=full' in url:
                        return 200, json.dumps({
                            'id': 'm1', 'threadId': 't1', 'internalDate': '1950000000000',
                            'payload': {'headers': [{'name': 'Content-Type',
                                'value': f'text/plain; charset="{charset}"'}],
                                'mimeType': 'text/plain', 'body': {'data': encoded}},
                        }).encode()
                    return 200, b'{"messages":[{"id":"m1"}]}'
                result = GmailReadonlyAdapter('fictional-token', transport).intake('Fictional newer_than:30d')
                self.assertEqual(result['messages'][0]['body'], text)
                if charset != 'x-fictional':
                    self.assertTrue(_relevant(result['messages'][0], _search_profile({
                        'client': 'Société Fictionnelle', 'description': 'bail commercial',
                    })))

    def test_quoted_display_names_remain_verified_after_imap_normalization(self):
        message = EmailMessage()
        message['From'] = '"Fictional, Client" <client@example.invalid>'
        message['To'] = '"Fictional, Lawyer" <lawyer@example.invalid>'
        message['Cc'] = '"Fictional (Counsel)" <counsel@example.invalid>'
        message.set_content('Fictional message.')
        adapter, _client = fixtures.GmailImapTransportTests().adapter(message.as_bytes())
        bundle = adapter.intake('Fictional newer_than:30d -in:spam -in:trash')
        result = reconcile(bundle['messages'][0], {
            'from': 'client@example.invalid', 'to': 'lawyer@example.invalid', 'cc': 'counsel@example.invalid',
        })
        self.assertEqual(result['state'], 'verified')

    def test_imap_does_not_charge_matched_attachment_budget_again_for_thread_probe(self):
        def message():
            value = EmailMessage()
            value.set_content('Fictional message.')
            value.add_attachment(b'X' * 32, maintype='text', subtype='plain', filename='evidence.txt')
            return value.as_bytes()
        class MatchedSubsetClient(fixtures.FakeImapClient):
            def uid(self, command, *args):
                if command == 'SEARCH' and 'X-GM-RAW' in args:
                    self.calls.append(('UID', command, *args))
                    return 'OK', [b'101 102']
                return super().uid(command, *args)
        client = MatchedSubsetClient({101: (1, 16, message()), 102: (2, 16, message()), 103: (3, 16, message())})
        adapter = GmailImapReadonlyAdapter('fictional@example.invalid', 'fictional-secret', lambda _host: client)
        with patch('lawyeredos.imap_mail.MAX_RUN_ATTACHMENT_BYTES', 100):
            bundle = adapter.intake('Fictional newer_than:30d -in:spam -in:trash', 5,
                [{'thread_id': '10', 'marker_message_id': ''}])
        for item in bundle['messages']:
            self.assertIn('content_base64', item['attachments'][0])
            self.assertEqual(item['acquisition_basis'], 'thread_probe')
        raw_fetches = [call for call in client.calls if call[:2] == ('UID', 'FETCH') and 'BODY.PEEK[]' in call[3]]
        self.assertEqual(len(raw_fetches), 3)

    def test_rest_does_not_charge_matched_attachment_budget_again_for_thread_probe(self):
        encoded = base64.urlsafe_b64encode(b'X' * 32).decode().rstrip('=')
        calls = []
        def transport(method, url, headers, request_body):
            calls.append(url)
            if url.endswith('/profile'):
                return 200, b'{"emailAddress":"fictional@example.invalid"}'
            if '/threads/' in url:
                return 200, b'{"messages":[{"id":"a1"},{"id":"a2"},{"id":"a3"}]}'
            if 'format=full' in url:
                message_id = url.split('/messages/')[1].split('?')[0]
                return 200, json.dumps({
                    'id': message_id, 'threadId': 't1', 'internalDate': '1950000000000',
                    'payload': {'headers': [], 'parts': [{'mimeType': 'text/plain', 'filename': 'evidence.txt',
                        'body': {'data': encoded, 'size': 32}}]},
                }).encode()
            return 200, b'{"messages":[{"id":"a1"},{"id":"a2"}]}'
        with patch('lawyeredos.integrations.MAX_MAIL_RUN_ATTACHMENT_BYTES', 100):
            result = GmailReadonlyAdapter('fictional-token', transport).intake('Fictional newer_than:30d', 5,
                [{'thread_id': 't1', 'marker_message_id': ''}])
        self.assertTrue(all('content_base64' in value['attachments'][0] for value in result['messages']))
        self.assertEqual(sum('format=full' in url for url in calls), 3)
