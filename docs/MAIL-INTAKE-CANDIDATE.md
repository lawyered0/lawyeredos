# Matter-mail intake candidate record

This record covers the unreleased shared matter-mail intake candidate. It does
not amend the acceptance scope of the published Claude beta.2 or Codex beta.1
archives and is not a live-mail acceptance.

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

- 93 LawyeredOS unit, distribution, setup, confinement, and workflow tests;
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

Two independent reviews challenged the candidate for security, privacy,
accuracy, host-boundary wording, and visual claims. Their findings drove
fail-closed handling for long content, inline and filename-less parts,
acquisition limits, unexplained provider matches, cross-account deduplication,
OOXML embeddings and external relationships, transient bundle retention, and
destination-directory replacement races.

## Explicit exclusions

- No real mailbox, real matter, credential, OAuth flow, send/draft action,
  mailbox mutation, or persistent permission change was used.
- No live Claude connector or Codex session-mail tool acceptance was performed.
- No background polling is implemented.
- OCR completion remains unavailable on the tested host.
- Other operating systems and host versions remain unaccepted.
- The existing public archives and site downloads were not replaced.
