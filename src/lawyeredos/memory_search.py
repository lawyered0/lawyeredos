from __future__ import annotations

import argparse
import fcntl
import os
import re
import sqlite3
import secrets
import stat
from pathlib import Path
from typing import Any

from .common import confined_path, emit, preview_token, sha256_file
from .private_fs import create_private_file
from .matter_write import (
    _install_file, _matter_identity, _open_target_parent, _target_digest, _verify_parent_binding,
)


ALLOWED_MEMORY = {"_matter-brief.md", "_matter-decisions.md", "_matter-comms.md"}


def build_index(root: Path, database: Path) -> dict[str, Any]:
    root = root.resolve()
    if database.exists() or database.is_symlink():
        raise ValueError("search index already exists")
    paths = sorted(path for path in root.rglob("*.md") if path.is_file() and not path.is_symlink())
    database.parent.mkdir(parents=True, exist_ok=True)
    create_private_file(database)
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE VIRTUAL TABLE documents USING fts5(path UNINDEXED, title, body)")
        for path in paths:
            relative = path.relative_to(root).as_posix()
            confined_path(root, relative)
            text = path.read_text(encoding="utf-8", errors="replace")
            title = next((line.lstrip("# ").strip() for line in text.splitlines() if line.startswith("#")), path.stem)
            connection.execute("INSERT INTO documents(path,title,body) VALUES (?,?,?)", (relative, title, text))
        connection.execute("CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT)")
        connection.execute("INSERT INTO meta VALUES('root',?)", (str(root),))
    return {"ok": True, "index": str(database), "documents": len(paths), "read_only_sources": True}


def search(database: Path, query: str, limit: int = 20, raw: bool = False) -> dict[str, Any]:
    if not query.strip():
        raise ValueError("search query is required")
    expression = query if raw else fts_query(query)
    if not expression:
        raise ValueError("search query must contain searchable text")
    uri = database.resolve().as_uri() + "?mode=ro"
    with sqlite3.connect(uri, uri=True) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            "SELECT path,title,snippet(documents,2,'[',']',' … ',20) snippet,bm25(documents) rank "
            "FROM documents WHERE documents MATCH ? ORDER BY rank LIMIT ?", (expression, min(max(limit, 1), 100)),
        ).fetchall()
    return {"ok": True, "query": query, "results": [dict(row) for row in rows]}


def fts_query(query: str) -> str:
    """Treat ordinary input as literal tokens, never as FTS query syntax."""
    tokens = re.findall(r"[^\W_]+(?:['’.-][^\W_]+)*", query)
    return " AND ".join('"' + token.replace('"', '""') + '"' for token in tokens)


def _memory_payload(root: Path, relative: str, content: bytes, expect_sha256: str,
                    database: Path | None, file_number: str) -> dict[str, Any]:
    if root.is_symlink():
        raise ValueError("workspace root contains a symlink")
    root = root.resolve()
    rel = Path(relative)
    if rel.name not in ALLOWED_MEMORY or rel.is_absolute() or ".." in rel.parts:
        raise ValueError("memory target must be an allowed matter-memory filename inside the workspace")
    target = confined_path(root, relative)
    if database is None or not file_number:
        raise ValueError("memory writes require a registered open matter: database and file number")
    matter, revision = _matter_identity(database, file_number)
    registered = confined_path(root, matter["matter_folder"])
    if target.parent != registered or not registered.is_dir():
        raise ValueError("memory target must be directly inside the registered matter folder")
    parent_fd, name = _open_target_parent(root, matter["matter_folder"], rel.name, create=False)
    try:
        try:
            current = _target_digest(parent_fd, name)
        except FileNotFoundError:
            current = ""
    finally:
        os.close(parent_fd)
    if current and not expect_sha256:
        raise ValueError("existing memory requires the previously observed sha256")
    if current != expect_sha256:
        raise ValueError("memory compare-and-swap check failed")
    return {"target": str(target), "root": str(root), "matter_folder": matter["matter_folder"],
            "database": str(database.resolve()), "file_number": file_number, "tracker_revision": revision,
            "relative_path": rel.name, "old_sha256": current, "new_text": content.decode("utf-8")}


def memory_preview(root: Path, relative: str, content: bytes, expect_sha256: str = "",
                   database: Path | None = None, file_number: str = "") -> dict[str, Any]:
    payload = _memory_payload(root, relative, content, expect_sha256, database, file_number)
    return {"ok": True, "dry_run": True, "target": payload["target"],
            "old_sha256": payload["old_sha256"], "confirm_token": preview_token("memory-write", payload)}


def memory_commit(root: Path, relative: str, content: bytes, expect_sha256: str, token: str,
                  database: Path | None = None, file_number: str = "") -> dict[str, Any]:
    payload = _memory_payload(root, relative, content, expect_sha256, database, file_number)
    parent_fd, target_name = _open_target_parent(
        Path(payload["root"]), payload["matter_folder"], Path(relative).name, create=False,
    )
    parent_identity = os.fstat(parent_fd)
    lock_fd = None
    staged = ".memory-stage-" + secrets.token_hex(12)
    try:
        lock_fd = os.open(".lawyeredos-memory.lock", os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW,
                          0o600, dir_fd=parent_fd)
        lock_stat = os.fstat(lock_fd)
        if not stat.S_ISREG(lock_stat.st_mode) or lock_stat.st_nlink != 1:
            raise ValueError("memory lock is not a single-link regular file")
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        # Re-bind identity, revision and old bytes while writers share the lock.
        payload = _memory_payload(root, relative, content, expect_sha256, database, file_number)
        if token != preview_token("memory-write", payload):
            raise ValueError("memory confirmation token is missing, stale, or mismatched")
        fd = os.open(staged, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600, dir_fd=parent_fd)
        with os.fdopen(fd, "wb") as handle:
            handle.write(content); handle.flush(); os.fsync(handle.fileno())
        _verify_parent_binding(payload, parent_identity)
        # The install uses exclusive links, preserving an unexpectedly appeared target.
        _install_file("replace" if expect_sha256 else "create", staged, target_name,
                      parent_fd, secrets.token_hex(12), expect_sha256)
        digest = _target_digest(parent_fd, target_name)
        return {"ok": True, "committed": True, "target": payload["target"], "sha256": digest}
    finally:
        try:
            os.unlink(staged, dir_fd=parent_fd)
        except FileNotFoundError:
            pass
        if lock_fd is not None:
            os.close(lock_fd)
        os.close(parent_fd)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Local matter-memory index, search, and guarded write")
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("build-index"); build.add_argument("--root", required=True); build.add_argument("--database", required=True)
    find = sub.add_parser("search"); find.add_argument("--database", required=True); find.add_argument("--query", required=True); find.add_argument("--limit", type=int, default=20); find.add_argument("--raw", action="store_true")
    for name in ("preview-write", "commit-write"):
        item = sub.add_parser(name); item.add_argument("--root", required=True); item.add_argument("--relative", required=True); item.add_argument("--content-file", required=True); item.add_argument("--expect-sha256", default=""); item.add_argument("--database", required=True); item.add_argument("--file-number", required=True)
        if name == "commit-write": item.add_argument("--confirm-token", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "build-index": result = build_index(Path(args.root), Path(args.database))
        elif args.command == "search": result = search(Path(args.database), args.query, args.limit, args.raw)
        else:
            content = Path(args.content_file).read_bytes()
            if args.command == "preview-write": result = memory_preview(Path(args.root), args.relative, content, args.expect_sha256, Path(args.database), args.file_number)
            else: result = memory_commit(Path(args.root), args.relative, content, args.expect_sha256, args.confirm_token, Path(args.database), args.file_number)
        emit(result); return 0
    except (ValueError, OSError, sqlite3.Error, UnicodeDecodeError) as exc:
        emit({"ok": False, "committed": False, "error": str(exc)}); return 2


if __name__ == "__main__":
    raise SystemExit(main())
