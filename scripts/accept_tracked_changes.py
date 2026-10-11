from __future__ import annotations

import argparse
import io
import os
import zipfile
from pathlib import Path


WORD_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
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
    "pPrChange", "rPrChange", "sectPrChange", "tblPrChange", "tblGridChange",
    "trPrChange", "tcPrChange",
}
COMMENT_ELEMENTS = {"commentRangeStart", "commentRangeEnd", "commentReference"}


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


def inspect_source(package: zipfile.ZipFile, etree) -> None:
    problems = set()
    for name in package.namelist():
        if name.startswith("word/comments") and name.endswith(".xml"):
            problems.add("comments part")
        if not name.startswith("word/") or not name.endswith(".xml"):
            continue
        root = etree.fromstring(package.read(name))
        problems.update(f"comment marker {item}" for item in _markers(root, COMMENT_ELEMENTS))
        problems.update(
            f"unsupported revision marker {item}"
            for item in _markers(root, UNSUPPORTED_REVISION_ELEMENTS)
        )
    if problems:
        raise ValueError(
            "input contains comments or revision types that cannot be safely accepted: "
            + ", ".join(sorted(problems))
        )


def accept_xml(data: bytes, etree) -> bytes:
    root = etree.fromstring(data)
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
        root = etree.fromstring(package.read(name))
        leftovers.update(_markers(root, forbidden))
    if leftovers:
        raise ValueError("accepted copy still contains revision/tracking markers: " + ", ".join(sorted(leftovers)))


def _reject_symlink_parents(path: Path) -> None:
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


def accept(input_path: Path, output_path: Path) -> None:
    etree = require_lxml()
    if not input_path.is_file() or input_path.is_symlink():
        raise ValueError("input must be a regular DOCX file")
    if output_path.exists() or output_path.is_symlink():
        raise ValueError("output already exists")
    staged = io.BytesIO()
    with zipfile.ZipFile(input_path) as source:
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
