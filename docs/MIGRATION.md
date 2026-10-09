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
4. Run the matching `commit` command with the returned confirmation token.
5. Verify the new database and compare a representative sample. Do not point
   normal workflows at it until the owner approves the cutover.

The commit builds a new temporary database, verifies it, and atomically moves
it to a previously absent target. It never edits the source or overwrites a
target. Legacy court-deadline text that is not JSON is preserved as one clearly
marked migration item for human cleanup.

## Backups and exports

`practice-tracker-migrate export` writes a new CSV or JSON snapshot and refuses
an existing destination. `practice-tracker-xlsx` produces separate Open Matters
and Closed Matters sheets from a read-only database connection. The XLSX is a
disposable projection and must not be edited as the system of record.

Migration maps field names, not organization-specific paths or identities. If
the legacy schema differs from the documented aliases, prepare an explicit
intermediate CSV/JSON mapping and review it before committing.
