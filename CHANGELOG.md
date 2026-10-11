# Changelog

All notable source changes are recorded here. Published host packages retain
their own reviewed version and checksum boundaries.

## 0.2.3 beta.1 — 2026-10-11

- Add shared scope, source-verification, client-advice/delivery, date,
  semantic-record/handoff and intake/closure contracts to existing workflows.
- Add manual instruction modules for substantive contract review, outbound
  demands, inbound-demand options, sourced advocacy and evidence chronologies.
- Add explicitly requested daily attention, bounded inbox workup, overdue
  investigation and read-only orientation claim checks.
- Extend correspondence completeness, calendar-policy and redline-meaning
  instructions without adding adapters, commands, schema fields or native setup
  module keys. All authoritative record changes keep existing approval gates.
- Document all fifteen workflow gap dispositions, manual discovery dependencies
  and release limits. The initial instruction review did not execute project
  checks; ordinary unchanged release validation is a separate candidate gate.
  The published 0.2.2 beta.1 archives remain unchanged.
- Publish the two reviewed 172-member, 1,554,842-byte packages at protected merge
  `c2dca1a7028bd77f0e69de9a9f9fec3a42e4e218`, with shared SHA-256
  `c5b28fb086f18dc09c2ec89062a578e06469036538d71953cb8134f59312ce35`.
  Required reviewed-head and post-merge CI, 254 project tests, 103 vendored tests,
  ordinary acceptance, strict plugin/archive checks and fresh both-host
  installed-reference checks passed. See [release record](docs/RELEASE-0.2.3.md).

## 0.2.2 beta.1 — 2026-10-11

- Add normalized, hash-bound From/To/Cc audience reconciliation with explicit
  verified, mismatch, unknown, and ambiguous states. The result never grants
  send, delivery, filing, service, signature, or account-mutation authority.
- Add targeted one-lens, quick two-lens, and procedural micro-correspondence
  review packets alongside the existing full four-lens mode. Each manifest,
  task bundle, and report binds the exact ordered lens set and source hashes.
- Bind the installed neutral letter template to a generated path/hash manifest
  checked by setup validation and letter creation; private replacement
  templates remain untrusted until separately reviewed and bound.
- Add a fingerprint-checked Codex successful-upgrade rollback that restores
  only installer-owned discovery and links while preserving configuration,
  tracker and matter data, unrelated files, and both versioned cores.
- Quote and escape the discovered Gmail `\\All` mailbox before issuing the
  read-only IMAP `EXAMINE` command, including localized names containing
  spaces, quotes, or backslashes.
- Parse quoted, atom, and literal IMAP `LIST` mailbox forms conservatively and
  replace malformed or server-supplied protocol errors with bounded messages.
- Add wire-level regressions against Python's real `imaplib` command formatter
  so permissive fake clients cannot conceal invalid IMAP syntax.

## 0.2.0 beta.3 / Codex beta.2 — 2026-10-11

- Documented one shared core with separate Claude and Codex project
  integrations and preserved the released host-specific setup prompts.
- Added dual-host contribution guidance, host-aware issue forms, a pull-request
  template, and public-only least-privilege CI.
- Added architecture, lifecycle, mail-boundary, and troubleshooting guidance.
- Clarified that the shared tracker performs local party/name conflict
  screening across recorded fields, while final legal clearance, fuzzy/alias
  matching, external sources, and a clearance-status field remain outside the
  implementation.
- Made Claude setup roll back installer-created paths and restore replaced
  managed files when apply raises or is cancelled; Codex cancellation now uses
  the same cleanup boundary.
- Rejected symlink components in confined matter and output paths so one matter
  cannot be accessed through an in-workspace alias.
- Added a pre-import Python 3.11 version gate to both setup entrypoints so an
  older macOS Python receives an actionable error instead of a traceback.
- Made tracker conflict screening and name resolution use Unicode case folding
  with literal substring semantics, avoiding non-ASCII false negatives and
  accidental SQL wildcard behavior.
- Added a shared bounded matter-mail intake core for Claude and Codex routes:
  exact matter-derived queries, complete-body and attachment retrieval,
  stable-ID deduplication, bounded-window checkpoints, and explicit partial-coverage
  reporting. No complete live mailbox acceptance is claimed.
- Added conservative attachment handling for PDF, DOCX, XLSX, TXT, Markdown,
  and CSV: size, MIME, signature, archive, hash, path-confinement, and
  no-overwrite checks precede local filing and evidence extraction.
- Extended the experimental Gmail REST adapter with read-only full-message and
  attachment retrieval and covered it using a fake GET-only transport. Session
  tool routes require an actually available authorized tool and remain partial
  when bodies, bytes, or bounded-search coverage are missing.
- Added an experimental portable read-only Gmail IMAP provider with localized
  All Mail discovery, stable Gmail IDs, `BODY.PEEK`, bounded MIME acquisition,
  user-selected environment/Keychain credential sources, and comprehensive
  fake-transport coverage.
- Separated acquisition and extraction from semantic review. Long content is
  now divided into durable paragraph/page/sheet-aware chunks, each requiring a
  hash-bound host-model acknowledgement with locator-linked evidence before a
  message or checkpoint can complete. Added interruption/resume, changed-source
  reset, legacy-state invalidation, and long DOCX/PDF/XLSX regressions.
- Re-ran the bounded delegated-session Gmail self-test through that protocol:
  all three DOCX chunks and the message body received actual model review
  acknowledgements, final reconciliation completed, and repeat deduplication
  passed. Ordinary-host and live IMAP acceptance remain pending.
- Published the shared-core update as Claude beta.3 and Codex beta.2 after the
  owner waived ordinary-host/live-IMAP acceptance as a release prerequisite.
  That path remains explicitly unverified and experimental; the waiver is not
  evidence of successful ordinary-host or portable-IMAP operation.

## 0.2.0 beta.2

- Made email a required explicit onboarding decision instead of silently
  defaulting it off.
- Added an honest configured-but-unverified route for Claude's Gmail connector,
  retained safe skip behavior, and kept the narrower token-based REST adapter
  clearly experimental.
- Documented connector permissions, direct user authentication, bounded reads,
  runtime connection verification, and the separate approval boundary for all
  send or mailbox-write actions.

## 0.2.0 — private macOS beta candidate

- Renamed the package and plugin namespace to LawyeredOS / `lawyeredos`.
- Added a guided project-local setup wizard with preview, versioned plugin
  copies, runtime binding, upgrade reuse, and conservative rollback.
- Added a manually invoked `/lawyeredos-setup` bootstrap skill that delegates
  writes to the deterministic wizard after an exact-plan approval.
- Changed the Desktop launcher to open the workspace folder directly in Claude
  Desktop, avoiding a separate CLI-login requirement.
- Added fail-closed preflight checks for symlinked managed paths and malformed
  project environment settings.
- Made the first setup preview standard-library-only, made dependency gates
  follow selected modules, and documented the required Local Code environment.
- Qualified plugin skill-to-skill references with the `lawyeredos:` namespace
  while preserving collision-safe `lawyeredos-*` project references.
- Added guarded matter tracking, exact-folder orientation, no-overwrite output,
  letter and tracked-redline workflows, optional integrations, local memory and
  document helpers, and Claude-only review instructions.
- Added neutral fixtures, template provenance, GPL licensing, third-party MIT
  attribution, privacy scanning, and fictional acceptance coverage.
- Documented that local storage does not mean offline Claude processing.
- Runtime-accepted one bounded current-name source-fidelity reviewer invocation
  on the tested Mac; the complete four-lens workflow remains experimental.

No public compatibility promise applies to earlier private builds.
