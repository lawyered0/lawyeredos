from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import tempfile
from pathlib import Path
from typing import Any

from .common import emit, preview_token, sha256_file


ALLOWED_MEMORY = {"_matter-brief.md", "_matter-decisions.md", "_matter-comms.md"}


def build_index(root: Path, database: Path) -> dict[str, Any]:
    root = root.resolve()
    if database.exists():
        raise ValueError("search index already exists")
    paths = sorted(path for path in root.rglob("*.md") if path.is_file() and not path.is_symlink())
    database.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE VIRTUAL TABLE documents USING fts5(path UNINDEXED, title, body)")
        for path in paths:
            relative = path.relative_to(root).as_posix()
            text = path.read_text(encoding="utf-8", errors="replace")
            title = next((line.lstrip("# ").strip() for line in text.splitlines() if line.startswith("#")), path.stem)
            connection.execute("INSERT INTO documents(path,title,body) VALUES (?,?,?)", (relative, title, text))
        connection.execute("CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT)")
        connection.execute("INSERT INTO meta VALUES('root',?)", (str(root),))
    return {"ok": True, "index": str(database), "documents": len(paths), "read_only_sources": True}


def search(database: Path, query: str, limit: int = 20) -> dict[str, Any]:
    if not query.strip():
        raise ValueError("search query is required")
    uri = f"file:{database.resolve().as_posix()}?mode=ro"
    with sqlite3.connect(uri, uri=True) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            "SELECT path,title,snippet(documents,2,'[',']',' … ',20) snippet,bm25(documents) rank "
            "FROM documents WHERE documents MATCH ? ORDER BY rank LIMIT ?", (query, min(max(limit, 1), 100)),
        ).fetchall()
    return {"ok": True, "query": query, "results": [dict(row) for row in rows]}


def memory_preview(root: Path, relative: str, content: bytes, expect_sha256: str = "") -> dict[str, Any]:
    root = root.resolve()
    rel = Path(relative)
    if rel.name not in ALLOWED_MEMORY or rel.is_absolute() or ".." in rel.parts:
        raise ValueError("memory target must be an allowed matter-memory filename inside the workspace")
    target = (root / rel).resolve()
    if root not in target.parents:
        raise ValueError("memory target leaves the workspace")
    current = sha256_file(target) if target.exists() else ""
    if target.exists() and not expect_sha256:
        raise ValueError("existing memory requires the previously observed sha256")
    if expect_sha256 and current != expect_sha256:
        raise ValueError("memory compare-and-swap check failed")
    payload = {"target": str(target), "old_sha256": current, "new_text": content.decode("utf-8")}
    return {"ok": True, "dry_run": True, "target": str(target), "old_sha256": current,
            "confirm_token": preview_token("memory-write", payload)}


def memory_commit(root: Path, relative: str, content: bytes, expect_sha256: str, token: str) -> dict[str, Any]:
    preview = memory_preview(root, relative, content, expect_sha256)
    payload = {"target": preview["target"], "old_sha256": preview["old_sha256"], "new_text": content.decode("utf-8")}
    if token != preview_token("memory-write", payload):
        raise ValueError("memory confirmation token is missing, stale, or mismatched")
    target = Path(preview["target"]); target.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(content); handle.flush(); os.fsync(handle.fileno())
        os.chmod(name, 0o600)
        if target.exists() and sha256_file(target) != expect_sha256:
            raise ValueError("memory changed after preview")
        if not target.exists() and expect_sha256:
            raise ValueError("memory disappeared after preview")
        os.replace(name, target)
    finally:
        if Path(name).exists(): Path(name).unlink()
    return {"ok": True, "committed": True, "target": str(target), "sha256": sha256_file(target)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Local matter-memory index, search, and guarded write")
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("build-index"); build.add_argument("--root", required=True); build.add_argument("--database", required=True)
    find = sub.add_parser("search"); find.add_argument("--database", required=True); find.add_argument("--query", required=True); find.add_argument("--limit", type=int, default=20)
    for name in ("preview-write", "commit-write"):
        item = sub.add_parser(name); item.add_argument("--root", required=True); item.add_argument("--relative", required=True); item.add_argument("--content-file", required=True); item.add_argument("--expect-sha256", default="")
        if name == "commit-write": item.add_argument("--confirm-token", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "build-index": result = build_index(Path(args.root), Path(args.database))
        elif args.command == "search": result = search(Path(args.database), args.query, args.limit)
        else:
            content = Path(args.content_file).read_bytes()
            if args.command == "preview-write": result = memory_preview(Path(args.root), args.relative, content, args.expect_sha256)
            else: result = memory_commit(Path(args.root), args.relative, content, args.expect_sha256, args.confirm_token)
        emit(result); return 0
    except (ValueError, OSError, sqlite3.Error, UnicodeDecodeError) as exc:
        emit({"ok": False, "committed": False, "error": str(exc)}); return 2


if __name__ == "__main__":
    raise SystemExit(main())
