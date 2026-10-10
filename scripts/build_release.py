from __future__ import annotations

import argparse
import stat
import zipfile
from pathlib import Path


ROOT_FILES = {
    ".gitignore",
    "ATTRIBUTION.md",
    "CHANGELOG.md",
    "CODEX.md",
    "CONTRIBUTING.md",
    "COPYRIGHT",
    "LICENSE",
    "LICENSE-DECISION.md",
    "PROVENANCE.md",
    "README.md",
    "RELEASE-CHECKLIST.md",
    "ROADMAP.md",
    "SECURITY.md",
    "SETUP.md",
    "SUPPORT.md",
    "THIRD_PARTY_NOTICES.md",
    "USE-NOTICE.md",
    "config.example.toml",
    "pyproject.toml",
    "requirements-documents.txt",
    "requirements-lock.txt",
    "requirements-test.txt",
}
ROOT_DIRECTORIES = {
    ".agents",
    ".claude",
    ".claude-plugin",
    ".github",
    "agents",
    "assets",
    "docs",
    "fixtures",
    "profiles",
    "scripts",
    "skills",
    "src",
    "tests",
    "vendor",
}
EXCLUDED_PARTS = {
    ".DS_Store",
    ".git",
    ".pytest_cache",
    ".venv",
    "__pycache__",
    "dist",
    "qa",
}
FIXED_TIME = (2026, 1, 1, 0, 0, 0)


def package_root() -> Path:
    return Path(__file__).resolve().parents[1]


def release_files(root: Path) -> list[Path]:
    missing = sorted(name for name in ROOT_FILES if not (root / name).is_file())
    missing.extend(sorted(name for name in ROOT_DIRECTORIES if not (root / name).is_dir()))
    if missing:
        raise ValueError(f"release inputs missing: {', '.join(missing)}")
    files = [root / name for name in sorted(ROOT_FILES)]
    for name in sorted(ROOT_DIRECTORIES):
        for path in sorted((root / name).rglob("*")):
            relative = path.relative_to(root)
            if any(part in EXCLUDED_PARTS for part in relative.parts):
                continue
            if path.is_symlink():
                raise ValueError(f"release input must not be a symlink: {relative}")
            if path.is_file() and not path.name.endswith((".pyc", ".pyo")):
                files.append(path)
    return files


def build(output: Path) -> dict[str, int | str]:
    root = package_root()
    output = output.expanduser().absolute()
    if output.exists():
        raise ValueError(f"output already exists: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    files = release_files(root)
    temporary = output.with_name(f".{output.name}.partial")
    if temporary.exists():
        raise ValueError(f"partial output already exists: {temporary}")
    try:
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for path in files:
                relative = Path("lawyeredos") / path.relative_to(root)
                info = zipfile.ZipInfo(relative.as_posix(), FIXED_TIME)
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = (stat.S_IFREG | 0o644) << 16
                archive.writestr(info, path.read_bytes())
        temporary.replace(output)
    except Exception:
        if temporary.exists():
            temporary.unlink()
        raise
    return {"output": str(output), "file_count": len(files), "size_bytes": output.stat().st_size}


def main() -> int:
    parser = argparse.ArgumentParser(description="Build an allowlisted LawyeredOS source archive")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    try:
        result = build(Path(args.output))
    except (OSError, ValueError, zipfile.BadZipFile) as exc:
        print(f"error: {exc}")
        return 2
    print(f"Built {result['file_count']} files: {result['output']} ({result['size_bytes']} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
