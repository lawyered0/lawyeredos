from __future__ import annotations

import argparse
import csv
import io
import json
import os
import sqlite3
import tempfile
from pathlib import Path
from typing import Any

from .common import emit, preview_token, sqlite_ro_uri
from .private_fs import create_private_file
from .tracker_cli import initialize, now, verify
from .tracker_values import csv_text, folder_key, normalize_folder


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
SNAPSHOT_TABLES = {
    "meta": ("key", "value"),
    "matters": CANONICAL_FIELDS + ("created_at", "updated_at"),
    "timeline": ("id", "file_number", "event_date", "text", "created_at"),
    "audit": ("id", "revision", "action", "file_number", "payload_json", "created_at"),
    "sqlite_sequence": ("name", "seq"),
}


def _snapshot_rows(connection: sqlite3.Connection) -> dict[str, Any]:
    connection.row_factory = sqlite3.Row
    connection.execute("BEGIN")
    return {"tracker_snapshot_version": 1, "schema_version": 1, **{
        table: [dict(row) for row in connection.execute(f"SELECT * FROM {table} ORDER BY 1")]
        for table in SNAPSHOT_TABLES
    }}


def _read_snapshot(source: Path) -> dict[str, Any] | None:
    if source.suffix.casefold() == ".json":
        value = json.loads(source.read_text(encoding="utf-8"))
        if not isinstance(value, dict) or "tracker_snapshot_version" not in value:
            return None
    elif source.suffix.casefold() in {".sqlite", ".sqlite3", ".db"}:
        uri = sqlite_ro_uri(source)
        with sqlite3.connect(uri, uri=True) as connection:
            if not connection.execute("SELECT 1 FROM sqlite_master WHERE name='meta'").fetchone():
                return None
            value = _snapshot_rows(connection)
    else:
        return None
    if value.get("tracker_snapshot_version") != 1 or value.get("schema_version") != 1:
        raise ValueError("unsupported tracker snapshot version")
    for table, columns in SNAPSHOT_TABLES.items():
        rows = value.get(table)
        if not isinstance(rows, list) or any(not isinstance(row, dict) or set(row) != set(columns) for row in rows):
            raise ValueError(f"invalid tracker snapshot table: {table}")
    if any(not isinstance(row["key"], str) or not isinstance(row["value"], str)
           for row in value["meta"]):
        raise ValueError("invalid tracker snapshot metadata types")
    meta = {row["key"]: row["value"] for row in value["meta"]}
    revision_text = meta.get("revision", "")
    if (len(meta) != len(value["meta"]) or meta.get("schema_version") != "1"
            or not revision_text.isascii() or not revision_text.isdecimal()):
        raise ValueError("invalid tracker snapshot metadata")
    current_revision = int(revision_text)
    audit_revisions = [row["revision"] for row in value["audit"]]
    if (any(type(item) is not int or item <= 0 or item > current_revision for item in audit_revisions)
            or len(audit_revisions) != len(set(audit_revisions))):
        raise ValueError("invalid tracker snapshot audit revision history")
    largest_ids = {}
    for table in ("timeline", "audit"):
        ids = [row["id"] for row in value[table]]
        if any(type(item) is not int for item in ids):
            raise ValueError(f"invalid tracker snapshot {table} ID types")
        largest_ids[table] = max([0, *ids])
    sequence_names = set()
    for row in value["sqlite_sequence"]:
        name, counter = row["name"], row["seq"]
        if (not isinstance(name, str) or name not in largest_ids or name in sequence_names
                or type(counter) is not int or not largest_ids[name] <= counter <= 2 ** 63 - 1):
            raise ValueError("invalid tracker snapshot sequence record")
        sequence_names.add(name)
    # Do not require contiguous history or equality with the highest retained
    # audit revision: legacy imports can have no audit, and retained history can
    # have gaps. Never rewrite the source's timestamps, revisions or sequences.
    return value


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
    value["matter_folder"] = normalize_folder(value["matter_folder"])
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
        uri = sqlite_ro_uri(path)
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
    snapshot = _read_snapshot(source)
    source_rows = snapshot["matters"] if snapshot is not None else read_source(source)
    rows = [normalize(row, index) for index, row in enumerate(source_rows, 1)]
    file_numbers = [row["file_number"] for row in rows]
    folders = [folder_key(row["matter_folder"]) for row in rows]
    if len(file_numbers) != len(set(file_numbers)):
        raise ValueError("source contains duplicate file numbers")
    if len(folders) != len(set(folders)):
        raise ValueError("source contains duplicate matter folders")
    digest_input = {"source": str(source.resolve()), "target": str(target.resolve()), "rows": rows,
                    "snapshot": snapshot}
    return {
        "ok": True, "dry_run": True, "source": str(source.resolve()),
        "target": str(target.resolve()), "matter_count": len(rows),
        "status_counts": {name: sum(row["status"] == name for row in rows) for name in ("open", "closed")},
        "rows": rows, "snapshot": snapshot,
        "history_preserved": snapshot is not None,
        "confirm_token": preview_token("tracker-migrate", digest_input),
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
    published = False
    try:
        initialize(temp_path)
        timestamp = now()
        with sqlite3.connect(temp_path) as connection:
            if plan["snapshot"] is not None:
                connection.execute("PRAGMA foreign_keys=ON")
                connection.execute("DELETE FROM meta")
                for table, columns in SNAPSHOT_TABLES.items():
                    if table == "sqlite_sequence":
                        connection.execute("DELETE FROM sqlite_sequence")
                    placeholders = ",".join("?" for _ in columns)
                    for row in plan["snapshot"][table]:
                        connection.execute(
                            f"INSERT INTO {table} ({','.join(columns)}) VALUES ({placeholders})",
                            tuple(row[column] for column in columns),
                        )
            else:
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
        os.link(temp_path, target)
        published = True
        try:
            temp_path.unlink()
        except OSError as exc:
            return {"ok": False, "committed": True, "retry_safe": False,
                    "target": str(target), "temporary": str(temp_path),
                    "verification_state": "temporary_cleanup_failed", "error": str(exc),
                    "recovery": "Inspect both paths; do not repeat migration. Remove only its temporary link before normal use."}
        return {"ok": True, "committed": True, "target": str(target), "matter_count": plan["matter_count"],
                "history_preserved": plan["history_preserved"]}
    finally:
        if temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                if not published:
                    raise


def export_tracker(database: Path, output: Path, fmt: str) -> dict[str, Any]:
    if output.exists():
        raise ValueError("export output already exists")
    uri = sqlite_ro_uri(database)
    with sqlite3.connect(uri, uri=True) as connection:
        connection.row_factory = sqlite3.Row
        if fmt == "json":
            snapshot = _snapshot_rows(connection)
            rows = snapshot["matters"]
        else:
            rows = [dict(row) for row in connection.execute("SELECT * FROM matters ORDER BY file_number")]
    output.parent.mkdir(parents=True, exist_ok=True)
    if fmt == "json":
        data = (json.dumps(snapshot, indent=2, sort_keys=True) + "\n").encode("utf-8")
    else:
        handle = io.StringIO(newline="")
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]) if rows else list(CANONICAL_FIELDS))
        writer.writeheader()
        writer.writerows({key: csv_text(value) for key, value in row.items()} for row in rows)
        data = handle.getvalue().encode("utf-8")
    create_private_file(output, data)
    return {"ok": True, "output": str(output), "format": fmt, "matter_count": len(rows),
            "history_preserved": fmt == "json"}


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
            result.pop("snapshot")
        elif args.command == "commit":
            result = commit_migration(Path(args.source), Path(args.target), args.confirm_token)
        else:
            result = export_tracker(Path(args.database), Path(args.output), args.format)
        emit(result)
        return 0 if result["ok"] else 3 if result.get("committed") else 2
    except (ValueError, OSError, sqlite3.Error, json.JSONDecodeError) as exc:
        emit({"ok": False, "committed": False, "error": str(exc)})
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
