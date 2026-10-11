# Matter-mail intake candidate record

## 0.2.1 acceptance addendum — 2026-10-11

After the 0.2.0 record below was completed, one exact self-addressed,
user-created Gmail test thread passed through the portable read-only IMAP path
in each supported ordinary desktop host: Claude Desktop Code Local and Codex
Desktop / GPT-5. Each host acknowledged one body and three hash-bound DOCX
chunks, completed the checkpoint, deduplicated the repeat, and completed
guarded bundle deletion. This accepts only the tested account, thread,
launcher, and host; it does not establish broader mailbox/account coverage,
OAuth or REST acceptance, sending, mutation, or general session-tool support.

The remainder of this document preserves the earlier 0.2.0 beta.3/beta.2 gate
as a historical record.

This record covers the shared matter-mail intake released in Claude beta.3 and
Codex beta.2. It is not a complete live-mail acceptance. The owner waived the
pending ordinary-host/live-IMAP test as a publication prerequisite; the
capability remains experimental and explicitly unverified.

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
separate disposable fictional workspaces. For each route it exposes a complete
message body and PDF, DOCX, XLSX, TXT, Markdown, and CSV attachments through the
review queue; submits clearly labelled synthetic acknowledgements to test the
hash/progress plumbing; verifies a repeat does not duplicate files or reviews;
handles a new message; proves an incomplete body and missing attachment bytes
hold the prior checkpoint; and then completes the same message on retry. This
script tests mechanics, not model comprehension. The PDF extractor is replaced
only in this deterministic acceptance script so CI does not claim a platform
Poppler binary that it did not exercise. The regular setup smoke remains the
platform dependency gate.

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

- 109 LawyeredOS unit, distribution, setup, confinement, and workflow tests;
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
session. The initial run exposed that extraction beyond one fixed window was
not full review. After implementing the resumable protocol, the 30,333-character
DOCX produced 298 paragraph units and three hash-bound chunks. The active model
read and acknowledged every chunk plus the message body with locator-linked
evidence; final reconciliation advanced the checkpoint and the repeat returned
`already_reviewed` without duplicating the file. No message content or
attachment bytes were retained in the repository. This is delegated-path
acceptance, not ordinary-host or portable-IMAP acceptance.

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
  completed delegated connector self-test does not establish ordinary-host or
  portable-IMAP acceptance.
- No background polling is implemented.
- OCR completion remains unavailable on the tested host.
- Other operating systems and host versions remain unaccepted.
- Earlier versioned public archives remain immutable alongside the new
  beta.3/beta.2 downloads.
