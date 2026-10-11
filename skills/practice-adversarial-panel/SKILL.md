---
name: practice-adversarial-panel
description: Independently challenge a bounded legal draft through a proportional read-only review, verify findings, and confirm the artifact stayed unchanged. Never rewrites or acts.
---

# Claude-Only Adversarial Panel

This workflow uses Claude reviewers only. Do not invoke another model provider
or an external review service.

## Choose the review contract

Choose the mode explicitly from the work actually requested. Do not infer a
mode from a risk label and do not add lenses for reassurance:

- `targeted`: exactly one named principal lens for one bounded risk;
- `procedural`: only `procedural-micro-correspondence` (Lens 5) for one to
  three coordinated short procedural messages;
- `quick`: exactly two distinct named principal lenses where two bounded risks
  are material; or
- `full`: all four principal lenses. This is the default when the mode is
  omitted and remains the safety default for substantive or high-risk work and
  whenever a full review was requested.

The principal lens names are `opposing-reader`, `fact-and-source-check`,
`privilege-admissions-and-authority`, and
`pre-mortem-and-operational-risk`. Mode selection never itself grants authority
to edit, send, file, serve, sign, or take another external action.

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
  --source "<controlling source>" --mode "<mode>" \
  --lens "<selected lens>" --output "<scratch manifest.json>"
```

Repeat `--lens` exactly twice for `quick`; use it exactly once for `targeted`.
For `procedural`, the Lens 5 selection is automatic and `--lens` may be
omitted. For `full`, omit both `--mode` and `--lens` to retain the backwards-
compatible four-lens default. Every mode freezes the exact deliverable and all
supplied sources by SHA-256 before reviewer tasks are generated.

The briefing identifies the deliverable, issue, mode (outbound or historical),
controlling sources, evidence gaps, relevant bounded correspondence, and the
user's focus. Working memory is not proof of underlying documents.

Generate the concrete job bundle. The orchestrator uses only the manifest's
exact selected lens set; it never expands or substitutes lenses:

```bash
PYTHONPATH="${LAWYEREDOS_ROOT}/src" "${LAWYEREDOS_PYTHON:-python3}" -m lawyeredos.review_orchestrator prepare \
  --manifest "<scratch manifest.json>" --output "<scratch tasks.json>" --focus "<user focus>"
```

## Review

Read [`references/lenses.md`](references/lenses.md). For a full review, launch
four independent `lawyeredos:legal-review-lens` agents concurrently, each with the same
briefing and exactly one lens. For `quick`, launch the two selected principal
lenses. For `targeted`, launch the one selected principal lens. For
`procedural`, launch one reviewer with Lens 5. Reviewers
have only read/search tools, cannot write, browse, call connectors, run shell,
or spawn agents.

## Verify and report

Deduplicate findings. Agreement raises salience, not truth. Verify citations
against the actual extracted source, check the strongest countervailing
evidence, distinguish observation from inference and legal significance, and
classify live versus contingent, cured, historical, dormant, or unverified.
Disposition every material finding as accepted, rejected, or deferred. Correct
accepted findings in the owning workflow; reject only on a verified source
basis; and surface deferred findings. A missing controlling source, failed
reviewer, or deferred material finding blocks any “ready” or equivalent label.

Reviewer findings are evidence, not authority. A panel concern alone never
establishes that insurer notice, independent advice, withdrawal, conflict
action, stopping work, or a client warning is required. The owning workflow
must apply the governing threshold, actual prejudice, urgency, curability, and
proportional alternatives before recommending a protective step.

Run `review_bundle verify --manifest <manifest>` before reporting. If the hash
changed, lead with that fact and do not treat the review as read-only.

Save each requested agent's structured result in private scratch as
`<lens-name>.json`, then run `review_orchestrator collect`. It validates that
the result files match the selected lens contract, every cited path was
supplied, every finding has the required evidence and countervailing-evidence
fields, all requested lenses returned, and all hashes remain unchanged. Each
finding's `severity` must be exactly `critical`, `material`, or `optional`;
other labels are invalid. Missing/invalid results are coverage gaps, never
silent success.

Collection completeness and readiness are separate. `collection_complete`
means every requested reviewer returned a valid result; it is not clearance.
`ready` (and the CLI result's `ok`) remains false when there are no controlling
sources, when coverage gaps or questions remain, or while any critical or
material finding remains unresolved. Correct the draft or evidence, create a
new manifest, and re-run the review to clear such a finding. The report's
`authorizes_action` field is always false: even a ready review does not
authorize edits, sending, filing, service, or any other action.

Lead with the supported recommendation. Material findings identify the exact
passage, source, countervailing evidence, consequence, and confidence. Close
with coverage gaps and unchanged SHA-256. The panel never authorizes edits,
sending, filing, service, tracker changes, or account actions.
