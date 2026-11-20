# Selected fictional metadata regressions from public PR #18.
# Source head: 9612dfea07914eb093f167a7c269fa6c1d10db18.
"""Synthetic regression fixtures; no matter files or mail are used."""
from __future__ import annotations

import importlib.util
import sys
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path
from xml.etree.ElementTree import ParseError

from docx import Document
from lxml import etree

ROOT = Path(__file__).resolve().parents[1]
MC = "http://schemas.openxmlformats.org/markup-compatibility/2006"
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def script(name):
    sys.path.insert(0, str(ROOT / "scripts"))
    try:
        spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / (name + ".py"))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.pop(0)


class MetadataIntegrityTests(unittest.TestCase):
    def test_bundled_template_retains_valid_compatibility_namespaces(self):
        with zipfile.ZipFile(ROOT / "assets" / "neutral-letterhead.docx") as package:
            for name in package.namelist():
                if name.endswith(".xml"):
                    for element in etree.fromstring(package.read(name)).iter():
                        for prefix in element.get("{" + MC + "}Ignorable", "").split():
                            self.assertIn(prefix, element.nsmap, name)
    def test_scrub_preserves_namespace_bindings_for_ignorable_prefixes(self):
        helper = script("scrub_docx_metadata")
        xml = (f'<w:document xmlns:w="{W}" xmlns:mc="{MC}" '
               'xmlns:w14="http://schemas.microsoft.com/office/word/2010/wordml" '
               'mc:Ignorable="w14"><w:body><w:p w:rsidR="00112233"/></w:body></w:document>')
        root = etree.fromstring(helper.scrub_xml("word/document.xml", xml.encode()))
        for prefix in root.get("{" + MC + "}Ignorable").split():
            self.assertIn(prefix, root.nsmap)
        self.assertNotIn("{" + W + "}rsidR", root.find(".//{" + W + "}p").attrib)

    def test_generated_template_retains_valid_compatibility_namespaces(self):
        builder = script("build_neutral_template")
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "neutral.docx"
            builder.build(output)
            Document(output)
            with zipfile.ZipFile(output) as package:
                for name in package.namelist():
                    if name.endswith(".xml"):
                        root = etree.fromstring(package.read(name))
                        for element in root.iter():
                            for prefix in element.get("{" + MC + "}Ignorable", "").split():
                                self.assertIn(prefix, element.nsmap, name)

    def test_scrub_invalid_xml_leaves_no_partial_output(self):
        helper = script("scrub_docx_metadata")
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            source, output = folder / "fictional.docx", folder / "scrubbed.docx"
            Document().save(source)
            with zipfile.ZipFile(source) as package:
                parts = {name: package.read(name) for name in package.namelist()}
            parts["docProps/core.xml"] = b"<broken"
            with zipfile.ZipFile(source, "w") as package:
                for name, data in parts.items():
                    package.writestr(name, data)
            with self.assertRaises((ValueError, etree.XMLSyntaxError, ParseError)):
                helper.scrub(source, output)
            self.assertFalse(output.exists())

    def test_custom_properties_are_removed_with_package_references(self):
        helper = script("scrub_docx_metadata")
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            source, output = folder / "fictional.docx", folder / "scrubbed.docx"
            Document().save(source)
            with zipfile.ZipFile(source) as package:
                parts = {name: package.read(name) for name in package.namelist()}
            root = etree.fromstring(parts["_rels/.rels"])
            etree.SubElement(root, "{" + helper.REL_NS + "}Relationship", Id="fictionalCustom", Target="docProps/custom.xml", Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/custom-properties")
            parts["_rels/.rels"] = etree.tostring(root)
            root = etree.fromstring(parts["[Content_Types].xml"])
            etree.SubElement(root, "{" + helper.CONTENT_NS + "}Override", PartName="/docProps/custom.xml", ContentType="application/vnd.openxmlformats-officedocument.custom-properties+xml")
            parts["[Content_Types].xml"] = etree.tostring(root)
            parts["docProps/custom.xml"] = b'<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/custom-properties"/>'
            with zipfile.ZipFile(source, "w") as package:
                for name, data in parts.items():
                    package.writestr(name, data)
            helper.scrub(source, output)
            with zipfile.ZipFile(output) as package:
                self.assertNotIn("docProps/custom.xml", package.namelist())
                self.assertNotIn(b"docProps/custom.xml", package.read("_rels/.rels"))
                self.assertNotIn(b"docProps/custom.xml", package.read("[Content_Types].xml"))
from docx.oxml import OxmlElement
from docx.oxml.ns import qn


class SelectedCustomPropertyTests(unittest.TestCase):
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

    def test_scrubber_refuses_conflicting_content_type_declarations(self):
        scrubber = script("scrub_docx_metadata")
        for declaration in ("Override", "Default"):
            with self.subTest(declaration=declaration), tempfile.TemporaryDirectory() as temporary:
                source, output = Path(temporary) / "fictional.docx", Path(temporary) / "scrubbed.docx"
                self._custom_property_fixture(source, orphan=True)
                with zipfile.ZipFile(source) as package:
                    parts = {name: package.read(name) for name in package.namelist()}
                root = etree.fromstring(parts["[Content_Types].xml"])
                if declaration == "Override":
                    etree.SubElement(root, "{" + scrubber.CONTENT_NS + "}Override", PartName="/docProps/review-props.xml",
                                     ContentType="application/xml")
                else:
                    parts["docProps/review.reviewprops"] = parts.pop("docProps/review-props.xml")
                    root.remove(next(item for item in root if item.get("PartName") == "/docProps/review-props.xml"))
                    for content_type in ("application/vnd.openxmlformats-officedocument.custom-properties+xml", "application/xml"):
                        etree.SubElement(root, "{" + scrubber.CONTENT_NS + "}Default", Extension="reviewprops", ContentType=content_type)
                parts["[Content_Types].xml"] = etree.tostring(root)
                with zipfile.ZipFile(source, "w") as package:
                    for name, data in parts.items():
                        package.writestr(name, data)
                original = source.read_bytes()
                with self.assertRaisesRegex(ValueError, "conflicting content-type"):
                    scrubber.scrub(source, output)
                self.assertEqual(source.read_bytes(), original)
                self.assertFalse(output.exists())

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
