from __future__ import annotations

import base64
import hashlib
import html
import imaplib
import mimetypes
import re
import subprocess
from dataclasses import dataclass, field
from datetime import UTC, datetime
from email import policy
from email.header import decode_header
from email.message import Message
from email.parser import BytesParser
from email.utils import getaddresses, parsedate_to_datetime
from typing import Any, Callable

from .config import PracticeConfig


SCHEMA = "lawyeredos-mail-bundle-v1"
IMAP_HOST = "imap.gmail.com"
MAX_RESULTS = 500
MAX_QUERY_CHARS = 4_000
MAX_BODY_CHARS = 200_000
MAX_RAW_MESSAGE_BYTES = 40 * 1024 * 1024
MAX_RUN_RAW_MESSAGE_BYTES = 80 * 1024 * 1024
MAX_ATTACHMENT_BYTES = 25 * 1024 * 1024
MAX_RUN_ATTACHMENT_BYTES = 50 * 1024 * 1024


ClientFactory = Callable[[str], Any]


def _default_client(host: str) -> imaplib.IMAP4_SSL:
    return imaplib.IMAP4_SSL(host, timeout=30)


def _environment_name(value: str) -> str:
    if not value or not value.replace("_", "").isalnum():
        raise ValueError("IMAP credential configuration must name an environment variable")
    return value


def credentials_from_config(config: PracticeConfig) -> tuple[str, str]:
    import os

    account_env = _environment_name(config.gmail_imap_account_env)
    password_env = _environment_name(config.gmail_imap_secret_env)
    account = os.environ.get(account_env, "").strip()
    password = os.environ.get(password_env, "").replace(" ", "").strip()
    if bool(account) != bool(password):
        raise ValueError(
            "Gmail IMAP environment credentials are incomplete; set both configured variables"
        )
    if account and password:
        return account, password
    service = config.gmail_imap_keychain_service
    if service:
        if any(ord(character) < 32 for character in service) or len(service) > 128:
            raise ValueError("Gmail IMAP Keychain service name is invalid")
        try:
            account_result = subprocess.run(
                ["security", "find-generic-password", "-s", service],
                capture_output=True, text=True, timeout=15, check=False,
            )
            secret_result = subprocess.run(
                ["security", "find-generic-password", "-s", service, "-w"],
                capture_output=True, text=True, timeout=15, check=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise ValueError(
                "Gmail IMAP credential could not be read from the configured macOS "
                "Keychain service"
            ) from exc
        match = re.search(r'"acct"<blob>="([^"]+)"', account_result.stdout)
        if account_result.returncode == 0 and secret_result.returncode == 0 and match:
            secret = secret_result.stdout.replace(" ", "").strip()
            if secret:
                return match.group(1), secret
        raise ValueError(
            "Gmail IMAP credential is unavailable from the configured macOS Keychain service"
        )
    raise ValueError(
        "Gmail IMAP credentials are unavailable; set both configured environment variables or "
        "explicitly configure a user-created macOS Keychain service. LawyeredOS never creates "
        "credentials or reads sidecar credential files."
    )


def _decode_header(value: str | None) -> str:
    parts: list[str] = []
    for payload, encoding in decode_header(value or ""):
        if isinstance(payload, bytes):
            parts.append(payload.decode(encoding or "utf-8", errors="replace"))
        else:
            parts.append(payload)
    return "".join(parts)


def _addresses(message: Message, name: str) -> str:
    values = message.get_all(name, [])
    return ", ".join(
        f"{_decode_header(display)} <{address}>" if display else address
        for display, address in getaddresses(values)
        if address
    )


def _safe_generated_name(part: Message, index: int) -> str:
    suffix = mimetypes.guess_extension(part.get_content_type()) or ".bin"
    return f"attachment-{index}{suffix}"


def _filename(part: Message) -> str:
    return _decode_header(part.get_filename()).replace("\\", "_").replace("/", "_").strip()


def _plain_body(message: Message) -> tuple[str, bool]:
    plain: list[str] = []
    markup: list[str] = []

    def visit(part: Message) -> None:
        if part.get_content_maintype() == "message":
            return
        if part.is_multipart():
            for child in part.iter_parts():
                visit(child)
            return
        if part.get_filename() or part.get_content_disposition() == "attachment":
            return
        payload = part.get_payload(decode=True)
        if payload is None:
            return
        charset = part.get_content_charset() or "utf-8"
        text = payload.decode(charset, errors="replace")
        if part.get_content_type() == "text/plain":
            plain.append(text)
        elif part.get_content_type() == "text/html":
            markup.append(text)

    visit(message)
    if plain:
        body = "\n".join(plain)
    else:
        body = html.unescape(re.sub(r"<[^>]+>", " ", "\n".join(markup)))
        body = re.sub(r"\s+", " ", body).strip()
    return body[:MAX_BODY_CHARS], len(body) <= MAX_BODY_CHARS


def _attachment_parts(message: Message) -> list[tuple[str, str, Message]]:
    output: list[tuple[str, str, Message]] = []
    counter = 0

    def visit(part: Message, path: str) -> None:
        nonlocal counter
        if part.get_content_type() == "message/rfc822":
            counter += 1
            name = _filename(part) or f"attached-email-{counter}.eml"
            output.append((path, name if name.casefold().endswith(".eml") else name + ".eml", part))
            return
        if part.is_multipart():
            for child_index, child in enumerate(part.iter_parts(), start=1):
                visit(child, f"{path}.{child_index}" if path else str(child_index))
            return
        filename = _filename(part)
        disposition = (part.get_content_disposition() or "").casefold()
        is_body = not filename and disposition != "attachment" and part.get_content_maintype() == "text"
        if is_body:
            return
        counter += 1
        output.append((path or str(counter), filename or _safe_generated_name(part, counter), part))

    visit(message, "")
    return output


def _part_bytes(part: Message) -> bytes:
    if part.get_content_type() == "message/rfc822":
        nested = part.get_payload()
        if isinstance(nested, list) and nested and isinstance(nested[0], Message):
            return nested[0].as_bytes(policy=policy.default)
    return part.get_payload(decode=True) or b""


def _imap_list_entry(value: Any) -> tuple[set[bytes], str] | None:
    """Parse one LIST response without exposing untrusted server text."""
    line: bytes
    literal: bytes | None = None
    if isinstance(value, bytes):
        line = value.strip()
    elif (
        isinstance(value, tuple)
        and len(value) >= 2
        and isinstance(value[0], bytes)
        and isinstance(value[1], bytes)
    ):
        line = value[0].strip()
        literal = value[1]
    else:
        return None

    flag_match = re.match(rb"^\(([^)]*)\)\s+", line)
    if not flag_match:
        return None
    flags = {flag.lower() for flag in flag_match.group(1).split()}

    try:
        if literal is not None:
            size_match = re.search(rb"\{(\d+)\}\s*$", line)
            if not size_match or int(size_match.group(1)) != len(literal):
                raise ValueError
            mailbox_bytes = literal
        else:
            quoted_match = re.search(rb'"((?:[^"\\]|\\.)*)"\s*$', line)
            if quoted_match:
                escaped = quoted_match.group(1)
                if not re.fullmatch(rb'(?:[^\\]|\\[\\"])*', escaped):
                    raise ValueError
                mailbox_bytes = re.sub(rb"\\([\\\"])", rb"\1", escaped)
            else:
                parts = line.rsplit(None, 1)
                if len(parts) != 2:
                    raise ValueError
                mailbox_bytes = parts[1]
        mailbox = mailbox_bytes.decode("utf-8")
        if not mailbox or any(ord(character) < 32 or ord(character) == 127 for character in mailbox):
            raise ValueError
    except (UnicodeDecodeError, ValueError):
        raise ValueError("Gmail IMAP mailbox discovery returned malformed data") from None
    return flags, mailbox


def _attribute_number(attributes: bytes, name: str) -> int | None:
    match = re.search(rb"\b" + name.encode("ascii") + rb"\s+(\d+)", attributes)
    return int(match.group(1)) if match else None


def _internal_date(attributes: bytes) -> str:
    match = re.search(rb'\bINTERNALDATE\s+"([^"]+)"', attributes)
    if not match:
        return ""
    try:
        parsed = parsedate_to_datetime(match.group(1).decode("ascii"))
        return parsed.astimezone(UTC).replace(microsecond=0).isoformat()
    except (ValueError, TypeError):
        return ""


def _literal(data: list[Any] | tuple[Any, ...] | None) -> tuple[bytes, bytes]:
    for item in data or []:
        if isinstance(item, tuple) and len(item) >= 2 and isinstance(item[0], bytes):
            return item[0], item[1] if isinstance(item[1], bytes) else b""
    return b"", b""


def _imap_quote(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


@dataclass
class GmailImapReadonlyAdapter:
    account: str
    password: str = field(repr=False)
    client_factory: ClientFactory = _default_client
    host: str = IMAP_HOST

    def _connect(self) -> tuple[Any, str]:
        if not self.account.strip() or not self.password:
            raise ValueError("Gmail IMAP account and app password are required")
        client = self.client_factory(self.host)
        try:
            try:
                status, _ = client.login(self.account, self.password)
            except imaplib.IMAP4.error:
                raise ValueError("Gmail IMAP login failed") from None
            if status != "OK":
                raise ValueError("Gmail IMAP login failed")
            try:
                status, mailboxes = client.list()
            except imaplib.IMAP4.error:
                raise ValueError("Gmail IMAP mailbox discovery failed") from None
            if status != "OK":
                raise ValueError("Gmail IMAP mailbox discovery failed")
            entries = [entry for line in mailboxes or [] if (entry := _imap_list_entry(line))]
            all_mail = [name for flags, name in entries if b"\\all" in flags]
            if len(all_mail) != 1:
                raise ValueError("Gmail IMAP did not expose one localized \\All mailbox")
            try:
                status, _ = client.select(_imap_quote(all_mail[0]), readonly=True)
            except (imaplib.IMAP4.error, UnicodeError):
                raise ValueError("Gmail IMAP All Mail could not be opened read-only") from None
            if status != "OK":
                raise ValueError("Gmail IMAP All Mail could not be opened read-only")
            return client, all_mail[0]
        except Exception:
            try:
                client.logout()
            except Exception:
                pass
            raise

    def _message(self, client: Any, uid: int, raw_budget: int, attachment_budget: int) -> tuple[dict[str, Any], int, int]:
        metadata_query = (
            "(UID X-GM-MSGID X-GM-THRID INTERNALDATE RFC822.SIZE "
            "BODY.PEEK[HEADER.FIELDS (FROM TO CC SUBJECT DATE)])"
        )
        status, metadata_data = client.uid("FETCH", str(uid), metadata_query)
        if status != "OK":
            raise ValueError(f"Gmail IMAP metadata fetch failed for UID {uid}")
        attributes, header_bytes = _literal(metadata_data)
        message_id_number = _attribute_number(attributes, "X-GM-MSGID")
        thread_id_number = _attribute_number(attributes, "X-GM-THRID")
        declared_size = _attribute_number(attributes, "RFC822.SIZE")
        if message_id_number is None or thread_id_number is None or declared_size is None:
            raise ValueError(f"Gmail IMAP metadata was incomplete for UID {uid}")
        headers = BytesParser(policy=policy.default).parsebytes(header_bytes)
        base = {
            "id": f"{message_id_number:x}",
            "thread_id": f"{thread_id_number:x}",
            "received_at": _internal_date(attributes),
            "from": _addresses(headers, "From"),
            "to": _addresses(headers, "To"),
            "cc": _addresses(headers, "Cc"),
            "subject": _decode_header(headers.get("Subject")),
            "snippet": "",
        }
        if declared_size > MAX_RAW_MESSAGE_BYTES or declared_size > raw_budget:
            return {
                **base,
                "body": "",
                "body_complete": False,
                "attachments": [{
                    "id": "raw-message",
                    "filename": "oversized-message.eml",
                    "mime_type": "message/rfc822",
                    "size": declared_size,
                    "retrieval_error": "raw message exceeds the bounded IMAP intake limit",
                }],
            }, 0, 0
        status, raw_data = client.uid("FETCH", str(uid), "(UID BODY.PEEK[])")
        if status != "OK":
            raise ValueError(f"Gmail IMAP message fetch failed for UID {uid}")
        _raw_attributes, raw = _literal(raw_data)
        if len(raw) != declared_size or len(raw) > MAX_RAW_MESSAGE_BYTES or len(raw) > raw_budget:
            return {
                **base,
                "body": "",
                "body_complete": False,
                "attachments": [{
                    "id": "raw-message",
                    "filename": "incomplete-message.eml",
                    "mime_type": "message/rfc822",
                    "size": len(raw),
                    "retrieval_error": "raw message size did not match bounded IMAP metadata",
                }],
            }, len(raw), 0
        message = BytesParser(policy=policy.default).parsebytes(raw)
        body, body_complete = _plain_body(message)
        attachments: list[dict[str, Any]] = []
        used_attachment_bytes = 0
        for part_path, name, part in _attachment_parts(message):
            payload = _part_bytes(part)
            mime_type = part.get_content_type().casefold()
            item = {
                "id": f"imap-part-{part_path}",
                "filename": name,
                "mime_type": mime_type,
                "size": len(payload),
                "inline": (part.get_content_disposition() or "").casefold() == "inline",
            }
            if not payload:
                item["retrieval_error"] = "attachment bytes unavailable in raw MIME"
            elif len(payload) > MAX_ATTACHMENT_BYTES or len(payload) > attachment_budget - used_attachment_bytes:
                item["retrieval_error"] = "attachment exceeds the bounded IMAP intake limit"
            else:
                used_attachment_bytes += len(payload)
                item["sha256"] = hashlib.sha256(payload).hexdigest()
                item["content_base64"] = base64.b64encode(payload).decode("ascii")
            attachments.append(item)
        return {
            **base,
            "body": body,
            "body_complete": body_complete,
            "attachments": attachments,
        }, len(raw), used_attachment_bytes

    def intake(self, query: str, limit: int = 100) -> dict[str, Any]:
        query = " ".join(query.split()).strip()
        if not query or len(query) > MAX_QUERY_CHARS:
            raise ValueError("bounded Gmail IMAP query is missing or oversized")
        if "newer_than:" not in query or "-in:spam" not in query or "-in:trash" not in query:
            raise ValueError("Gmail IMAP intake requires the bounded matter query from mail_intake plan")
        limit = min(max(int(limit), 1), MAX_RESULTS)
        client, mailbox = self._connect()
        messages: list[dict[str, Any]] = []
        raw_bytes = 0
        attachment_bytes = 0
        failures: list[dict[str, Any]] = []
        try:
            status, search_data = client.uid("SEARCH", None, "X-GM-RAW", _imap_quote(query))
            if status != "OK":
                raise ValueError("Gmail IMAP X-GM-RAW search failed")
            uids = sorted(
                {
                    int(token)
                    for block in search_data or []
                    if isinstance(block, bytes)
                    for token in block.split()
                    if token.isdigit()
                },
                reverse=True,
            )
            selected = uids[:limit]
            for uid in selected:
                try:
                    message, used_raw, used_attachments = self._message(
                        client,
                        uid,
                        max(0, MAX_RUN_RAW_MESSAGE_BYTES - raw_bytes),
                        max(0, MAX_RUN_ATTACHMENT_BYTES - attachment_bytes),
                    )
                except (ValueError, OSError, imaplib.IMAP4.error) as exc:
                    failures.append({"uid": uid, "error": str(exc)})
                    continue
                raw_bytes += used_raw
                attachment_bytes += used_attachments
                messages.append(message)
        finally:
            try:
                client.logout()
            except Exception:
                pass
        fingerprint = hashlib.sha256(f"gmail:{self.account.strip().casefold()}".encode()).hexdigest()
        return {
            "schema": SCHEMA,
            "source": "gmail-imap",
            "account_fingerprint": fingerprint,
            "query": query,
            "messages": messages,
            "coverage": {
                "complete": len(uids) <= limit and not failures,
                "completed_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
                "result_cap": limit,
                "matched": len(uids),
                "localized_all_mail_discovered": bool(mailbox),
                "failed_messages": failures,
            },
        }


def gmail_imap_from_config(
    config: PracticeConfig,
    client_factory: ClientFactory = _default_client,
) -> GmailImapReadonlyAdapter:
    if config.mail_adapter != "gmail-imap-readonly":
        raise ValueError("mail adapter is not configured as gmail-imap-readonly")
    account, password = credentials_from_config(config)
    return GmailImapReadonlyAdapter(account, password, client_factory)
