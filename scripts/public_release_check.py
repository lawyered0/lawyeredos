"""Fail-closed local release gate. Findings never include matched values.

The reviewed policy lists exact files and approved opaque image hashes. No
network, home-directory discovery, or automatic policy update occurs here.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import stat
import zipfile
from pathlib import Path, PurePosixPath
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[1]
MAX_BYTES = 64 * 1024 * 1024
MAX_MEMBERS = 4096
MAX_DEPTH = 6
TEXT_SUFFIXES = {".py", ".md", ".txt", ".toml", ".json", ".xml", ".rels", ".yml", ".yaml", ".html", ".css", ".js", ".sh", ".csv"}
PATTERNS = {
    "private-key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "credential-shaped": re.compile(r"\b(?:sk-|gh[pousr]_|github_pat_|AIza|xox[baprs]-)[A-Za-z0-9_-]{20,}\b"),
    "cloud-access-key": re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    "absolute-user-path": re.compile(r"/(?:Users|home)/[^/\s]+/|[A-Z]:\\Users\\[^\\\s]+\\", re.I),
    "account-identifier": re.compile(r'(?i)(?:account_?id|client_?id|tenant_?id)["\s:=]+["\s]*[A-Za-z0-9_-]{8,}|\b\d{4,}\+[\w.-]+@users\.noreply\.github\.com'),
    # Contact-pattern coverage reviewed in public PR #15.
    "phone-number": re.compile(r"(?<![\w])(?:\+?1[ .-]?)?\(?[2-9][0-9]{2}\)?[ .-][0-9]{3}[ .-][0-9]{4}(?![0-9])"),
}
EMAIL = re.compile(r"[\w.+-]+@([\w.-]+\.[a-z]{2,})", re.I)
FICTIONAL_DOMAINS = {"example.invalid", "example.test"}


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def safe_label(label: str, forbidden: list[str] = ()) -> str:
    for value in forbidden:
        if value:
            label = re.sub(re.escape(value), "[redacted]", label, flags=re.I)
    for pattern in [*PATTERNS.values(), EMAIL]:
        label = pattern.sub("[redacted]", label)
    return label


def text_findings(label: str, text: str, forbidden: list[str]) -> list[tuple[str, str]]:
    categories = [name for name, pattern in PATTERNS.items() if pattern.search(text)]
    if any(m.group(1).casefold() not in FICTIONAL_DOMAINS for m in EMAIL.finditer(text)):
        categories.append("nonfictional-email")
    if any(value and value.casefold() in text.casefold() for value in forbidden):
        categories.append("forbidden-value")
    return [(safe_label(label, forbidden), category) for category in categories]


def unsafe_path(name: str) -> bool:
    path = PurePosixPath(name)
    return (not name or "\\" in name or name.startswith("/") or
            any(part in {"..", ".git", ".DS_Store", "__MACOSX"} for part in path.parts) or
            bool(re.match(r"^[A-Za-z]:", name)) or
            path.as_posix().rstrip("/") != name.rstrip("/"))


def scan_bytes(label: str, data: bytes, policy: dict, forbidden: list[str],
               *, depth: int = 0, budget: list[int] | None = None) -> list[tuple[str, str]]:
    budget = budget if budget is not None else [MAX_BYTES, MAX_MEMBERS]
    budget[0] -= len(data)
    if budget[0] < 0 or depth > MAX_DEPTH:
        return [(safe_label(label, forbidden), "inspection-limit")]
    findings = text_findings(label, data.decode("utf-8", errors="replace"), forbidden)
    findings += text_findings(label+"!path", label, forbidden)
    if Path(label).name.startswith(".env") or Path(label).suffix.casefold() in {".db", ".sqlite", ".sqlite3", ".log", ".bak", ".tmp", ".swp"}:
        findings.append((safe_label(label, forbidden), "private-or-residual-file"))
    if zipfile.is_zipfile(io.BytesIO(data)) or data.startswith(b"PK"):
        if not data.startswith(b"PK\x03\x04") or data[-22:-18] != b"PK\x05\x06":
            findings.append((safe_label(label, forbidden), "unexpected-archive-envelope"))
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                seen = set()
                findings += text_findings(label+"!archive-comment", archive.comment.decode("utf-8", "replace"), forbidden)
                if archive.comment:
                    findings.append((safe_label(label, forbidden), "unexpected-archive-comment"))
                for info in archive.infolist():
                    budget[1] -= 1
                    nested = label + "!" + info.filename
                    if budget[1] < 0 or info.file_size > budget[0]:
                        findings.append((safe_label(nested, forbidden), "inspection-limit"))
                        break
                    mode = info.external_attr >> 16
                    if unsafe_path(info.filename) or info.filename.casefold() in seen or stat.S_ISLNK(mode):
                        findings.append((safe_label(nested, forbidden), "unsafe-or-duplicate-archive-path"))
                    seen.add(info.filename.casefold())
                    findings += text_findings(nested+"!metadata", (info.filename.encode()+info.comment+info.extra).decode("utf-8", "replace"), forbidden)
                    if info.comment or info.extra or info.flag_bits & 1:
                        findings.append((safe_label(nested, forbidden), "unexpected-archive-metadata"))
                    if not info.is_dir():
                        findings += scan_bytes(nested, archive.read(info), policy, forbidden, depth=depth+1, budget=budget)
        except (OSError, RuntimeError, NotImplementedError, zipfile.BadZipFile, ValueError):
            findings.append((safe_label(label, forbidden), "unreadable-archive"))
        return findings
    suffix = Path(label.split("!")[-1]).suffix.casefold()
    if suffix in {".zip", ".docx", ".xlsx", ".pptx"}:
        return findings + [(safe_label(label, forbidden), "invalid-archive")]
    if suffix == ".xml" and label.endswith("docProps/core.xml"):
        try:
            element = ElementTree.fromstring(data)
            if any(item.tag.rsplit("}", 1)[-1] in {"creator", "lastModifiedBy", "lastPrinted", "created", "modified"} and (item.text or "").strip() for item in element.iter()):
                findings.append((safe_label(label, forbidden), "identifying-office-properties"))
        except ElementTree.ParseError:
            findings.append((safe_label(label, forbidden), "invalid-xml-metadata"))
    if suffix in TEXT_SUFFIXES or (not suffix and b"\x00" not in data):
        if b"\x00" in data:
            findings.append((safe_label(label, forbidden), "binary-in-text"))
        try:
            data.decode("utf-8")
        except UnicodeDecodeError:
            findings.append((safe_label(label, forbidden), "invalid-text-encoding"))
    elif policy.get("opaque_sha256", {}).get(label) != digest(data):
        findings.append((safe_label(label, forbidden), "unreviewed-binary"))
    return findings


def load_policy(root: Path) -> dict:
    policy = json.loads((root / "release-policy.json").read_text(encoding="utf-8"))
    files = policy["files"]
    if policy.get("schema_version") != 1 or files != sorted(set(files)) or any(unsafe_path(p) for p in files):
        raise ValueError("invalid release policy")
    return policy


def check_tree(root: Path, files: list[Path], policy: dict, forbidden: list[str]) -> list[tuple[str, str]]:
    found = {path.relative_to(root).as_posix() for path in files}
    expected = set(policy["files"])
    findings = [(safe_label(p, forbidden), "unexpected-staged-file") for p in sorted(found-expected)]
    findings += [(safe_label(p, forbidden), "missing-staged-file") for p in sorted(expected-found)]
    for path in files:
        label = path.relative_to(root).as_posix()
        if path.is_symlink() or not path.is_file():
            findings.append((safe_label(label, forbidden), "nonregular-staged-file"))
        else:
            if path.stat().st_size > MAX_BYTES:
                findings.append((safe_label(label, forbidden), "inspection-limit"))
            else:
                findings += scan_bytes(label, path.read_bytes(), policy, forbidden)
    return findings


def check_archive(path: Path, root: Path, policy: dict, forbidden: list[str]) -> list[tuple[str, str]]:
    findings = []
    if path.stat().st_size > MAX_BYTES:
        return [(path.name, "inspection-limit")]
    data = path.read_bytes()
    findings += text_findings(path.name+"!raw-envelope", data.decode("utf-8", "replace"), forbidden)
    if not data.startswith(b"PK\x03\x04") or data[-22:-18] != b"PK\x05\x06":
        findings.append((path.name, "unexpected-archive-envelope"))
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        names = [item.filename for item in archive.infolist()]
        expected = {"lawyeredos/"+p for p in policy["files"]}
        if set(names) != expected or len(names) != len(expected):
            findings.append((path.name, "archive-manifest-mismatch"))
        if archive.comment:
            findings.append((path.name, "unexpected-archive-comment"))
        budget = [MAX_BYTES, MAX_MEMBERS]
        for info in archive.infolist():
            budget[1] -= 1
            if budget[1] < 0 or info.file_size > budget[0]:
                findings.append((path.name, "inspection-limit"))
                break
            label = info.filename.removeprefix("lawyeredos/")
            if (unsafe_path(info.filename) or info.comment or info.extra or info.flag_bits & 1 or
                    stat.S_ISLNK(info.external_attr >> 16) or info.date_time != (2026, 1, 1, 0, 0, 0)):
                findings.append((safe_label(label, forbidden), "unexpected-archive-metadata"))
            findings += text_findings(label+"!metadata", (info.filename.encode()+info.comment+info.extra).decode("utf-8", "replace"), forbidden)
            data = archive.read(info)
            findings += scan_bytes(label, data, policy, forbidden, budget=budget)
            if info.filename in expected and data != (root/label).read_bytes():
                findings.append((safe_label(label, forbidden), "archive-source-mismatch"))
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--archive", type=Path)
    parser.add_argument("--forbid", action="append", default=[])
    args = parser.parse_args()
    try:
        from build_release import release_files
        policy = load_policy(args.root)
        findings = check_tree(args.root, release_files(args.root), policy, args.forbid)
        if args.archive:
            findings += check_archive(args.archive, args.root, policy, args.forbid)
        for location, category in findings:
            print(f"{location}\t{category}")
        if findings:
            return 2
    except (OSError, ValueError, KeyError, RuntimeError, zipfile.BadZipFile):
        print("release inspection failed closed")
        return 2
    print("public release check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
