---
name: practice-matter-tracker
description: Find, list, create, update, close, reopen, or inspect matters in the configured local register. Use for register operations and conflict-search inputs, not ordinary substantive work on an existing matter.
---

# Matter Tracker

Treat the configured SQLite database as authoritative. Never edit it directly.
Use the bundled CLI with `PYTHONPATH="${LAWYEREDOS_ROOT}/src"` and the
database path from `LAWYEREDOS_CONFIG`.

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

## Link the first existing matter folder

For a new installation, the register is intentionally empty. When the user asks
to link an existing folder, collect the exact file number, client display name,
matter description, and folder path relative to the configured workspace.
Resolve that folder and confirm it is a real directory inside the workspace and
not a symlink. Do not move, rename, or copy the user's files.

Preview a `create` operation, show the exact values, and commit only after the
user approves that preview. Re-read the new row, then hand off to
`lawyeredos:practice-work-on-matter` for the first orientation. If the folder is missing,
outside the workspace, ambiguous, or already assigned, stop and explain what
the user must correct.

## Writes

`create`, `update`, `timeline`, `close`, and `reopen` require a dry run and a
matching current-revision token. Present the exact proposed values and
downstream effects before committing. A stale token fails closed.

```bash
PYTHONPATH="${LAWYEREDOS_ROOT}/src" "${LAWYEREDOS_PYTHON:-python3}" -m lawyeredos.tracker_cli update --database "<database>" \
  --file-number "<file>" --set "next_action=<value>" --dry-run
# After the user approves this exact change:
PYTHONPATH="${LAWYEREDOS_ROOT}/src" "${LAWYEREDOS_PYTHON:-python3}" -m lawyeredos.tracker_cli update --database "<database>" \
  --file-number "<file>" --set "next_action=<value>" \
  --confirm-token "<preview token>"
```

Always re-read after commit. Close, reopen, deadline changes, calendar changes,
and external practice-manager writes require exact current approval. Do not
retry an ambiguous result blindly; inspect `history`, `show`, and `verify`.

`court_deadlines` is JSON data, not a verified legal calculation. The register
stores facts and sources; jurisdiction-specific rules live in separate profiles.

Read [`references/schema.md`](references/schema.md) when mapping fields or
building an adapter.

## Migration and projections

Never migrate or cut over during an ordinary tracker operation. On an explicit
migration request, follow `${LAWYEREDOS_ROOT}/docs/MIGRATION.md`: preview into a new absent target,
obtain approval for the exact count/mapping, commit with the preview token, then
verify and sample before any cutover. Export and XLSX projection are read-only
with respect to the database and refuse to overwrite their output. The XLSX is
derived data and never an input to ordinary writes.
