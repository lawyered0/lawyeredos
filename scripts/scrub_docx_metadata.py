from __future__ import annotations

import argparse
import io
import os
import posixpath
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlsplit
from accept_tracked_changes import _validate_docx_package


def require_lxml():
    try:
        from lxml import etree
    except ImportError as exc:
        raise ValueError("lxml is required; install requirements-documents.txt") from exc
    return etree


CORE_REMOVE = {
    "{http://purl.org/dc/elements/1.1/}creator",
    "{http://schemas.openxmlformats.org/package/2006/metadata/core-properties}lastModifiedBy",
    "{http://purl.org/dc/terms/}created",
    "{http://purl.org/dc/terms/}modified",
    "{http://schemas.openxmlformats.org/package/2006/metadata/core-properties}lastPrinted",
    "{http://purl.org/dc/elements/1.1/}title",
    "{http://purl.org/dc/elements/1.1/}subject",
    "{http://purl.org/dc/elements/1.1/}description",
    "{http://purl.org/dc/elements/1.1/}identifier",
    "{http://schemas.openxmlformats.org/package/2006/metadata/core-properties}keywords",
    "{http://schemas.openxmlformats.org/package/2006/metadata/core-properties}category",
    "{http://schemas.openxmlformats.org/package/2006/metadata/core-properties}revision",
    "{http://schemas.openxmlformats.org/package/2006/metadata/core-properties}contentStatus",
}
W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
W14_NS = "http://schemas.microsoft.com/office/word/2010/wordml"
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
CONTENT_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
APP_NS = "http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"
CUSTOM_NS = "http://schemas.openxmlformats.org/officeDocument/2006/custom-properties"
CUSTOM_TYPE = "application/vnd.openxmlformats-officedocument.custom-properties+xml"


def local_name(value: str) -> str:
    return value.rsplit("}", 1)[-1] if isinstance(value, str) else ""


def _custom_property_parts(package: zipfile.ZipFile) -> set[str]:
    """Find declared custom-property parts without trusting a fixed filename."""
    etree = require_lxml()
    parser = etree.XMLParser(resolve_entities=False, no_network=True)

    def parse(name):
        try:
            return etree.fromstring(package.read(name), parser)
        except etree.XMLSyntaxError as exc:
            raise ValueError("input contains invalid DOCX XML") from exc

    def local_part(target, base=""):
        uri = urlsplit(target)
        decoded = unquote(uri.path)
        if uri.scheme or uri.netloc or uri.query or uri.fragment or not decoded or "\\" in decoded:
            raise ValueError("custom-property target must be a local package part")
        part = posixpath.normpath(decoded.lstrip("/") if decoded.startswith("/") else posixpath.join(base, decoded))
        if part in {".", ".."} or part.startswith("../"):
            raise ValueError("custom-property target escapes the package")
        return part

    declarations = parse("[Content_Types].xml")
    overrides, defaults = {}, {}
    for item in declarations:
        if item.tag == f"{{{CONTENT_NS}}}Override":
            table, key = overrides, local_part(item.get("PartName", ""))
        elif item.tag == f"{{{CONTENT_NS}}}Default":
            table, key = defaults, item.get("Extension", "").casefold()
        else:
            continue
        content_type = item.get("ContentType")
        if key in table and table[key] != content_type:
            raise ValueError("custom-property discovery found conflicting content-type declarations")
        table[key] = content_type

    def effective_type(part):
        return overrides.get(part, defaults.get(PurePosixPath(part).suffix.lstrip(".").casefold()))

    parts = {part for part, content_type in overrides.items() if content_type == CUSTOM_TYPE}
    parts.update(part for part in package.namelist()
                 if part != "[Content_Types].xml" and effective_type(part) == CUSTOM_TYPE)
    for name in package.namelist():
        if not name.endswith(".rels"):
            continue
        base = "" if name == "_rels/.rels" else str(PurePosixPath(name).parent.parent)
        for item in parse(name):
            if item.tag != f"{{{REL_NS}}}Relationship" or not item.get("Type", "").endswith("/custom-properties"):
                continue
            if item.get("TargetMode") not in {None, "Internal"}:
                raise ValueError("custom-property target must be a local package part")
            target = local_part(item.get("Target", ""), base)
            if effective_type(target) != CUSTOM_TYPE:
                raise ValueError("custom-property target lacks its expected content type")
            parts.add(target)
    for part in parts:
        if part not in package.namelist():
            raise ValueError("custom-property part is missing from the package")
        if parse(part).tag != f"{{{CUSTOM_NS}}}Properties":
            raise ValueError("custom-property part has an unexpected XML root")
    return parts


def scrub_xml(name: str, data: bytes) -> bytes:
    etree = require_lxml()
    try:
        root = etree.fromstring(data, etree.XMLParser(resolve_entities=False, no_network=True))
    except etree.XMLSyntaxError as exc:
        raise ValueError("input contains invalid DOCX XML") from exc
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
            if relationship.tag == f"{{{REL_NS}}}Relationship" and (
                "customXml" in relationship.get("Target", "")
                or relationship.get("Type", "").endswith("/custom-properties")
            ):
                root.remove(relationship)
                changed = True
    if name == "[Content_Types].xml":
        for child in list(root):
            if child.tag == f"{{{CONTENT_NS}}}Default" and child.get("ContentType") == CUSTOM_TYPE:
                root.remove(child)
                changed = True
            elif child.tag == f"{{{CONTENT_NS}}}Override" and (child.get("PartName", "").startswith("/customXml/")
                or child.get("PartName") == "/docProps/custom.xml"
                or child.get("ContentType") == CUSTOM_TYPE):
                root.remove(child)
                changed = True
    if not changed:
        return data
    return etree.tostring(root, encoding="utf-8", xml_declaration=True)


def scrub(source: Path, output: Path) -> None:
    if not source.is_file() or source.is_symlink() or source.suffix.casefold() != ".docx":
        raise ValueError("source must be a regular DOCX file")
    if output.exists():
        raise ValueError("output already exists")
    output.parent.mkdir(parents=True, exist_ok=True)
    staged = io.BytesIO()
    with zipfile.ZipFile(source) as input_package, zipfile.ZipFile(staged, "w", zipfile.ZIP_DEFLATED) as result:
        _validate_docx_package(input_package)
        custom_parts = _custom_property_parts(input_package)
        etree = require_lxml()
        for name in input_package.namelist():
            if name.startswith("word/") and name.endswith(".xml"):
                if name.startswith("word/comments") or name == "word/people.xml":
                    raise ValueError("DOCX contains review metadata; a separate sanitization decision is required")
                try:
                    root = etree.fromstring(input_package.read(name), etree.XMLParser(resolve_entities=False, no_network=True))
                except etree.XMLSyntaxError as exc:
                    raise ValueError("input contains invalid DOCX XML") from exc
                if any(f"{{{W_NS}}}author" in element.attrib for element in root.iter()):
                    raise ValueError("DOCX contains review metadata; a separate sanitization decision is required")
        for info in input_package.infolist():
            if info.filename.startswith("customXml/") or info.filename == "docProps/custom.xml" or info.filename in custom_parts:
                continue
            data = input_package.read(info.filename)
            if info.filename.endswith((".xml", ".rels")):
                data = scrub_xml(info.filename, data)
            result.writestr(info, data)
    # Do not publish a partial package when parsing or scrubbing fails.
    with output.open("xb") as stream:
        stream.write(staged.getvalue())



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
    except (ValueError, OSError, zipfile.BadZipFile) as exc:
        print(f"error: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
