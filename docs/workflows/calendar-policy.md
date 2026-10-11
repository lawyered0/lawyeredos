# Calendar policy

Use this reference for read-only calendar audit or an explicitly approved
reconciliation of tracked legal dates. The register remains authoritative;
calendar entries are a projection. This reference supplies no adapter,
credential, background polling, or new event payload contract.

## Establish what can be projected

Apply the dates contract first. Identify the source, governing date class,
confirmed inputs, verification limit, and lawyer approval for the proposed
date. A party's asserted cutoff is not automatically a binding deadline.
An unresolved relative anchor, proposed strategy window, or unverified
calculation must not be silently promoted into a confirmed legal event.

An undated next action remains an action without a calendar event. Do not
invent a date to make it calendarable. A missing event never erases the
register's obligation. A passed date does not prove performance, adjournment,
waiver, or expiry of the obligation.

Use the configured dedicated calendar and timezone. Keep the legal date and
its source timezone distinct from any display conversion. Establish whether
the source calls for a date-only item or an exact time; do not invent a time,
holiday adjustment, recurrence, or reminder policy. Use only fields supported
by the active declared planner and adapter. Unsupported preferences remain
human-readable proposals, not fabricated accepted payloads.

## Derive the proposed events

Read the final authoritative row and any expressly approved follow-up record.
Use the table as a human checklist; its categories are not new register fields
or payload keys.

| Source item | Proposed projection |
|---|---|
| Confirmed live limitation date | One expiry event, with its governing source and verification limits |
| Each confirmed sourced court date | One event per obligation; an unresolved relative/anchored date is not yet calendarable |
| Dated supported next action | One follow-up event unless it duplicates an existing court/limitation obligation |
| Explicitly recorded third-party follow-up | An event only for the actual recorded request and date; no inferred recurring chase |
| Missing, malformed or partial source | Unresolved proposal, not an empty desired state and not a reason to remove events |

Choose a reminder/time policy with the lawyer, or reuse a current approved
practice note. Propose separate lead reminders for protective expiry, court
obligations, ordinary follow-ups and third-party responses, with a final due-time
reminder where supported. Record the exact lead intervals, clock time/date-only
form, timezone and any notification-suppression preference in the proposal.
This contract sets no universal reminder schedule or nine-o'clock deadline.
Check actual declared interface support before including a preference in a
payload; an unsupported reminder remains a manual-calendar action, not a
pretended successful sync. Re-read and verify any supported reminder settings
after mutation along with the date and private visibility.

Legacy titles, date-only forms or key formats do not automatically authorize a
new duplicate or conversion. Use only legacy matching explicitly supported by
the active adapter. If a legacy key cannot be parsed by that declared interface,
report the candidate and obtain a separately supported/manual reconciliation;
do not create beside it or fabricate a legacy parser. A supported conversion
still needs an approved exact update of the owned event. Preserve unresolved
ownership and incomplete desired-state derivation as visible gaps.

## Audit ownership and show the exact effect

Run the existing bounded read and planner route. Paginate all candidate reads
within the stated window and distinguish owned events, unmatched candidates,
duplicates, stale entries, unchanged items, and incomplete coverage. An exact
parseable sync key establishes the adapter's event relationship; title
similarity does not establish ownership or permission to delete.

Before mutation, show the exact bounded plan: matter identifier, calendar,
source, legal date/time and timezone, purpose, intended title/description,
create/update/remove action, existing event ID where applicable, and duplicate
or reconciliation effect. Use minimum necessary matter detail, private
visibility, and no attendees or meeting link. A deadline reminder must not
become an invitation to a client or opposing party.

Creation, update, and deletion require approval of that precise event or set
and the existing matching preview token. Closure or completion in another
system does not independently authorize calendar cancellation. Remove only
positively identified owned events whose exact removal was approved. Leave an
ambiguous or unrelated candidate unchanged and report the decision required.

## Complete and report independently

After an approved tracker write, use its read-back and the current calendar
state; do not project an earlier proposal as if it committed. Re-read created
or updated events before reporting success. On an uncertain response, inspect
current events through the declared route before any retry.

Report tracker and calendar outcomes separately, including partial success,
created/updated/removed/unchanged entries, unresolved duplicates or ownership,
and any unavailable coverage. An unavailable calendar or failed projection
does not undo or conceal an approved tracker change. Propose an unsynced
obligation or follow-up record under records-and-handoffs, subject to its
approval rules; do not add one automatically.
