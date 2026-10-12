from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterator, Mapping

from .common import emit, preview_token, sqlite_ro_uri
from .private_fs import assert_private_file, create_private_file
from .tracker_values import folder_key, normalize_folder, validate_text


SCHEMA_VERSION = 1
FIELDS = {
    "client": "client",
    "description": "description",
    "matter_folder": "matter_folder",
    "status": "status",
    "opposing_party": "opposing_party",
    "other_parties": "other_parties",
    "primary_email": "primary_email",
    "next_action": "next_action",
    "next_action_date": "next_action_date",
    "limitation_date": "limitation_date",
    "court_deadlines": "court_deadlines",
}


def now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


@contextmanager
def connect(path: Path, *, write: bool = False) -> Iterator[sqlite3.Connection]:
    assert_private_file(path)
    if write:
        connection = sqlite3.connect(path, timeout=5, isolation_level=None)
    else:
        uri = sqlite_ro_uri(path)
        connection = sqlite3.connect(uri, uri=True, timeout=5)
    connection.row_factory = sqlite3.Row
    connection.create_function(
        "casefold", 1,
        lambda value: value.casefold() if isinstance(value, str) else "",
        deterministic=True,
    )
    try:
        yield connection
    finally:
        connection.close()


def initialize(path: Path) -> None:
    if path.exists() or path.is_symlink():
        raise ValueError("database already exists")
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    create_private_file(path)
    try:
        with sqlite3.connect(path) as connection:
            connection.executescript(
            """
            PRAGMA foreign_keys = ON;
            CREATE TABLE meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            INSERT INTO meta(key, value) VALUES
                ('schema_version', '1'),
                ('revision', '0');
            CREATE TABLE matters (
                file_number TEXT PRIMARY KEY,
                client TEXT NOT NULL,
                description TEXT NOT NULL,
                matter_folder TEXT NOT NULL UNIQUE,
                status TEXT NOT NULL CHECK(status IN ('open', 'closed')),
                opposing_party TEXT NOT NULL DEFAULT '',
                other_parties TEXT NOT NULL DEFAULT '',
                primary_email TEXT NOT NULL DEFAULT '',
                next_action TEXT NOT NULL DEFAULT '',
                next_action_date TEXT NOT NULL DEFAULT '',
                limitation_date TEXT NOT NULL DEFAULT '',
                court_deadlines TEXT NOT NULL DEFAULT '[]',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE timeline (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_number TEXT NOT NULL REFERENCES matters(file_number),
                event_date TEXT NOT NULL,
                text TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                revision INTEGER NOT NULL,
                action TEXT NOT NULL,
                file_number TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE INDEX timeline_file_idx ON timeline(file_number, id);
            CREATE INDEX audit_file_idx ON audit(file_number, id);
            """
            )
        assert_private_file(path)
    except BaseException:
        path.unlink(missing_ok=True)
        raise


def revision(connection: sqlite3.Connection) -> int:
    row = connection.execute("SELECT value FROM meta WHERE key='revision'").fetchone()
    if row is None:
        raise ValueError("missing tracker revision")
    return int(row[0])


def verify(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"ok": False, "problems": ["database missing"]}
    problems: list[str] = []
    try:
        with connect(path) as connection:
            integrity = connection.execute("PRAGMA quick_check").fetchone()[0]
            if integrity != "ok":
                problems.append(f"sqlite quick_check: {integrity}")
            schema = connection.execute(
                "SELECT value FROM meta WHERE key='schema_version'"
            ).fetchone()
            if schema is None or int(schema[0]) != SCHEMA_VERSION:
                problems.append("unsupported schema version")
            folders = [row[0] for row in connection.execute("SELECT matter_folder FROM matters")]
            try:
                keys = [folder_key(folder) for folder in folders]
                if any(folder != normalize_folder(folder) for folder in folders):
                    problems.append("noncanonical matter folder")
            except ValueError:
                problems.append("unsafe matter folder")
                keys = []
            if len(keys) != len(set(keys)):
                problems.append("duplicate matter folders")
            if any(not row[0].strip() or not row[1].strip() for row in connection.execute("SELECT client, description FROM matters")):
                problems.append("blank required matter fields")
            bad_deadlines = []
            for row in connection.execute("SELECT file_number, court_deadlines FROM matters"):
                try:
                    value = json.loads(row["court_deadlines"])
                    if not isinstance(value, list):
                        raise ValueError
                except (json.JSONDecodeError, ValueError):
                    bad_deadlines.append(row["file_number"])
            if bad_deadlines:
                problems.append("malformed court_deadlines JSON")
            current_revision = revision(connection)
    except (sqlite3.Error, ValueError) as exc:
        return {"ok": False, "problems": [str(exc)]}
    return {"ok": not problems, "revision": current_revision, "problems": problems}


def row_dict(row: sqlite3.Row, *, include_timeline: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    value = dict(row)
    value["court_deadlines"] = json.loads(value["court_deadlines"])
    if include_timeline is not None:
        value["timeline"] = include_timeline
    return value


def get_matter(connection: sqlite3.Connection, file_number: str) -> sqlite3.Row | None:
    return connection.execute(
        "SELECT * FROM matters WHERE file_number=?", (file_number,)
    ).fetchone()


def read_show(path: Path, file_number: str) -> dict[str, Any]:
    with connect(path) as connection:
        row = get_matter(connection, file_number)
        if row is None:
            raise ValueError("matter not found")
        timeline = [dict(item) for item in connection.execute(
            "SELECT id, event_date, text, created_at FROM timeline WHERE file_number=? ORDER BY id",
            (file_number,),
        )]
        return row_dict(row, include_timeline=timeline)


def mutation_payload(action: str, args: argparse.Namespace, current_revision: int) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "database": str(Path(args.database).expanduser().resolve()),
        "revision": current_revision,
        "action": action,
        "file_number": args.file_number,
    }
    if action == "create":
        payload["values"] = {
            "client": args.client.strip(),
            "description": args.description.strip(),
            "matter_folder": normalize_folder(args.matter_folder),
            "status": "open",
            "opposing_party": args.opposing_party.strip(),
            "other_parties": args.other_parties.strip(),
            "primary_email": args.primary_email.strip(),
        }
    elif action == "update":
        changes: dict[str, str] = {}
        for item in args.set_values:
            if "=" not in item:
                raise ValueError("--set requires field=value")
            field, value = item.split("=", 1)
            field = field.strip()
            if field not in FIELDS or field == "status":
                raise ValueError(f"unsupported update field: {field}")
            changes[field] = value.strip()
        if not changes:
            raise ValueError("at least one --set is required")
        if "matter_folder" in changes:
            changes["matter_folder"] = normalize_folder(changes["matter_folder"])
        if "court_deadlines" in changes:
            parsed = json.loads(changes["court_deadlines"])
            if not isinstance(parsed, list):
                raise ValueError("court_deadlines must be a JSON list")
            validate_text(parsed)
            changes["court_deadlines"] = json.dumps(parsed, ensure_ascii=False, sort_keys=True)
        payload["changes"] = changes
    elif action == "timeline":
        if not args.event_date.strip() or not args.text.strip():
            raise ValueError("timeline date and text are required")
        payload["event_date"] = args.event_date.strip()
        payload["text"] = args.text.strip()
    elif action == "workflow":
        changes: dict[str, str] = {}
        if args.next_action is not None:
            changes["next_action"] = args.next_action.strip()
        if args.next_action_date is not None:
            changes["next_action_date"] = args.next_action_date.strip()
        event_date = args.event_date.strip()
        text = args.text.strip()
        if bool(event_date) != bool(text):
            raise ValueError("workflow timeline date and text must be supplied together")
        if not changes and not text:
            raise ValueError("workflow requires a next-action change or timeline entry")
        if changes.get("next_action") == "":
            if not args.clear_next_action:
                raise ValueError("clearing a next action requires --clear-next-action")
            if not text:
                raise ValueError("clearing a next action requires a disposition timeline entry")
            if changes.get("next_action_date", ""):
                raise ValueError("a cleared next action cannot retain a next-action date")
            changes["next_action_date"] = ""
        elif args.clear_next_action:
            raise ValueError("--clear-next-action only applies to an empty next action")
        payload["changes"] = changes
        if text:
            payload["timeline"] = {"event_date": event_date, "text": text}
    elif action in {"close", "reopen"}:
        payload["new_status"] = "closed" if action == "close" else "open"
    else:
        raise ValueError(f"unsupported action: {action}")
    validate_text(payload)
    return payload


def bind_workflow_state(payload: dict[str, Any], row: Mapping[str, Any]) -> None:
    if payload["action"] != "workflow":
        return
    current = {"next_action": row["next_action"], "next_action_date": row["next_action_date"]}
    resulting = dict(current)
    resulting.update(payload["changes"])
    payload["current_workflow"] = current
    payload["resulting_workflow"] = resulting


def validate_payload(connection: sqlite3.Connection, payload: dict[str, Any]) -> None:
    action = payload["action"]
    file_number = payload["file_number"]
    row = get_matter(connection, file_number)
    if action == "create":
        if row is not None:
            raise ValueError("file number already exists")
        values = payload["values"]
        if not file_number.strip() or not values["client"] or not values["description"]:
            raise ValueError("file number, client, and description are required")
    else:
        if row is None:
            raise ValueError("matter not found")
        if action == "update":
            changes = payload["changes"]
            if any(field in changes and not changes[field] for field in ("client", "description")):
                raise ValueError("client and description are required")
            if any(field in changes and not changes[field] for field in ("next_action", "next_action_date")):
                raise ValueError("use workflow to clear next-action state with a disposition")
            if row["status"] == "closed" and set(changes) - {"primary_email", "other_parties"}:
                raise ValueError("matter is closed; reopen it before changing operational fields")
        if action == "timeline" and row["status"] == "closed":
            raise ValueError("matter is closed; reopen it before adding timeline entries")
        if action == "workflow" and row["status"] != "open":
            raise ValueError("matter is closed; reopen it before changing workflow state")
        if action == "close" and row["status"] != "open":
            raise ValueError("matter is not open")
        if action == "reopen" and row["status"] != "closed":
            raise ValueError("matter is not closed")
    folder = (payload["values"]["matter_folder"] if action == "create" else
              payload.get("changes", {}).get("matter_folder"))
    if folder is not None:
        key = folder_key(folder)
        for existing in connection.execute("SELECT file_number, matter_folder FROM matters"):
            if existing["file_number"] != file_number and folder_key(existing["matter_folder"]) == key:
                raise ValueError("matter folder already assigned")


def preview_mutation(path: Path, action: str, args: argparse.Namespace) -> dict[str, Any]:
    with connect(path) as connection:
        current_revision = revision(connection)
        payload = mutation_payload(action, args, current_revision)
        validate_payload(connection, payload)
        row = get_matter(connection, payload["file_number"])
        if row is not None:
            bind_workflow_state(payload, row)
    return {"ok": True, "dry_run": True, "payload": payload, "confirm_token": preview_token(action, payload)}


def _commit_transaction(connection: sqlite3.Connection) -> None:
    """Isolated for deterministic testing of SQLite's ambiguous COMMIT errors."""
    connection.execute("COMMIT")


def commit_mutation(path: Path, action: str, args: argparse.Namespace, token: str) -> dict[str, Any]:
    # Preview validation is not authority to keep using the same pathname. Rebind
    # the confidentiality and single-link invariants immediately before SQLite
    # opens the database so a post-preview path or mode substitution fails closed.
    assert_private_file(path)
    connection = sqlite3.connect(path, timeout=5, isolation_level=None)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("BEGIN IMMEDIATE")
        current_revision = revision(connection)
        payload = mutation_payload(action, args, current_revision)
        validate_payload(connection, payload)
        row = get_matter(connection, payload["file_number"])
        if row is not None:
            bind_workflow_state(payload, row)
        expected = preview_token(action, payload)
        if token != expected:
            raise ValueError("confirmation token is missing, stale, or does not match this mutation")
        timestamp = now()
        file_number = payload["file_number"]
        if action == "create":
            values = payload["values"]
            connection.execute(
                """INSERT INTO matters(
                    file_number, client, description, matter_folder, status,
                    opposing_party, other_parties, primary_email,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, 'open', ?, ?, ?, ?, ?)""",
                (
                    file_number, values["client"], values["description"],
                    values["matter_folder"], values["opposing_party"],
                    values["other_parties"], values["primary_email"], timestamp, timestamp,
                ),
            )
        elif action == "update":
            changes = payload["changes"]
            assignments = ", ".join(f"{FIELDS[key]}=?" for key in sorted(changes))
            values = [changes[key] for key in sorted(changes)]
            connection.execute(
                f"UPDATE matters SET {assignments}, updated_at=? WHERE file_number=?",
                (*values, timestamp, file_number),
            )
        elif action == "timeline":
            connection.execute(
                "INSERT INTO timeline(file_number, event_date, text, created_at) VALUES (?, ?, ?, ?)",
                (file_number, payload["event_date"], payload["text"], timestamp),
            )
            connection.execute(
                "UPDATE matters SET updated_at=? WHERE file_number=?", (timestamp, file_number)
            )
        elif action == "workflow":
            changes = payload["changes"]
            if changes:
                assignments = ", ".join(f"{FIELDS[key]}=?" for key in sorted(changes))
                values = [changes[key] for key in sorted(changes)]
                connection.execute(
                    f"UPDATE matters SET {assignments}, updated_at=? WHERE file_number=?",
                    (*values, timestamp, file_number),
                )
            else:
                connection.execute(
                    "UPDATE matters SET updated_at=? WHERE file_number=?", (timestamp, file_number)
                )
            if "timeline" in payload:
                timeline = payload["timeline"]
                connection.execute(
                    "INSERT INTO timeline(file_number, event_date, text, created_at) VALUES (?, ?, ?, ?)",
                    (file_number, timeline["event_date"], timeline["text"], timestamp),
                )
        elif action in {"close", "reopen"}:
            connection.execute(
                "UPDATE matters SET status=?, updated_at=? WHERE file_number=?",
                (payload["new_status"], timestamp, file_number),
            )
        new_revision = current_revision + 1
        connection.execute("UPDATE meta SET value=? WHERE key='revision'", (str(new_revision),))
        audit_cursor = connection.execute(
            "INSERT INTO audit(revision, action, file_number, payload_json, created_at) VALUES (?, ?, ?, ?, ?)",
            (new_revision, action, file_number, json.dumps(payload, sort_keys=True), timestamp),
        )
        audit_id = int(audit_cursor.lastrowid)
        recovery = {
            "retry_mutation": False,
            "database": str(path),
            "file_number": file_number,
            "expected_revision": new_revision,
            "audit_id": audit_id,
            "required_inspection": ["show", "history", "verify"],
        }
        try:
            _commit_transaction(connection)
        except Exception as exc:
            # A COMMIT call can fail before or after SQLite made the transaction
            # durable. Neither a rollback attempt nor the exception alone can
            # distinguish those outcomes, so require read-only recovery checks.
            try:
                connection.execute("ROLLBACK")
            except sqlite3.Error:
                pass
            return {
                "ok": False,
                "committed": None,
                "commit_state": "outcome_unknown",
                "verification_state": "not_performed",
                "audit_verification_state": "not_performed",
                "audit_id": audit_id,
                "retry_safe": False,
                "revision": new_revision,
                "action": action,
                "file_number": file_number,
                "commit_error": str(exc),
                "recovery": recovery,
            }
        # COMMIT is the durable boundary. A later readback failure must never be
        # reported as an uncommitted, safely retryable mutation: blindly
        # replaying the approved command could create a second timeline entry or
        # apply a later revision than the user approved.
        commit_evidence = {
            "revision": new_revision,
            "action": action,
            "file_number": file_number,
            "audit_id": audit_id,
            "audit_created_at": timestamp,
        }
        try:
            matter = read_show(path, file_number)
        except Exception as exc:
            return {
                "ok": False,
                "committed": True,
                "commit_state": "committed",
                "verification_state": "readback_failed",
                "audit_verification_state": "not_performed",
                "audit_id": audit_id,
                "retry_safe": False,
                "revision": new_revision,
                "action": action,
                "file_number": file_number,
                "commit_evidence": commit_evidence,
                "verification_error": str(exc),
                "recovery": recovery,
            }
        return {
            "ok": True,
            "committed": True,
            "commit_state": "committed",
            "verification_state": "readback_verified",
            "audit_verification_state": "not_performed",
            "audit_id": audit_id,
            "retry_safe": False,
            "revision": new_revision,
            "action": action,
            "file_number": file_number,
            "commit_evidence": commit_evidence,
            "recovery": recovery,
            "matter": matter,
        }
    except Exception:
        try:
            connection.execute("ROLLBACK")
        except sqlite3.Error:
            pass
        raise
    finally:
        connection.close()


def add_mutation_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--database", required=True)
    parser.add_argument("--file-number", required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--confirm-token")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Guarded local matter register")
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init")
    init.add_argument("--database", required=True)
    verify_parser = sub.add_parser("verify")
    verify_parser.add_argument("--database", required=True)
    listing = sub.add_parser("list")
    listing.add_argument("--database", required=True)
    listing.add_argument("--status", choices=["open", "closed", "all"], default="open")
    find = sub.add_parser("find")
    find.add_argument("--database", required=True)
    find.add_argument("--query", required=True)
    find.add_argument("--status", choices=["open", "closed", "all"], default="all")
    show = sub.add_parser("show")
    show.add_argument("--database", required=True)
    show.add_argument("--file-number", required=True)
    history = sub.add_parser("history")
    history.add_argument("--database", required=True)
    history.add_argument("--file-number", required=True)
    create = sub.add_parser("create")
    add_mutation_options(create)
    create.add_argument("--client", required=True)
    create.add_argument("--description", required=True)
    create.add_argument("--matter-folder", required=True)
    create.add_argument("--opposing-party", default="")
    create.add_argument("--other-parties", default="")
    create.add_argument("--primary-email", default="")
    update = sub.add_parser("update")
    add_mutation_options(update)
    update.add_argument("--set", dest="set_values", action="append", default=[])
    timeline = sub.add_parser("timeline")
    add_mutation_options(timeline)
    timeline.add_argument("--event-date", required=True)
    timeline.add_argument("--text", required=True)
    workflow = sub.add_parser("workflow")
    add_mutation_options(workflow)
    workflow.add_argument("--next-action")
    workflow.add_argument("--next-action-date")
    workflow.add_argument("--event-date", default="")
    workflow.add_argument("--text", default="")
    workflow.add_argument("--clear-next-action", action="store_true")
    close = sub.add_parser("close")
    add_mutation_options(close)
    reopen = sub.add_parser("reopen")
    add_mutation_options(reopen)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    path = Path(args.database).expanduser().resolve()
    try:
        if args.command == "init":
            initialize(path)
            emit({"ok": True, "created": str(path), "schema_version": SCHEMA_VERSION})
        elif args.command == "verify":
            result = verify(path)
            emit(result)
            return 0 if result["ok"] else 2
        elif args.command == "list":
            with connect(path) as connection:
                if args.status == "all":
                    rows = connection.execute("SELECT * FROM matters ORDER BY file_number").fetchall()
                else:
                    rows = connection.execute(
                        "SELECT * FROM matters WHERE status=? ORDER BY file_number", (args.status,)
                    ).fetchall()
            emit({"ok": True, "matters": [row_dict(row) for row in rows]})
        elif args.command == "find":
            query = args.query.casefold()
            sql = """SELECT * FROM matters WHERE (
                instr(casefold(file_number), ?) > 0 OR instr(casefold(client), ?) > 0 OR
                instr(casefold(description), ?) > 0 OR instr(casefold(opposing_party), ?) > 0 OR
                instr(casefold(other_parties), ?) > 0 OR instr(casefold(primary_email), ?) > 0
            )"""
            params: list[Any] = [query] * 6
            if args.status != "all":
                sql += " AND status=?"
                params.append(args.status)
            sql += " ORDER BY file_number"
            with connect(path) as connection:
                rows = connection.execute(sql, params).fetchall()
            emit({"ok": True, "query": args.query, "matters": [row_dict(row) for row in rows]})
        elif args.command == "show":
            emit({"ok": True, "matter": read_show(path, args.file_number)})
        elif args.command == "history":
            with connect(path) as connection:
                rows = connection.execute(
                    "SELECT id, revision, action, payload_json, created_at FROM audit WHERE file_number=? ORDER BY id",
                    (args.file_number,),
                ).fetchall()
            emit({"ok": True, "history": [dict(row) for row in rows]})
        else:
            if args.dry_run:
                emit(preview_mutation(path, args.command, args))
            else:
                result = commit_mutation(path, args.command, args, args.confirm_token)
                emit(result)
                return 0 if result["ok"] else 3
        return 0
    except (ValueError, sqlite3.Error, OSError, json.JSONDecodeError) as exc:
        emit({
            "ok": False,
            "committed": False,
            "commit_state": "not_committed",
            "audit_id": None,
            "retry_safe": False,
            "error": str(exc),
        })
        return 2


if __name__ == "__main__":
    sys.exit(main())
