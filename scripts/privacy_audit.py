from __future__ import annotations

import argparse
import io
import re
import zipfile
from pathlib import Path


TOKEN_PATTERNS = {
    "private-key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "openai-style-token": re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    "google-api-key": re.compile(r"\bAIza[0-9A-Za-z_-]{20,}\b"),
    "github-token": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    "slack-token": re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"),
    "absolute-user-path": re.compile(r"/(?:Users|home)/[^/\s\"\'<>]+(?:/|\b)"),
    "windows-user-path": re.compile(r"[A-Za-z]:\\Users\\[^\\\s\"\'<>]+", re.IGNORECASE),
    "phone-number": re.compile(r"(?<![\w])(?:\+?1[ .-]?)?\(?[2-9][0-9]{2}\)?[ .-][0-9]{3}[ .-][0-9]{4}(?![0-9])"),
}


EMAIL_PATTERN = re.compile(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?\.[A-Za-z]{2,}")
FICTIONAL_EMAIL_DOMAINS = {"example.com", "example.net", "example.org", "example.invalid", "users.noreply.github.com", "noreply.github.com"}
OFFICE_SUFFIXES = {".docx", ".dotx", ".docm", ".dotm", ".xlsx", ".xltx", ".xlsm", ".xltm", ".pptx", ".potx", ".pptm", ".potm"}
PRIVATE_SUFFIXES = {".sqlite3", ".sqlite", ".db", ".log", ".bak", ".tmp", ".swp"}


def safe_label(label: str, forbidden: list[str]) -> str:
    for value in forbidden:
        if value:
            label = re.sub(re.escape(value), "[redacted]", label, flags=re.IGNORECASE)
    for pattern in (*TOKEN_PATTERNS.values(), EMAIL_PATTERN):
        label = pattern.sub("[redacted]", label)
    return label


def scan_text(path: Path, text: str, forbidden: list[str]) -> list[str]:
    findings = [name for name, pattern in TOKEN_PATTERNS.items() if pattern.search(text)]
    if any(
        (domain := item.group().rsplit("@", 1)[1].casefold()) not in FICTIONAL_EMAIL_DOMAINS
        and not domain.endswith((".invalid", ".test", ".example", ".localhost"))
        for item in EMAIL_PATTERN.finditer(text)
    ):
        findings.append("email-address")
    if any(value and value.casefold() in text.casefold() for value in forbidden):
        findings.append("forbidden-term")
    return findings


def scan_file_bytes(label: str, data: bytes, forbidden: list[str]) -> list[tuple[str, str]]:
    path = Path(label)
    findings: list[tuple[str, str]] = []
    if path.name.startswith(".env") or path.suffix.lower() in PRIVATE_SUFFIXES:
        findings.append((label, "private-or-residual-file"))
    if path.suffix.lower() in OFFICE_SUFFIXES:
        findings.extend(scan_office_bytes(label, data, forbidden))
    else:
        findings.extend((label, item) for item in scan_text(path, data.decode("utf-8", errors="replace"), forbidden))
        try:
            data.decode("utf-8")
            binary = b"\0" in data
        except UnicodeDecodeError:
            binary = True
        if binary and not (path.suffix.lower() == ".png" and data.startswith(b"\x89PNG\r\n\x1a\n")):
            findings.append((label, "unsupported-binary-file"))
    return [(safe_label(location, forbidden), category) for location, category in findings]


def scan_office_bytes(label: str, data: bytes, forbidden: list[str]) -> list[tuple[str, str]]:
    findings: list[tuple[str, str]] = []
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as package:
            for name in package.namelist():
                if name.endswith(".xml") or name.endswith(".rels"):
                    text = package.read(name).decode("utf-8", errors="replace")
                    findings.extend(
                        (safe_label(f"{label}:{name}", forbidden), item)
                        for item in scan_text(Path(label), text, forbidden)
                    )
    except zipfile.BadZipFile:
        findings.append((safe_label(label, forbidden), "invalid-office-zip"))
    return findings


def scan_archive(path: Path, forbidden: list[str]) -> list[tuple[str, str]]:
    findings: list[tuple[str, str]] = []
    with zipfile.ZipFile(path) as package:
        for info in package.infolist():
            name = info.filename
            lowered = name.casefold()
            if name.startswith("/") or "../" in name or lowered.endswith(".ds_store") or "/.git/" in lowered:
                findings.append((safe_label(name, forbidden), "unsafe-or-residual-archive-path"))
            for value in forbidden:
                if value and value.casefold() in lowered:
                    findings.append((safe_label(name, forbidden), "forbidden-filename"))
            if info.is_dir():
                continue
            data = package.read(info)
            findings.extend(scan_file_bytes(name, data, forbidden))
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description="Scan a distributable for common privacy leaks")
    parser.add_argument("root")
    parser.add_argument("--forbid", action="append", default=[])
    args = parser.parse_args()
    root = Path(args.root).expanduser().resolve()
    findings: list[tuple[str, str]] = []
    if root.is_file():
        if root.suffix.lower() != ".zip":
            print("privacy audit file input must be a ZIP archive")
            return 2
        try:
            findings.extend(scan_archive(root, args.forbid))
        except (OSError, ValueError, RuntimeError, zipfile.BadZipFile):
            findings.append(("archive", "archive-read-or-format-error"))
    elif not root.is_dir():
        print("privacy audit target is unavailable")
        return 2
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            findings.append((safe_label(str(path.relative_to(root)), args.forbid), "symlink"))
            continue
        if not path.is_file():
            continue
        relative = str(path.relative_to(root))
        for forbidden in args.forbid:
            if forbidden.casefold() in relative.casefold():
                findings.append((safe_label(relative, args.forbid), "forbidden-filename"))
        try:
            findings.extend(scan_file_bytes(relative, path.read_bytes(), args.forbid))
        except (OSError, ValueError, RuntimeError, zipfile.BadZipFile):
            findings.append((safe_label(relative, args.forbid), "file-read-or-format-error"))
    if findings:
        for location, finding in findings:
            print(f"{location}\t{finding}")
        return 2
    print("privacy scan passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
