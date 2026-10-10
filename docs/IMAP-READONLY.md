# Portable Gmail IMAP intake

`gmail-imap-readonly` is the portable, host-neutral route for complete Gmail
message bodies and attachment bytes. It adapts the architecture used by the
maintainer's established private workflow without copying private credentials,
paths, matter identifiers, or credential files into LawyeredOS.

## Security boundary

The provider uses only:

- localized All Mail discovery through the IMAP `\\All` special-use flag;
- Gmail `X-GM-RAW` search with the exact bounded matter query;
- stable `X-GM-MSGID` and `X-GM-THRID` identifiers;
- metadata `FETCH` calls; and
- `BODY.PEEK` for selected messages, which does not set the Seen flag.

The mailbox is selected read-only. The provider has no code path for `STORE`,
draft, send, label, archive, move, or delete operations. It preflights raw MIME
size before downloading a message, applies per-message, per-attachment, and
aggregate byte limits, and feeds retrieved bytes into the shared attachment
validation, confinement, no-overwrite, hashing, extraction, deduplication, and
checkpoint core.

Inline images, attached emails, unnamed parts, unsupported formats, incomplete
bodies, oversized content, and extraction beyond the bounded review window are
explicit. They hold the checkpoint rather than being silently treated as read.

## User-mediated credentials

LawyeredOS never creates an app password, enables IMAP, writes a credential
value to TOML, or reads a sidecar credential file. The user must first confirm
that their Google or Workspace policy permits IMAP and app passwords. App
passwords require 2-Step Verification and may be unavailable for some
organization, security-key-only, or Advanced Protection accounts. Google says
app passwords are not its preferred sign-in method; use this route only when
the account owner and applicable administrator permit it. See Google's
[current app-password guidance](https://support.google.com/accounts/answer/185833).

Choose exactly one runtime source:

1. Set both environment variables named in `[credentials]`:
   `LAWYEREDOS_GMAIL_IMAP_ACCOUNT` and `LAWYEREDOS_GMAIL_IMAP_SECRET`; or
2. On macOS, deliberately create a new Keychain generic-password item and put
   its service name in `gmail_imap_keychain_service`. Leave this value blank
   unless that item was created for LawyeredOS. Setup never creates, probes, or
   imports an existing private service.

The default generated configuration is:

```toml
[integrations]
mail_adapter = "gmail-imap-readonly"

[credentials]
gmail_imap_account_env = "LAWYEREDOS_GMAIL_IMAP_ACCOUNT"
gmail_imap_secret_env = "LAWYEREDOS_GMAIL_IMAP_SECRET"
gmail_imap_keychain_service = ""
```

The two environment variables must be available to the process that launches
the host and its local commands. Do not paste a credential into chat, command
arguments, project files, shell history, or setup output. For a Keychain-backed
Desktop run, create the item manually outside LawyeredOS and configure only its
non-secret service name.

## Run and verify

After setup, validation checks only whether a credential source is configured;
it never reads a Keychain secret. A bounded live read is still required:

```bash
python3 scripts/validate_setup.py --config /absolute/workspace/.lawyeredos/config.toml

PYTHONPATH=src python3 -m lawyeredos.mail_intake imap \
  --config /absolute/workspace/.lawyeredos/config.toml \
  --identifier "exact matter identifier" --limit 100
```

Run the same exact matter intake again to verify stable-ID and file-hash
deduplication. A `partial`, `review_truncated`, `needs_ocr`, deferred attachment,
or incomplete coverage result is a safe stop, not an accepted review.

## Acceptance status

The provider has comprehensive synthetic fake-IMAP acceptance. Tests verify
localized All Mail discovery, exact Gmail raw queries, stable ID conversion,
read-only selection, `BODY.PEEK`, raw and attachment limits, nested and unnamed
parts, inline unsupported content, full supported attachment processing, and
repeat-run deduplication. No live IMAP credential or mailbox was used during
implementation. Ordinary Claude Desktop and Codex project sessions still need
separate live-host acceptance.

One user-created, self-addressed Gmail message was also exercised through the
authorized connector available in the delegated development session. Search,
full-message read, and attachment-byte retrieval reached the shared core. The
DOCX exceeded the core's review-character window, so the run correctly ended
`review_truncated`, did not advance the checkpoint, and did not duplicate the
saved file on repeat. This is useful partial-path evidence, not complete
acceptance of this IMAP provider or of an ordinary Claude/Codex host session.
