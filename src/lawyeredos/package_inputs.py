from __future__ import annotations

import subprocess
from pathlib import Path

# One payload definition for source ZIPs, setup copying, and package identity.
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
    "build",
    ".demo",
    "qa",
}

ALLOWED_SUFFIXES = {".md", ".txt", ".py", ".toml", ".json", ".yml", ".yaml", ".png", ".docx"}
EXTENSIONLESS_NAMES = {"LICENSE", "COPYRIGHT"}


def excluded_part(name: str) -> bool:
    return name in EXCLUDED_PARTS or name.endswith((".pyc", ".pyo", ".egg-info"))


def release_files(root: Path) -> list[Path]:
    root = root.resolve()
    missing = sorted(name for name in ROOT_FILES if not (root / name).is_file())
    missing.extend(sorted(name for name in ROOT_DIRECTORIES if not (root / name).is_dir()))
    if missing:
        raise ValueError(f"release inputs missing: {', '.join(missing)}")
    files = [root / name for name in sorted(ROOT_FILES)]
    for name in sorted(ROOT_DIRECTORIES):
        directory = root / name
        if directory.is_symlink():
            raise ValueError(f"release input must not be a symlink: {name}")
        for path in sorted(directory.rglob("*")):
            relative = path.relative_to(root)
            if any(excluded_part(part) for part in relative.parts):
                continue
            if path.is_symlink():
                raise ValueError(f"release input must not be a symlink: {relative}")
            if path.is_dir():
                continue
            if not path.is_file():
                raise ValueError(f"unsupported release input type: {relative}")
            if (path.name.startswith(".env") or path.name == "config.toml"
                    or (path.suffix.lower() not in ALLOWED_SUFFIXES and path.name not in EXTENSIONLESS_NAMES)):
                raise ValueError(f"unsupported or private release input: {relative}")
            files.append(path)
    for path in files:
        if path.is_symlink():
            raise ValueError(f"release input must not be a symlink: {path.relative_to(root)}")
    # A checkout may contain new source-shaped files that suffix checks cannot
    # distinguish from the product. Require explicit tracked membership there.
    if (root / ".git").exists():
        completed = subprocess.run(
            ["git", "-C", str(root), "ls-files", "-z"], capture_output=True, check=False,
        )
        if completed.returncode:
            raise ValueError("cannot verify tracked release inputs")
        tracked = {value.decode("utf-8", errors="surrogateescape") for value in completed.stdout.split(b"\0") if value}
        unexpected = [str(path.relative_to(root)) for path in files if path.relative_to(root).as_posix() not in tracked]
        if unexpected:
            raise ValueError(f"untracked release input: {', '.join(unexpected)}")
    return sorted(files)
