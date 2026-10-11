from __future__ import annotations

import argparse
import io
import os
import stat
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from xml.etree import ElementTree


WORD_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
RELATIONSHIP_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
REVISION_WRAPPERS_REMOVE = {"del", "moveFrom"}
REVISION_WRAPPERS_UNWRAP = {"ins", "moveTo"}
REVISION_RANGE_MARKERS = {
    "moveFromRangeStart", "moveFromRangeEnd", "moveToRangeStart", "moveToRangeEnd",
}
UNSUPPORTED_REVISION_ELEMENTS = {
    "cellIns", "cellDel", "cellMerge", "conflictIns", "conflictDel",
    "customXmlInsRangeStart",
    "customXmlInsRangeEnd", "customXmlDelRangeStart", "customXmlDelRangeEnd",
    "customXmlMoveFromRangeStart", "customXmlMoveFromRangeEnd",
    "customXmlMoveToRangeStart", "customXmlMoveToRangeEnd", "numberingChange",
    "pPrChange", "rPrChange", "sectPrChange", "tblPrChange", "tblPrExChange",
    "tblGridChange", "trPrChange", "tcPrChange",
}
COMMENT_ELEMENTS = {"commentRangeStart", "commentRangeEnd", "commentReference"}
MAX_DOCX_BYTES = 100 * 1024 * 1024
MAX_DOCX_ENTRY_BYTES = 50 * 1024 * 1024
MAX_DOCX_UNCOMPRESSED_BYTES = 200 * 1024 * 1024
MAX_DOCX_ENTRIES = 10_000
REQUIRED_DOCX_PARTS = {"[Content_Types].xml", "_rels/.rels", "word/document.xml"}
CONTENT_TYPES_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
PACKAGE_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
MAIN_DOCUMENT_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"
OFFICE_DOCUMENT_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument"
REMOVED_REVISION_EXTERNAL_ELEMENTS = {
    "altChunk", "drawing", "endnoteReference", "footnoteReference", "object", "pict",
}


def require_lxml():
    try:
        from lxml import etree
    except ImportError as exc:
        raise SystemExit("lxml is required; install requirements-documents.txt") from exc
    return etree


def _local_name(element) -> str:
    return element.tag.rsplit("}", 1)[-1]


def _markers(root, names: set[str]) -> set[str]:
    return {
        _local_name(element)
        for element in root.iter()
        if element.tag.startswith(f"{{{WORD_NS}}}") and _local_name(element) in names
    }


def _parse_xml(data: bytes, etree):
    try:
        return etree.fromstring(data)
    except etree.XMLSyntaxError as exc:
        raise ValueError("input contains invalid Word XML") from exc


def _validate_docx_package(package: zipfile.ZipFile) -> None:
    infos = package.infolist()
    if len(infos) > MAX_DOCX_ENTRIES:
        raise ValueError("DOCX package contains too many entries")
    names = [info.filename for info in infos]
    if len(names) != len(set(names)):
        raise ValueError("DOCX package contains duplicate entries")
    if not REQUIRED_DOCX_PARTS.issubset(names):
        raise ValueError("input is not a valid Word DOCX package")
    total = 0
    for info in infos:
        parsed = PurePosixPath(info.filename)
        if parsed.is_absolute() or ".." in parsed.parts or "\\" in info.filename:
            raise ValueError("DOCX package contains an unsafe member name")
        if info.file_size > MAX_DOCX_ENTRY_BYTES:
            raise ValueError("DOCX package entry exceeds the uncompressed safety limit")
        total += info.file_size
        if total > MAX_DOCX_UNCOMPRESSED_BYTES:
            raise ValueError("DOCX package exceeds the uncompressed safety limit")
    try:
        types = ElementTree.fromstring(package.read("[Content_Types].xml"))
        relationships = ElementTree.fromstring(package.read("_rels/.rels"))
        document = ElementTree.fromstring(package.read("word/document.xml"))
    except ElementTree.ParseError as exc:
        raise ValueError("input is not a valid Word DOCX package") from exc
    overrides = {
        (item.get("PartName"), item.get("ContentType"))
        for item in types.findall(f"{{{CONTENT_TYPES_NS}}}Override")
    }
    office_targets = {
        item.get("Target", "").lstrip("/")
        for item in relationships.findall(f"{{{PACKAGE_REL_NS}}}Relationship")
        if item.get("Type") == OFFICE_DOCUMENT_REL and not item.get("TargetMode")
    }
    if (
        types.tag != f"{{{CONTENT_TYPES_NS}}}Types"
        or ("/word/document.xml", MAIN_DOCUMENT_TYPE) not in overrides
        or relationships.tag != f"{{{PACKAGE_REL_NS}}}Relationships"
        or "word/document.xml" not in office_targets
        or document.tag != f"{{{WORD_NS}}}document"
    ):
        raise ValueError("input is not a valid Word DOCX package")


def inspect_source(package: zipfile.ZipFile, etree) -> None:
    _validate_docx_package(package)
    problems = set()
    for name in package.namelist():
        if name.startswith("word/comments") and name.endswith(".xml"):
            problems.add("comments part")
        if not name.startswith("word/") or not name.endswith(".xml"):
            continue
        root = _parse_xml(package.read(name), etree)
        problems.update(f"comment marker {item}" for item in _markers(root, COMMENT_ELEMENTS))
        problems.update(
            f"unsupported revision marker {item}"
            for item in _markers(root, UNSUPPORTED_REVISION_ELEMENTS)
        )
        ns = {"w": WORD_NS}
        for revision in root.xpath(".//w:del | .//w:moveFrom", namespaces=ns):
            unsafe = set()
            for element in revision.iter():
                local = _local_name(element)
                if local in REMOVED_REVISION_EXTERNAL_ELEMENTS:
                    unsafe.add(local)
                if any(key.startswith(f"{{{RELATIONSHIP_NS}}}") for key in element.attrib):
                    unsafe.add("relationship reference")
            if unsafe:
                problems.add("removed revision contains external/package content: " + ", ".join(sorted(unsafe)))
    if problems:
        raise ValueError(
            "input contains comments or revision types that cannot be safely accepted: "
            + ", ".join(sorted(problems))
        )


def accept_xml(data: bytes, etree) -> bytes:
    root = _parse_xml(data, etree)
    ns = {"w": WORD_NS}
    for deletion in list(root.xpath(".//w:del | .//w:moveFrom", namespaces=ns)):
        parent = deletion.getparent()
        if parent is not None:
            parent.remove(deletion)
    for insertion in list(root.xpath(".//w:ins | .//w:moveTo", namespaces=ns)):
        parent = insertion.getparent()
        if parent is None:
            continue
        index = parent.index(insertion)
        for child in list(insertion):
            insertion.remove(child)
            parent.insert(index, child)
            index += 1
        parent.remove(insertion)
    for marker in list(root.xpath(
        ".//w:moveFromRangeStart | .//w:moveFromRangeEnd | "
        ".//w:moveToRangeStart | .//w:moveToRangeEnd | .//w:trackRevisions",
        namespaces=ns,
    )):
        parent = marker.getparent()
        if parent is not None:
            parent.remove(marker)
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)


def validate_clean(package: zipfile.ZipFile, etree) -> None:
    _validate_docx_package(package)
    forbidden = (
        REVISION_WRAPPERS_REMOVE | REVISION_WRAPPERS_UNWRAP | REVISION_RANGE_MARKERS
        | UNSUPPORTED_REVISION_ELEMENTS | {"trackRevisions"} | COMMENT_ELEMENTS
    )
    leftovers = set()
    for name in package.namelist():
        if name.startswith("word/comments") and name.endswith(".xml"):
            leftovers.add("comments part")
        if not name.startswith("word/") or not name.endswith(".xml"):
            continue
        root = _parse_xml(package.read(name), etree)
        leftovers.update(_markers(root, forbidden))
    if leftovers:
        raise ValueError("accepted copy still contains revision/tracking markers: " + ", ".join(sorted(leftovers)))


def _reject_symlink_parents(path: Path) -> None:
    current = path.parent
    root = Path(path.anchor)
    while current != current.parent:
        if current.is_symlink():
            metadata = current.lstat()
            if current.parent != root or getattr(metadata, "st_uid", -1) != 0:
                raise ValueError(f"output parent must not contain a symlink: {current}")
        current = current.parent


def _write_new(path: Path, data: bytes) -> None:
    _reject_symlink_parents(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    _reject_symlink_parents(path)
    descriptor, staged_name = tempfile.mkstemp(prefix=".lawyeredos-", dir=path.parent)
    staged = Path(staged_name)
    created = os.fstat(descriptor)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            descriptor = -1
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(staged, path, follow_symlinks=False)
        except FileExistsError as exc:
            raise ValueError("output already exists") from exc
    except BaseException:
        raise
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        try:
            current = staged.stat(follow_symlinks=False)
            if (created.st_dev, created.st_ino) == (current.st_dev, current.st_ino):
                staged.unlink()
        except OSError:
            pass


def _read_regular_bytes(path: Path) -> bytes:
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise ValueError("input must be a regular, non-symlink DOCX file") from exc
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise ValueError("input must be a regular, non-symlink DOCX file")
        if metadata.st_size > MAX_DOCX_BYTES:
            raise ValueError(f"input exceeds the {MAX_DOCX_BYTES}-byte safety limit")
        with os.fdopen(descriptor, "rb") as stream:
            descriptor = -1
            data = stream.read(MAX_DOCX_BYTES + 1)
            if len(data) > MAX_DOCX_BYTES:
                raise ValueError(f"input exceeds the {MAX_DOCX_BYTES}-byte safety limit")
            return data
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def accept(input_path: Path, output_path: Path) -> None:
    etree = require_lxml()
    if output_path.exists() or output_path.is_symlink():
        raise ValueError("output already exists")
    source_bytes = _read_regular_bytes(input_path)
    staged = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(source_bytes)) as source:
        inspect_source(source, etree)
        with zipfile.ZipFile(staged, "w", zipfile.ZIP_DEFLATED) as target:
            for info in source.infolist():
                data = source.read(info.filename)
                if info.filename.startswith("word/") and info.filename.endswith(".xml"):
                    data = accept_xml(data, etree)
                target.writestr(info, data)
    generated = staged.getvalue()
    with zipfile.ZipFile(io.BytesIO(generated)) as package:
        validate_clean(package, etree)
    _write_new(output_path, generated)


def main() -> int:
    parser = argparse.ArgumentParser(description="Accept Word tracked changes in a DOCX copy")
    parser.add_argument("input")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    try:
        accept(Path(args.input).expanduser().absolute(), Path(args.output).expanduser().absolute())
        return 0
    except (ValueError, OSError, zipfile.BadZipFile) as exc:
        print(f"error: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
