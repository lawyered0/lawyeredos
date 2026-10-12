# Tracker migration and projections

The SQLite database created by this package is authoritative. CSV, JSON, legacy
SQLite databases, and generated XLSX workbooks are import/export surfaces, not
parallel writable stores.

## Safe migration

1. Export or copy the existing tracker without changing it.
2. Run `practice-tracker-migrate preview --source SOURCE --target NEW.sqlite3`.
3. Review the record count and status totals. The source must map a unique file
   number, client, description, and confined relative matter folder for every
   row.
   Folder identity ignores redundant separators and dot components, letter
   case, and canonically equivalent Unicode spellings for macOS portability.
   A folder cannot be assigned to a second matter by creation or update.
4. Run the matching `commit` command with the returned confirmation token.
5. Verify the new database and compare a representative sample. Do not point
   normal workflows at it until the owner approves the cutover.

The commit builds a new temporary database, verifies it, and atomically moves
it to a previously absent target. It never edits the source or overwrites a
target. Legacy court-deadline text that is not JSON is preserved as one clearly
marked migration item for human cleanup.

## Backups and exports

`practice-tracker-migrate export --format json` writes a complete versioned
tracker snapshot: matters, original timestamps, revision metadata, timeline,
audit history, and sequence counters. Migration of that snapshot or a canonical
LawyeredOS SQLite database preserves those records. The preview and commit
receipts state `history_preserved`; legacy CSV/JSON mappings cannot restore
history absent from their source.

CSV export contains matter rows only and prefixes formula-like text with an
apostrophe for spreadsheet safety. It is a presentation surface, not a complete
backup or a lossless roundtrip format. JSON retains the original text. All
exports refuse an existing destination.
JSON, CSV, and XLSX exports create each new file with mode `0600`, independently
of the process umask. Migration publishes its verified private temporary database
with an exclusive link, so a destination created during the build is preserved.

`practice-tracker-xlsx` produces separate Open Matters
and Closed Matters sheets from a read-only database connection. The XLSX is a
disposable projection and must not be edited as the system of record. All text
cells are stored as text, including values beginning with an equals sign.
Unsupported XML control characters in legacy rows are replaced visibly with
`�` in the projection, and cells over Excel's 32,767-character cap receive a
visible truncation marker. The result identifies each affected file number and
field in `sanitized` and `truncated`, and sets `lossless_projection` to false.
The authoritative database and JSON snapshot retain the original text.
Export is a separate operation; its failure does not undo a committed tracker
mutation or authorize replaying that mutation.

Migration maps field names, not organization-specific paths or identities. If
the legacy schema differs from the documented aliases, prepare an explicit
intermediate CSV/JSON mapping and review it before committing.

## Private-path permission migration

New confidential LawyeredOS state is private by construction: app-owned
directories under `.lawyeredos` are created as `0700`, and config, tracker,
state, mail-ledger, staging, saved-attachment, acknowledgement, and recovery
files are created as `0600`. Setup does not change an existing path's mode.

An older installation with broader modes stops with a migration-required error
that names the path, observed mode, and required mode. Before changing it,
review that the path is genuinely LawyeredOS-owned and is not a shared user
directory. Back up the workspace, apply the named mode only to the exact path,
and build a fresh setup plan. Never recursively change the workspace, matter
tree, `.claude`, `.agents`, or a personal skills directory. Symlinks,
hard-linked confidential files, and special filesystem entries require an
explicitly reviewed replacement; setup will not repair them automatically.
