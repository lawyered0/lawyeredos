from __future__ import annotations

import argparse
import io
import os
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree


PLACEHOLDER = re.compile(r"\{\{[A-Z][A-Z0-9_]*\}\}")
WORD_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
REVISION_ELEMENTS = {
    "ins", "del", "moveFrom", "moveTo", "moveFromRangeStart",
    "moveFromRangeEnd", "moveToRangeStart", "moveToRangeEnd", "cellIns",
    "cellDel", "cellMerge", "conflictIns", "conflictDel", "trackRevisions",
    "customXmlInsRangeStart", "customXmlInsRangeEnd",
    "customXmlDelRangeStart", "customXmlDelRangeEnd", "customXmlMoveFromRangeStart",
    "customXmlMoveFromRangeEnd", "customXmlMoveToRangeStart",
    "customXmlMoveToRangeEnd", "numberingChange", "pPrChange", "rPrChange",
    "sectPrChange", "tblPrChange", "tblGridChange", "trPrChange", "tcPrChange",
}
COMMENT_ELEMENTS = {"commentRangeStart", "commentRangeEnd", "commentReference"}


def require_docx():
    try:
        from docx import Document
        from docx.oxml import OxmlElement
    except ImportError as exc:
        raise SystemExit("python-docx is required; install requirements-documents.txt") from exc
    return Document, OxmlElement


def _paragraphs_in(parent):
    """Yield paragraphs in a document/header/footer, including table cells."""
    seen = set()

    def walk(container):
        for paragraph in container.paragraphs:
            marker = id(paragraph._p)
            if marker not in seen:
                seen.add(marker)
                yield paragraph
        for table in container.tables:
            for row in table.rows:
                for cell in row.cells:
                    yield from walk(cell)

    yield from walk(parent)


def _replace_in_runs(paragraph, key: str, value: str) -> None:
    """Replace a possibly split placeholder without flattening other runs."""
    while True:
        runs = list(paragraph.runs)
        combined = "".join(run.text for run in runs)
        start = combined.find(key)
        if start < 0:
            return
        end = start + len(key)
        offsets = []
        cursor = 0
        for run in runs:
            offsets.append((cursor, cursor + len(run.text)))
            cursor += len(run.text)
        touched = [i for i, (left, right) in enumerate(offsets) if left < end and right > start]
        if not touched:
            return
        first, last = touched[0], touched[-1]
        first_left, _ = offsets[first]
        last_left, _ = offsets[last]
        prefix = runs[first].text[:start - first_left]
        suffix = runs[last].text[end - last_left:]
        runs[first].text = prefix + value + (suffix if first == last else "")
        if first != last:
            for index in touched[1:-1]:
                runs[index].text = ""
            runs[last].text = suffix


def replace_simple(document, mapping: dict[str, str]) -> None:
    paragraphs = list(_paragraphs_in(document))
    for section in document.sections:
        paragraphs.extend(_paragraphs_in(section.header))
        paragraphs.extend(_paragraphs_in(section.footer))
    for paragraph in paragraphs:
        for key, value in mapping.items():
            _replace_in_runs(paragraph, key, value)


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


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def package_review_markers(package: zipfile.ZipFile) -> list[str]:
    markers = set()
    for name in package.namelist():
        if name.startswith("word/comments") and name.endswith(".xml"):
            markers.add("comments part")
        if not name.startswith("word/") or not name.endswith(".xml"):
            continue
        root = ElementTree.fromstring(package.read(name))
        for element in root.iter():
            local = _local_name(element.tag)
            if element.tag.startswith(f"{{{WORD_NS}}}") and local in REVISION_ELEMENTS:
                markers.add(f"revision marker {local}")
            if element.tag.startswith(f"{{{WORD_NS}}}") and local in COMMENT_ELEMENTS:
                markers.add(f"comment marker {local}")
    return sorted(markers)


def package_placeholders(package: zipfile.ZipFile) -> list[str]:
    unresolved = set()
    for name in package.namelist():
        if not name.startswith("word/") or not name.endswith(".xml"):
            continue
        root = ElementTree.fromstring(package.read(name))
        unresolved.update(PLACEHOLDER.findall("".join(root.itertext())))
    return sorted(unresolved)


def _reject_symlink_parents(path: Path) -> None:
    # Refuse a caller-supplied symlink directory without rejecting platform
    # aliases such as macOS /var -> /private/var farther up the absolute path.
    if path.parent.is_symlink():
        raise ValueError(f"output parent must not be a symlink: {path.parent}")


def _write_new(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    _reject_symlink_parents(path)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags, 0o600)
    except FileExistsError as exc:
        raise ValueError("output already exists") from exc
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        try:
            path.unlink()
        except OSError:
            pass
        raise


def create(args: argparse.Namespace) -> None:
    Document, OxmlElement = require_docx()
    template_input = Path(args.template).expanduser()
    if template_input.is_symlink():
        raise ValueError("template must be a regular file")
    template = template_input.resolve()
    output = Path(args.output).expanduser().absolute()
    if not template.is_file():
        raise ValueError("template must be a regular file")
    if output.exists() or output.is_symlink():
        raise ValueError("output already exists")
    with zipfile.ZipFile(template) as package:
        review_markers = package_review_markers(package)
    if review_markers:
        raise ValueError("template contains pre-existing revision/comment markup: " + ", ".join(review_markers))
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
    scrub(document, args.author)
    staged = io.BytesIO()
    document.save(staged)
    generated = staged.getvalue()
    with zipfile.ZipFile(io.BytesIO(generated)) as package:
        unresolved = package_placeholders(package)
        if unresolved:
            raise ValueError(f"unresolved template placeholders: {unresolved}")
        if "docProps/custom.xml" in package.namelist():
            raise ValueError("custom properties remain in output")
        if package_review_markers(package):
            raise ValueError("generated output contains revision/comment markup")
    _write_new(output, generated)


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
