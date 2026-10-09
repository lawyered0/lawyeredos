from __future__ import annotations

import argparse
import csv
import json
import os
import sqlite3
import tempfile
from pathlib import Path
from typing import Any

from .common import emit, preview_token
from .tracker_cli import initialize, now, verify


CANONICAL_FIELDS = (
    "file_number", "client", "description", "matter_folder", "status",
    "opposing_party", "other_parties", "primary_email", "next_action",
    "next_action_date", "limitation_date", "court_deadlines",
)
ALIASES = {
    "file_number": ("file_number", "file_no", "File #"),
    "client": ("client", "client_name", "Client Name"),
    "description": ("description", "matter_description", "Matter Description"),
    "matter_folder": ("matter_folder", "Matter Folder"),
    "status": ("status", "Status", "sheet"),
    "opposing_party": ("opposing_party", "Opposing Party"),
    "other_parties": ("other_parties", "Other Parties / Related Persons"),
    "primary_email": ("primary_email", "client_email", "Client Email"),
    "next_action": ("next_action", "Next Action / Deadline"),
    "next_action_date": ("next_action_date",),
    "limitation_date": ("limitation_date", "limitation_deadline", "Limitation Deadline"),
    "court_deadlines": ("court_deadlines", "Court Deadlines"),
}


def _first(row: dict[str, Any], names: tuple[str, ...]) -> Any:
    for name in names:
        if name in row and row[name] not in (None, ""):
            return row[name]
    return ""


def normalize(row: dict[str, Any], index: int) -> dict[str, str]:
    value = {field: str(_first(row, ALIASES[field])).strip() for field in CANONICAL_FIELDS}
    status = value["status"].casefold()
    value["status"] = "closed" if "closed" in status else "open"
    if not value["file_number"] or not value["client"] or not value["description"]:
        raise ValueError(f"source row {index} lacks file number, client, or description")
    if not value["matter_folder"]:
        raise ValueError(f"source row {index} lacks a matter folder mapping")
    folder = Path(value["matter_folder"])
    if folder.is_absolute() or ".." in folder.parts:
        raise ValueError(f"source row {index} has an unsafe matter folder")
    raw_deadlines = value["court_deadlines"]
    if raw_deadlines:
        try:
            parsed = json.loads(raw_deadlines)
        except json.JSONDecodeError:
            parsed = [{"description": raw_deadlines, "migration_note": "unparsed legacy text"}]
        if not isinstance(parsed, list):
            raise ValueError(f"source row {index} court deadlines are not a list")
        value["court_deadlines"] = json.dumps(parsed, ensure_ascii=False, sort_keys=True)
    else:
        value["court_deadlines"] = "[]"
    return value


def read_source(path: Path) -> list[dict[str, Any]]:
    suffix = path.suffix.casefold()
    if suffix == ".csv":
        with path.open(newline="", encoding="utf-8-sig") as handle:
            return list(csv.DictReader(handle))
    if suffix == ".json":
        value = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(value, dict):
            value = value.get("matters")
        if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
            raise ValueError("JSON source must be a list, or an object with a matters list")
        return value
    if suffix in {".sqlite", ".sqlite3", ".db"}:
        uri = f"file:{path.resolve().as_posix()}?mode=ro"
        with sqlite3.connect(uri, uri=True) as connection:
            connection.row_factory = sqlite3.Row
            columns = {item[1] for item in connection.execute("PRAGMA table_info(matters)")}
            if not columns:
                raise ValueError("source SQLite database has no matters table")
            return [dict(row) for row in connection.execute("SELECT * FROM matters")]
    raise ValueError("migration source must be CSV, JSON, or SQLite")


def migration_plan(source: Path, target: Path) -> dict[str, Any]:
    if not source.is_file() or source.is_symlink():
        raise ValueError("migration source must be a regular file")
    if target.exists():
        raise ValueError("migration target already exists")
    rows = [normalize(row, index) for index, row in enumerate(read_source(source), 1)]
    file_numbers = [row["file_number"] for row in rows]
    folders = [row["matter_folder"] for row in rows]
    if len(file_numbers) != len(set(file_numbers)):
        raise ValueError("source contains duplicate file numbers")
    if len(folders) != len(set(folders)):
        raise ValueError("source contains duplicate matter folders")
    digest_input = {"source": str(source.resolve()), "target": str(target.resolve()), "rows": rows}
    return {
        "ok": True, "dry_run": True, "source": str(source.resolve()),
        "target": str(target.resolve()), "matter_count": len(rows),
        "status_counts": {name: sum(row["status"] == name for row in rows) for name in ("open", "closed")},
        "rows": rows, "confirm_token": preview_token("tracker-migrate", digest_input),
    }


def commit_migration(source: Path, target: Path, token: str) -> dict[str, Any]:
    plan = migration_plan(source, target)
    if token != plan["confirm_token"]:
        raise ValueError("confirmation token is missing, stale, or does not match this migration")
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=target.parent)
    os.close(fd)
    temp_path = Path(temporary)
    temp_path.unlink()
    try:
        initialize(temp_path)
        timestamp = now()
        with sqlite3.connect(temp_path) as connection:
            for row in plan["rows"]:
                connection.execute(
                    """INSERT INTO matters(file_number,client,description,matter_folder,status,
                    opposing_party,other_parties,primary_email,next_action,next_action_date,
                    limitation_date,court_deadlines,created_at,updated_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    tuple(row[field] for field in CANONICAL_FIELDS) + (timestamp, timestamp),
                )
        health = verify(temp_path)
        if not health["ok"]:
            raise ValueError("migrated database failed verification: " + "; ".join(health["problems"]))
        if target.exists():
            raise ValueError("migration target appeared during build; refusing replacement")
        os.replace(temp_path, target)
        return {"ok": True, "committed": True, "target": str(target), "matter_count": plan["matter_count"]}
    finally:
        if temp_path.exists():
            temp_path.unlink()


def export_tracker(database: Path, output: Path, fmt: str) -> dict[str, Any]:
    if output.exists():
        raise ValueError("export output already exists")
    uri = f"file:{database.resolve().as_posix()}?mode=ro"
    with sqlite3.connect(uri, uri=True) as connection:
        connection.row_factory = sqlite3.Row
        rows = [dict(row) for row in connection.execute("SELECT * FROM matters ORDER BY file_number")]
    output.parent.mkdir(parents=True, exist_ok=True)
    if fmt == "json":
        output.write_text(json.dumps({"schema_version": 1, "matters": rows}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    else:
        with output.open("x", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]) if rows else list(CANONICAL_FIELDS))
            writer.writeheader()
            writer.writerows(rows)
    return {"ok": True, "output": str(output), "format": fmt, "matter_count": len(rows)}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Preview/commit safe tracker migration and export")
    sub = parser.add_subparsers(dest="command", required=True)
    preview = sub.add_parser("preview")
    preview.add_argument("--source", required=True)
    preview.add_argument("--target", required=True)
    commit = sub.add_parser("commit")
    commit.add_argument("--source", required=True)
    commit.add_argument("--target", required=True)
    commit.add_argument("--confirm-token", required=True)
    export = sub.add_parser("export")
    export.add_argument("--database", required=True)
    export.add_argument("--output", required=True)
    export.add_argument("--format", choices=["json", "csv"], required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "preview":
            result = migration_plan(Path(args.source), Path(args.target))
            result.pop("rows")
        elif args.command == "commit":
            result = commit_migration(Path(args.source), Path(args.target), args.confirm_token)
        else:
            result = export_tracker(Path(args.database), Path(args.output), args.format)
        emit(result)
        return 0
    except (ValueError, OSError, sqlite3.Error, json.JSONDecodeError) as exc:
        emit({"ok": False, "committed": False, "error": str(exc)})
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
