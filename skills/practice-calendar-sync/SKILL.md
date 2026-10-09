---
name: practice-calendar-sync
description: Audit or reconcile approved tracked dates with a configured dedicated calendar. Use for exact calendar diffs, not general scheduling or unverified legal-date calculation.
---

# Calendar Reconciliation

The matter register is authoritative; Calendar is a downstream projection.
Missing or failed calendar access never reverses or conceals a tracker result.

Use the bundled planner for fixture or exported event JSON:

```bash
PYTHONPATH="${LAWYEREDOS_ROOT}/src" "${LAWYEREDOS_PYTHON:-python3}" -m lawyeredos.calendar_plan plan \
  --desired desired.json --existing existing.json
```

It produces a read-only create/update/remove/unchanged diff. If
`calendar_adapter = "google-calendar-api"` is explicitly configured, use the
bundled adapter described in `${LAWYEREDOS_ROOT}/docs/ADAPTERS.md`. Credentials come only from the
named environment variable. Automated tests use a fake transport and never a
live account.

For an adapter operation:

1. Require a non-empty configured calendar ID and timezone. Never default to a
   primary calendar.
2. Search a bounded window, paginate fully, and read every candidate.
3. Match on an exact parseable sync key, not title similarity.
4. Present the precise diff. Creation, update, and deletion require approval of
   the exact event or bounded set.
5. After an ambiguous response, search and read again; never blindly retry.
6. Use no attendees or meeting link, private visibility, and minimum necessary
   matter detail.
7. Re-read created or updated events before reporting success.

The adapter itself requires an exact event ID for update/delete, a private
`sync_key` for create/update, and a matching preview confirmation token. A
missing token, credential, calendar ID, or complete page traversal fails closed.
Use `lawyeredos.integrations calendar-preview` and
`calendar-commit`; never call the remote endpoint directly from the skill.

An asserted or calculated date is not a verified legal deadline. Use the
applicable jurisdiction profile and current primary sources first.
