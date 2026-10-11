# Release-readiness checklist

This file separates verified package properties from choices and environment
tests that remain before public distribution.

## Verified in the private build

- [x] Final ZIP installs in a fresh temporary Python 3.12 virtual environment
  using only its declared Python requirements.
- [x] Package and vendored redline tests run against the extracted ZIP rather
  than the original source tree.
- [x] Six skills, one read-only review agent, referenced scripts, fixtures,
  template, documentation, and the vendored component are bundled.
- [x] A project-local fictional Claude Desktop Code trial exercised the six
  pre-rename skills without a live connector or real matter data. This is useful
  behavioral evidence. A later exact RC13 Local session accepted the configured
  runtime, validator, and read-only tracker commands, and a fresh Local session
  discovered the three selected `lawyeredos-*` project skills and the
  `lawyeredos-legal-review-lens` agent.
- [x] Privacy audit and archive scan found no personal paths, credentials,
  account IDs, real client data, or identifying DOCX metadata.
- [x] Provenance is recorded in `PROVENANCE.md`; the vendored MIT license and
  attribution are retained.
- [x] The neutral DOCX was traced to the bundled fresh-document generator and
  inspected for copied branding, embedded media/fonts, active content, custom
  XML, signatures, and identifying metadata; none was found.
- [x] The vendored MIT component was compared with upstream tag `v0.2.0`, exact
  commit `eef61a0cb6afe2867fde70335c179d4a6ad298c8`; its unchanged license and
  local modifications are recorded separately.
- [x] `GPL-3.0-or-later` is selected for original LawyeredOS material; the full
  GPLv3 text, SPDX package metadata, coverage statement, and redistribution
  guidance are bundled.
- [x] Quick-start commands, fictional demo setup, sample configuration, host
  boundaries, and known unavailable capabilities are documented.
- [x] The project-local setup wizard previews before writing, preserves existing
  config by default, versions selected-module plugin copies, provides rollback,
  avoids credentials/global Claude settings, and passes disposable tests for
  cancellation, repeat runs, invalid input, replacement, rollback, and upgrade.
- [x] The release-candidate source binds skill commands to the exact approved
  setup runtime and atomically refuses rollback after post-setup changes. A
  virtual environment is required only when selected-module dependencies are
  missing.
- [x] Directly opening the extracted folder in Claude Desktop reaches the
  normal workspace permission prompt without a separate CLI login. An earlier
  exact-build attempt also established that Claude Code 2.1.288 rejects
  `--desktop` with `--plugin-dir`; the corrected wizard uses project `.claude/`
  discovery and the direct Desktop app route instead.
- [x] Plain-language install, first-matter, troubleshooting, update, rollback,
  uninstall, support, security, contribution, changelog, attribution, and
  roadmap guidance is included.

## Pending environment and compatibility checks

- [x] In an exact RC13 Local Code installation, confirm the configured macOS
  Python, validator, read-only tracker verification/listing, and unchanged file
  hashes. Quit and open a fresh Local session; confirm the three selected
  project skills and review agent are registered. The later source changes are
  dependency-gating, documentation, and reference-qualification corrections
  covered by automated tests; the accepted RC13 workspace remains preserved.
- [x] Verify rollback refuses atomically and preserves the complete setup after
  an actually modified SQLite tracker. Unit coverage also checks config drift.
- [x] Verify the launcher stops clearly if the retained runtime is moved or
  unavailable; the regression test exercises the failure without moving user data.
- [x] Confirm Desktop Code discovers the installed project skills, local env,
  and review agent after workspace trust and again in a fresh Local session.
- [x] Invoke the renamed `lawyeredos-legal-review-lens` once on a bounded,
  entirely inline fictional briefing. The agent ran exactly once, identified
  the overstatement, returned the required schema and an allowed severity, and
  used no files, shell, network, connectors, or writes. Full four-lens
  orchestration remains experimental.

- [ ] Exercise OCR on a disposable document with OCRmyPDF and its platform
  dependencies installed. OCR remains optional and unavailable on the tested
  host.
- [ ] Complete ordinary-host acceptance for the configured Claude Gmail
  connector, Codex session-mail route, portable IMAP provider, REST provider,
  and dedicated-calendar operations against purpose-created test accounts.
  The bounded delegated-session Gmail self-test completed actual model review
  acknowledgements for all three DOCX chunks and the message body, then passed
  final reconciliation and repeat deduplication. The local providers otherwise
  use injected fake transports. No ordinary-host, live-IMAP, live-REST, or
  live-calendar claim is made.
- [ ] Validate migration against a read-only copy or export of the owner's real
  tracker, reconcile every row and history count, and keep rollback material.
  Fictional SQLite/CSV/JSON/XLSX paths are verified; private tracker
  compatibility is not.
- [ ] Decide which operating systems and Python versions beyond the tested Mac
  and Python 3.12 will be supported, then run the clean-room suite there.
- [ ] If desired, run a Desktop Code UI trial under a separate empty Claude
  profile. The completed Desktop trial was isolated by workspace and data, but
  the signed-in account still exposed its normal global skill catalog.

## Resolved owner input

- [x] Record the owner's report that all original LawyeredOS instructions,
  scripts, fixtures, templates, and assets were created by the owner with AI
  assistance and that no other contributors supplied original material.
- [x] Choose the surrounding package's license: `GPL-3.0-or-later`. The
  vendored component remains MIT and dependencies retain their own licenses.
- [x] Select the working software name: **LawyeredOS**, with `lawyeredos` as the
  lowercase plugin, Python distribution/module, path, and archive identifier.
  This names the package, not the Claude assistant.
- [x] Select the pseudonymous publisher account: **Lawyered** / `lawyered0`.
  The intended repository is `github.com/lawyered0/lawyeredos`; authenticated
  inspection found no existing public or private repository at that name.

## Remaining owner and publication decisions

- [x] Use the pseudonymous notice `Copyright (C) 2026 Lawyered` for original
  material. Preserve the separate vendored MIT notice and the AI-assistance
  provenance qualification.
- [ ] Clear the LawyeredOS name for the intended jurisdictions and channels,
  including trademark, package-registry, repository, domain, and marketplace
  availability. This private rename makes no availability or registration claim.
- [ ] Approve version `0.2.0` and the intended repository. GitHub Issues is the
  sanitized public support route; enable and verify GitHub Private vulnerability
  reporting before changing repository visibility.
- [x] Record the exact separately installed dependency-license inventory. No
  dependency code is vendored beyond the retained MIT component; rebuild and
  re-review the inventory whenever the lock changes.
- [x] Perform a final release-archive privacy scan after the preceding metadata
  and licensing choices, then checksum the immutable archive.
- [x] Create repository staging from the audited allowlisted tree or rebuilt
  archive, never from the working directory containing `.venv`, QA output,
  caches, or task history. Configure repository-local pseudonymous Git author
  metadata before the first commit; do not change global Git settings.

## Known limitations to disclose

- A Local Desktop Code session on the tested Mac is the only accepted host
  target. Project discovery survives a fresh session. Terminal is fallback;
  Cowork, Cloud, Windows, and Linux are not accepted targets.
- Skill descriptions can be reduced to names by Claude Code when a user's
  shared skill-description budget is crowded; skill invocation still works.
- The practice-manager adapter is deliberately unavailable.
- Live legal authority is not bundled. The Ontario profile is boundary guidance,
  not a substitute for current primary-law verification.
- Calendar deletion and all other live mutations require exact current approval;
  nothing in the demo authorizes live changes.
- OCR, LibreOffice, Poppler, Gmail, and Google Calendar are optional external
  capabilities and fail closed when unavailable. A configured Claude Gmail
  choice is not called connected until a bounded read succeeds in that session.
