---
name: practice-adversarial-panel
description: Independently challenge an important legal draft through four read-only Claude lenses, verify findings, and confirm the artifact stayed unchanged. Never rewrites or acts.
---

# Claude-Only Adversarial Panel

This workflow uses Claude reviewers only. Do not invoke another model provider
or an external review service.

## Prepare

This full workflow requires Claude Code. Confirm that the
`lawyeredos:legal-review-lens` agent is available.
If it is absent, report that the independent panel is unavailable; a single
main-thread review is not equivalent to four independent lenses.

Resolve the matter read-only and bound the issue. Extract PDFs and DOCX files
through verified local routes. Build a manifest before review:

```bash
PYTHONPATH="${LAWYEREDOS_ROOT}/src" "${LAWYEREDOS_PYTHON:-python3}" -m lawyeredos.review_bundle create \
  --allowed-root "<resolved matter folder>" --deliverable "<draft>" \
  --source "<controlling source>" --output "<scratch manifest.json>"
```

The briefing identifies the deliverable, issue, mode (outbound or historical),
controlling sources, evidence gaps, relevant bounded correspondence, and the
user's focus. Working memory is not proof of underlying documents.

Generate the concrete four-lens job bundle:

```bash
PYTHONPATH="${LAWYEREDOS_ROOT}/src" "${LAWYEREDOS_PYTHON:-python3}" -m lawyeredos.review_orchestrator prepare \
  --manifest "<scratch manifest.json>" --output "<scratch tasks.json>" --focus "<user focus>"
```

## Review

Read [`references/lenses.md`](references/lenses.md). For a full review, launch
four independent `lawyeredos:legal-review-lens` agents concurrently, each with the same
briefing and exactly one lens. For a targeted review, use one lens. Reviewers
have only read/search tools, cannot write, browse, call connectors, run shell,
or spawn agents.

## Verify and report

Deduplicate findings. Agreement raises salience, not truth. Verify citations
against the actual extracted source, check the strongest countervailing
evidence, distinguish observation from inference and legal significance, and
classify live versus contingent, cured, historical, dormant, or unverified.

Run `review_bundle verify --manifest <manifest>` before reporting. If the hash
changed, lead with that fact and do not treat the review as read-only.

Save each agent's structured result in private scratch as
`<lens-name>.json`, then run `review_orchestrator collect`. It validates that
every cited path was supplied, every finding has the required evidence and
countervailing-evidence fields, all lenses returned, and all hashes remain
unchanged. Each finding's `severity` must be exactly `critical`, `material`, or
`optional`; other labels are invalid. Missing/invalid results are coverage gaps,
never silent success.

Lead with the supported recommendation. Material findings identify the exact
passage, source, countervailing evidence, consequence, and confidence. Close
with coverage gaps and unchanged SHA-256. The panel never authorizes edits,
sending, filing, service, tracker changes, or account actions.
