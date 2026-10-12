"""Conservative page coverage assessment for Poppler text extraction."""
from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path


def pdf_page_count(source: Path, command: str = "pdfinfo") -> int | None:
    executable = shutil.which(command)
    if not executable:
        return None
    try:
        result = subprocess.run(
            [executable, str(source)], stdin=subprocess.DEVNULL,
            capture_output=True, text=True, timeout=120,
            env={**os.environ, "LC_ALL": "C"},
        )
    except (OSError, subprocess.SubprocessError):
        return None
    match = re.search(r"^Pages:\s+(\d+)\s*$", result.stdout, re.MULTILINE)
    return int(match.group(1)) if result.returncode == 0 and match else None


def split_pdf_pages(text: str) -> list[str]:
    if not text:
        return []
    pages = text.split("\f")
    # Poppler emits one terminal delimiter; earlier empty segments are real pages.
    if pages[-1] == "":
        pages.pop()
    return pages


def assess_pdf_text(text: str, expected_pages: int | None, minimum_characters: int = 40) -> dict:
    pages = split_pdf_pages(text)
    counts = [len("".join(page.split())) for page in pages]
    sparse = [number for number, count in enumerate(counts, 1) if count < minimum_characters]
    missing = list(range(len(pages) + 1, expected_pages + 1)) if expected_pages is not None else []
    verified = expected_pages is not None and expected_pages == len(pages)
    return {
        "expected_pages": expected_pages,
        "extracted_pages": len(pages),
        "page_characters": counts,
        "sparse_pages": sparse,
        "missing_pages": missing,
        "page_count_verified": verified,
        "needs_ocr": not verified or bool(sparse) or not pages,
    }
