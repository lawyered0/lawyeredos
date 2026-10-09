from __future__ import annotations

import argparse
import os
import tempfile
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET


CORE_REMOVE = {
    "{http://purl.org/dc/elements/1.1/}creator",
    "{http://schemas.openxmlformats.org/package/2006/metadata/core-properties}lastModifiedBy",
    "{http://purl.org/dc/terms/}created",
    "{http://purl.org/dc/terms/}modified",
    "{http://schemas.openxmlformats.org/package/2006/metadata/core-properties}lastPrinted",
}
W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
W14_NS = "http://schemas.microsoft.com/office/word/2010/wordml"
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
CONTENT_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
APP_NS = "http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"


def local_name(value: str) -> str:
    return value.rsplit("}", 1)[-1]


def scrub_xml(name: str, data: bytes) -> bytes:
    root = ET.fromstring(data)
    changed = False
    if name == "docProps/core.xml":
        for child in list(root):
            if child.tag in CORE_REMOVE:
                root.remove(child)
                changed = True
    if name == "docProps/app.xml":
        for child in list(root):
            if local_name(child.tag) in {"Company", "Manager", "Template", "HyperlinkBase", "AppVersion"}:
                root.remove(child)
                changed = True
            elif local_name(child.tag) == "Application":
                child.text = "Office Open XML"
                changed = True
    if name.startswith("word/") and name.endswith(".xml"):
        for element in root.iter():
            for attribute in list(element.attrib):
                if attribute.startswith(f"{{{W_NS}}}rsid"):
                    del element.attrib[attribute]
                    changed = True
        for parent in root.iter():
            for child in list(parent):
                if child.tag in {
                    f"{{{W14_NS}}}docId",
                    f"{{{W_NS}}}rsid",
                    f"{{{W_NS}}}rsids",
                }:
                    parent.remove(child)
                    changed = True
    if name.endswith(".rels"):
        for relationship in list(root):
            if relationship.tag == f"{{{REL_NS}}}Relationship" and "customXml" in relationship.get("Target", ""):
                root.remove(relationship)
                changed = True
    if name == "[Content_Types].xml":
        for child in list(root):
            if child.tag == f"{{{CONTENT_NS}}}Override" and child.get("PartName", "").startswith("/customXml/"):
                root.remove(child)
                changed = True
    if not changed:
        return data
    if name.endswith(".rels"):
        ET.register_namespace("", REL_NS)
    elif name == "[Content_Types].xml":
        ET.register_namespace("", CONTENT_NS)
    elif name == "docProps/app.xml":
        ET.register_namespace("", APP_NS)
        ET.register_namespace("vt", "http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes")
    elif name == "docProps/core.xml":
        ET.register_namespace("cp", "http://schemas.openxmlformats.org/package/2006/metadata/core-properties")
        ET.register_namespace("dc", "http://purl.org/dc/elements/1.1/")
        ET.register_namespace("dcterms", "http://purl.org/dc/terms/")
        ET.register_namespace("dcmitype", "http://purl.org/dc/dcmitype/")
        ET.register_namespace("xsi", "http://www.w3.org/2001/XMLSchema-instance")
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def scrub(source: Path, output: Path) -> None:
    if not source.is_file() or source.is_symlink() or source.suffix.casefold() != ".docx":
        raise ValueError("source must be a regular DOCX file")
    if output.exists():
        raise ValueError("output already exists")
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(source) as input_package, zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as result:
        for info in input_package.infolist():
            if info.filename.startswith("customXml/") or info.filename == "docProps/custom.xml":
                continue
            data = input_package.read(info.filename)
            if info.filename.endswith((".xml", ".rels")):
                data = scrub_xml(info.filename, data)
            result.writestr(info, data)


def scrub_in_place(path: Path) -> None:
    descriptor, name = tempfile.mkstemp(prefix=".metadata-scrub-", suffix=".docx", dir=path.parent)
    os.close(descriptor)
    temporary = Path(name)
    temporary.unlink()
    try:
        scrub(path, temporary)
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def main() -> int:
    parser = argparse.ArgumentParser(description="Remove identifying DOCX package metadata")
    parser.add_argument("input")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    try:
        scrub(Path(args.input).expanduser().resolve(), Path(args.output).expanduser().resolve())
        return 0
    except (ValueError, OSError, ET.ParseError, zipfile.BadZipFile) as exc:
        print(f"error: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
