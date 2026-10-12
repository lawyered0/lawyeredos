"""Fictional fixtures for the remaining recovered document claims."""
import importlib.util
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from lxml import etree

ROOT = Path(__file__).resolve().parents[1]


def script(name):
    sys.path.insert(0, str(ROOT / "scripts"))
    try:
        spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / (name + ".py"))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.pop(0)


class RecoveredDocumentRegressionTests(unittest.TestCase):
    def _custom_property_fixture(self, source, target="docProps/review-props.xml", *, orphan=False, invalid_root=False):
        Document().save(source)
        with zipfile.ZipFile(source) as package:
            parts = {name: package.read(name) for name in package.namelist()}
        scrubber = script("scrub_docx_metadata")
        if not orphan:
            root = etree.fromstring(parts["_rels/.rels"])
            etree.SubElement(root, "{" + scrubber.REL_NS + "}Relationship", Id="fictionalCustom",
                             Target=target, Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/custom-properties")
            parts["_rels/.rels"] = etree.tostring(root)
        root = etree.fromstring(parts["[Content_Types].xml"])
        etree.SubElement(root, "{" + scrubber.CONTENT_NS + "}Override", PartName="/docProps/review-props.xml",
                         ContentType="application/vnd.openxmlformats-officedocument.custom-properties+xml")
        parts["[Content_Types].xml"] = etree.tostring(root)
        parts["docProps/review-props.xml"] = (
            b'<unexpected>Fictional private metadata</unexpected>' if invalid_root else
            b'<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/custom-properties" '
            b'xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">'
            b'<property fmtid="{D5CDD505-2E9C-101B-9397-08002B2CF9AE}" pid="2" name="Fictional confidential">'
            b'<vt:lpwstr>Fictional private metadata</vt:lpwstr></property></Properties>'
        )
        with zipfile.ZipFile(source, "w") as package:
            for name, data in parts.items():
                package.writestr(name, data)

    def test_scrubber_removes_renamed_and_orphaned_custom_property_parts(self):
        scrubber = script("scrub_docx_metadata")
        for orphan in (False, True):
            with self.subTest(orphan=orphan), tempfile.TemporaryDirectory() as temporary:
                source, output = Path(temporary) / "fictional.docx", Path(temporary) / "scrubbed.docx"
                self._custom_property_fixture(source, orphan=orphan)
                original = source.read_bytes()
                scrubber.scrub(source, output)
                self.assertEqual(source.read_bytes(), original)
                Document(output)
                with zipfile.ZipFile(output) as package:
                    self.assertNotIn("docProps/review-props.xml", package.namelist())
                    self.assertNotIn(b"review-props.xml", package.read("[Content_Types].xml"))
                    self.assertNotIn(b"review-props.xml", package.read("_rels/.rels"))
                    self.assertFalse(any(b"Fictional private metadata" in package.read(name) for name in package.namelist()))

    def test_scrubber_refuses_unsafe_or_misdeclared_custom_property_targets(self):
        scrubber = script("scrub_docx_metadata")
        for target in ("../escaped.xml", "https://fictional.invalid/properties.xml", "word/document.xml", "docProps/missing.xml"):
            with self.subTest(target=target), tempfile.TemporaryDirectory() as temporary:
                source, output = Path(temporary) / "fictional.docx", Path(temporary) / "scrubbed.docx"
                self._custom_property_fixture(source, target=target)
                original = source.read_bytes()
                with self.assertRaisesRegex(ValueError, "custom-property"):
                    scrubber.scrub(source, output)
                self.assertEqual(source.read_bytes(), original)
                self.assertFalse(output.exists())

    def test_scrubber_refuses_misdeclared_custom_property_content(self):
        scrubber = script("scrub_docx_metadata")
        with tempfile.TemporaryDirectory() as temporary:
            source, output = Path(temporary) / "fictional.docx", Path(temporary) / "scrubbed.docx"
            self._custom_property_fixture(source, invalid_root=True)
            with self.assertRaisesRegex(ValueError, "unexpected XML root"):
                scrubber.scrub(source, output)
            self.assertFalse(output.exists())

    def test_scrubber_respects_default_custom_property_types_and_override_precedence(self):
        scrubber = script("scrub_docx_metadata")
        for extension, overridden in (("reviewprops", False), ("xml", False), ("reviewprops", True)):
            with self.subTest(extension=extension, overridden=overridden), tempfile.TemporaryDirectory() as temporary:
                source, output = Path(temporary) / "fictional.docx", Path(temporary) / "scrubbed.docx"
                self._custom_property_fixture(source)
                with zipfile.ZipFile(source) as package:
                    parts = {name: package.read(name) for name in package.namelist()}
                property_part = "docProps/review." + extension
                parts[property_part] = parts.pop("docProps/review-props.xml")
                root = etree.fromstring(parts["_rels/.rels"])
                next(item for item in root if item.get("Id") == "fictionalCustom").set("Target", property_part)
                parts["_rels/.rels"] = etree.tostring(root)
                root = etree.fromstring(parts["[Content_Types].xml"])
                root.remove(next(item for item in root if item.get("PartName") == "/docProps/review-props.xml"))
                old_default = next((item.get("ContentType") for item in root if item.get("Extension") == extension), None)
                existing_overrides = {item.get("PartName") for item in root if item.get("PartName")}
                if old_default:
                    for name in parts:
                        if name.endswith("." + extension) and name not in {"[Content_Types].xml", property_part} and "/" + name not in existing_overrides:
                            etree.SubElement(root, "{" + scrubber.CONTENT_NS + "}Override", PartName="/" + name, ContentType=old_default)
                for item in list(root):
                    if item.get("Extension") == extension:
                        root.remove(item)
                etree.SubElement(root, "{" + scrubber.CONTENT_NS + "}Default", Extension=extension,
                                 ContentType="application/vnd.openxmlformats-officedocument.custom-properties+xml")
                if overridden:
                    etree.SubElement(root, "{" + scrubber.CONTENT_NS + "}Override", PartName="/" + property_part,
                                     ContentType="application/xml")
                parts["[Content_Types].xml"] = etree.tostring(root)
                with zipfile.ZipFile(source, "w") as package:
                    for name, data in parts.items():
                        package.writestr(name, data)
                original = source.read_bytes()
                if overridden:
                    with self.assertRaisesRegex(ValueError, "expected content type"):
                        scrubber.scrub(source, output)
                    self.assertFalse(output.exists())
                else:
                    scrubber.scrub(source, output)
                    Document(output)
                    with zipfile.ZipFile(output) as package:
                        self.assertNotIn(property_part, package.namelist())
                        self.assertNotIn(b"application/vnd.openxmlformats-officedocument.custom-properties+xml", package.read("[Content_Types].xml"))
                        self.assertNotIn(property_part.encode(), package.read("_rels/.rels"))
                self.assertEqual(source.read_bytes(), original)

    def test_field_values_cannot_inject_another_placeholder(self):
        creator = script("create_letter")
        document = Document()
        paragraph = document.add_paragraph("ORGANIZATION NAME {{DATE}}")
        with self.assertRaisesRegex(ValueError, "field values"):
            creator.replace_simple(document, {"ORGANIZATION NAME": "{{DATE}}", "{{DATE}}": "Fictional date"})
        self.assertEqual(paragraph.text, "ORGANIZATION NAME {{DATE}}")

    def test_placeholder_value_containing_its_key_terminates(self):
        code = '''from docx import Document
from create_letter import _replace_in_runs
document = Document()
paragraph = document.add_paragraph("ORGANIZATION NAME and ORGANIZATION NAME")
_replace_in_runs(paragraph, "ORGANIZATION NAME", "NORTH ORGANIZATION NAME SERVICES")
assert paragraph.text == "NORTH ORGANIZATION NAME SERVICES and NORTH ORGANIZATION NAME SERVICES"
'''
        completed = subprocess.run([sys.executable, "-c", code], cwd=ROOT / "scripts", capture_output=True, text=True, timeout=3)
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_acceptance_refuses_structural_deletions_without_output(self):
        acceptor = script("accept_tracked_changes")
        for location, marker in (("paragraph", "del"), ("paragraph", "moveFrom"), ("row", "del"), ("row", "moveFrom")):
            with self.subTest(location=location, marker=marker), tempfile.TemporaryDirectory() as temporary:
                folder = Path(temporary)
                source, output = folder / "fictional.docx", folder / "clean.docx"
                document = Document()
                if location == "paragraph":
                    paragraph = document.add_paragraph("Merge this fictional paragraph.")
                    document.add_paragraph("With the following paragraph.")
                    props = paragraph._p.get_or_add_pPr()
                    run_props = OxmlElement("w:rPr")
                    run_props.append(OxmlElement("w:" + marker))
                    props.append(run_props)
                else:
                    table = document.add_table(rows=2, cols=1)
                    table.cell(0, 0).text = "Kept fictional row."
                    table.cell(1, 0).text = "Deleted fictional row."
                    props = table.rows[1]._tr.get_or_add_trPr()
                    props.append(OxmlElement("w:" + marker))
                document.save(source)
                before = source.read_bytes()
                with self.assertRaisesRegex(ValueError, "structural.*deletion"):
                    acceptor.accept(source, output)
                self.assertFalse(output.exists())
                self.assertEqual(source.read_bytes(), before)

    def test_scrubber_refuses_review_metadata_without_erasing_content(self):
        scrubber = script("scrub_docx_metadata")
        for kind in ("comments", "people", "revision"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as temporary:
                folder = Path(temporary)
                source, output = folder / "fictional.docx", folder / "scrubbed.docx"
                document = Document()
                paragraph = document.add_paragraph("Fictional clause.")
                if kind == "revision":
                    insertion = OxmlElement("w:ins")
                    insertion.set(qn("w:author"), "Fictional Reviewer")
                    paragraph._p.append(insertion)
                document.save(source)
                if kind != "revision":
                    with zipfile.ZipFile(source, "a") as package:
                        package.writestr("word/" + kind + ".xml", '<records author="Fictional Reviewer"/>')
                before = source.read_bytes()
                with self.assertRaisesRegex(ValueError, "review metadata"):
                    scrubber.scrub(source, output)
                self.assertFalse(output.exists())
                self.assertEqual(source.read_bytes(), before)

    def test_scrubber_clears_additional_core_metadata(self):
        scrubber = script("scrub_docx_metadata")
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            source, output = folder / "fictional.docx", folder / "scrubbed.docx"
            document = Document()
            document.add_paragraph("Fictional clean correspondence.")
            props = document.core_properties
            for field in ("title", "subject", "keywords", "comments", "category", "identifier", "content_status"):
                setattr(props, field, "Fictional confidential metadata")
            props.revision = 47
            document.save(source)
            scrubber.scrub(source, output)
            with zipfile.ZipFile(output) as package:
                core = etree.fromstring(package.read("docProps/core.xml"))
                self.assertNotIn(b"Fictional confidential metadata", etree.tostring(core))
                self.assertFalse(any(node.tag.rsplit("}", 1)[-1] == "revision" for node in core))
