# External adapters

External access is opt-in. The default configuration makes every adapter
unavailable. Credentials are read only from explicitly named environment
variables and are never written to logs, plans, fixtures, or reports.

## Gmail

`gmail-api-readonly` uses the Gmail REST API to run a bounded query and retrieve
message metadata and snippets. The caller must supply a token scoped no more
broadly than `gmail.readonly`. This adapter does not mark read, label, archive,
delete, download attachments, create drafts, or send. Results disclose that
coverage is bounded and retain a next-page token instead of claiming a complete
mailbox search.

For offline demonstrations, `fixture-json` searches a fictional JSON message
list. It never contacts a service.

## Google Calendar

`google-calendar-api` requires an exact dedicated calendar ID; `primary` is
refused. Searches require explicit start and end times and paginate to
completion. Mutations require an exact event ID where applicable, a private
`sync_key`, and a fresh preview confirmation token. The included automated
tests inject a fake HTTP transport. They do not contact Google.

Calendar tokens should use the least privilege compatible with the intended
operation. A read-only token supports audit/listing; create, update, or delete
requires a write scope and separate user authority for the exact change.

## Configuration example

```toml
[integrations]
mail_adapter = "gmail-api-readonly"
calendar_adapter = "google-calendar-api"
practice_manager_adapter = "unavailable"

[credentials]
gmail_token_env = "LAWYEREDOS_GMAIL_TOKEN"
calendar_token_env = "LAWYEREDOS_CALENDAR_TOKEN"

[calendar]
calendar_id = "dedicated-calendar@example.invalid"
```

Never place token values in TOML. If an adapter or its credential is missing,
the workflow stops with an unavailable result rather than falling back to a
different account, calendar, or provider.

## Commands

```bash
python3 -m lawyeredos.integrations mail-search \
  --config "$LAWYEREDOS_CONFIG" --query "after:2031/01/01" --limit 100

python3 -m lawyeredos.integrations calendar-list \
  --config "$LAWYEREDOS_CONFIG" \
  --time-min "2031-01-01T00:00:00Z" --time-max "2031-02-01T00:00:00Z"

python3 -m lawyeredos.integrations calendar-preview \
  --config "$LAWYEREDOS_CONFIG" --action create \
  --event-json event.json
```

After the user approves that exact event, repeat with `calendar-commit` and the
returned token. Create/update commits re-read the exact event and verify its
private sync key before reporting success.
