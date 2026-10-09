# Register schema

Every matter has an immutable `file_number`, unique relative `matter_folder`,
`client`, `description`, and `open` or `closed` status. Optional fields are
`opposing_party`, `other_parties`, `primary_email`, `next_action`,
`next_action_date`, `limitation_date`, and JSON-list `court_deadlines`.

Timeline entries are append-only. Audit rows record every committed mutation
and monotonically increasing register revision. A spreadsheet, report, or
external practice-management system is a downstream projection unless a local
profile explicitly declares otherwise.
