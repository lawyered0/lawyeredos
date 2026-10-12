from __future__ import annotations

import importlib.util
import io
import tempfile
import unittest
import zipfile
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('privacy_audit_fixture', ROOT/'scripts/privacy_audit.py')
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


class PrivacyAuditTests(unittest.TestCase):
    def scan(self, files, forbidden=None):
        with tempfile.TemporaryDirectory() as temporary:
            archive = Path(temporary)/'synthetic.zip'
            with zipfile.ZipFile(archive, 'w') as package:
                for name, value in files.items():
                    package.writestr(name,value)
            return audit.scan_archive(archive, forbidden or [])

    def test_scans_extensionless_csv_xml_and_ooxml_template(self):
        office=io.BytesIO()
        with zipfile.ZipFile(office,'w') as package:
            package.writestr('docProps/core.xml','<author>SyntheticForbiddenPerson</author>')
        findings=self.scan({'COPYRIGHT':'SyntheticForbiddenPerson', 'fixture.csv':'SyntheticForbiddenPerson',
                            'fixture.xml':'SyntheticForbiddenPerson', 'fixture.dotx':office.getvalue()},['SyntheticForbiddenPerson'])
        found={name.split(':',1)[0] for name,_category in findings}
        self.assertEqual(found,{'COPYRIGHT','fixture.csv','fixture.xml','fixture.dotx'})
        self.assertFalse(any('SyntheticForbiddenPerson' in category for _,category in findings))

    def test_common_contact_and_user_path_categories(self):
        findings=self.scan({'fixture.txt':'person' + '@' + 'synthetic-company.com ' + '+1 416-' + '555-0123 C:\\Users\\SyntheticPerson ' + '/Users' + '/SyntheticPerson'})
        categories={category for _,category in findings}
        self.assertTrue({'email-address','phone-number','absolute-user-path','windows-user-path'} <= categories)

    def test_common_contacts_in_archive_member_names_are_reported_and_redacted(self):
        email='person'+'@'+'synthetic-company.com'
        phone='416-'+'555-0123'
        findings=self.scan({f'fixtures/{email}.txt':'fictional content',
                            f'fixtures/{phone}/':''})
        self.assertTrue({'filename-email-address','filename-phone-number'} <= {category for _,category in findings})
        self.assertFalse(any(email in location or phone in location for location,_ in findings))

    def test_common_contacts_in_directory_relative_names_are_reported_and_redacted(self):
        email='person'+'@'+'synthetic-company.com'
        phone='416-'+'555-0123'
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            (root/f'{email}.txt').write_text('fictional content',encoding='utf-8')
            (root/phone).mkdir()
            output=io.StringIO()
            with patch('sys.argv',['privacy_audit.py',temporary]),redirect_stdout(output):
                self.assertEqual(audit.main(),2)
            self.assertIn('filename-email-address',output.getvalue())
            self.assertIn('filename-phone-number',output.getvalue())
            self.assertNotIn(email,output.getvalue())
            self.assertNotIn(phone,output.getvalue())

    def test_common_contacts_in_office_member_names_are_reported_and_redacted(self):
        email='person'+'@'+'synthetic-company.com'
        office=io.BytesIO()
        with zipfile.ZipFile(office,'w') as package:
            package.writestr(f'word/{email}.xml','<document>fictional content</document>')
        findings=self.scan({'fixture.docx':office.getvalue()})
        self.assertIn('filename-email-address',{category for _,category in findings})
        self.assertFalse(any(email in location for location,_ in findings))

    def test_fictional_and_public_attribution_email_allowlist(self):
        self.assertEqual(self.scan({'fixture.txt':'person@example.invalid person@example.com 4802498+lawyered0@users.noreply.github.com'}),[])

    def test_residue_and_unknown_binary_are_refused_by_category(self):
        for name in ('.env','fixture.sqlite3','fixture.log','fixture.bak','fixture.dat'):
            with self.subTest(name=name):
                self.assertTrue(self.scan({name:b'\x00fictional binary'}))

    def test_reports_categories_without_forbidden_literal(self):
        findings=self.scan({'SyntheticForbiddenPerson.txt':'SyntheticForbiddenPerson'},['SyntheticForbiddenPerson'])
        self.assertFalse(any('SyntheticForbiddenPerson' in category for _,category in findings))

    def test_read_failure_returns_nonzero_without_traceback(self):
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/'fixture.txt';path.write_text('fictional text',encoding='utf-8')
            with patch('sys.argv',['privacy_audit.py',temporary]),patch.object(Path,'read_bytes',side_effect=OSError('fictional read failure')),redirect_stdout(io.StringIO()):
                self.assertEqual(audit.main(),2)
