# Portable instruction workflow catalog

This unreleased candidate adds instructions and reference contracts. It adds no
Python behavior, schema field, adapter, legal calculator or native setup option.
The published 0.2.2 beta.1 archives and acceptance boundaries remain unchanged.

## Entry and discovery

Use the installed `lawyeredos-work-on-matter` skill for a specific matter task.
It reads this catalog only when the requested work needs a specialist module.
For an expressly requested practice-wide task, use the installed matter skill
to locate the catalog without choosing a fictitious single matter first. The
selected module defines its own bounded sources and per-matter resolution.

The existing six native installed skills remain matter work, tracker,
correspondence, redline, calendar and panel. Both host installers have six fixed
module/name mappings; the configuration declares those same six module keys.
The additional folders live under `docs/workflow-modules/`, outside the native
`skills/` tree. They have descriptive frontmatter but are **manual catalog
modules**, not new `lawyeredos-*` native skills or accepted setup flags.

To use one, read the selected `SKILL.md` at its package-relative location below.
Resolve the package root from the current installed entrypoint: configured
`LAWYEREDOS_ROOT` for Claude, or project-local `.lawyeredos/current-codex` for
Codex. In a source checkout use that checkout's root for reading only. Never
set global variables or change setup state to make a module appear installed.

Relative Markdown links resolve against the manually read source file. Links
to canonical existing skills explain workflow ownership; use the active host's
**installed** version for actual commands and its exact runtime paths. Canonical
source command examples are not projectized Codex commands. If a selected optional
installed capability is absent, report the dependent operation unavailable.

Native installation of additional modules requires a separately scoped change
to installer mappings, configuration selection, host projectization and their
acceptance. That runtime work is not part of this candidate. The declared release
input directories include `skills` and `docs`; the manual modules and contracts
travel inside the complete documentation tree. Initial static review established
the declared route; exact archive and installed-path checks are separate
release-validation evidence, not proof of new model behavior.

## Choose only the requested workflow

| Request | Manual source entry | Needed installed capabilities |
|---|---|---|
| Review an agreement and develop positions | [Contract review](workflow-modules/practice-contract-review/SKILL.md) | Matter/tracker; redline only when requested and selected; panel when required |
| Draft demand, cure, cease-and-desist or preservation language | [Demand drafting](workflow-modules/practice-demand-draft/SKILL.md) | Matter/tracker; letters for formal DOCX; review when required |
| Assess an inbound demand and response options | [Inbound demand](workflow-modules/practice-demand-received/SKILL.md) | Matter/tracker; actual source extraction; no merits calculation tool |
| Draft sourced submissions or argument | [Advocacy drafting](workflow-modules/practice-brief-drafter/SKILL.md) | Matter/tracker; authorized primary-text research; review when required |
| Build an evidence chronology or facts/witness variant | [Chronology](workflow-modules/practice-chronology/SKILL.md) | Matter/tracker; source extraction; guarded save when requested |
| Identify practice-wide attention items | [Daily triage](workflow-modules/practice-daily-triage/SKILL.md) | Explicit source/window scope; supplied mail or actual authorized broad read route |
| Work a defined mail selection into matters and replies | [Inbox workup](workflow-modules/practice-inbox-workup/SKILL.md) | Explicit scope; per-matter intake where supported; independent review when required |
| Investigate overdue/stale items | [Overdue triage](workflow-modules/practice-overdue-triage/SKILL.md) | Explicit register/source scope; exact approved changes only |
| Check an orientation account against evidence | [Orientation audit](workflow-modules/practice-orientation-audit/SKILL.md) | Express read-only claim-check scope; same-provider independence only if available/authorized |

The final four are optional, explicitly requested practice workflows. No source
module installs a broad mailbox adapter, background task or standing permission.
The bundled mail intake stays single-matter; broader acquisition requires
source-complete supplied material or an actually authorized active read/search
tool supporting the bounded request. A connector description is not evidence
that a tool exists or that its results are complete.

## Shared reference contracts

- [Scope and authority](workflows/scope-and-authority.md): operation and host boundaries.
- [Source verification](workflows/source-verification.md): proposition/source chain and adverse evidence.
- [Client advice](workflows/client-advice.md): retainer preparation, source tracing and complete delivery.
- [Dates](workflows/dates.md): classifications, confirmation and stale relative windows.
- [Records and handoffs](workflows/records-and-handoffs.md): preserved meaning and review continuation.
- [Intake and lifecycle](workflows/intake-and-lifecycle.md): role/conflict research and closing/reopening.
- [Correspondence completeness](workflows/correspondence-completeness.md): unread message/visual parts.
- [Calendar policy](workflows/calendar-policy.md): proposed event construction and verified outcomes.
- [Redline meaning](workflows/redline-meaning.md): source/marked/accepted-copy comparison.

## Limits retained

No Ontario legal-deadline calculator, trust package, practice-manager projection,
identity-verification or courier integration is added. Signed-engagement retrieval
requires a separately supported explicit route. Cross-provider review remains
excluded, and existing-revision continuation remains outside the bundled redline
workflow. Personal identity, template, voice and standing authority are never
imported. Proposed practice preferences are human-readable approved policy, not
new TOML keys. Instructions do not prove runtime success or host discovery.
