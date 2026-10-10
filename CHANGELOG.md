# Changelog

All notable source changes are recorded here. Published host packages retain
their own reviewed version and checksum boundaries.

## Unreleased source

- Documented one shared core with separate Claude and Codex project
  integrations and preserved the released host-specific setup prompts.
- Added dual-host contribution guidance, host-aware issue forms, a pull-request
  template, and public-only least-privilege CI.
- Added architecture, lifecycle, mail-boundary, and troubleshooting guidance
  without changing the published Claude beta.2 or Codex beta.1 archives.
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
  reporting. No live mailbox acceptance is claimed.
- Added conservative attachment handling for PDF, DOCX, XLSX, TXT, Markdown,
  and CSV: size, MIME, signature, archive, hash, path-confinement, and
  no-overwrite checks precede local filing and evidence extraction.
- Extended the experimental Gmail REST adapter with read-only full-message and
  attachment retrieval and covered it using a fake GET-only transport. Session
  tool routes require an actually available authorized tool and remain partial
  when bodies, bytes, or bounded-search coverage are missing.

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
