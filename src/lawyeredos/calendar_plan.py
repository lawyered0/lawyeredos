from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .common import emit


REQUIRED = {"sync_key", "date", "title", "timezone"}


def load_events(path: Path, required: bool = True) -> list[dict[str, Any]]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, list):
        raise ValueError(f"{path} must contain a JSON list")
    events: list[dict[str, Any]] = []
    for index, event in enumerate(value):
        if not isinstance(event, dict):
            raise ValueError(f"event {index} in {path} must be an object")
        if not required:
            events.append(event)
            continue
        if not REQUIRED.issubset(event):
            raise ValueError(f"event {index} in {path} is missing required fields")
        if not all(isinstance(event[key], str) and event[key].strip() for key in REQUIRED):
            raise ValueError(f"event {index} in {path} has blank required fields")
        events.append(event)
    return events


def keyed(events: list[dict[str, Any]], label: str) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for event in events:
        key = event["sync_key"]
        if key in result:
            raise ValueError(f"duplicate {label} sync_key: {key}")
        result[key] = event
    return result


PROJECTED_FIELDS = ("date", "title", "timezone", "time", "description", "reminders")


def _valid_event(event: dict[str, Any]) -> bool:
    return all(isinstance(event.get(key), str) and event[key].strip() for key in REQUIRED)


def plan(desired: list[dict[str, Any]], existing: list[dict[str, Any]],
         scope_prefixes: list[str] | None = None, complete: bool = True) -> dict[str, Any]:
    if any(not isinstance(event, dict) or not _valid_event(event) for event in desired):
        raise ValueError("desired events must have nonblank sync_key, date, title and timezone")
    prefixes = list(scope_prefixes or [])
    if any(not isinstance(prefix, str) or not prefix.strip() for prefix in prefixes):
        raise ValueError("scope prefixes must be nonblank")
    def in_scope(key: str) -> bool:
        return any(key.startswith(prefix) for prefix in prefixes)
    if prefixes and any(not in_scope(event["sync_key"]) for event in desired):
        raise ValueError("desired event falls outside the explicit scope")
    desired_by_key = keyed(desired, "desired")
    groups: dict[str, list[dict[str, Any]]] = {}
    unowned = []
    for event in existing:
        if not isinstance(event, dict) or not _valid_event(event):
            unowned.append(event)
            continue
        groups.setdefault(event["sync_key"], []).append(event)
    duplicates = [{"sync_key": key, "events": groups[key]} for key in sorted(groups)
                  if len(groups[key]) > 1]
    existing_by_key = {key: events[0] for key, events in groups.items() if len(events) == 1}
    # A duplicate is evidence of ambiguity, never of an absent desired event.
    create = [desired_by_key[key] for key in sorted(desired_by_key.keys() - groups.keys())]
    unmatched = [existing_by_key[key] for key in sorted(existing_by_key.keys() - desired_by_key.keys())]
    removals_enabled = bool(prefixes and desired and complete)
    remove = [event for event in unmatched if removals_enabled and in_scope(event["sync_key"])]
    update = []
    unchanged = []
    for key in sorted(desired_by_key.keys() & existing_by_key.keys()):
        wanted = desired_by_key[key]
        current = existing_by_key[key]
        if all(wanted.get(field) == current.get(field) for field in PROJECTED_FIELDS):
            unchanged.append(current)
        else:
            update.append({"sync_key": key, "before": current, "after": wanted})
    return {
        "ok": True, "read_only": True, "create": create, "update": update,
        "remove": remove, "unchanged": unchanged, "duplicates": duplicates,
        "unowned_or_unparseable": unowned,
        "unmatched": [event for event in unmatched if event not in remove],
        "scope_prefixes": prefixes, "derivation_complete": complete,
        "removals_enabled": removals_enabled,
        "warning": "This is a plan only. A live connector must search, paginate, read candidates, obtain approval, mutate, and re-read.",
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Read-only calendar reconciliation planner")
    sub = parser.add_subparsers(dest="command", required=True)
    command = sub.add_parser("plan")
    command.add_argument("--desired", required=True)
    command.add_argument("--existing", required=True)
    command.add_argument("--scope-prefix", action="append", default=[],
                         help="exact owned sync-key prefix; repeat for each bounded scope")
    command.add_argument("--partial", action="store_true", help="suppress removals for an incomplete derivation")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = plan(load_events(Path(args.desired)), load_events(Path(args.existing), required=False),
                      args.scope_prefix, complete=not args.partial)
        emit(result)
        return 0
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        emit({"ok": False, "read_only": True, "error": str(exc)})
        return 2


if __name__ == "__main__":
    sys.exit(main())
