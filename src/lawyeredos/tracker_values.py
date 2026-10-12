"""Portable folder identity and inert spreadsheet text for tracker surfaces."""
from pathlib import Path
import unicodedata


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
