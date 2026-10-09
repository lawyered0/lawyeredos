from __future__ import annotations

import argparse
import re
import zipfile
from pathlib import Path


PLACEHOLDER = re.compile(r"\{\{[A-Z][A-Z0-9_]*\}\}")


def require_docx():
    try:
        from docx import Document
        from docx.oxml import OxmlElement
    except ImportError as exc:
        raise SystemExit("python-docx is required; install requirements-documents.txt") from exc
    return Document, OxmlElement


def replace_simple(document, mapping: dict[str, str]) -> None:
    containers = [document, *document.sections]
    paragraphs = list(document.paragraphs)
    for section in document.sections:
        paragraphs.extend(section.header.paragraphs)
        paragraphs.extend(section.footer.paragraphs)
    for paragraph in paragraphs:
        combined = "".join(run.text for run in paragraph.runs)
        if not any(key in combined for key in mapping):
            continue
        for key, value in mapping.items():
            combined = combined.replace(key, value)
        if paragraph.runs:
            paragraph.runs[0].text = combined
            for run in paragraph.runs[1:]:
                run.text = ""


def replace_body(document, body_text: str, OxmlElement) -> None:
    target = next((paragraph for paragraph in document.paragraphs if "{{BODY}}" in paragraph.text), None)
    if target is None:
        raise ValueError("template is missing {{BODY}}")
    blocks = [block.strip() for block in re.split(r"\n\s*\n", body_text.strip()) if block.strip()]
    if not blocks:
        raise ValueError("body is empty")
    for block in blocks:
        paragraph_xml = OxmlElement("w:p")
        target._p.addprevious(paragraph_xml)
        from docx.text.paragraph import Paragraph
        paragraph = Paragraph(paragraph_xml, target._parent)
        paragraph.style = target.style
        paragraph.add_run(block)
    target._element.getparent().remove(target._element)


def scrub(document, author: str) -> None:
    props = document.core_properties
    props.author = author
    props.last_modified_by = author
    props.title = "Correspondence"
    props.subject = ""
    props.comments = ""
    props.keywords = ""
    props.category = ""


def create(args: argparse.Namespace) -> None:
    Document, OxmlElement = require_docx()
    template = Path(args.template).expanduser().resolve()
    output = Path(args.output).expanduser().resolve()
    if not template.is_file() or template.is_symlink():
        raise ValueError("template must be a regular file")
    if output.exists():
        raise ValueError("output already exists")
    body = Path(args.body_file).read_text(encoding="utf-8")
    if PLACEHOLDER.search(body):
        raise ValueError("body contains an unresolved template placeholder")
    document = Document(template)
    replace_body(document, body, OxmlElement)
    replace_simple(document, {
        "ORGANIZATION NAME": args.organization,
        "{{DATE}}": args.date,
        "{{RECIPIENT}}": args.recipient,
        "{{ADDRESS}}": args.address,
        "{{SUBJECT}}": args.subject,
        "{{SIGNOFF}}": args.signoff,
    })
    unresolved = []
    for paragraph in document.paragraphs:
        unresolved.extend(PLACEHOLDER.findall(paragraph.text))
    for section in document.sections:
        unresolved.extend(PLACEHOLDER.findall("\n".join(p.text for p in section.header.paragraphs)))
        unresolved.extend(PLACEHOLDER.findall("\n".join(p.text for p in section.footer.paragraphs)))
    if unresolved:
        raise ValueError(f"unresolved template placeholders: {sorted(set(unresolved))}")
    scrub(document, args.author)
    output.parent.mkdir(parents=True, exist_ok=True)
    document.save(output)
    with zipfile.ZipFile(output) as package:
        if "docProps/custom.xml" in package.namelist():
            raise ValueError("custom properties remain in output")


def main() -> int:
    parser = argparse.ArgumentParser(description="Create neutral DOCX correspondence")
    parser.add_argument("--template", required=True)
    parser.add_argument("--body-file", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--organization", required=True)
    parser.add_argument("--date", required=True)
    parser.add_argument("--recipient", required=True)
    parser.add_argument("--address", required=True)
    parser.add_argument("--subject", required=True)
    parser.add_argument("--signoff", required=True)
    parser.add_argument("--author", default="Authorized reviewer")
    args = parser.parse_args()
    try:
        create(args)
        return 0
    except (ValueError, OSError) as exc:
        print(f"error: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
