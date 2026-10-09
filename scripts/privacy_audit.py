from __future__ import annotations

import argparse
import io
import re
import zipfile
from pathlib import Path


TEXT_SUFFIXES = {
    ".css", ".html", ".js", ".json", ".md", ".py", ".sh", ".toml",
    ".txt", ".yaml", ".yml",
}
TOKEN_PATTERNS = {
    "private-key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "openai-style-token": re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    "google-api-key": re.compile(r"\bAIza[0-9A-Za-z_-]{20,}\b"),
    "github-token": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    "slack-token": re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"),
    "absolute-user-path": re.compile(r"/(?:Users|home)/[^/\s]+/"),
}


def scan_text(path: Path, text: str, forbidden: list[str]) -> list[str]:
    findings = [name for name, pattern in TOKEN_PATTERNS.items() if pattern.search(text)]
    findings.extend(f"forbidden:{value}" for value in forbidden if value and value.casefold() in text.casefold())
    return findings


def scan_office_bytes(label: str, data: bytes, forbidden: list[str]) -> list[tuple[str, str]]:
    findings: list[tuple[str, str]] = []
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as package:
            for name in package.namelist():
                if name.endswith(".xml") or name.endswith(".rels"):
                    text = package.read(name).decode("utf-8", errors="replace")
                    findings.extend(
                        (f"{label}:{name}", item)
                        for item in scan_text(Path(label), text, forbidden)
                    )
    except zipfile.BadZipFile:
        findings.append((label, "invalid-office-zip"))
    return findings


def scan_archive(path: Path, forbidden: list[str]) -> list[tuple[str, str]]:
    findings: list[tuple[str, str]] = []
    with zipfile.ZipFile(path) as package:
        for info in package.infolist():
            name = info.filename
            lowered = name.casefold()
            if name.startswith("/") or "../" in name or lowered.endswith(".ds_store") or "/.git/" in lowered:
                findings.append((name, "unsafe-or-residual-archive-path"))
            for value in forbidden:
                if value and value.casefold() in lowered:
                    findings.append((name, f"forbidden-filename:{value}"))
            if info.is_dir():
                continue
            suffix = Path(name).suffix.lower()
            data = package.read(info)
            if suffix in TEXT_SUFFIXES:
                text = data.decode("utf-8", errors="replace")
                findings.extend((name, item) for item in scan_text(Path(name), text, forbidden))
            elif suffix in {".docx", ".xlsx"}:
                findings.extend(scan_office_bytes(name, data, forbidden))
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
        findings.extend(scan_archive(root, args.forbid))
    elif not root.is_dir():
        print(f"privacy audit target is unavailable: {root}")
        return 2
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            findings.append((str(path.relative_to(root)), "symlink"))
            continue
        if not path.is_file():
            continue
        relative = str(path.relative_to(root))
        for forbidden in args.forbid:
            if forbidden.casefold() in relative.casefold():
                findings.append((relative, f"forbidden-filename:{forbidden}"))
        if path.suffix.lower() in TEXT_SUFFIXES:
            text = path.read_text(encoding="utf-8", errors="replace")
            findings.extend((relative, item) for item in scan_text(path, text, args.forbid))
        elif path.suffix.lower() in {".docx", ".xlsx"}:
            findings.extend(scan_office_bytes(relative, path.read_bytes(), args.forbid))
    if findings:
        for location, finding in findings:
            print(f"{location}\t{finding}")
        return 2
    print("privacy scan passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
