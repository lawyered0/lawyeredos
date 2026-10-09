from __future__ import annotations

import argparse
import zipfile
from pathlib import Path


WORD_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def require_lxml():
    try:
        from lxml import etree
    except ImportError as exc:
        raise SystemExit("lxml is required; install requirements-documents.txt") from exc
    return etree


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
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)


def accept(input_path: Path, output_path: Path) -> None:
    etree = require_lxml()
    if not input_path.is_file() or input_path.is_symlink():
        raise ValueError("input must be a regular DOCX file")
    if output_path.exists():
        raise ValueError("output already exists")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(input_path) as source, zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as target:
        for info in source.infolist():
            data = source.read(info.filename)
            if info.filename.startswith("word/") and info.filename.endswith(".xml"):
                data = accept_xml(data, etree)
            target.writestr(info, data)


def main() -> int:
    parser = argparse.ArgumentParser(description="Accept Word tracked changes in a DOCX copy")
    parser.add_argument("input")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    try:
        accept(Path(args.input).expanduser().resolve(), Path(args.output).expanduser().resolve())
        return 0
    except (ValueError, OSError, zipfile.BadZipFile) as exc:
        print(f"error: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
