from __future__ import annotations

import argparse
import base64
import hashlib
import html
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

from .common import emit, preview_token
from .config import PracticeConfig, load_config


Transport = Callable[[str, str, dict[str, str], bytes | None], tuple[int, bytes]]
MAX_MAIL_BODY_CHARS = 200_000
MAX_HTTP_RESPONSE_BYTES = 40 * 1024 * 1024
MAX_MAIL_ATTACHMENT_BYTES = 25 * 1024 * 1024
MAX_MAIL_RUN_ATTACHMENT_BYTES = 50 * 1024 * 1024


def url_transport(method: str, url: str, headers: dict[str, str], body: bytes | None) -> tuple[int, bytes]:
    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = response.read(MAX_HTTP_RESPONSE_BYTES + 1)
            if len(payload) > MAX_HTTP_RESPONSE_BYTES:
                raise ValueError("integration response exceeded the bounded read limit")
            return response.status, payload
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()


def _token(env_name: str) -> str:
    if not env_name or not env_name.replace("_", "").isalnum():
        raise ValueError("credential configuration must name an environment variable")
    value = os.environ.get(env_name, "")
    if not value:
        raise ValueError(f"credential unavailable: set environment variable {env_name}")
    return value


def _json_call(transport: Transport, method: str, url: str, token: str, payload: Any = None) -> dict[str, Any]:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    status, data = transport(method, url, headers, body)
    if len(data) > MAX_HTTP_RESPONSE_BYTES:
        raise ValueError("integration response exceeded the bounded read limit")
    if status < 200 or status >= 300:
        raise ValueError(f"remote adapter request failed with HTTP {status}")
    value = json.loads(data.decode("utf-8")) if data else {}
    if not isinstance(value, dict):
        raise ValueError("remote adapter returned a non-object JSON response")
    return value


def _decode_body(message: dict[str, Any]) -> str:
    data = message.get("payload", {}).get("body", {}).get("data", "")
    if not data:
        return ""
    try:
        return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4)).decode("utf-8", errors="replace")
    except (ValueError, TypeError):
        return ""


@dataclass
class GmailReadonlyAdapter:
    token: str
    transport: Transport = url_transport
    api_base: str = "https://gmail.googleapis.com/gmail/v1/users/me"

    def search(self, query: str, limit: int = 100) -> dict[str, Any]:
        if not query.strip():
            raise ValueError("Gmail query is required")
        limit = min(max(int(limit), 1), 500)
        url = f"{self.api_base}/messages?" + urllib.parse.urlencode({"q": query, "maxResults": limit})
        listing = _json_call(self.transport, "GET", url, self.token)
        records = []
        for item in listing.get("messages", []):
            message_id = str(item.get("id", ""))
            if not message_id:
                continue
            message = _json_call(
                self.transport, "GET",
                f"{self.api_base}/messages/{urllib.parse.quote(message_id)}?format=metadata&metadataHeaders=From&metadataHeaders=To&metadataHeaders=Subject&metadataHeaders=Date",
                self.token,
            )
            headers = {str(h.get("name", "")).casefold(): str(h.get("value", "")) for h in message.get("payload", {}).get("headers", [])}
            records.append({
                "id": message_id, "thread_id": message.get("threadId", ""),
                "from": headers.get("from", ""), "to": headers.get("to", ""),
                "subject": headers.get("subject", ""), "date": headers.get("date", ""),
                "snippet": str(message.get("snippet", ""))[:500],
            })
        return {"ok": True, "read_only": True, "query": query, "messages": records,
                "coverage": "bounded", "next_page_token": listing.get("nextPageToken")}

    @staticmethod
    def _decode(value: str) -> bytes:
        try:
            return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
        except (ValueError, TypeError) as exc:
            raise ValueError("Gmail returned malformed base64 content") from exc

    @staticmethod
    def _headers(payload: dict[str, Any]) -> dict[str, str]:
        return {
            str(item.get("name", "")).casefold(): str(item.get("value", ""))
            for item in payload.get("headers", []) if isinstance(item, dict)
        }

    def _full_message(self, message_id: str, attachment_budget: int) -> dict[str, Any]:
        message = _json_call(
            self.transport, "GET",
            f"{self.api_base}/messages/{urllib.parse.quote(message_id)}?format=full",
            self.token,
        )
        payload = message.get("payload", {})
        if not isinstance(payload, dict):
            raise ValueError("Gmail message payload is unavailable")
        headers = self._headers(payload)
        bodies: list[str] = []
        html_bodies: list[str] = []
        attachments: list[dict[str, Any]] = []
        attachment_bytes = 0

        def walk(part: dict[str, Any], index: list[int]) -> None:
            nonlocal attachment_bytes
            part_headers = self._headers(part)
            disposition = part_headers.get("content-disposition", "").casefold()
            mime_type = str(part.get("mimeType", "application/octet-stream")).casefold()
            filename = str(part.get("filename", "")).strip()
            body = part.get("body", {}) if isinstance(part.get("body", {}), dict) else {}
            encoded = str(body.get("data", ""))
            attachment_id = str(body.get("attachmentId", ""))
            declared_size = int(body.get("size", 0) or 0)
            is_body = not filename and mime_type in {"text/plain", "text/html"}
            is_attachment = bool(filename) or bool(attachment_id and not is_body)
            if is_attachment and (
                declared_size > MAX_MAIL_ATTACHMENT_BYTES
                or declared_size > attachment_budget - attachment_bytes
            ):
                attachments.append({
                    "id": attachment_id or f"part-{index[0]}",
                    "filename": filename or f"unnamed-part-{index[0]}",
                    "mime_type": mime_type, "size": declared_size,
                    "inline": "inline" in disposition,
                    "retrieval_error": "attachment exceeds the bounded intake byte limit",
                })
                index[0] += 1
            else:
                if attachment_id:
                    fetched = _json_call(
                        self.transport, "GET",
                        f"{self.api_base}/messages/{urllib.parse.quote(message_id)}/attachments/"
                        f"{urllib.parse.quote(attachment_id)}",
                        self.token,
                    )
                    encoded = str(fetched.get("data", ""))
                if is_attachment and not encoded:
                    attachments.append({
                        "id": attachment_id or f"part-{index[0]}",
                        "filename": filename or f"unnamed-part-{index[0]}",
                        "mime_type": mime_type, "size": body.get("size"),
                        "inline": "inline" in disposition,
                        "retrieval_error": "attachment bytes unavailable",
                    })
                    index[0] += 1
                elif is_attachment:
                    raw = self._decode(encoded)
                    if (
                        len(raw) > MAX_MAIL_ATTACHMENT_BYTES
                        or len(raw) > attachment_budget - attachment_bytes
                    ):
                        attachments.append({
                            "id": attachment_id or f"part-{index[0]}",
                            "filename": filename or f"unnamed-part-{index[0]}",
                            "mime_type": mime_type, "size": len(raw),
                            "inline": "inline" in disposition,
                            "retrieval_error": "attachment exceeds the bounded intake byte limit",
                        })
                    else:
                        attachment_bytes += len(raw)
                        attachments.append({
                            "id": attachment_id or f"part-{index[0]}",
                            "filename": filename or f"unnamed-part-{index[0]}",
                            "mime_type": mime_type, "size": len(raw),
                            "inline": "inline" in disposition,
                            "sha256": hashlib.sha256(raw).hexdigest(),
                            "content_base64": base64.b64encode(raw).decode("ascii"),
                        })
                    index[0] += 1
                elif encoded and mime_type == "text/plain":
                    bodies.append(self._decode(encoded).decode("utf-8", errors="replace"))
                elif encoded and mime_type == "text/html":
                    html_bodies.append(self._decode(encoded).decode("utf-8", errors="replace"))
            for child in part.get("parts", []):
                if isinstance(child, dict):
                    walk(child, index)

        walk(payload, [1])
        if bodies:
            body_text = "\n".join(bodies)
        else:
            body_text = html.unescape(re.sub(r"<[^>]+>", " ", "\n".join(html_bodies)))
            body_text = re.sub(r"\s+", " ", body_text).strip()
        body_complete = len(body_text) <= MAX_MAIL_BODY_CHARS
        internal = str(message.get("internalDate", ""))
        received_at = ""
        if internal.isdigit():
            received_at = datetime.fromtimestamp(int(internal) / 1000, UTC).replace(microsecond=0).isoformat()
        return {
            "id": message_id, "thread_id": str(message.get("threadId", "")),
            "received_at": received_at, "from": headers.get("from", ""),
            "to": headers.get("to", ""), "cc": headers.get("cc", ""),
            "subject": headers.get("subject", ""), "snippet": str(message.get("snippet", ""))[:500],
            "body": body_text[:MAX_MAIL_BODY_CHARS], "body_complete": body_complete,
            "attachments": attachments,
        }

    def intake(self, query: str, limit: int = 100) -> dict[str, Any]:
        if not query.strip():
            raise ValueError("Gmail query is required")
        profile = _json_call(
            self.transport, "GET", f"{self.api_base}/profile", self.token
        )
        account = str(profile.get("emailAddress", "")).strip().casefold()
        if not account:
            raise ValueError("Gmail account identity is unavailable")
        account_fingerprint = hashlib.sha256(f"gmail:{account}".encode("utf-8")).hexdigest()
        limit = min(max(int(limit), 1), 500)
        messages: list[dict[str, Any]] = []
        attachment_bytes = 0
        page_token = ""
        while len(messages) < limit:
            params: dict[str, Any] = {"q": query, "maxResults": min(100, limit - len(messages))}
            if page_token:
                params["pageToken"] = page_token
            listing = _json_call(
                self.transport, "GET", f"{self.api_base}/messages?{urllib.parse.urlencode(params)}",
                self.token,
            )
            for item in listing.get("messages", []):
                message_id = str(item.get("id", ""))
                if message_id:
                    message = self._full_message(
                        message_id, max(0, MAX_MAIL_RUN_ATTACHMENT_BYTES - attachment_bytes)
                    )
                    messages.append(message)
                    attachment_bytes += sum(
                        int(attachment.get("size", 0))
                        for attachment in message["attachments"]
                        if attachment.get("content_base64")
                    )
                    if len(messages) >= limit:
                        break
            page_token = str(listing.get("nextPageToken", ""))
            if not page_token:
                break
        return {
            "schema": "lawyeredos-mail-bundle-v1", "source": "gmail-rest",
            "account_fingerprint": account_fingerprint,
            "query": query, "messages": messages,
            "coverage": {
                "complete": not bool(page_token), "completed_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
                "result_cap": limit, "next_page_token_present": bool(page_token),
            },
        }


@dataclass
class GoogleCalendarAdapter:
    token: str
    calendar_id: str
    transport: Transport = url_transport
    api_base: str = "https://www.googleapis.com/calendar/v3"

    def _calendar(self) -> str:
        if not self.calendar_id or self.calendar_id == "primary":
            raise ValueError("a non-primary dedicated calendar_id is required")
        return urllib.parse.quote(self.calendar_id, safe="")

    def list_events(self, time_min: str, time_max: str, page_limit: int = 20) -> dict[str, Any]:
        if not time_min or not time_max:
            raise ValueError("calendar search requires explicit time_min and time_max")
        events: list[dict[str, Any]] = []
        page_token = ""
        pages = 0
        while True:
            params = {"timeMin": time_min, "timeMax": time_max, "singleEvents": "true", "maxResults": 2500}
            if page_token:
                params["pageToken"] = page_token
            value = _json_call(self.transport, "GET", f"{self.api_base}/calendars/{self._calendar()}/events?{urllib.parse.urlencode(params)}", self.token)
            events.extend(item for item in value.get("items", []) if isinstance(item, dict))
            page_token = str(value.get("nextPageToken", ""))
            pages += 1
            if not page_token:
                break
            if pages >= page_limit:
                raise ValueError("calendar pagination limit reached; coverage incomplete")
        return {"ok": True, "read_only": True, "events": events, "pages": pages, "coverage": "complete"}

    def preview(self, action: str, event: dict[str, Any], event_id: str = "") -> dict[str, Any]:
        if action not in {"create", "update", "delete"}:
            raise ValueError("calendar action must be create, update, or delete")
        if action != "create" and not event_id:
            raise ValueError("calendar update/delete requires an exact event_id")
        if action != "delete" and not event.get("extendedProperties", {}).get("private", {}).get("sync_key"):
            raise ValueError("calendar event requires a private sync_key")
        payload = {"action": action, "calendar_id": self.calendar_id, "event_id": event_id, "event": event}
        return {"ok": True, "dry_run": True, "payload": payload,
                "confirm_token": preview_token("calendar-mutation", payload)}

    def commit(self, action: str, event: dict[str, Any], event_id: str, confirm_token: str) -> dict[str, Any]:
        preview = self.preview(action, event, event_id)
        if confirm_token != preview["confirm_token"]:
            raise ValueError("calendar confirmation token is missing, stale, or mismatched")
        base = f"{self.api_base}/calendars/{self._calendar()}/events"
        if action == "create":
            result = _json_call(self.transport, "POST", base, self.token, event)
        elif action == "update":
            result = _json_call(self.transport, "PUT", f"{base}/{urllib.parse.quote(event_id)}", self.token, event)
        else:
            status, _data = self.transport("DELETE", f"{base}/{urllib.parse.quote(event_id)}", {"Authorization": f"Bearer {self.token}"}, None)
            if status not in {200, 204, 410}:
                raise ValueError(f"remote adapter request failed with HTTP {status}")
            result = {"id": event_id, "deleted": True}
        verified = None
        if action in {"create", "update"}:
            final_id = str(result.get("id", event_id))
            if not final_id:
                raise ValueError("calendar mutation response did not provide an event ID; commit state is uncertain")
            verified = _json_call(self.transport, "GET", f"{base}/{urllib.parse.quote(final_id)}", self.token)
            expected_key = event["extendedProperties"]["private"]["sync_key"]
            actual_key = verified.get("extendedProperties", {}).get("private", {}).get("sync_key")
            if actual_key != expected_key:
                raise ValueError("calendar mutation committed but re-read sync_key did not match")
        return {"ok": True, "committed": True, "action": action, "result": result, "verified": verified}


def gmail_from_config(config: PracticeConfig, transport: Transport = url_transport) -> GmailReadonlyAdapter:
    if config.mail_adapter != "gmail-api-readonly":
        raise ValueError("mail adapter is not configured as gmail-api-readonly")
    return GmailReadonlyAdapter(_token(config.gmail_token_env), transport)


def calendar_from_config(config: PracticeConfig, transport: Transport = url_transport) -> GoogleCalendarAdapter:
    if config.calendar_adapter != "google-calendar-api":
        raise ValueError("calendar adapter is not configured as google-calendar-api")
    return GoogleCalendarAdapter(_token(config.calendar_token_env), config.calendar_id, transport, config.calendar_api_base)


def fixture_mail(path: Path, query: str, limit: int) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    messages = value.get("messages", value) if isinstance(value, dict) else value
    if not isinstance(messages, list):
        raise ValueError("mail fixture must contain a messages list")
    terms = [term.casefold() for term in query.split() if term]
    hits = [item for item in messages if isinstance(item, dict) and all(term in json.dumps(item).casefold() for term in terms)]
    return {"ok": True, "read_only": True, "fixture": True, "messages": hits[:limit], "coverage": "fixture-only"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Explicitly configured Gmail and Calendar adapters")
    sub = parser.add_subparsers(dest="command", required=True)
    mail = sub.add_parser("mail-search")
    mail.add_argument("--config", required=True); mail.add_argument("--query", required=True); mail.add_argument("--limit", type=int, default=100)
    cal = sub.add_parser("calendar-list")
    cal.add_argument("--config", required=True); cal.add_argument("--time-min", required=True); cal.add_argument("--time-max", required=True)
    for name in ("calendar-preview", "calendar-commit"):
        item = sub.add_parser(name)
        item.add_argument("--config", required=True); item.add_argument("--action", choices=["create", "update", "delete"], required=True)
        item.add_argument("--event-json", required=True); item.add_argument("--event-id", default="")
        if name == "calendar-commit": item.add_argument("--confirm-token", required=True)
    args = parser.parse_args(argv)
    try:
        config = load_config(args.config)
        if args.command == "mail-search":
            if config.mail_adapter == "fixture-json":
                if config.mail_fixture is None:
                    raise ValueError("fixture-json mail adapter requires integrations.mail_fixture")
                result = fixture_mail(config.mail_fixture, args.query, args.limit)
            elif config.mail_adapter == "gmail-api-readonly":
                result = gmail_from_config(config).search(args.query, args.limit)
            elif config.mail_adapter == "claude-gmail-connector":
                raise ValueError(
                    "the Claude Gmail connector is available only through an authorized Claude session; "
                    "the local integrations CLI cannot call it"
                )
            elif config.mail_adapter == "codex-session-tools":
                raise ValueError(
                    "Codex session mail tools are available only when the active session exposes an "
                    "authorized read/search tool; the local integrations CLI cannot call them"
                )
            else:
                raise ValueError("mail is unavailable because setup explicitly skipped a mail connection")
        elif args.command == "calendar-list":
            result = calendar_from_config(config).list_events(args.time_min, args.time_max)
        else:
            event = json.loads(Path(args.event_json).read_text(encoding="utf-8"))
            if not isinstance(event, dict):
                raise ValueError("calendar event JSON must be an object")
            adapter = calendar_from_config(config)
            if args.command == "calendar-preview":
                result = adapter.preview(args.action, event, args.event_id)
            else:
                result = adapter.commit(args.action, event, args.event_id, args.confirm_token)
        emit(result); return 0
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        emit({"ok": False, "error": str(exc)}); return 2


if __name__ == "__main__":
    raise SystemExit(main())
