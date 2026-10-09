from __future__ import annotations

import argparse
import os
import shutil
import sys
import tempfile
from pathlib import Path

from .common import confined_path, emit, preview_token, sha256_file


def payload(args: argparse.Namespace) -> dict[str, str | int]:
    root = Path(args.root).expanduser().resolve()
    matter = confined_path(root, args.matter_folder)
    if not matter.is_dir() or matter.is_symlink():
        raise ValueError("matter folder is missing, a symlink, or not a directory")
    target = confined_path(matter, args.relative_path)
    content = Path(args.content_file).expanduser().resolve()
    if not content.is_file() or content.is_symlink() or content.stat().st_size == 0:
        raise ValueError("content file must be a non-empty regular file")
    if target.exists():
        raise ValueError("target already exists; choose a new versioned name")
    return {
        "root": str(root),
        "matter_folder": args.matter_folder,
        "relative_path": args.relative_path,
        "content_file": str(content),
        "content_sha256": sha256_file(content),
        "content_size": content.stat().st_size,
    }


def preview(args: argparse.Namespace) -> dict:
    value = payload(args)
    return {"ok": True, "dry_run": True, "payload": value, "confirm_token": preview_token("safe-output", value)}


def commit(args: argparse.Namespace) -> dict:
    value = payload(args)
    expected = preview_token("safe-output", value)
    if args.confirm_token != expected:
        raise ValueError("confirmation token is missing, stale, or does not match")
    root = Path(value["root"])
    matter = confined_path(root, value["matter_folder"])
    target = confined_path(matter, value["relative_path"])
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.parent.is_symlink():
        raise ValueError("target parent is a symlink")
    source = Path(value["content_file"])
    descriptor, temporary_name = tempfile.mkstemp(prefix=".practice-write-", dir=target.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as output, source.open("rb") as input_file:
            shutil.copyfileobj(input_file, output)
            output.flush()
            os.fsync(output.fileno())
        if sha256_file(temporary) != value["content_sha256"]:
            raise ValueError("staged content digest mismatch")
        try:
            os.link(temporary, target)
        except FileExistsError as exc:
            raise ValueError("target appeared during commit; nothing overwritten") from exc
        temporary.unlink()
    finally:
        if temporary.exists():
            temporary.unlink()
    return {"ok": True, "committed": True, "path": str(target), "sha256": sha256_file(target)}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="No-overwrite guarded output writer")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("preview", "commit"):
        command = sub.add_parser(name)
        command.add_argument("--root", required=True)
        command.add_argument("--matter-folder", required=True)
        command.add_argument("--relative-path", required=True)
        command.add_argument("--content-file", required=True)
        if name == "commit":
            command.add_argument("--confirm-token", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        emit(preview(args) if args.command == "preview" else commit(args))
        return 0
    except (ValueError, OSError) as exc:
        emit({"ok": False, "committed": False, "error": str(exc)})
        return 2


if __name__ == "__main__":
    sys.exit(main())
