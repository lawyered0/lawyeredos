# Examples

In ordinary use, ask naturally—for example, `Let’s work on Northstar.` The
installed skill resolves the saved matter and performs local orientation
automatically without changing the tracker or external accounts. When configured email access is available,
that workflow also checks the bounded matter-specific email slice and reviews
fully retrieved new messages and safely retrieved supported attachments within
bounded review windows. It may write the disclosed local attachment cache and
review ledger. Partial or unavailable mail coverage is disclosed and held for retry. The commands below
are technical examples for maintainers, testing, and troubleshooting; users do
not need to type them.

All names and file numbers below are fictional.

## Orient to a matter

```bash
PYTHONPATH=src python3 -m lawyeredos.matter_context \
  --config /private/config.toml --identifier 2030-001
```

## Preview and create a tracker row

```bash
PYTHONPATH=src python3 -m lawyeredos.tracker_cli create \
  --database /workspace/matters.sqlite3 --file-number 2030-002 \
  --client "Rivera Foods Ltd." --description "Commercial lease advice" \
  --matter-folder "2030-002-rivera-foods" --dry-run
```

Repeat the command with `--confirm-token TOKEN` returned by the preview.

## Screen the local register for potential conflicts

```bash
PYTHONPATH=src python3 -m lawyeredos.tracker_cli find \
  --database /workspace/matters.sqlite3 \
  --query "Harbor Paper" --status all
```

The Unicode case-folded literal substring search covers file number, client, description,
opposing party, other parties, and primary email in both open and closed local
matters. Report the query, fields, register scope, results, and limitations. It
does not perform fuzzy or alias matching, query outside systems, populate a
clearance-status field, or make the lawyer's final conflict decision.

## Preview a safe output save

```bash
PYTHONPATH=src python3 -m lawyeredos.safe_output preview \
  --root /workspace --matter-folder 2030-001-northstar \
  --relative-path correspondence/draft-v01.docx --content-file /scratch/draft.docx
```

Use the returned token with the `commit` command and identical arguments.

## Plan calendar reconciliation

```bash
PYTHONPATH=src python3 -m lawyeredos.calendar_plan plan \
  --desired fixtures/calendar/desired.json \
  --existing fixtures/calendar/existing.json
```

This produces a diff only. No mock or live mutation command is bundled; it
changes neither an event file nor a live account.
