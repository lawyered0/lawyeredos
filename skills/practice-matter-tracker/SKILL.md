---
name: practice-matter-tracker
description: Find, list, create, update, close, reopen, or inspect matters in the configured local register. Use for register operations and conflict-search inputs, not ordinary substantive work on an existing matter.
---

# Matter Tracker

Treat the configured SQLite database as authoritative. Never edit it directly.
Use the bundled CLI with `PYTHONPATH="${LAWYEREDOS_ROOT}/src"` and the
database path from `LAWYEREDOS_CONFIG`.

Read `${LAWYEREDOS_ROOT}/docs/workflows/scope-and-authority.md` for authority and
`${LAWYEREDOS_ROOT}/docs/workflows/intake-and-lifecycle.md` when opening,
updating parties, closing, or reopening a matter. Read
`${LAWYEREDOS_ROOT}/docs/workflows/dates.md` for any date change and
`${LAWYEREDOS_ROOT}/docs/workflows/records-and-handoffs.md` when matter memory
or a completion record is involved. These contracts add workflow checks, not
new CLI fields, commands, or standing write authority.

## Reads

Available read commands are `verify`, `list`, `find`, `show`, and `history`:

```bash
PYTHONPATH="${LAWYEREDOS_ROOT}/src" "${LAWYEREDOS_PYTHON:-python3}" -m lawyeredos.tracker_cli verify --database "<database>"
PYTHONPATH="${LAWYEREDOS_ROOT}/src" "${LAWYEREDOS_PYTHON:-python3}" -m lawyeredos.tracker_cli find --database "<database>" \
  --query "<bounded terms>" --status all
PYTHONPATH="${LAWYEREDOS_ROOT}/src" "${LAWYEREDOS_PYTHON:-python3}" -m lawyeredos.tracker_cli show --database "<database>" \
  --file-number "<exact file number>"
```

Use names only to locate candidates. For conflict screening, search with
`--status all` and report that the Unicode case-folded literal substring search covers
file number, client, description, opposing party, other parties, and primary
email in this local register. It does not do fuzzy or alias matching, query
external sources, maintain a clearance-status field, or make the lawyer's
final conflict decision. Report “No located hit in the local register fields
searched,” never “no conflict,” “clear,” or equivalent. Mutate by exact file
number.

Preserve each searched name's role and relevant variants. Distinguish a possible
duplicate engagement, current or former client potentially adverse, related
person, repeat adverse party, and name-only ambiguity. A same-client match
requires deciding whether this is the existing engagement or a separate one;
a repeat opponent alone is not clearance or a conflict. Re-screen material
parties discovered during intake or later updates. Disclose sources and limits.
Broader folder or correspondence research needs a separately available,
authorized route; the register's search command does not perform it.

## Link the first existing matter folder

For a new installation, the register is intentionally empty. When the user asks
to link an existing folder, collect the exact file number, client display name,
matter description, and folder path relative to the configured workspace.
Resolve that folder and confirm it is a real directory inside the workspace and
not a symlink. Do not move, rename, or copy the user's files.

Before proposing creation, complete the intake-and-lifecycle contract's
source-limited intake and lawyer-decision checks. Keep clearance, verification,
engagement dates, related matters, and other facts unsupported by the current
schema in a human-readable proposal or separately approved generic matter
memory. Never pass invented fields to the tracker or call a linked row a
completed professional clearance. Missing deadline inputs remain open questions.

Preview a `create` operation, show the exact values, and commit only after the
user approves that preview. Re-read the new row, then hand off to
`lawyeredos:practice-work-on-matter` for the first orientation. If the folder is missing,
outside the workspace, ambiguous, or already assigned, stop and explain what
the user must correct.

## Writes

`create`, `update`, `timeline`, `workflow`, `close`, and `reopen` require a dry run and a
matching current-revision token. Present the exact proposed values and
downstream effects before committing. A stale token fails closed.

```bash
PYTHONPATH="${LAWYEREDOS_ROOT}/src" "${LAWYEREDOS_PYTHON:-python3}" -m lawyeredos.tracker_cli workflow --database "<database>" \
  --file-number "<file>" --next-action "<value>" --dry-run
# After the user approves this exact change:
PYTHONPATH="${LAWYEREDOS_ROOT}/src" "${LAWYEREDOS_PYTHON:-python3}" -m lawyeredos.tracker_cli workflow --database "<database>" \
  --file-number "<file>" --next-action "<value>" \
  --confirm-token "<preview token>"
```

Always re-read after commit. Close, reopen, deadline changes, calendar changes,
and external practice-manager writes require exact current approval. Do not
retry an ambiguous result blindly; inspect `history`, `show`, and `verify`.
The CLI treats SQLite `COMMIT` as the durable boundary. If its post-commit
readback fails, it reports `committed: true`, `verification_state:
readback_failed`, and structured recovery evidence. That result is not safe to
retry: inspect the stated revision with the read commands before doing anything
else. A successful matter readback reports `verification_state:
readback_verified`; that narrow state does not verify the audit/history, so the
result also reports `audit_verification_state: not_performed`.
If the `COMMIT` call itself raises, the outcome may be durable or rolled back;
the CLI reports `committed: null`, `commit_state: outcome_unknown`, and
`retry_safe: false`. Do not infer an outcome or retry. Run all three mandatory
read-only recovery checks in the result (`show`, `history`, and `verify`) and
reconcile the reported revision and provisional `audit_id` first.

`workflow` atomically combines explicitly requested next-action fields and an
optional timeline entry in one tracker revision. It does not infer a change from
matter or message content. Clearing a nonempty next action requires the exact
empty value, `--clear-next-action`, and a disposition timeline entry. When the
same request also saves a durable matter file, route the coordinated preview and
commit through `lawyeredos.matter_write` as described in
`lawyeredos:practice-work-on-matter`.

`court_deadlines` is JSON data, not a verified legal calculation. The register
stores facts and sources; jurisdiction-specific rules live in separate profiles.

Before close or reopen, review surviving obligations, evidence of completion,
the current next action, and proposed brief/calendar consequences under the
intake-and-lifecycle contract. A passed date or changed status is not completion
evidence. Preview every supported operation and obtain its exact approval;
unsupported integration effects remain proposals. Report canonical tracker,
matter-memory, and optional projection outcomes separately, including partial
success. When a proceeding is identified, propose its verified identifier and
style in searchable description text rather than only in a timeline entry.

Read [`references/schema.md`](references/schema.md) when mapping fields or
building an adapter.

## Migration and projections

Never migrate or cut over during an ordinary tracker operation. On an explicit
migration request, follow `${LAWYEREDOS_ROOT}/docs/MIGRATION.md`: preview into a new absent target,
obtain approval for the exact count/mapping, commit with the preview token, then
verify and sample before any cutover. Export and XLSX projection are read-only
with respect to the database and refuse to overwrite their output. The XLSX is
derived data and never an input to ordinary writes.
