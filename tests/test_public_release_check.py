from __future__ import annotations

import importlib.util
import io
import stat
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import public_release_check as gate
import build_release as builder


def archive(entries, comment=b""):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as package:
        package.comment = comment
        for name, data in entries:
            package.writestr(name, data)
    return stream.getvalue()


class PublicReleaseCheckTests(unittest.TestCase):
    def categories(self, label, data):
        return {category for _, category in gate.scan_bytes(label, data, {}, [])}

    def test_nested_archive_with_opaque_extension_is_inspected(self):
        secret = ("sk-" + "SYNTHETIC" * 4).encode()
        data = archive([("nested.bin", archive([("evidence.txt", secret)]))])
        self.assertIn("credential-shaped", self.categories("outer.zip", data))

    def test_metadata_and_member_names_are_scanned(self):
        secret = ("ghp_" + "SYNTHETIC" * 4).encode()
        data = archive([("note.txt", b"Fictional")], comment=secret)
        self.assertIn("credential-shaped", self.categories("outer.zip", data))
        self.assertIn("unexpected-archive-comment", self.categories("outer.zip", data))
        data = archive([("client@"+"real-domain.test.txt", b"Fictional")])
        self.assertIn("nonfictional-email", self.categories("outer.zip", data))

    def test_traversal_duplicates_and_symlinks_are_rejected(self):
        for name in ("../escape.txt", "a/../../escape", "a\\escape.txt", "/absolute.txt"):
            self.assertIn("unsafe-or-duplicate-archive-path", self.categories("outer.zip", archive([(name, b"Fictional")])) )
        self.assertIn("unsafe-or-duplicate-archive-path", self.categories("outer.zip", archive([("A.txt",b"one"),("a.txt",b"two")])))
        stream = io.BytesIO()
        with zipfile.ZipFile(stream,"w") as package:
            info = zipfile.ZipInfo("link")
            info.external_attr = (stat.S_IFLNK | 0o777) << 16
            package.writestr(info,b"target")
        self.assertIn("unsafe-or-duplicate-archive-path", self.categories("outer.zip",stream.getvalue()))

    def test_unknown_binary_bad_container_and_limits_fail_closed(self):
        self.assertIn("unreviewed-binary", self.categories("unknown.bin", b"\x00\xff"))
        self.assertIn("binary-in-text", self.categories("disguised.py", b"\x00\xff"))
        self.assertIn("unexpected-archive-envelope",self.categories("trailing.zip",archive([("note.txt",b"fictional")])+b"hidden"))
        self.assertIn("invalid-archive", self.categories("broken.docx", b"not a package"))
        self.assertIn("unreadable-archive", self.categories("broken.bin", b"PKbroken"))
        result = gate.scan_bytes("too-large.txt", b"fictional", {}, [], budget=[1,1])
        self.assertEqual(result[0][1], "inspection-limit")
        nested=b"fictional"
        for _ in range(gate.MAX_DEPTH+2):
            nested=archive([("nested.zip",nested)])
        self.assertIn("inspection-limit",self.categories("outer.zip",nested))

    def test_office_author_properties_are_not_ignored(self):
        xml=b'<properties><creator>Fictional Author</creator></properties>'
        self.assertIn("identifying-office-properties", self.categories("example.docx",archive([("docProps/core.xml",xml)])))

    def test_paths_emails_account_ids_and_forbidden_values_are_redacted(self):
        samples = [
            ("absolute-user-path", ("/Us"+"ers/synthetic/secret/").encode()),
            ("nonfictional-email", ("synthetic@"+"mail.test").encode()),
            ("account-identifier", ("account_"+'id = "'+'1234567890"').encode()),
        ]
        for category,data in samples:
            self.assertIn(category,self.categories("sample.txt",data))
        result=gate.text_findings("fixture.txt","SYNTHETIC-PRIVATE-MARKER",["SYNTHETIC-PRIVATE-MARKER"])
        self.assertEqual(result,[("fixture.txt","forbidden-value")])
        result=gate.text_findings("SYNTHETIC-PRIVATE-MARKER.txt","SYNTHETIC-PRIVATE-MARKER",["SYNTHETIC-PRIVATE-MARKER"])
        self.assertEqual(result,[("[redacted].txt","forbidden-value")])
        self.assertIn("phone-number",self.categories("sample.txt",("202"+"-555-0100").encode()))
        self.assertIn("private-or-residual-file",self.categories("evidence.log",b"fictional"))

    def test_only_exact_opaque_digest_is_allowed(self):
        data=b"\x89PNG\r\n\x1a\nfictional"
        policy={"opaque_sha256":{"image.png":gate.digest(data)}}
        self.assertEqual(gate.scan_bytes("image.png",data,policy,[]),[])
        self.assertIn("unreviewed-binary",{c for _,c in gate.scan_bytes("image.png",data+b"changed",policy,[])})

    def test_extra_staged_file_and_root_symlink_are_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            (root/"intended.txt").write_text("fictional")
            (root/"unexpected.txt").write_text("fictional")
            findings=gate.check_tree(root,list(root.iterdir()),{"files":["intended.txt"]},[])
            self.assertIn(("unexpected.txt","unexpected-staged-file"),findings)

    def test_real_source_and_exact_builder_roundtrip(self):
        root=SCRIPTS.parent
        policy=gate.load_policy(root)
        self.assertEqual(gate.check_tree(root,builder.release_files(root),policy,[]),[])
        with tempfile.TemporaryDirectory() as folder:
            output=Path(folder)/"candidate.zip"
            builder.build(output)
            self.assertEqual(gate.check_archive(output,root,policy,[]),[])
            from candidate_metadata import prepare
            candidate=Path(folder)/"metadata"
            manifest=prepare(output,candidate)
            self.assertEqual(len(manifest["files"]),2)
            for name in manifest["files"]:
                self.assertEqual(gate.digest((candidate/name).read_bytes()),manifest["sha256"])
            with self.assertRaisesRegex(ValueError,"absent"):
                prepare(output,candidate)
            with zipfile.ZipFile(output,"a") as package:
                package.writestr("lawyeredos/extra.txt","fictional")
            self.assertIn("archive-manifest-mismatch",{c for _,c in gate.check_archive(output,root,policy,[])})

    def test_root_symlink_is_rejected_before_build(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            (root/"target").write_text("fictional")
            (root/"root.txt").symlink_to(root/"target")
            with patch.object(builder,"ROOT_FILES",{"root.txt"}), patch.object(builder,"ROOT_DIRECTORIES",set()):
                with self.assertRaisesRegex(ValueError,"symlink"):
                    builder.release_files(root)
            (root/"source").mkdir()
            (root/"linked-directory").symlink_to(root/"source",target_is_directory=True)
            with patch.object(builder,"ROOT_FILES",set()), patch.object(builder,"ROOT_DIRECTORIES",{"linked-directory"}):
                with self.assertRaisesRegex(ValueError,"symlink"):
                    builder.release_files(root)
