from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .common import emit


REQUIRED = {"sync_key", "date", "title", "timezone"}


def load_events(path: Path) -> list[dict[str, Any]]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, list):
        raise ValueError(f"{path} must contain a JSON list")
    events: list[dict[str, Any]] = []
    for index, event in enumerate(value):
        if not isinstance(event, dict) or not REQUIRED.issubset(event):
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


def plan(desired: list[dict[str, Any]], existing: list[dict[str, Any]]) -> dict[str, Any]:
    desired_by_key = keyed(desired, "desired")
    existing_by_key = keyed(existing, "existing")
    create = [desired_by_key[key] for key in sorted(desired_by_key.keys() - existing_by_key.keys())]
    remove = [existing_by_key[key] for key in sorted(existing_by_key.keys() - desired_by_key.keys())]
    update = []
    unchanged = []
    for key in sorted(desired_by_key.keys() & existing_by_key.keys()):
        wanted = desired_by_key[key]
        current = existing_by_key[key]
        if wanted == current:
            unchanged.append(wanted)
        else:
            update.append({"sync_key": key, "before": current, "after": wanted})
    return {
        "ok": True,
        "read_only": True,
        "create": create,
        "update": update,
        "remove": remove,
        "unchanged": unchanged,
        "warning": "This is a plan only. A live connector must search, paginate, read candidates, obtain approval, mutate, and re-read.",
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Read-only calendar reconciliation planner")
    sub = parser.add_subparsers(dest="command", required=True)
    command = sub.add_parser("plan")
    command.add_argument("--desired", required=True)
    command.add_argument("--existing", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = plan(load_events(Path(args.desired)), load_events(Path(args.existing)))
        emit(result)
        return 0
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        emit({"ok": False, "read_only": True, "error": str(exc)})
        return 2


if __name__ == "__main__":
    sys.exit(main())
