"""Portable folder identity and inert spreadsheet text for tracker surfaces."""
from pathlib import Path
import re
import unicodedata

ILLEGAL_XML_CONTROLS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def validate_text(value: object) -> None:
    if isinstance(value, str) and ILLEGAL_XML_CONTROLS.search(value):
        raise ValueError("tracker text contains an unsupported control character")
    if isinstance(value, dict):
        for key, item in value.items():
            validate_text(key)
            validate_text(item)
    elif isinstance(value, list):
        for item in value:
            validate_text(item)


def normalize_folder(value: str) -> str:
    folder = Path(value.strip())
    if not value.strip() or folder.is_absolute() or ".." in folder.parts or not folder.parts:
        raise ValueError("matter_folder must be a confined nonempty relative path")
    return folder.as_posix()


def folder_key(value: str) -> str:
    # Conservatively reject aliases on the supported case-insensitive macOS
    # filesystem, including canonically equivalent Unicode spellings.
    return unicodedata.normalize("NFC", normalize_folder(value)).casefold()


def csv_text(value: object) -> object:
    if isinstance(value, str) and value.lstrip(" \t\r\n").startswith(("=", "+", "-", "@")):
        return "'" + value
    return value
