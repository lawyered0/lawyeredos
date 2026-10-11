from __future__ import annotations

import argparse
import json
import re
from email.utils import getaddresses
from pathlib import Path
from typing import Any

from .common import canonical_json, emit, sha256_bytes


SCHEMA = "lawyeredos-audience-reconciliation-v1"
MAX_INPUT_BYTES = 5 * 1024 * 1024
FIELDS = ("from", "to", "cc")
ADDRESS = re.compile(r"^[^@\s<>,;:]+@[^@\s<>,;:]+$")


def _parse_field(value: Any, *, allow_empty: bool) -> tuple[list[str], list[str]]:
    if isinstance(value, str):
        values = [value]
    elif isinstance(value, list) and all(isinstance(item, str) for item in value):
        values = value
    else:
        return [], ["header must be a string or a list of strings"]
    raw = ", ".join(values).strip()
    if not raw:
        return ([], []) if allow_empty else ([], ["header is empty"])
    parsed = getaddresses(values)
    addresses: list[str] = []
    problems: list[str] = []
    for _display, address in parsed:
        normalized = address.strip().casefold()
        if not normalized:
            problems.append("header contains a group, placeholder, or unparseable recipient")
            continue
        if not ADDRESS.fullmatch(normalized):
            problems.append("header contains an invalid address")
            continue
        if normalized not in addresses:
            addresses.append(normalized)
    if not addresses and not allow_empty and not problems:
        problems.append("header has no address")
    return sorted(addresses), sorted(set(problems))


def _normalize_audience(
    value: Any, *, retrieved: bool,
) -> tuple[dict[str, list[str]], dict[str, list[str]], list[str]]:
    normalized: dict[str, list[str]] = {}
    ambiguous: dict[str, list[str]] = {}
    unknown: list[str] = []
    if not isinstance(value, dict):
        return normalized, {"audience": ["audience must be an object"]}, unknown
    if retrieved and value.get("headers_complete") is False:
        unknown.append("headers_complete is false")
    for field in FIELDS:
        if field not in value:
            unknown.append(f"{field} header is absent")
            continue
        addresses, problems = _parse_field(value[field], allow_empty=field == "cc")
        normalized[field] = addresses
        if problems:
            ambiguous[field] = problems
    return normalized, ambiguous, unknown


def reconcile(
    message: dict[str, Any],
    expected: dict[str, Any],
    provenance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compare normalized headers; never infer audience from message content."""
    retrieved, retrieved_ambiguous, unknown = _normalize_audience(message, retrieved=True)
    proposed, proposed_ambiguous, proposed_unknown = _normalize_audience(expected, retrieved=False)
    if proposed_unknown:
        proposed_ambiguous["audience"] = proposed_unknown

    evidence_payload = {
        "message_id": str(message.get("id", "")),
        "thread_id": str(message.get("thread_id", "")),
        "headers": retrieved,
        "headers_complete": (
            message.get("headers_complete")
            if isinstance(message.get("headers_complete"), bool) else None
        ),
        "provenance": provenance or {"input_kind": "direct_api"},
    }
    proposed_payload = {"headers": proposed}
    mismatches: dict[str, dict[str, list[str]]] = {}
    if unknown:
        state = "unknown"
    elif retrieved_ambiguous or proposed_ambiguous:
        state = "ambiguous"
    else:
        for field in FIELDS:
            if retrieved[field] != proposed[field]:
                mismatches[field] = {
                    "retrieved": retrieved[field],
                    "proposed": proposed[field],
                    "only_retrieved": sorted(set(retrieved[field]) - set(proposed[field])),
                    "only_proposed": sorted(set(proposed[field]) - set(retrieved[field])),
                }
        state = "mismatch" if mismatches else "verified"

    return {
        "schema": SCHEMA,
        "state": state,
        "retrieved_audience_evidence": {
            **evidence_payload,
            "source": "normalized_message_headers",
            "sha256": sha256_bytes(canonical_json(evidence_payload).encode("utf-8")),
            "limitations": unknown,
            "ambiguities": retrieved_ambiguous,
        },
        "proposed_audience": {
            **proposed_payload,
            "sha256": sha256_bytes(canonical_json(proposed_payload).encode("utf-8")),
            "ambiguities": proposed_ambiguous,
        },
        "comparison": {"exact_role_match": state == "verified", "mismatches": mismatches},
        "authorization": {
            "state": "not_established",
            "statement": (
                "Retrieved From/To/Cc evidence does not authorize sending, delivery, "
                "filing, service, signature, or any account mutation."
            ),
        },
        "delivery_state": "not_established",
        "service_state": "not_established",
    }


def _read_json(path: Path) -> Any:
    if path.is_symlink() or not path.is_file():
        raise ValueError("input must be a regular non-symlink file")
    if path.stat().st_size > MAX_INPUT_BYTES:
        raise ValueError(f"input exceeds {MAX_INPUT_BYTES} bytes")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("input is not readable UTF-8 JSON") from exc


def _select_message(value: Any, message_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    if not isinstance(value, dict):
        raise ValueError("message input must be an object")
    if not message_id:
        raise ValueError("--message-id is required")
    if "messages" not in value:
        if str(value.get("id", "")) != message_id:
            raise ValueError("--message-id does not match the standalone normalized message")
        return value, {"input_kind": "standalone_message"}
    messages = value["messages"]
    if not isinstance(messages, list):
        raise ValueError("bundle messages must be a list")
    if value.get("schema") != "lawyeredos-mail-bundle-v1":
        raise ValueError("normalized mail bundle has an unsupported schema")
    source = value.get("source")
    if not isinstance(source, str) or not source.strip():
        raise ValueError("normalized mail bundle requires a source")
    account_fingerprint = value.get("account_fingerprint")
    if account_fingerprint is not None and not isinstance(account_fingerprint, str):
        raise ValueError("normalized mail bundle account_fingerprint must be a string")
    query = value.get("query")
    if query is not None and not isinstance(query, str):
        raise ValueError("normalized mail bundle query must be a string")
    matches = [
        item for item in messages
        if isinstance(item, dict) and str(item.get("id", "")) == message_id
    ]
    if len(matches) != 1:
        raise ValueError("--message-id must select exactly one normalized message")
    return matches[0], {
        "input_kind": "normalized_bundle",
        "schema": value["schema"],
        "source": source.strip(),
        "account_fingerprint": account_fingerprint.strip().casefold()
        if isinstance(account_fingerprint, str) else None,
        "query": query,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Compare retrieved normalized From/To/Cc evidence with a proposed audience."
    )
    parser.add_argument("--message", type=Path, required=True)
    parser.add_argument("--message-id", required=True)
    parser.add_argument("--expected", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        message, provenance = _select_message(_read_json(args.message), args.message_id)
        expected = _read_json(args.expected)
        emit({"ok": True, **reconcile(message, expected, provenance)})
        return 0
    except ValueError as exc:
        emit({"ok": False, "error": str(exc)})
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
