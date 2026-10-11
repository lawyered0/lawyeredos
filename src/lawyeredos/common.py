from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def preview_token(action: str, payload: dict[str, Any]) -> str:
    return sha256_bytes(f"{action}\n{canonical_json(payload)}".encode("utf-8"))


def emit(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))


def confined_path(root: Path, relative: str) -> Path:
    if not relative or Path(relative).is_absolute():
        raise ValueError("path must be non-empty and relative")
    root = root.resolve()
    relative_path = Path(relative)
    if ".." in relative_path.parts:
        raise ValueError("path leaves configured root")
    unresolved = root / relative_path
    current = root
    for part in relative_path.parts:
        if part in {"", "."}:
            continue
        current = current / part
        if current.is_symlink():
            raise ValueError("path contains a symlink")
    candidate = unresolved.resolve()
    if candidate == root or root not in candidate.parents:
        raise ValueError("path leaves configured root")
    return candidate
