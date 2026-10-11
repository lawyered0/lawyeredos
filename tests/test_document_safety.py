from __future__ import annotations

import importlib.util
import tempfile
import unittest
import zipfile
from pathlib import Path
from xml.etree import ElementTree


ROOT = Path(__file__).resolve().parents[1]


def load_script(name: str):
    path = ROOT / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"document_safety_{name}", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def letter_args(template: Path, body: Path, output: Path):
    return type("Args", (), {
        "template": str(template),
        "body_file": str(body),
        "output": str(output),
        "organization": "Northstar Legal Lab",
        "date": "October 11, 2026",
        "recipient": "Alex Example",
        "address": "100 Example Street",
        "subject": "Fictional matter",
        "signoff": "Example Counsel",
        "author": "Authorized reviewer",
    })()


class DocumentSafetyTests(unittest.TestCase):
    def setUp(self):
        try:
            from docx import Document  # noqa: F401
            from lxml import etree  # noqa: F401
        except ImportError:
            self.skipTest("document dependencies are not installed")

    def _template(self, folder: Path) -> Path:
        from docx import Document

        path = folder / "template.docx"
        document = Document()
        date = document.add_paragraph()
        lead = date.add_run("Date: ")
        lead.italic = True
        marker = date.add_run("{{DA")
        marker.bold = True
        date.add_run("TE}}")
        tail = date.add_run(" — private draft")
        tail.underline = True
        document.add_paragraph("{{BODY}}")
        header_cell = document.sections[0].header.add_table(1, 1, 6_000_000).cell(0, 0)
        header = header_cell.paragraphs[0]
        header.add_run("ORGAN")
        header.add_run("IZATION NAME")
        document.save(path)
        return path

    def test_letter_replaces_split_markers_without_flattening_styles(self):
        from docx import Document

        creator = load_script("create_letter")
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            template = self._template(folder)
            body = folder / "body.txt"
            body.write_text("This is fictional correspondence.", encoding="utf-8")
            output = folder / "letter.docx"
            creator.create(letter_args(template, body, output))

            document = Document(output)
            date = document.paragraphs[0]
            self.assertEqual(date.text, "Date: October 11, 2026 — private draft")
            self.assertTrue(date.runs[0].italic)
            self.assertTrue(date.runs[1].bold)
            self.assertTrue(date.runs[-1].underline)
            header = document.sections[0].header.tables[0].cell(0, 0).text
            self.assertEqual(header, "Northstar Legal Lab")

    def test_letter_refuses_review_markup_and_does_not_publish(self):
        from docx import Document
        from docx.oxml import OxmlElement

        creator = load_script("create_letter")
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            template = self._template(folder)
            document = Document(template)
            document.paragraphs[0]._p.append(OxmlElement("w:ins"))
            document.save(template)
            body = folder / "body.txt"
            body.write_text("Fictional body.", encoding="utf-8")
            output = folder / "letter.docx"
            with self.assertRaisesRegex(ValueError, "pre-existing revision/comment"):
                creator.create(letter_args(template, body, output))
            self.assertFalse(output.exists())

            linked_template = folder / "linked-template.docx"
            linked_template.symlink_to(template)
            with self.assertRaisesRegex(ValueError, "template must be a regular file"):
                creator.create(letter_args(linked_template, body, output))
            self.assertFalse(output.exists())

    def test_acceptance_removes_revisions_and_track_revisions_setting(self):
        from docx import Document

        vendor = ROOT / "vendor" / "legal-redline-tools"
        import sys
        sys.path.insert(0, str(vendor))
        try:
            from legal_redline import apply_redlines
        finally:
            sys.path.pop(0)
        accepter = load_script("accept_tracked_changes")
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            source = folder / "source.docx"
            redlined = folder / "redlined.docx"
            accepted = folder / "accepted.docx"
            document = Document()
            document.add_paragraph("Payment is due in thirty days.")
            document.save(source)
            apply_redlines(str(source), str(redlined), [{
                "type": "replace", "old": "thirty days", "new": "forty-five days",
            }])
            accepter.accept(redlined, accepted)
            local_tags = set()
            with zipfile.ZipFile(accepted) as package:
                for name in package.namelist():
                    if name.startswith("word/") and name.endswith(".xml"):
                        root = ElementTree.fromstring(package.read(name))
                        local_tags.update(element.tag.rsplit("}", 1)[-1] for element in root.iter())
            for marker in ("ins", "del", "trackRevisions"):
                self.assertNotIn(marker, local_tags)
            self.assertIn("forty-five days", Document(accepted).paragraphs[0].text)

    def test_acceptance_refuses_comments_and_unsupported_property_revisions(self):
        from docx import Document
        from docx.oxml import OxmlElement

        accepter = load_script("accept_tracked_changes")
        for marker in ("w:commentReference", "w:pPrChange"):
            with self.subTest(marker=marker), tempfile.TemporaryDirectory() as temporary:
                folder = Path(temporary)
                source = folder / "source.docx"
                output = folder / "accepted.docx"
                document = Document()
                paragraph = document.add_paragraph("Fictional clause.")
                if marker == "w:pPrChange":
                    paragraph._p.get_or_add_pPr().append(OxmlElement(marker))
                else:
                    paragraph._p.append(OxmlElement(marker))
                document.save(source)
                with self.assertRaisesRegex(ValueError, "cannot be safely accepted"):
                    accepter.accept(source, output)
                self.assertFalse(output.exists())

    def test_letter_output_collision_and_symlink_leave_target_unchanged(self):
        creator = load_script("create_letter")
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            template = self._template(folder)
            body = folder / "body.txt"
            body.write_text("Fictional body.", encoding="utf-8")
            existing = folder / "existing.docx"
            existing.write_bytes(b"do not replace")
            with self.assertRaisesRegex(ValueError, "output already exists"):
                creator.create(letter_args(template, body, existing))
            self.assertEqual(existing.read_bytes(), b"do not replace")

            victim = folder / "victim.docx"
            victim.write_bytes(b"victim")
            link = folder / "linked-output.docx"
            link.symlink_to(victim)
            with self.assertRaisesRegex(ValueError, "output already exists"):
                creator.create(letter_args(template, body, link))
            self.assertEqual(victim.read_bytes(), b"victim")

    def test_acceptance_output_collision_and_symlink_leave_target_unchanged(self):
        from docx import Document

        accepter = load_script("accept_tracked_changes")
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            source = folder / "source.docx"
            document = Document()
            document.add_paragraph("Fictional clean clause.")
            document.save(source)

            existing = folder / "existing.docx"
            existing.write_bytes(b"do not replace")
            with self.assertRaisesRegex(ValueError, "output already exists"):
                accepter.accept(source, existing)
            self.assertEqual(existing.read_bytes(), b"do not replace")

            victim = folder / "victim.docx"
            victim.write_bytes(b"victim")
            link = folder / "linked-output.docx"
            link.symlink_to(victim)
            with self.assertRaisesRegex(ValueError, "output already exists"):
                accepter.accept(source, link)
            self.assertEqual(victim.read_bytes(), b"victim")


if __name__ == "__main__":
    unittest.main()
