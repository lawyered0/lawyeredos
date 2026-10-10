# Matter-mail intake candidate record

This record covers the unreleased shared matter-mail intake candidate. It does
not amend the acceptance scope of the published Claude beta.2 or Codex beta.1
archives and is not a complete live-mail acceptance.

## Host-tool boundary

- Anthropic documents Gmail message search/read plus attachment metadata, but
  says attachment contents are not directly accessible. Claude messages with
  attachments therefore cannot complete through that connector alone.
- Codex documents MCP and plugin tool discovery, but no built-in Gmail tool
  contract. The Codex route inspects the actual session and names no invented
  tool.
- Both routes feed the same versioned normalized bundle only when a runtime
  tool actually returns complete bodies, complete bounded coverage, stable
  identifiers, and required attachment bytes. No complete live-account
  acceptance is claimed.

Official references: [Claude Google Workspace connectors](https://support.claude.com/en/articles/10166901-use-google-workspace-connectors),
[Codex MCP](https://learn.chatgpt.com/docs/extend/mcp?surface=cli), and
[Codex skills](https://learn.chatgpt.com/docs/build-skills).

## Scripted host-route acceptance

`python scripts/accept_mail_host_routes.py` runs both normalized host routes in
separate disposable fictional workspaces. For each route it reviews a complete
message body and PDF, DOCX, XLSX, TXT, Markdown, and CSV attachments; verifies a
repeat does not duplicate files or reviews; reviews a new message; proves an
incomplete body and missing attachment bytes hold the prior checkpoint; and
then completes the same message on retry. The PDF extractor is replaced only in
this deterministic acceptance script so CI does not claim a platform Poppler
binary that it did not exercise. The regular setup smoke remains the platform
dependency gate.

## Implemented boundary

The shared Python core resolves one tracker matter, builds a conservative
30-day query using the exact file number or paired identity/discriminator
terms, validates a host-specific normalized bundle, reviews bounded content,
safely files supported attachments, and records account-scoped stable IDs and
hashes in a rebuildable SQLite ledger. Mailbox access is read-only. The only
local writes are the disclosed attachment cache, ledger/checkpoint, and a
guarded transient session bundle.

Claude and Codex keep separate session-tool instructions. A configured session
route is not treated as available unless the active host exposes and authorizes
a suitable read/search tool. Missing account identity, bodies, attachment
bytes, pages, search coverage, OCR, exact matter relevance, or bounded review
remains partial and does not advance the complete checkpoint.

## Fictional verification

The reviewed source passed:

- 101 LawyeredOS unit, distribution, setup, confinement, and workflow tests;
- scripted positive acceptance for both normalized host routes, with complete
  fictional bodies and every supported attachment category;
- 97 vendored legal-redline tests;
- fictional partial/retry, long-content, inline/filename-less MIME,
  account/source/query binding, attachment safety, no-overwrite, private-bundle
  cleanup, and complete-checkpoint tests;
- setup/rollback smoke with a repeated idempotent Codex install;
- ZIP integrity and repository privacy scanning; and
- a fresh ephemeral Codex CLI session on macOS with Codex CLI 0.147.0 that
  discovered the installed project-local work-on-matter skill, read the
  fictional tracker and matter brief, ran the bounded mail plan, disclosed the
  unavailable adapter, and correctly described the permitted local writes.

A separate, bounded read of one user-created, self-addressed Gmail test thread
used the authorized connector exposed only in the delegated development
session. Search, full-message read, and DOCX attachment-byte retrieval reached
the shared core. The document exceeded the core review-character window, so
the result correctly remained `review_truncated`, the checkpoint did not
advance, and the repeat created no duplicate file. No message content or
attachment bytes were retained in the repository. This is a partial-path test,
not ordinary-host or portable-IMAP acceptance.

Two independent reviews challenged the candidate for security, privacy,
accuracy, host-boundary wording, and visual claims. Their findings drove
fail-closed handling for long content, inline and filename-less parts,
acquisition limits, unexplained provider matches, cross-account deduplication,
OOXML embeddings and external relationships, transient bundle retention, and
destination-directory replacement races.

## Explicit exclusions

- No real matter, new credential, OAuth flow, send/draft action, mailbox
  mutation, or persistent permission change was used. The only live mailbox
  input was the bounded, user-created self-test described above.
- No ordinary Claude or Codex host session completed live-mail acceptance; the
  delegated connector self-test remained partial as described above.
- No background polling is implemented.
- OCR completion remains unavailable on the tested host.
- Other operating systems and host versions remain unaccepted.
- The existing public archives and site downloads were not replaced.
