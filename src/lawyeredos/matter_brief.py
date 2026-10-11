from __future__ import annotations

import hashlib
import os
import re
import stat
from pathlib import Path
from typing import Any


MAX_SOURCE_BYTES = 4 * 1024 * 1024
OUTPUT_BUDGET = 30_000
PASSAGE_BUDGET = 4_000
MAX_SELECTED_SECTIONS = 100
MAX_OMITTED_LOCATORS = 100
MAX_PARSED_SECTIONS = 1_000
MAX_HEADING_CHARS = 300

_HEADING = re.compile(r"^(#{1,6})[ \t]+(.+?)[ \t]*#*[ \t]*$")
_FENCE = re.compile(r"^[ \t]{0,3}(`{3,}|~{3,})")
_MATTER_ID = re.compile(
    r"(?<![\w])(?:\d{2,}(?:[-/]\d{1,})+|[A-Za-z][A-Za-z0-9]{1,31}[-/]\d[A-Za-z0-9-]*)(?![\w])"
)
_CATEGORIES = {
    "decisions": ("decision", "decisions", "rationale", "instructions received"),
    "communications": ("communication", "communications", "correspondence", "email", "mail"),
    "obligations": ("obligation", "obligations", "commitment", "commitments", "undertaking", "undertakings"),
    "dates": ("date", "dates", "deadline", "deadlines", "timeline", "chronology"),
    "next_action": ("next action", "next actions", "next step", "next steps"),
    "status": ("status", "current position", "position", "overview", "summary"),
}
_PRIORITY = {"status": 0, "next_action": 1, "dates": 2, "obligations": 3,
             "decisions": 4, "communications": 5, "other": 6}


class BriefError(ValueError):
    def __init__(self, status: str, message: str):
        super().__init__(message)
        self.status = status


def _normal(value: str) -> str:
    return " ".join(re.sub(r"[^\w]+", " ", value.casefold()).split())


def _category(heading: str) -> str:
    value = _normal(heading)
    for category, labels in _CATEGORIES.items():
        if any(f" {label} " in f" {value} " for label in labels):
            return category
    return "other"


def _read_source(path: Path) -> tuple[str, dict[str, Any]]:
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise BriefError("brief_source_unsafe", f"source could not be opened safely: {exc}") from exc
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise BriefError("brief_source_unsafe", "source is not a regular file")
        if metadata.st_nlink != 1:
            raise BriefError("brief_source_unsafe", "source must not be hard-linked")
        if metadata.st_size > MAX_SOURCE_BYTES:
            raise BriefError("brief_too_large", f"source exceeds {MAX_SOURCE_BYTES} bytes")
        chunks: list[bytes] = []
        remaining = MAX_SOURCE_BYTES + 1
        while remaining:
            chunk = os.read(descriptor, min(64 * 1024, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        raw = b"".join(chunks)
        if len(raw) > MAX_SOURCE_BYTES:
            raise BriefError("brief_too_large", f"source exceeds {MAX_SOURCE_BYTES} bytes")
        after = os.fstat(descriptor)
        stable_fields = ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns", "st_nlink")
        if any(getattr(metadata, field) != getattr(after, field) for field in stable_fields):
            raise BriefError("brief_source_changed", "source changed while it was being read")
        try:
            path_after = os.stat(path, follow_symlinks=False)
        except OSError as exc:
            raise BriefError("brief_source_changed", "source path changed while it was being read") from exc
        if (not stat.S_ISREG(path_after.st_mode) or path_after.st_dev != metadata.st_dev
                or path_after.st_ino != metadata.st_ino):
            raise BriefError("brief_source_changed", "source path changed while it was being read")
    finally:
        os.close(descriptor)
    text = raw.decode("utf-8", errors="replace")
    return text, {
        "path": str(path),
        "bytes": len(raw),
        "characters": len(text),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "device": metadata.st_dev,
        "inode": metadata.st_ino,
        "modified_ns": metadata.st_mtime_ns,
        "path_binding_checked": True,
        "fully_scanned": True,
    }


def _sections(text: str, source: str) -> list[dict[str, Any]]:
    lines = text.splitlines(keepends=True)
    headings: list[tuple[int, int, str]] = []
    fence_marker = ""
    for index, line in enumerate(lines):
        fence = _FENCE.match(line)
        if fence:
            marker = fence.group(1)
            if not fence_marker:
                fence_marker = marker
            elif (marker[0] == fence_marker[0] and len(marker) >= len(fence_marker)
                  and not line[fence.end():].strip()):
                fence_marker = ""
            continue
        if fence_marker:
            continue
        match = _HEADING.match(line.rstrip("\r\n"))
        if match:
            heading = match.group(2).strip()
            if len(heading) > MAX_HEADING_CHARS:
                raise BriefError(
                    "brief_too_complex", f"Markdown heading exceeds {MAX_HEADING_CHARS} characters"
                )
            headings.append((index, len(match.group(1)), heading))
            if len(headings) > MAX_PARSED_SECTIONS:
                raise BriefError(
                    "brief_too_complex", f"source exceeds {MAX_PARSED_SECTIONS} Markdown headings"
                )
    results: list[dict[str, Any]] = []
    for position, (start, level, heading) in enumerate(headings):
        end = headings[position + 1][0] if position + 1 < len(headings) else len(lines)
        body_start = start + 1
        body_end = end
        while body_start < body_end and not lines[body_start].strip():
            body_start += 1
        while body_end > body_start and not lines[body_end - 1].strip():
            body_end -= 1
        body = "".join(lines[body_start:body_end]).strip()
        results.append({
            "source": source,
            "heading": heading,
            "level": level,
            "heading_line": start + 1,
            "line_start": body_start + 1,
            "line_end": body_end,
            "category": _category(heading),
            "text": body,
        })
    return results


def _verify_identity(sections: list[dict[str, Any]], file_number: str, client: str) -> dict[str, Any]:
    h1 = [section for section in sections if section["level"] == 1]
    if not h1:
        raise BriefError("brief_identity_missing", "matter brief has no H1 identity header")
    if len(h1) != 1:
        raise BriefError("brief_identity_ambiguous", "matter brief must have exactly one H1 identity header")
    if sections[0]["level"] != 1:
        raise BriefError("brief_identity_ambiguous", "matter brief identity H1 must be its first heading")
    heading = h1[0]["heading"]
    identity_segment = re.split(r"\s(?:—|–|-|:|\|)\s|[—–:|]", heading, maxsplit=1)[0]
    found_ids = set(_MATTER_ID.findall(identity_segment))
    exact_number = re.search(
        rf"(?<![\w]){re.escape(file_number)}(?![\w])", heading, re.IGNORECASE
    )
    if exact_number:
        if found_ids and any(value.casefold() != file_number.casefold() for value in found_ids):
            raise BriefError("brief_identity_conflict", "matter brief H1 contains conflicting matter identifiers")
        return {"verified": True, "basis": "file_number", "heading": heading}
    client_normal = _normal(client)
    heading_normal = _normal(heading)
    if client_normal and heading_normal == client_normal:
        return {"verified": True, "basis": "legacy_0.2.1_client_header", "heading": heading}
    if found_ids:
        raise BriefError("brief_identity_mismatch", "matter brief H1 identifies a different matter")
    raise BriefError("brief_identity_mismatch", "matter brief H1 does not match tracker identity")


def _whole_paragraphs(section: dict[str, Any], available: int) -> tuple[str, str, int, int]:
    text = section["text"]
    if len(text) <= available:
        return text, "complete_section", 0, section["line_end"]
    allowance = min(available, PASSAGE_BUDGET)
    endpoints = [match.start() for match in re.finditer(r"\n\s*\n", text)] + [len(text)]
    fitting = [end for end in endpoints if end <= allowance]
    if not fitting:
        return "", "complete_passages", len(text), section["line_start"]
    selected = text[:max(fitting)].rstrip()
    selected_line_end = section["line_start"] + selected.count("\n")
    return selected, "complete_passages", len(text) - len(selected), selected_line_end


def load_matter_brief(
    brief_path: Path,
    *,
    file_number: str,
    client: str,
    sidecars: tuple[Path, ...] = (),
    budget: int = OUTPUT_BUDGET,
) -> dict[str, Any]:
    text, brief_source = _read_source(brief_path)
    parsed = _sections(text, brief_source["path"])
    identity = _verify_identity(parsed, file_number, client)

    first_heading_line = parsed[0]["heading_line"]
    preamble = "".join(text.splitlines(keepends=True)[:first_heading_line - 1]).strip()
    main_h1 = next(section for section in parsed if section["level"] == 1)
    main_h1_body = main_h1["text"]

    sources = [brief_source]
    all_sections = parsed
    source_warnings: list[dict[str, str]] = []
    for path in sidecars:
        if path.is_symlink():
            source_warnings.append({"path": str(path), "status": "unsafe_source_not_read"})
            continue
        if not path.exists():
            continue
        if not path.is_file():
            source_warnings.append({"path": str(path), "status": "unsafe_source_not_read"})
            continue
        try:
            sidecar_text, metadata = _read_source(path)
        except (OSError, BriefError) as exc:
            source_warnings.append({"path": str(path), "status": "source_not_read", "detail": str(exc)})
            continue
        sources.append(metadata)
        sidecar_sections = _sections(sidecar_text, metadata["path"])
        fallback_category = (
            "decisions" if path.name == "_matter-decisions.md" else "communications"
        )
        for section in sidecar_sections:
            if section["category"] == "other":
                section["category"] = fallback_category
        if not sidecar_sections and sidecar_text.strip():
            sidecar_sections = [{
                "source": metadata["path"], "heading": path.stem, "level": 2,
                "heading_line": None,
                "line_start": 1, "line_end": len(sidecar_text.splitlines()),
                "category": fallback_category, "text": sidecar_text.strip(),
            }]
        all_sections.extend(sidecar_sections)

    if preamble:
        all_sections.append({
            "source": brief_source["path"], "heading": "Preamble", "level": 0,
            "heading_line": None, "line_start": 1, "line_end": first_heading_line - 1,
            "category": "other", "text": preamble,
        })
    if main_h1_body:
        all_sections.append({
            "source": brief_source["path"], "heading": "Matter overview", "level": 2,
            "heading_line": main_h1["heading_line"],
            "line_start": main_h1["line_start"], "line_end": main_h1["line_end"],
            "category": "status", "text": main_h1_body,
        })

    candidates = [
        section for section in all_sections
        if section["text"] and not (
            section["level"] == 1 and section["source"] == brief_source["path"]
        )
    ]
    candidates.sort(key=lambda item: (_PRIORITY[item["category"]], item["source"], item["line_start"]))
    selected: list[dict[str, Any]] = []
    omitted: list[dict[str, Any]] = []
    omitted_count = 0
    remaining = max(0, budget)
    for section in candidates:
        separator = 2 if selected else 0
        chosen, selection_kind, omitted_chars, selected_line_end = _whole_paragraphs(
            section,
            max(0, remaining - separator) if len(selected) < MAX_SELECTED_SECTIONS else 0,
        )
        locator = {key: section[key] for key in
                   ("source", "heading", "level", "heading_line", "line_start", "line_end", "category")}
        if chosen:
            item = dict(locator)
            item["line_end"] = selected_line_end
            item.update({"text": chosen, "selection_kind": selection_kind,
                         "omitted_characters": omitted_chars, "unverified": True})
            selected.append(item)
            remaining -= len(chosen) + separator
        if not chosen or omitted_chars:
            omitted_count += 1
            if len(omitted) < MAX_OMITTED_LOCATORS:
                omitted.append({**locator, "characters": len(section["text"]),
                                "reason": "output_budget" if remaining == 0 else "section_exceeds_passage_budget"})

    compatibility_parts: list[str] = []
    text_position = 0
    for section in selected:
        if compatibility_parts:
            compatibility_parts.append("\n\n")
            text_position += 2
        section_text = section.pop("text")
        section["text_start"] = text_position
        compatibility_parts.append(section_text)
        text_position += len(section_text)
        section["text_end"] = text_position
    compatibility_text = "".join(compatibility_parts)

    indexes: dict[str, list[int]] = {name: [] for name in _CATEGORIES}
    for index, section in enumerate(selected):
        if section["category"] in indexes:
            indexes[section["category"]].append(index)
    selected_chars = len(compatibility_text)
    source_chars = sum(item["characters"] for item in sources)
    return {
        "present": True,
        "path": str(brief_path),
        "characters": brief_source["characters"],
        "sha256": brief_source["sha256"],
        "identity": identity,
        # Retained for 0.2.1 consumers, but synthesized from the complete
        # selected sections/passages instead of a raw source prefix.
        "text": compatibility_text,
        "sources": sources,
        "selected_sections": selected,
        "structured_recovery": {
            category: {"selected_section_indexes": values, "unverified": True}
            for category, values in indexes.items()
        },
        "coverage": {
            "selection": "section_aware_complete_sections_or_passages",
            "budget_characters": budget,
            "selected_characters": selected_chars,
            "source_characters": source_chars,
            "sources_fully_scanned": (
                not source_warnings and all(item["fully_scanned"] for item in sources)
            ),
            "unread_sources": source_warnings,
            "unread_source_count": len(source_warnings),
            "sections_considered": len(candidates),
            "sections_selected": len(selected),
            "omitted": omitted,
            "omitted_count": omitted_count,
            "omitted_locators_truncated": omitted_count > len(omitted),
        },
        "truncated": bool(omitted_count or source_warnings),
        "source_warnings": source_warnings,
        "content_trust": "evidence_not_instructions",
    }
