"""Apply tracked changes (redlines) to Word documents via OOXML manipulation."""

import copy
import io
import os
import re
import stat
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from xml.etree import ElementTree

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.text.paragraph import Paragraph
from docx.text.run import Run


_rev_id_counter = 100000
MAX_DOCX_BYTES = 100 * 1024 * 1024
MAX_DOCX_ENTRY_BYTES = 50 * 1024 * 1024
MAX_DOCX_UNCOMPRESSED_BYTES = 200 * 1024 * 1024
MAX_DOCX_ENTRIES = 10_000
REQUIRED_DOCX_PARTS = {"[Content_Types].xml", "_rels/.rels", "word/document.xml"}
CONTENT_TYPES_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
PACKAGE_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
MAIN_DOCUMENT_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"
OFFICE_DOCUMENT_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument"
_WORD_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_EXISTING_REVIEW_ELEMENTS = {
    "ins", "del", "moveFrom", "moveTo", "moveFromRangeStart",
    "moveFromRangeEnd", "moveToRangeStart", "moveToRangeEnd", "cellIns",
    "cellDel", "cellMerge", "conflictIns", "conflictDel",
    "customXmlInsRangeStart", "customXmlInsRangeEnd",
    "customXmlDelRangeStart", "customXmlDelRangeEnd", "customXmlMoveFromRangeStart",
    "customXmlMoveFromRangeEnd", "customXmlMoveToRangeStart",
    "customXmlMoveToRangeEnd", "numberingChange", "pPrChange", "rPrChange",
    "sectPrChange", "tblPrChange", "tblPrExChange", "tblGridChange",
    "trPrChange", "tcPrChange",
    "commentRangeStart", "commentRangeEnd", "commentReference",
}


def existing_review_markup(input_path):
    """Return revision/comment markers found anywhere in a DOCX package."""
    markers = set()
    package_source = io.BytesIO(input_path) if isinstance(input_path, bytes) else input_path
    try:
        with zipfile.ZipFile(package_source) as package:
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
            types = ElementTree.fromstring(package.read("[Content_Types].xml"))
            relationships = ElementTree.fromstring(package.read("_rels/.rels"))
            document = ElementTree.fromstring(package.read("word/document.xml"))
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
                or document.tag != f"{{{_WORD_NS}}}document"
            ):
                raise ValueError("input is not a valid Word DOCX package")
            for name in names:
                if name.startswith("word/comments") and name.endswith(".xml"):
                    markers.add("comments part")
                if not name.startswith("word/") or not name.endswith(".xml"):
                    continue
                root = ElementTree.fromstring(package.read(name))
                for element in root.iter():
                    if not element.tag.startswith(f"{{{_WORD_NS}}}"):
                        continue
                    local = element.tag.rsplit("}", 1)[-1]
                    if local in _EXISTING_REVIEW_ELEMENTS:
                        markers.add(local)
    except (zipfile.BadZipFile, ElementTree.ParseError) as exc:
        raise ValueError("input is not a valid DOCX package") from exc
    return sorted(markers)


def _reject_symlink_parents(path):
    current = path.parent
    root = Path(path.anchor)
    while current != current.parent:
        if current.is_symlink():
            metadata = current.lstat()
            if current.parent != root or getattr(metadata, "st_uid", -1) != 0:
                raise ValueError(f"output parent must not contain a symlink: {current}")
        current = current.parent


def _save_document_new(doc, output_path):
    """Serialize then create output exclusively; never follow or replace a link."""
    path = Path(output_path).expanduser().absolute()
    if path.exists() or path.is_symlink():
        raise ValueError(f"output already exists: {path}")
    if not path.parent.is_dir():
        raise ValueError(f"output parent does not exist: {path.parent}")
    _reject_symlink_parents(path)
    serialized = io.BytesIO()
    doc.save(serialized)
    descriptor, staged_name = tempfile.mkstemp(prefix=".legal-redline-", dir=path.parent)
    staged = Path(staged_name)
    created = os.fstat(descriptor)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            descriptor = -1
            stream.write(serialized.getvalue())
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(staged, path, follow_symlinks=False)
        except FileExistsError as exc:
            raise ValueError(f"output already exists: {path}") from exc
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


def read_regular_bytes(input_path):
    path = Path(input_path).expanduser().absolute()
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


def next_rev_id():
    global _rev_id_counter
    _rev_id_counter += 1
    return str(_rev_id_counter)


# CT_Settings is a strict xsd:sequence, so w:trackRevisions is only valid in one
# position: after w:revisionView and before w:doNotTrackMoves. Appending it to the
# end of <w:settings> produces a file Word and OOXML validators can reject. These
# are the elements the schema places after w:trackRevisions; insert immediately
# before the first one that is present.
_SETTINGS_AFTER_TRACK_REVISIONS = (
    "w:doNotTrackMoves",
    "w:doNotTrackFormatting",
    "w:documentProtection",
    "w:autoFormatOverride",
    "w:styleLockTheme",
    "w:styleLockQFSet",
    "w:defaultTabStop",
    "w:autoHyphenation",
    "w:consecutiveHyphenLimit",
    "w:hyphenationZone",
    "w:doNotHyphenateCaps",
    "w:showEnvelope",
    "w:summaryLength",
    "w:clickAndTypeStyle",
    "w:defaultTableStyle",
    "w:evenAndOddHeaders",
    "w:bookFoldRevPrinting",
    "w:bookFoldPrinting",
    "w:bookFoldPrintingSheets",
    "w:drawingGridHorizontalSpacing",
    "w:drawingGridVerticalSpacing",
    "w:displayHorizontalDrawingGridEvery",
    "w:displayVerticalDrawingGridEvery",
    "w:doNotUseMarginsForDrawingGridOrigin",
    "w:drawingGridHorizontalOrigin",
    "w:drawingGridVerticalOrigin",
    "w:doNotShadeFormData",
    "w:noPunctuationKerning",
    "w:characterSpacingControl",
    "w:printTwoOnOne",
    "w:strictFirstAndLastChars",
    "w:noLineBreaksAfter",
    "w:noLineBreaksBefore",
    "w:savePreviewPicture",
    "w:doNotValidateAgainstSchema",
    "w:saveInvalidXml",
    "w:ignoreMixedContent",
    "w:alwaysShowPlaceholderText",
    "w:doNotDemarcateInvalidXml",
    "w:saveXmlDataOnly",
    "w:useXSLTWhenSaving",
    "w:saveThroughXslt",
    "w:showXMLTags",
    "w:alwaysMergeEmptyNamespace",
    "w:updateFields",
    "w:hdrShapeDefaults",
    "w:footnotePr",
    "w:endnotePr",
    "w:compat",
    "w:docVars",
    "w:rsids",
    "m:mathPr",
    "w:attachedSchema",
    "w:themeFontLang",
    "w:clrSchemeMapping",
    "w:doNotIncludeSubdocsInStats",
    "w:doNotAutoCompressPictures",
    "w:forceUpgrade",
    "w:captions",
    "w:readModeInkLockDown",
    "w:smartTagType",
    "sl:schemaLibrary",
    "w:shapeDefaults",
    "w:doNotEmbedSmartTags",
    "w:decimalSymbol",
    "w:listSeparator",
)


def enable_track_revisions(doc):
    """Set the trackRevisions flag in document settings, in schema order."""
    settings = doc.settings.element
    if settings.find(qn("w:trackRevisions")) is not None:
        return

    track_rev = OxmlElement("w:trackRevisions")
    successors = {qn(tag) for tag in _SETTINGS_AFTER_TRACK_REVISIONS}
    for child in settings:
        if child.tag in successors:
            child.addprevious(track_rev)
            return
    settings.append(track_rev)


def _make_ins(text, author, date_str, rpr=None):
    ins = OxmlElement("w:ins")
    ins.set(qn("w:id"), next_rev_id())
    ins.set(qn("w:author"), author)
    ins.set(qn("w:date"), date_str)
    r = OxmlElement("w:r")
    if rpr is not None:
        r.append(copy.deepcopy(rpr))
    t = OxmlElement("w:t")
    t.set(qn("xml:space"), "preserve")
    t.text = text
    r.append(t)
    ins.append(r)
    return ins


def _make_del(text, author, date_str, rpr=None):
    del_elem = OxmlElement("w:del")
    del_elem.set(qn("w:id"), next_rev_id())
    del_elem.set(qn("w:author"), author)
    del_elem.set(qn("w:date"), date_str)
    r = OxmlElement("w:r")
    if rpr is not None:
        r.append(copy.deepcopy(rpr))
    dt = OxmlElement("w:delText")
    dt.set(qn("xml:space"), "preserve")
    dt.text = text
    r.append(dt)
    del_elem.append(r)
    return del_elem


def _make_trailing_run(text, rpr=None):
    r = OxmlElement("w:r")
    if rpr is not None:
        r.append(copy.deepcopy(rpr))
    t = OxmlElement("w:t")
    t.set(qn("xml:space"), "preserve")
    t.text = text
    r.append(t)
    return r


def _slice_run(element, start, end, deleted=False):
    """Copy a run's character range without flattening formatting, tabs or breaks."""
    result = copy.deepcopy(element)
    position = 0
    for child in list(result):
        if child.tag == qn("w:rPr"):
            continue
        text = None
        if child.tag == qn("w:t"):
            text = child.text or ""
        elif child.tag in {qn("w:tab"), qn("w:ptab")}:
            text = "\t"
        elif child.tag == qn("w:noBreakHyphen"):
            text = "-"
        elif child.tag == qn("w:cr") or (
            child.tag == qn("w:br") and child.get(qn("w:type"), "textWrapping") == "textWrapping"
        ):
            text = "\n"
        if text is None:
            # Keep zero-width layout content at its original text boundary.
            if not (start <= position < end or position == end == len(Run(element, None).text)):
                result.remove(child)
            continue
        stop = position + len(text)
        lo, hi = max(start, position), min(end, stop)
        if lo >= hi:
            result.remove(child)
        elif child.tag == qn("w:t"):
            child.text = text[lo - position:hi - position]
            child.set(qn("xml:space"), "preserve")
            if deleted:
                child.tag = qn("w:delText")
        position = stop
    return result


def _replace_span(para, result, replacement_text, author, date_str):
    start_idx, start_offset, end_idx, end_offset, _ = result
    runs = para.runs
    parent = para._element
    insert_pos = list(parent).index(runs[start_idx]._element)
    first_rpr = runs[start_idx]._element.find(qn("w:rPr"))
    elements = []
    if start_offset:
        elements.append(_slice_run(runs[start_idx]._element, 0, start_offset))
    deletion = _make_del("", author, date_str)
    deletion.remove(deletion[0])
    for idx in range(start_idx, end_idx + 1):
        lo = start_offset if idx == start_idx else 0
        hi = end_offset + 1 if idx == end_idx else len(runs[idx].text or "")
        if hi > lo:
            deletion.append(_slice_run(runs[idx]._element, lo, hi, deleted=True))
    elements.append(deletion)
    if replacement_text is not None:
        elements.append(_make_ins(replacement_text, author, date_str, first_rpr))
    end_length = len(runs[end_idx].text or "")
    if end_offset + 1 < end_length:
        elements.append(_slice_run(runs[end_idx]._element, end_offset + 1, end_length))
    for run in runs[start_idx:end_idx + 1]:
        parent.remove(run._element)
    for offset, element in enumerate(elements):
        parent.insert(insert_pos + offset, element)


def _track_paragraph_mark(paragraph, author, date_str):
    """Track the inserted paragraph boundary as well as its text."""
    properties = paragraph.get_or_add_pPr()
    for child in list(properties):
        if child.tag in {qn("w:sectPr"), qn("w:pPrChange")}:
            properties.remove(child)
    run_properties = properties.find(qn("w:rPr"))
    if run_properties is None:
        run_properties = OxmlElement("w:rPr")
        # rPr precedes sectPr and pPrChange in paragraph properties.
        successors = {qn("w:sectPr"), qn("w:pPrChange")}
        index = next((i for i, child in enumerate(properties) if child.tag in successors), len(properties))
        properties.insert(index, run_properties)
    for child in list(run_properties):
        if child.tag in {qn("w:ins"), qn("w:del"), qn("w:moveFrom"), qn("w:moveTo"), qn("w:rPrChange")}:
            run_properties.remove(child)
    marker = OxmlElement("w:ins")
    marker.set(qn("w:id"), next_rev_id())
    marker.set(qn("w:author"), author)
    marker.set(qn("w:date"), date_str)
    run_properties.append(marker)


# Inline containers whose text python-docx's ``para.runs`` cannot see: an
# existing tracked change, a hyperlink, a content control, a simple field. A
# span whose runs straddle one would be rebuilt with that element pushed past
# the new revision (a counterparty's own tracked deletion relocated, a notice
# address moved to the end of the clause). Zero-width markers (proofErr,
# bookmarks, comment ranges, permStart/permEnd) carry no text and stay
# bridgeable.
_OPAQUE_INLINE_TAGS = frozenset(qn(t) for t in (
    "w:ins", "w:del", "w:moveFrom", "w:moveTo", "w:hyperlink", "w:sdt",
    "w:fldSimple", "w:smartTag", "w:customXml", "w:dir", "w:bdo",
))

# Run content that is not text: a complex field's begin, instruction, separator
# and end, a footnote, endnote or comment reference, an image or text box (Word
# wraps a modern one in mc:AlternateContent), an embedded object or a symbol.
# The appliers rebuild a span's runs from their text, so a span covering one of
# these removed it untracked (a REF cross-reference turned into static text, a
# footnote reference vanished).
_OPAQUE_RUN_CONTENT = frozenset(qn(t) for t in (
    "w:fldChar", "w:instrText", "w:footnoteReference", "w:endnoteReference",
    "w:commentReference", "w:drawing", "w:object", "w:pict", "w:sym",
)) | {"{http://schemas.openxmlformats.org/markup-compatibility/2006}AlternateContent"}


def _has_layout_break(element):
    return any(
        child.tag == qn("w:lastRenderedPageBreak")
        or (child.tag == qn("w:br") and child.get(qn("w:type"), "textWrapping") != "textWrapping")
        for child in element
    )


class SpanCrossesHiddenContent(ValueError):
    """The matched span straddles a tracked change, hyperlink, field, content
    control, note or comment reference, image, text box, object, symbol or
    non-text layout break."""


def _get_full_paragraph_text(para):
    return "".join(run.text or "" for run in para.runs)


def _normalize_text(text):
    """Normalize text for fuzzy matching.

    Handles common mismatches between JSON input and document content:
    - Smart quotes vs straight quotes (common in legal docs and PDF conversions)
    - Multiple whitespace characters (tabs, double spaces from PDF line breaks)
    - En/em dashes vs hyphens
    """
    text = text.replace('\u2018', "'").replace('\u2019', "'")  # smart single quotes
    text = text.replace('\u201C', '"').replace('\u201D', '"')  # smart double quotes
    text = text.replace('\u2013', '-').replace('\u2014', '-')  # en/em dashes
    return re.sub(r'\s+', ' ', text)


def _find_text_across_runs(para, search_text):
    """
    Find search_text across potentially split runs.

    Uses a two-pass strategy:
    1. Exact substring match (fast path)
    2. Normalized match (handles smart quotes, extra whitespace from PDF conversion)

    When the normalized path matches, maps positions back to the original text
    so the correct character ranges are used for run splitting.

    Returns (start_run_idx, start_offset, end_run_idx, end_offset, matched_text)
    or None. matched_text is the actual document text that was matched (may differ
    from search_text in whitespace/quote characters).
    """
    runs = para.runs
    if not runs:
        return None

    char_map = []
    for i, run in enumerate(runs):
        for j in range(len(run.text or "")):
            char_map.append((i, j))

    if not char_map:
        return None

    full_text = _get_full_paragraph_text(para)
    matched_text = search_text

    # Try exact match first
    pos = full_text.find(search_text)

    # Fall back to normalized match (smart quotes, whitespace differences)
    if pos < 0:
        norm_full = _normalize_text(full_text)
        norm_search = _normalize_text(search_text)
        norm_pos = norm_full.find(norm_search)
        if norm_pos < 0:
            return None

        # Map normalized position back to original text position.
        # Walk both strings in parallel: the normalized string advances one char
        # at a time, while the original may have extra whitespace chars to skip.
        orig_idx = 0
        norm_idx = 0
        while norm_idx < norm_pos and orig_idx < len(full_text):
            if full_text[orig_idx].isspace():
                while orig_idx + 1 < len(full_text) and full_text[orig_idx + 1].isspace():
                    orig_idx += 1
            orig_idx += 1
            norm_idx += 1
        pos = orig_idx

        # Find the span length in original text that corresponds to norm_search
        search_len = 0
        search_norm_len = 0
        while search_norm_len < len(norm_search) and pos + search_len < len(full_text):
            search_len += 1
            if full_text[pos + search_len - 1].isspace():
                while pos + search_len < len(full_text) and full_text[pos + search_len].isspace():
                    search_len += 1
            search_norm_len += 1

        # Use the actual document text for the matched span
        matched_text = full_text[pos:pos + search_len]

    if pos < 0:
        return None

    start_run_idx, start_offset = char_map[pos]
    end_pos = pos + len(matched_text) - 1
    if end_pos >= len(char_map):
        return None
    end_run_idx, end_offset = char_map[end_pos]
    children = list(para._element)
    lo = children.index(runs[start_run_idx]._element)
    hi = children.index(runs[end_run_idx]._element)
    if any(_has_layout_break(child) for child in children[lo:hi + 1]):
        raise SpanCrossesHiddenContent(matched_text)
    if any(c.tag in _OPAQUE_INLINE_TAGS or any(g.tag in _OPAQUE_RUN_CONTENT for g in c)
           for c in children[lo:hi + 1]):
        # 2026-10-07: a span bridging a counterparty w:del moved it to the end
        # of the sentence, and one across a REF field or footnote reference
        # removed it untracked. Raise rather than return None: callers `continue`
        # on None and would apply the change to a later clause with the same text.
        raise SpanCrossesHiddenContent(matched_text)
    return (start_run_idx, start_offset, end_run_idx, end_offset, matched_text)


def _contains_normalized(full_text, search_text):
    """Check if search_text is in full_text, with whitespace-normalized fallback."""
    if search_text in full_text:
        return True
    return _normalize_text(search_text) in _normalize_text(full_text)


def apply_tracked_replacement(doc, search_text, replacement_text, author, date_str):
    """Replace search_text with replacement_text as tracked changes."""
    for para in doc.paragraphs:
        full_text = _get_full_paragraph_text(para)
        if not _contains_normalized(full_text, search_text):
            continue

        result = _find_text_across_runs(para, search_text)
        if result is None:
            continue

        _replace_span(para, result, replacement_text, author, date_str)

        return True
    return False


def apply_tracked_deletion(doc, delete_text, author, date_str):
    """Delete text as a tracked deletion."""
    for para in doc.paragraphs:
        full_text = _get_full_paragraph_text(para)
        if not _contains_normalized(full_text, delete_text):
            continue

        result = _find_text_across_runs(para, delete_text)
        if result is None:
            continue

        _replace_span(para, result, None, author, date_str)

        return True
    return False


def apply_tracked_insertion(doc, after_text, new_text, author, date_str,
                            as_paragraph=False):
    """Insert new text after anchor text as a tracked insertion.

    Args:
        as_paragraph: If True, insert as a new paragraph after the anchor
            paragraph instead of inline. Use for whole clauses/sections.
    """
    for para in doc.paragraphs:
        full_text = _get_full_paragraph_text(para)
        if not _contains_normalized(full_text, after_text):
            continue

        result = _find_text_across_runs(para, after_text)
        if result is None:
            continue

        if as_paragraph:
            # Insert as a new paragraph after the anchor paragraph
            body = para._element.getparent()
            target_idx = list(body).index(para._element)

            new_para = OxmlElement("w:p")
            target_pPr = para._element.find(qn("w:pPr"))
            if target_pPr is not None:
                new_pPr = copy.deepcopy(target_pPr)
                for numPr in new_pPr.findall(qn("w:numPr")):
                    new_pPr.remove(numPr)
                new_para.append(new_pPr)

            end_rpr = None
            target_runs = para._element.findall(qn("w:r"))
            if target_runs:
                end_rpr = target_runs[0].find(qn("w:rPr"))

            ins_elem = _make_ins(new_text, author, date_str, end_rpr)
            new_para.append(ins_elem)
            _track_paragraph_mark(new_para, author, date_str)
            body.insert(target_idx + 1, new_para)
            return True

        _, _, end_run_idx, end_offset, _ = result
        runs = para.runs
        parent = para._element

        end_run = runs[end_run_idx]
        end_rpr = end_run._element.find(qn("w:rPr"))
        end_run_text = end_run.text or ""

        trailing_text = end_run_text[end_offset + 1:]
        if trailing_text:
            end_run.text = end_run_text[:end_offset + 1]

        insert_pos = list(parent).index(end_run._element) + 1

        ins_elem = _make_ins(new_text, author, date_str, end_rpr)
        parent.insert(insert_pos, ins_elem)

        if trailing_text:
            parent.insert(insert_pos + 1, _make_trailing_run(trailing_text, end_rpr))

        return True
    return False


def _anchor_paragraphs(doc, anchor):
    """Body paragraphs whose current text contains anchor; empty anchor matches nothing."""
    if not anchor or not anchor.strip():
        return []
    return [p for p in doc.paragraphs
            if _contains_normalized(_get_full_paragraph_text(p), anchor)]


def apply_tracked_add_section(doc, after_section, new_text, author, date_str,
                               new_section_number=None):
    """Insert a new section (as tracked insertion) after a section reference."""
    # 2026-10-07: the last paragraph containing after_section used to win, so "12"
    # landed the new clause after "the 12th day of March" in the signature block,
    # and "" (which every paragraph contains) put it at the end of the document.
    # after_section is anchor text and must identify exactly one paragraph.
    matches = _anchor_paragraphs(doc, after_section)
    if len(matches) != 1:
        return False
    target_para = matches[0]

    # Build the new paragraph text
    if new_section_number:
        insert_text = f"{new_section_number}. {new_text}"
    else:
        insert_text = new_text

    # Create a new paragraph after the target as a tracked insertion
    parent = target_para._element.getparent()
    target_idx = list(parent).index(target_para._element)

    # Create new paragraph element with formatting from target paragraph
    new_para = OxmlElement("w:p")
    target_pPr = target_para._element.find(qn("w:pPr"))
    if target_pPr is not None:
        import copy as _copy
        new_pPr = _copy.deepcopy(target_pPr)
        # Remove numbering properties to avoid wrong auto-numbering
        for numPr in new_pPr.findall(qn("w:numPr")):
            new_pPr.remove(numPr)
        new_para.append(new_pPr)

    ins = OxmlElement("w:ins")
    ins.set(qn("w:id"), next_rev_id())
    ins.set(qn("w:author"), author)
    ins.set(qn("w:date"), date_str)
    r = OxmlElement("w:r")
    # Copy run properties (font, size) from target paragraph's first run
    target_runs = target_para._element.findall(qn("w:r"))
    if target_runs:
        target_rPr = target_runs[0].find(qn("w:rPr"))
        if target_rPr is not None:
            import copy as _copy
            r.append(_copy.deepcopy(target_rPr))
    t = OxmlElement("w:t")
    t.set(qn("xml:space"), "preserve")
    t.text = insert_text
    r.append(t)
    ins.append(r)
    new_para.append(ins)
    _track_paragraph_mark(new_para, author, date_str)

    parent.insert(target_idx + 1, new_para)
    return True


# 2026-10-07: the appliers act on the first match, so a replace of "30 days"
# tagged section 9.2 changed the payment term in clause 1 and reported OK.
# `section` is only a schedule label; the span alone places the change, so every
# span must occur exactly once.
_SPAN_FIELD = {"replace": "old", "delete": "text",
               "insert_after": "anchor", "add_section": "after_section"}


_HIDDEN_RUN_ANCESTORS = frozenset(qn(t) for t in ("w:del", "w:moveFrom"))


def _visible_paragraph_text(p):
    """Text of every run in this w:p, including runs inside an existing insertion,
    hyperlink, content control, smart tag or field, which para.runs cannot see.
    Deleted text and nested (text-box) paragraphs are excluded."""
    parts = []
    for r in p.iter(qn("w:r")):
        hidden = False
        for anc in r.iterancestors():
            if anc is p:
                break
            if anc.tag == qn("w:p") or anc.tag in _HIDDEN_RUN_ANCESTORS:
                hidden = True
                break
        if not hidden:
            parts.append(Run(r, None).text)
    return "".join(parts)


def span_occurrences(doc, span, whole_paragraph=False):
    """Count matches over every w:p including table cells, both the way the
    appliers match (direct runs, normalized) and in the text a reader sees.
    whole_paragraph counts paragraphs."""
    needle = _normalize_text(span)
    if not needle.strip():
        return 0
    # Lookahead so a self-overlapping span ("1.1" in "1.1.1") counts twice.
    pattern = re.compile(f"(?={re.escape(needle)})")
    total = 0
    for p in doc.element.body.iter(qn("w:p")):
        # 2026-10-07: a second "30 days" inside a content control (and the same
        # for a counterparty's inserted clause or a hyperlink) was not counted, so
        # the change landed on the only copy the appliers can see, clause 1.
        direct = _normalize_text(_get_full_paragraph_text(Paragraph(p, doc._body)))
        visible = _normalize_text(_visible_paragraph_text(p))
        if whole_paragraph:
            total += (needle in direct) or (needle in visible)
        else:
            total += max(len(pattern.findall(direct)), len(pattern.findall(visible)))
    return total


def placement_problems(doc, redlines):
    """[(index, message)] for every span that does not occur exactly once."""
    problems = []
    for i, rl in enumerate(redlines):
        field = _SPAN_FIELD.get(rl.get("type"))
        if field is None:
            continue
        span = rl.get(field) or ""
        whole = rl["type"] == "add_section" or bool(rl.get("as_paragraph"))
        # A non-string span (after_section: 13) is never a valid anchor.
        n = span_occurrences(doc, span, whole_paragraph=whole) if isinstance(span, str) else 0
        if n != 1:
            problems.append((i, f"Redline {i} ({rl['type']}): {field} {str(span)[:50]!r} "
                                f"occurs {n} times; it must occur exactly once"))
    return problems


def apply_redlines(input_path, output_path, redlines, author="Reviewer"):
    """
    Apply a list of redlines to a .docx file.

    Args:
        input_path: Path to original .docx
        output_path: Path for output .docx with tracked changes
        redlines: List of dicts with type, old/new/text/anchor fields
        author: Author name for tracked changes

    Returns:
        List of (status, description) tuples
    """
    source_bytes = read_regular_bytes(input_path)
    existing = existing_review_markup(source_bytes)
    if existing:
        raise ValueError(
            "input contains pre-existing revision/comment markup; resolve it before "
            "applying a new redline: " + ", ".join(existing)
        )
    doc = Document(io.BytesIO(source_bytes))
    enable_track_revisions(doc)

    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    results = []
    for i, redline in enumerate(redlines):
        rtype = redline.get("type")
        if rtype is None:
            results.append(("ERROR", f"Redline {i}: missing 'type' field"))
            print(f"  [ERROR] Redline {i}: missing 'type' field")
            continue

        try:
            field = _SPAN_FIELD.get(rtype)
            if field is not None:
                span = redline[field]          # missing field -> KeyError -> ERROR
                if not isinstance(span, str) or not span.strip():
                    raise KeyError(field)
                whole = rtype == "add_section" or bool(redline.get("as_paragraph"))
                n = span_occurrences(doc, span, whole_paragraph=whole)
                if n > 1:
                    desc = (f"Redline {i} ({rtype}): {field} '{span[:50]}' occurs "
                            f"{n} times; lengthen the span")
                    results.append(("AMBIGUOUS", desc))
                    print(f"  [AMBIGUOUS] {desc}")
                    continue

            success = False

            if rtype == "replace":
                old = redline["old"]
                new = redline["new"]
                success = apply_tracked_replacement(doc, old, new, author, date_str)
                desc = f"Replace: '{old[:50]}...' -> '{new[:50]}...'"

            elif rtype == "delete":
                text = redline["text"]
                success = apply_tracked_deletion(doc, text, author, date_str)
                desc = f"Delete: '{text[:60]}...'"

            elif rtype == "insert_after":
                anchor = redline["anchor"]
                text = redline["text"]
                as_para = redline.get("as_paragraph", False)
                success = apply_tracked_insertion(
                    doc, anchor, text, author, date_str,
                    as_paragraph=as_para,
                )
                desc = f"Insert after: '{anchor[:40]}...'"

            elif rtype == "add_section":
                after_sec = redline["after_section"]
                text = redline["text"]
                new_sec = redline.get("new_section_number")
                success = apply_tracked_add_section(
                    doc, after_sec, text, author, date_str, new_sec
                )
                desc = f"Add section: '{new_sec or 'new'}' after '{after_sec}'"

            else:
                desc = f"Unknown type: {rtype}"

            status = "OK" if success else "NOT FOUND"
            results.append((status, desc))
            print(f"  [{status}] {desc}")

        except SpanCrossesHiddenContent as e:
            desc = (f"Redline {i} ({rtype}): '{str(e)[:60]}' straddles an existing "
                    "tracked change, hyperlink, field, content control, note or comment "
                    "reference, image, text box, symbol or non-text layout break; not applied")
            results.append(("ERROR", desc))
            print(f"  [ERROR] {desc}")

        except KeyError as e:
            desc = f"Redline {i} ({rtype}): missing required field {e}"
            results.append(("ERROR", desc))
            print(f"  [ERROR] {desc}")

    _save_document_new(doc, output_path)
    print(f"\nSaved: {output_path}")
    print(f"Applied: {sum(1 for s, _ in results if s == 'OK')}/{len(results)} redlines")
    return results
