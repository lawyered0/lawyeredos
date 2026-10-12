from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import sqlite3
import stat
import sys
import tempfile
import re
import secrets
from pathlib import Path
from typing import Any, Callable

from .common import confined_path, emit, preview_token, sha256_file
from .tracker_cli import (
    bind_workflow_state,
    commit_mutation,
    connect,
    get_matter,
    mutation_payload,
    revision,
)


REQUESTED_OPERATION = "write-matter-file"


def _regular_unlinked_path(path: Path, label: str) -> os.stat_result:
    if path.is_symlink():
        raise ValueError(f"{label} must not be a symlink")
    try:
        value = path.stat()
    except FileNotFoundError:
        raise ValueError(f"{label} is missing") from None
    if not stat.S_ISREG(value.st_mode):
        raise ValueError(f"{label} must be a regular file")
    if value.st_nlink != 1:
        raise ValueError(f"{label} must not have hard links")
    return value


def _matter_identity(database: Path, file_number: str) -> tuple[dict[str, Any], int]:
    with connect(database) as connection:
        row = get_matter(connection, file_number)
        if row is None:
            raise ValueError("matter not found")
        matter = dict(row)
        current_revision = revision(connection)
    if matter["status"] != "open":
        raise ValueError("matter is closed; reopen it through the tracker before writing")
    return matter, current_revision


def _workflow_args(args: argparse.Namespace) -> argparse.Namespace | None:
    requested = any((
        args.next_action is not None,
        args.next_action_date is not None,
        bool(args.timeline_event_date),
        bool(args.timeline_text),
        args.clear_next_action,
    ))
    if not requested:
        return None
    return argparse.Namespace(
        database=args.database,
        file_number=args.file_number,
        next_action=args.next_action,
        next_action_date=args.next_action_date,
        event_date=args.timeline_event_date,
        text=args.timeline_text,
        clear_next_action=args.clear_next_action,
    )


def _validate_target(matter: Path, relative_path: str, operation: str,
                     expect_target_sha256: str,
                     existing_content_disposition: str) -> tuple[Path, str, int]:
    target = confined_path(matter, relative_path)
    current = ""
    size = 0
    if target.exists() or target.is_symlink():
        target_stat = _regular_unlinked_path(target, "target")
        current = sha256_file(target)
        size = target_stat.st_size
    if operation == "create":
        if current:
            raise ValueError("create target already exists; nothing may be overwritten")
        if expect_target_sha256:
            raise ValueError("create does not accept an expected target digest")
        if existing_content_disposition:
            raise ValueError("create does not accept an existing-content disposition")
    elif operation == "replace":
        if not current:
            raise ValueError("replace target does not exist")
        if not expect_target_sha256:
            raise ValueError("replace requires the exact previously observed target sha256")
        if current != expect_target_sha256:
            raise ValueError("target compare-and-swap check failed")
        if not existing_content_disposition.strip():
            raise ValueError("replace requires an explicit existing-content disposition")
    else:
        raise ValueError("operation must be create or replace")
    return target, current, size


def write_payload(args: argparse.Namespace) -> dict[str, Any]:
    if args.requested_operation != REQUESTED_OPERATION:
        raise ValueError(f"requested operation must be exactly {REQUESTED_OPERATION}")
    raw_root = Path(args.root).expanduser()
    raw_database = Path(args.database).expanduser()
    raw_source = Path(args.content_file).expanduser()
    if raw_root.is_symlink():
        raise ValueError("workspace root must not be a symlink")
    if raw_database.is_symlink():
        raise ValueError("tracker database must not be a symlink")
    if raw_source.is_symlink():
        raise ValueError("content source must not be a symlink")
    root = raw_root.resolve()
    database = raw_database.resolve()
    _regular_unlinked_path(database, "tracker database")
    matter_record, tracker_revision = _matter_identity(database, args.file_number)
    if matter_record["matter_folder"] != args.matter_folder:
        raise ValueError("matter folder does not match the tracker identity")
    matter = confined_path(root, args.matter_folder)
    if not matter.is_dir() or matter.is_symlink():
        raise ValueError("registered matter folder is missing, a symlink, or not a directory")
    target, old_sha256, old_size = _validate_target(
        matter, args.relative_path, args.operation, args.expect_target_sha256,
        args.existing_content_disposition,
    )
    source = raw_source.resolve()
    source_stat = _regular_unlinked_path(source, "content source")
    if source_stat.st_size == 0:
        raise ValueError("content source must not be empty")
    workflow_args = _workflow_args(args)
    workflow = None
    if workflow_args is not None:
        workflow = mutation_payload("workflow", workflow_args, tracker_revision)
        bind_workflow_state(workflow, matter_record)
    return {
        "requested_operation": REQUESTED_OPERATION,
        "operation": args.operation,
        "root": str(root),
        "database": str(database),
        "file_number": args.file_number,
        "matter_folder": args.matter_folder,
        "matter_status": matter_record["status"],
        "tracker_revision": tracker_revision,
        "relative_path": args.relative_path,
        "target": str(target),
        "old_sha256": old_sha256,
        "old_size": old_size,
        "existing_content_disposition": args.existing_content_disposition.strip(),
        "content_file": str(source),
        "content_sha256": sha256_file(source),
        "content_size": source_stat.st_size,
        "workflow": workflow,
        "authority_source": "explicit_cli_request_only",
    }


def preview(args: argparse.Namespace) -> dict[str, Any]:
    value = write_payload(args)
    return {
        "ok": True,
        "dry_run": True,
        "payload": value,
        "confirm_token": preview_token("matter-write", value),
        "authorizes_external_action": False,
    }


def _private_directory(path: Path) -> None:
    if path.exists() or path.is_symlink():
        if path.is_symlink() or not path.is_dir():
            raise ValueError(f"transaction directory is unsafe: {path}")
        if stat.S_IMODE(path.stat().st_mode) & 0o077:
            raise ValueError(
                f"existing transaction directory is not private; migrate it to mode 0700: {path}"
            )
        return
    path.mkdir(parents=True, mode=0o700)
    os.chmod(path, 0o700)


def _private_journal_root(root: Path) -> Path:
    owner_root = root / ".lawyeredos"
    _private_directory(owner_root)
    transactions = owner_root / "transactions"
    _private_directory(transactions)
    return transactions


def _write_json(path: Path, value: dict[str, Any]) -> None:
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, sort_keys=True, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if temporary.exists():
            temporary.unlink()


def _sha256_descriptor(descriptor: int) -> str:
    digest = hashlib.sha256()
    offset = os.lseek(descriptor, 0, os.SEEK_CUR)
    try:
        os.lseek(descriptor, 0, os.SEEK_SET)
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
        return digest.hexdigest()
    finally:
        os.lseek(descriptor, offset, os.SEEK_SET)


def _write_all(descriptor: int, data: bytes) -> None:
    view = memoryview(data)
    while view:
        written = os.write(descriptor, view)
        if written <= 0:
            raise OSError("write made no forward progress")
        view = view[written:]


def _open_target_parent(root: Path, matter_folder: str, relative_path: str,
                        *, create: bool = True) -> tuple[int, str]:
    combined = Path(matter_folder) / Path(relative_path)
    parts = combined.parts
    if not parts or combined.is_absolute() or ".." in parts:
        raise ValueError("target path must remain inside the registered matter")
    flags = os.O_RDONLY | os.O_DIRECTORY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(root, flags)
    try:
        for part in parts[:-1]:
            try:
                child = os.open(part, flags, dir_fd=descriptor)
            except FileNotFoundError:
                if not create:
                    raise
                os.mkdir(part, 0o700, dir_fd=descriptor)
                os.fsync(descriptor)
                child = os.open(part, flags, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
        return descriptor, parts[-1]
    except Exception:
        os.close(descriptor)
        raise


def _descriptor_for_regular(parent_fd: int, name: str, label: str) -> tuple[int, os.stat_result]:
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(name, flags, dir_fd=parent_fd)
    value = os.fstat(descriptor)
    if not stat.S_ISREG(value.st_mode) or value.st_nlink != 1:
        os.close(descriptor)
        raise ValueError(f"{label} must be a single-link regular file")
    return descriptor, value


def _target_digest(parent_fd: int, name: str) -> str:
    descriptor, _ = _descriptor_for_regular(parent_fd, name, "target")
    try:
        return _sha256_descriptor(descriptor)
    finally:
        os.close(descriptor)


def _stage(source: Path, parent_fd: int, transaction_id: str, expected_sha256: str) -> str:
    source_flags = os.O_RDONLY | (getattr(os, "O_NOFOLLOW", 0))
    source_fd = os.open(source, source_flags)
    name = f".matter-write-{transaction_id}.stage"
    try:
        source_stat = os.fstat(source_fd)
        if not stat.S_ISREG(source_stat.st_mode) or source_stat.st_nlink != 1:
            raise ValueError("content source must remain a single-link regular file")
        if _sha256_descriptor(source_fd) != expected_sha256:
            raise ValueError("content source changed after preview")
        descriptor = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600, dir_fd=parent_fd)
        try:
            os.lseek(source_fd, 0, os.SEEK_SET)
            while True:
                chunk = os.read(source_fd, 1024 * 1024)
                if not chunk:
                    break
                _write_all(descriptor, chunk)
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        if _target_digest(parent_fd, name) != expected_sha256:
            raise ValueError("staged content digest mismatch")
        os.fsync(parent_fd)
        return name
    except Exception:
        try:
            os.unlink(name, dir_fd=parent_fd)
        except FileNotFoundError:
            pass
        raise
    finally:
        os.close(source_fd)


def _install_file(operation: str, staged: str, target: str, parent_fd: int,
                  transaction_id: str, expected_old_sha256: str,
                  *, on_publish: Callable[[], None] | None = None) -> str | None:
    displaced = None
    if operation == "replace":
        displaced = f".matter-write-{transaction_id}.displaced"
        try:
            os.link(target, displaced, src_dir_fd=parent_fd, dst_dir_fd=parent_fd)
        except FileExistsError as exc:
            raise ValueError("stale displaced-file artifact requires recovery") from exc
        if _recovery_file_state(parent_fd, displaced)["sha256"] != expected_old_sha256:
            os.unlink(displaced, dir_fd=parent_fd)
            os.fsync(parent_fd)
            raise ValueError("target changed during commit; approved content was not overwritten")
        target_stat = os.stat(target, dir_fd=parent_fd, follow_symlinks=False)
        displaced_stat = os.stat(displaced, dir_fd=parent_fd, follow_symlinks=False)
        if (target_stat.st_dev, target_stat.st_ino) != (displaced_stat.st_dev, displaced_stat.st_ino):
            os.unlink(displaced, dir_fd=parent_fd)
            raise ValueError("target identity changed during commit")
        os.unlink(target, dir_fd=parent_fd)
    try:
        os.link(staged, target, src_dir_fd=parent_fd, dst_dir_fd=parent_fd)
    except FileExistsError as exc:
        if displaced is not None:
            try:
                os.link(displaced, target, src_dir_fd=parent_fd, dst_dir_fd=parent_fd)
            except FileExistsError:
                pass
            os.unlink(displaced, dir_fd=parent_fd)
            os.fsync(parent_fd)
        raise ValueError("target appeared during commit; concurrent content was not overwritten") from exc
    if on_publish is not None:
        on_publish()
    os.unlink(staged, dir_fd=parent_fd)
    if displaced is not None:
        os.unlink(displaced, dir_fd=parent_fd)
    os.fsync(parent_fd)
    return displaced


def _restore(operation: str, parent_fd: int, target_name: str, backup: Path | None,
             installed_sha256: str, old_sha256: str) -> bool:
    rollback_name = f".matter-rollback-{os.getpid()}"
    restore_name = f".matter-restore-{os.getpid()}"
    try:
        if operation == "replace":
            if backup is None:
                return False
            backup_flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
            backup_fd = os.open(backup, backup_flags)
            try:
                backup_stat = os.fstat(backup_fd)
                if not stat.S_ISREG(backup_stat.st_mode) or backup_stat.st_nlink != 1:
                    return False
                if _sha256_descriptor(backup_fd) != old_sha256:
                    return False
                restore_fd = os.open(
                    restore_name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600, dir_fd=parent_fd,
                )
                try:
                    os.lseek(backup_fd, 0, os.SEEK_SET)
                    while True:
                        chunk = os.read(backup_fd, 1024 * 1024)
                        if not chunk:
                            break
                        _write_all(restore_fd, chunk)
                    os.fsync(restore_fd)
                finally:
                    os.close(restore_fd)
                if _recovery_file_state(parent_fd, restore_name)["sha256"] != old_sha256:
                    raise ValueError("restored staging digest mismatch")
            finally:
                os.close(backup_fd)
        try:
            os.link(target_name, rollback_name, src_dir_fd=parent_fd, dst_dir_fd=parent_fd)
        except FileExistsError:
            return False
        if _recovery_file_state(parent_fd, rollback_name)["sha256"] != installed_sha256:
            os.unlink(rollback_name, dir_fd=parent_fd)
            return False
        target_stat = os.stat(target_name, dir_fd=parent_fd, follow_symlinks=False)
        rollback_stat = os.stat(rollback_name, dir_fd=parent_fd, follow_symlinks=False)
        if (target_stat.st_dev, target_stat.st_ino) != (rollback_stat.st_dev, rollback_stat.st_ino):
            os.unlink(rollback_name, dir_fd=parent_fd)
            return False
        os.unlink(target_name, dir_fd=parent_fd)
        if operation == "create":
            os.unlink(rollback_name, dir_fd=parent_fd)
        else:
            try:
                os.link(restore_name, target_name, src_dir_fd=parent_fd, dst_dir_fd=parent_fd)
            except FileExistsError:
                os.unlink(restore_name, dir_fd=parent_fd)
                os.unlink(rollback_name, dir_fd=parent_fd)
                return False
            os.unlink(restore_name, dir_fd=parent_fd)
            os.unlink(rollback_name, dir_fd=parent_fd)
            if _target_digest(parent_fd, target_name) != old_sha256:
                return False
        os.fsync(parent_fd)
        return True
    except (OSError, ValueError):
        try:
            os.stat(target_name, dir_fd=parent_fd, follow_symlinks=False)
        except FileNotFoundError:
            try:
                os.link(rollback_name, target_name, src_dir_fd=parent_fd, dst_dir_fd=parent_fd)
            except (FileNotFoundError, FileExistsError):
                pass
        for name in (restore_name, rollback_name):
            try:
                os.unlink(name, dir_fd=parent_fd)
            except FileNotFoundError:
                pass
        return False
    finally:
        try:
            os.unlink(restore_name, dir_fd=parent_fd)
        except FileNotFoundError:
            pass


def _commit_workflow(value: dict[str, Any], args: argparse.Namespace) -> dict[str, Any] | None:
    if value["workflow"] is None:
        return None
    workflow_args = _workflow_args(args)
    assert workflow_args is not None
    workflow_token = preview_token("workflow", value["workflow"])
    try:
        return commit_mutation(Path(value["database"]), "workflow", workflow_args, workflow_token)
    except (ValueError, OSError, sqlite3.Error) as exc:
        # commit_mutation converts every ambiguous or post-COMMIT failure into a
        # receipt. An exception therefore occurred before its durable boundary.
        return {
            "ok": False,
            "committed": False,
            "commit_state": "not_committed",
            "verification_state": "not_performed",
            "retry_safe": False,
            "error": str(exc),
        }


def _recheck_tracker(value: dict[str, Any]) -> None:
    matter, current_revision = _matter_identity(Path(value["database"]), value["file_number"])
    if current_revision != value["tracker_revision"]:
        raise ValueError("tracker changed after preview")
    if matter["matter_folder"] != value["matter_folder"]:
        raise ValueError("matter folder changed after preview")


def _create_backup(parent_fd: int, target_name: str, backup: Path,
                   expected_sha256: str) -> None:
    source_fd, _ = _descriptor_for_regular(parent_fd, target_name, "target")
    output_fd = os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        if _sha256_descriptor(source_fd) != expected_sha256:
            raise ValueError("target changed after preview")
        os.lseek(source_fd, 0, os.SEEK_SET)
        while True:
            chunk = os.read(source_fd, 1024 * 1024)
            if not chunk:
                break
            _write_all(output_fd, chunk)
        os.fsync(output_fd)
    except Exception:
        os.close(output_fd)
        output_fd = -1
        backup.unlink(missing_ok=True)
        raise
    finally:
        os.close(source_fd)
        if output_fd >= 0:
            os.close(output_fd)
    if sha256_file(backup) != expected_sha256:
        backup.unlink()
        raise ValueError("recovery backup digest mismatch")
    directory = os.open(backup.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def _verify_parent_binding(value: dict[str, Any], expected: os.stat_result) -> None:
    descriptor, _ = _open_target_parent(
        Path(value["root"]), value["matter_folder"], value["relative_path"], create=False,
    )
    try:
        current = os.fstat(descriptor)
        if current.st_dev != expected.st_dev or current.st_ino != expected.st_ino:
            raise ValueError("target parent changed during commit")
    finally:
        os.close(descriptor)


def _journal_directory_descriptor(root: Path) -> int:
    flags = os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(root, flags)
    try:
        for part in (".lawyeredos", "transactions"):
            child = os.open(part, flags, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
        return descriptor
    except Exception:
        os.close(descriptor)
        raise


def _load_journal(root: Path, transaction_id: str) -> tuple[Path, dict[str, Any]]:
    if not re.fullmatch(r"[0-9a-f]{24}", transaction_id):
        raise ValueError("transaction id must be exactly 24 lowercase hexadecimal characters")
    if root.is_symlink():
        raise ValueError("workspace root must not be a symlink")
    journal_root = root / ".lawyeredos" / "transactions"
    journal = journal_root / f"{transaction_id}.json"
    directory = _journal_directory_descriptor(root)
    descriptor = -1
    try:
        descriptor = os.open(
            f"{transaction_id}.json", os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
            dir_fd=directory,
        )
        journal_stat = os.fstat(descriptor)
        if not stat.S_ISREG(journal_stat.st_mode) or journal_stat.st_nlink != 1:
            raise ValueError("transaction journal must be a single-link regular file")
        with os.fdopen(descriptor, "r", encoding="utf-8") as handle:
            descriptor = -1
            value = json.load(handle)
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        os.close(directory)
    if value.get("transaction_id") != transaction_id or not isinstance(value.get("approved_payload"), dict):
        raise ValueError("transaction journal identity or payload is invalid")
    return journal, value


def _write_recovery_journal(root: Path, transaction_id: str, value: dict[str, Any]) -> None:
    directory = _journal_directory_descriptor(root)
    temporary_name = f".{transaction_id}.recovery-{os.getpid()}"
    descriptor = -1
    try:
        descriptor = os.open(
            temporary_name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600, dir_fd=directory,
        )
        data = (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()
        _write_all(descriptor, data)
        os.fsync(descriptor)
        os.close(descriptor)
        descriptor = -1
        os.replace(
            temporary_name, f"{transaction_id}.json",
            src_dir_fd=directory, dst_dir_fd=directory,
        )
        os.fsync(directory)
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        try:
            os.unlink(temporary_name, dir_fd=directory)
        except FileNotFoundError:
            pass
        os.close(directory)


def _tracker_recovery_state(payload: dict[str, Any]) -> str:
    workflow = payload.get("workflow")
    if workflow is None:
        return "not_applicable"
    with connect(Path(payload["database"])) as connection:
        current_revision = revision(connection)
        row = connection.execute(
            "SELECT payload_json FROM audit WHERE revision=? AND action='workflow' AND file_number=?",
            (payload["tracker_revision"] + 1, payload["file_number"]),
        ).fetchone()
    if row is not None and json.loads(row["payload_json"]) == workflow:
        return "committed"
    if current_revision == payload["tracker_revision"]:
        return "not_committed"
    return "outcome_unknown"


def _recovery_file_state(parent_fd: int, name: str) -> dict[str, Any]:
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(name, flags, dir_fd=parent_fd)
    except FileNotFoundError:
        return {"sha256": "", "links": 0, "inode": None}
    try:
        value = os.fstat(descriptor)
        if not stat.S_ISREG(value.st_mode):
            raise ValueError("recovery target is not a regular file")
        return {
            "sha256": _sha256_descriptor(descriptor),
            "links": value.st_nlink,
            "inode": [value.st_dev, value.st_ino],
        }
    finally:
        os.close(descriptor)


def inspect_recovery(root: Path, transaction_id: str) -> dict[str, Any]:
    root = root.expanduser()
    if root.is_symlink():
        raise ValueError("workspace root must not be a symlink")
    root = root.resolve()
    journal, receipt = _load_journal(root, transaction_id)
    payload = receipt["approved_payload"]
    if Path(payload["root"]) != root:
        raise ValueError("transaction journal belongs to a different workspace")
    parent_fd, target_name = _open_target_parent(
        root, payload["matter_folder"], payload["relative_path"], create=False,
    )
    try:
        identity = os.fstat(parent_fd)
        expected_identity = receipt["target_parent_identity"]
        if identity.st_dev != expected_identity["device"] or identity.st_ino != expected_identity["inode"]:
            raise ValueError("target parent identity changed; automatic recovery is unsafe")
        target_state = _recovery_file_state(parent_fd, target_name)
        staged_name = receipt.get("staged_name") or f".matter-write-{transaction_id}.stage"
        staged_state = _recovery_file_state(parent_fd, staged_name)
        displaced_name = f".matter-write-{transaction_id}.displaced"
        displaced_state = _recovery_file_state(parent_fd, displaced_name)
    finally:
        os.close(parent_fd)
    target_sha256 = target_state["sha256"]
    backup_state = "not_applicable"
    backup_path = receipt.get("recovery_backup")
    if backup_path:
        try:
            _regular_unlinked_path(Path(backup_path), "recovery backup")
            backup_state = (
                "verified" if sha256_file(Path(backup_path)) == payload["old_sha256"] else "mismatch"
            )
        except (OSError, ValueError):
            backup_state = "missing"
    tracker_state = _tracker_recovery_state(payload)
    terminal_committed = (
        receipt.get("commit_state") == "committed"
        and receipt.get("verification_state") == "readback_verified"
        and target_sha256 == payload["content_sha256"]
        and tracker_state in {"committed", "not_applicable"}
    )
    terminal_not_committed = (
        receipt.get("commit_state") == "not_committed"
        and receipt.get("verification_state") in {"rollback_verified", "readback_verified"}
        and (target_sha256 == payload["old_sha256"] or (payload["operation"] == "create" and not target_sha256))
        and tracker_state in {"not_committed", "not_applicable"}
    )
    if terminal_committed:
        action = "finalize_committed"
    elif terminal_not_committed:
        action = "finalize_not_committed"
    elif tracker_state in {"committed", "outcome_unknown"}:
        action = "finalize_committed" if tracker_state == "committed" and target_sha256 == payload["content_sha256"] else "manual_required"
    elif target_sha256 == payload["content_sha256"]:
        action = "rollback_file"
    elif payload["operation"] == "replace" and not target_sha256 and backup_state == "verified":
        action = "restore_missing_target"
    elif target_sha256 == payload["old_sha256"] or (payload["operation"] == "create" and not target_sha256):
        action = "finalize_not_committed"
    else:
        action = "manual_required"
    plan = {
        "transaction_id": transaction_id,
        "journal": str(journal),
        "action": action,
        "target_sha256": target_sha256,
        "backup_state": backup_state,
        "tracker_state": tracker_state,
        "target_state": target_state,
        "staged_name": staged_name,
        "staged_state": staged_state,
        "displaced_name": displaced_name,
        "displaced_state": displaced_state,
    }
    return {
        "ok": action != "manual_required",
        "dry_run": True,
        "plan": plan,
        "confirm_token": preview_token("matter-write-recovery", plan),
    }


def _cleanup_recovery_artifact(parent_fd: int, name: str, planned: dict[str, Any],
                               allowed_sha256: set[str]) -> None:
    if planned["inode"] is None or planned["sha256"] not in allowed_sha256:
        return
    current = _recovery_file_state(parent_fd, name)
    if current["inode"] == planned["inode"] and current["sha256"] == planned["sha256"]:
        os.unlink(name, dir_fd=parent_fd)


def _restore_missing_from_backup(parent_fd: int, target_name: str, backup: Path,
                                 transaction_id: str, expected_sha256: str) -> bool:
    restore_name = f".matter-recovery-{transaction_id}.tmp"
    backup_fd = os.open(backup, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    restore_fd: int | None = None
    try:
        backup_stat = os.fstat(backup_fd)
        if not stat.S_ISREG(backup_stat.st_mode) or backup_stat.st_nlink != 1:
            raise ValueError("recovery backup is no longer a single-link regular file")
        if _sha256_descriptor(backup_fd) != expected_sha256:
            raise ValueError("recovery backup changed after inspection")
        os.lseek(backup_fd, 0, os.SEEK_SET)
        restore_fd = os.open(
            restore_name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600, dir_fd=parent_fd,
        )
        while True:
            chunk = os.read(backup_fd, 1024 * 1024)
            if not chunk:
                break
            _write_all(restore_fd, chunk)
        os.fsync(restore_fd)
        os.close(restore_fd)
        restore_fd = None
        if _recovery_file_state(parent_fd, restore_name)["sha256"] != expected_sha256:
            raise ValueError("staged recovery bytes did not match the approved backup")
        try:
            os.link(restore_name, target_name, src_dir_fd=parent_fd, dst_dir_fd=parent_fd)
        except FileExistsError:
            raise ValueError("target appeared during recovery; concurrent content was preserved") from None
        os.unlink(restore_name, dir_fd=parent_fd)
        os.fsync(parent_fd)
        return _target_digest(parent_fd, target_name) == expected_sha256
    finally:
        os.close(backup_fd)
        if restore_fd is not None:
            os.close(restore_fd)
        try:
            os.unlink(restore_name, dir_fd=parent_fd)
            os.fsync(parent_fd)
        except FileNotFoundError:
            pass


def recover(root: Path, transaction_id: str, token: str) -> dict[str, Any]:
    inspected = inspect_recovery(root, transaction_id)
    plan = inspected["plan"]
    if plan["action"] == "manual_required":
        raise ValueError("automatic recovery is unsafe; preserve the journal and inspect manually")
    if token != inspected["confirm_token"]:
        raise ValueError("recovery confirmation token is stale or mismatched")
    journal, receipt = _load_journal(root.expanduser().resolve(), transaction_id)
    payload = receipt["approved_payload"]
    parent_fd, target_name = _open_target_parent(
        Path(payload["root"]), payload["matter_folder"], payload["relative_path"], create=False,
    )
    try:
        current_parent = os.fstat(parent_fd)
        expected_parent = receipt["target_parent_identity"]
        if (current_parent.st_dev, current_parent.st_ino) != (
            expected_parent["device"], expected_parent["inode"],
        ):
            raise ValueError("target parent changed after recovery inspection")
        if _recovery_file_state(parent_fd, target_name) != plan["target_state"]:
            raise ValueError("target changed after recovery inspection")
        if _tracker_recovery_state(payload) != plan["tracker_state"]:
            raise ValueError("tracker changed after recovery inspection")
        if plan["action"] in {"rollback_file", "restore_missing_target"}:
            # A crash after link(stage,target) can leave the deterministic stage
            # name as a second hard link. Remove only the exact same inode.
            if (
                plan["staged_state"]["inode"] is not None
                and plan["staged_state"]["inode"] == plan["target_state"]["inode"]
                and plan["staged_state"]["sha256"] == payload["content_sha256"]
            ):
                _cleanup_recovery_artifact(
                    parent_fd, plan["staged_name"], plan["staged_state"],
                    {payload["content_sha256"]},
                )
                os.fsync(parent_fd)
            backup = Path(receipt["recovery_backup"]) if receipt.get("recovery_backup") else None
            if plan["action"] == "rollback_file":
                restored = _restore(
                    payload["operation"], parent_fd, target_name, backup,
                    payload["content_sha256"], payload["old_sha256"],
                )
            else:
                if backup is None or plan["backup_state"] != "verified":
                    restored = False
                else:
                    restored = _restore_missing_from_backup(
                        parent_fd, target_name, backup, transaction_id, payload["old_sha256"],
                    )
            if not restored:
                raise ValueError("recovery could not verify the restored target")
            receipt["commit_state"] = "not_committed"
            receipt["verification_state"] = "rollback_verified"
        elif plan["action"] == "finalize_committed":
            receipt["commit_state"] = "committed"
            receipt["verification_state"] = "readback_verified"
        else:
            receipt["commit_state"] = "not_committed"
            receipt["verification_state"] = "readback_verified"
        allowed = {payload["content_sha256"], payload["old_sha256"]} - {""}
        _cleanup_recovery_artifact(
            parent_fd, plan["staged_name"], plan["staged_state"], allowed,
        )
        _cleanup_recovery_artifact(
            parent_fd, plan["displaced_name"], plan["displaced_state"], allowed,
        )
        os.fsync(parent_fd)
    finally:
        os.close(parent_fd)
    receipt["recovered"] = True
    _write_recovery_journal(Path(payload["root"]), transaction_id, receipt)
    return {"ok": True, "committed": receipt["commit_state"] == "committed", **receipt, "journal": str(journal)}


def _reserve_attempt(root: Path, expected: str, journal: Path, receipt: dict[str, Any]) -> None:
    """Preserve each receipt while preventing replay of unresolved attempts."""
    directory = _journal_directory_descriptor(root)
    lock_fd = None
    try:
        lock_fd = os.open(".attempts.lock", os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW,
                          0o600, dir_fd=directory)
        details = os.fstat(lock_fd)
        if not stat.S_ISREG(details.st_mode) or details.st_nlink != 1:
            raise ValueError("transaction lock must be a single-link regular file")
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        for path in sorted(journal.parent.glob(expected[:16] + "*.json")):
            _, previous = _load_journal(root, path.stem)
            if previous.get("approved_payload_sha256") != expected:
                continue
            terminal = previous.get("commit_state") == "not_committed" and (
                previous.get("verification_state") == "rollback_verified"
                or (previous.get("recovered") is True
                    and previous.get("verification_state") == "readback_verified")
            )
            if not terminal:
                raise ValueError("this approved transaction already has a journal; inspect it instead of replaying")
        if journal.exists() or journal.is_symlink():
            raise ValueError("transaction attempt id already exists")
        _write_json(journal, receipt)
    finally:
        if lock_fd is not None:
            os.close(lock_fd)
        os.close(directory)


def commit(args: argparse.Namespace) -> dict[str, Any]:
    value = write_payload(args)
    expected = preview_token("matter-write", value)
    if args.confirm_token != expected:
        raise ValueError("confirmation token is missing, stale, or does not match this exact write")
    target = Path(value["target"])
    source = Path(value["content_file"])
    parent_fd, target_name = _open_target_parent(
        Path(value["root"]), value["matter_folder"], value["relative_path"],
    )
    journal_root = _private_journal_root(Path(value["root"]))
    transaction_id = expected[:16] + secrets.token_hex(4)
    journal = journal_root / f"{transaction_id}.json"
    backup = journal_root / f"{transaction_id}.backup" if value["operation"] == "replace" else None
    parent_identity = os.fstat(parent_fd)
    receipt: dict[str, Any] = {
        "transaction_id": transaction_id,
        "file_number": value["file_number"],
        "target": value["target"],
        "operation": value["operation"],
        "approved_payload_sha256": expected,
        "commit_state": "not_committed",
        "verification_state": "not_performed",
        "tracker_receipt": None,
        "recovery_backup": str(backup) if backup else None,
        "approved_payload": value,
        "target_parent_identity": {"device": parent_identity.st_dev, "inode": parent_identity.st_ino},
        "staged_name": None,
        "retry_safe": False,
    }
    try:
        _reserve_attempt(Path(value["root"]), expected, journal, receipt)
    except BaseException:
        os.close(parent_fd)
        raise
    staged: str | None = None
    installed = False
    tracker_phase = "not_started"
    try:
        _recheck_tracker(value)
        try:
            current_target = _target_digest(parent_fd, target_name)
        except FileNotFoundError:
            current_target = ""
        if current_target != value["old_sha256"]:
            raise ValueError("target changed after preview")
        if backup is not None:
            _create_backup(parent_fd, target_name, backup, value["old_sha256"])
        staged = _stage(source, parent_fd, transaction_id, value["content_sha256"])
        receipt["staged_name"] = staged
        receipt["commit_state"] = "prepared"
        _write_json(journal, receipt)
        _recheck_tracker(value)
        _install_file(
            value["operation"], staged, target_name, parent_fd, transaction_id, value["old_sha256"],
        )
        staged = None
        installed = True
        _verify_parent_binding(value, parent_identity)
        _recheck_tracker(value)
        if _target_digest(parent_fd, target_name) != value["content_sha256"]:
            raise ValueError("target readback digest mismatch after install")
        receipt["commit_state"] = "file_committed"
        receipt["verification_state"] = "file_readback_verified"
        receipt["staged_name"] = None
        _write_json(journal, receipt)
        tracker_phase = "invoked_unknown"
        tracker_receipt = _commit_workflow(value, args)
        receipt["tracker_receipt"] = tracker_receipt
        if tracker_receipt is not None and tracker_receipt["commit_state"] == "outcome_unknown":
            receipt["commit_state"] = "outcome_unknown"
            receipt["target_sha256"] = _target_digest(parent_fd, target_name)
            receipt["file_verification_state"] = "readback_verified"
            _write_json(journal, receipt)
            return {"ok": False, "committed": None, **receipt, "journal": str(journal)}
        if tracker_receipt is not None and not tracker_receipt["committed"]:
            tracker_phase = "not_committed"
            if not _restore(
                value["operation"], parent_fd, target_name, backup,
                value["content_sha256"], value["old_sha256"],
            ):
                receipt["commit_state"] = "outcome_unknown"
                _write_json(journal, receipt)
                return {"ok": False, "committed": None, **receipt, "journal": str(journal)}
            installed = False
            receipt["commit_state"] = "not_committed"
            receipt["verification_state"] = "rollback_verified"
            _write_json(journal, receipt)
            return {"ok": False, "committed": False, **receipt, "journal": str(journal)}
        if tracker_receipt is not None and tracker_receipt["verification_state"] != "readback_verified":
            receipt["commit_state"] = "committed"
            receipt["verification_state"] = "readback_failed"
            receipt["target_sha256"] = _target_digest(parent_fd, target_name)
            receipt["file_verification_state"] = "readback_verified"
            receipt["verification_error"] = "tracker commit was durable but its readback was not verified"
            _write_json(journal, receipt)
            return {"ok": False, "committed": True, **receipt, "journal": str(journal)}
        receipt["commit_state"] = "committed"
        try:
            if _target_digest(parent_fd, target_name) != value["content_sha256"]:
                raise ValueError("target readback digest mismatch")
            receipt["verification_state"] = "readback_verified"
            receipt["target_sha256"] = value["content_sha256"]
            _write_json(journal, receipt)
            return {"ok": True, "committed": True, **receipt, "journal": str(journal)}
        except Exception as exc:
            receipt["verification_state"] = "readback_failed"
            receipt["verification_error"] = str(exc)
            _write_json(journal, receipt)
            return {"ok": False, "committed": True, **receipt, "journal": str(journal)}
    except Exception as exc:
        if installed and tracker_phase in {"not_started", "not_committed"}:
            restored = _restore(
                value["operation"], parent_fd, target_name, backup,
                value["content_sha256"], value["old_sha256"],
            )
            receipt["commit_state"] = "not_committed" if restored else "outcome_unknown"
            receipt["verification_state"] = "rollback_verified" if restored else "rollback_failed"
        elif installed:
            receipt["commit_state"] = "outcome_unknown"
            try:
                receipt["target_sha256"] = _target_digest(parent_fd, target_name)
                receipt["file_verification_state"] = "readback_verified"
            except Exception as verify_exc:
                receipt["file_verification_state"] = "readback_failed"
                receipt["file_verification_error"] = str(verify_exc)
        receipt["error"] = str(exc)
        try:
            _write_json(journal, receipt)
        except Exception as journal_exc:
            receipt["journal_error"] = str(journal_exc)
        if receipt["commit_state"] == "outcome_unknown":
            return {"ok": False, "committed": None, **receipt, "journal": str(journal)}
        return {"ok": False, "committed": False, **receipt, "journal": str(journal)}
    finally:
        if staged is not None:
            try:
                os.unlink(staged, dir_fd=parent_fd)
                os.fsync(parent_fd)
            except FileNotFoundError:
                pass
        os.close(parent_fd)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Guarded durable matter-file writer")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("preview", "commit"):
        command = sub.add_parser(name)
        command.add_argument("--requested-operation", required=True)
        command.add_argument("--operation", choices=("create", "replace"), required=True)
        command.add_argument("--root", required=True)
        command.add_argument("--database", required=True)
        command.add_argument("--file-number", required=True)
        command.add_argument("--matter-folder", required=True)
        command.add_argument("--relative-path", required=True)
        command.add_argument("--content-file", required=True)
        command.add_argument("--expect-target-sha256", default="")
        command.add_argument("--existing-content-disposition", default="")
        command.add_argument("--next-action")
        command.add_argument("--next-action-date")
        command.add_argument("--timeline-event-date", default="")
        command.add_argument("--timeline-text", default="")
        command.add_argument("--clear-next-action", action="store_true")
        if name == "commit":
            command.add_argument("--confirm-token", required=True)
    inspect_command = sub.add_parser("inspect-recovery")
    inspect_command.add_argument("--root", required=True)
    inspect_command.add_argument("--transaction-id", required=True)
    recover_command = sub.add_parser("recover")
    recover_command.add_argument("--root", required=True)
    recover_command.add_argument("--transaction-id", required=True)
    recover_command.add_argument("--confirm-token", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "preview":
            result = preview(args)
        elif args.command == "commit":
            result = commit(args)
        elif args.command == "inspect-recovery":
            result = inspect_recovery(Path(args.root), args.transaction_id)
        else:
            result = recover(Path(args.root), args.transaction_id, args.confirm_token)
        emit(result)
        return 0 if result["ok"] else 3
    except (ValueError, OSError, sqlite3.Error, UnicodeDecodeError) as exc:
        emit({
            "ok": False,
            "committed": False,
            "commit_state": "not_committed",
            "verification_state": "not_performed",
            "retry_safe": False,
            "error": str(exc),
        })
        return 2


if __name__ == "__main__":
    sys.exit(main())
