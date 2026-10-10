# External adapters

External access is opt-in. The wizard requires an explicit mail choice and
leaves Calendar and practice-manager access unavailable unless selected.
Credentials are never written to logs, plans, fixtures, or reports.

## Gmail

### Codex session tools

`codex-session-tools` records permission to inspect the active Codex session
for a supported, already-authorized mail read/search tool supplied by a runtime
MCP server or plugin. Codex documents how MCP servers and plugin-bundled MCP
servers expose tools, but does not define a built-in Gmail tool contract. This
adapter therefore names no hypothetical tool. It does not install
an app, start OAuth, request credentials, broaden permissions, or prove a tool
is connected. Only a successful bounded read establishes availability for that
request. If no supported tool exists, the workflow reports that email was not
checked and continues only with independent work.

The workflow must not substitute a browser session, a different connector, or
a send-capable action. A session tool must return fully retrieved bodies and
attachment bytes before the shared intake core can review those items within
its bounded review window; metadata-only or over-window results are partial.
The transient normalized bundle uses restrictive private-scratch permissions
and is deleted by the guarded processor. A provider-prefixed, hashed stable
account identifier scopes deduplication without storing the raw identifier; if
the session tool cannot establish one, the result is incomplete. No live Codex
mail-tool acceptance is claimed.

See Codex's official [MCP documentation](https://learn.chatgpt.com/docs/extend/mcp?surface=cli)
and [skills documentation](https://learn.chatgpt.com/docs/build-skills) for the
supported discovery boundary.

### Claude Gmail connector

`claude-gmail-connector` records that the user chose Claude's supported Gmail
connector and authenticated directly with Google in Claude. LawyeredOS never
receives or stores that credential. The setup wizard cannot inspect connector
authorization, so this value means **configured, not verified connected**. A
workflow may report the connector connected only after a successful bounded
read in that active session.

Google's consent screen may mention sending permissions because Claude's
connector can expose draft, send, reply, forward, label, and thread actions.
LawyeredOS uses only bounded search/read access and never treats the connection
as approval to send or mutate a mailbox. If the tool is absent, authentication
is incomplete, or the user declines the permissions, the workflow reports mail
unavailable and continues only with independent work. Anthropic's documented
Gmail connector can search and read messages, but directly exposes attachment
metadata rather than attachment contents. Consequently, a message with an
attachment remains partial unless the active runtime separately provides an
authorized read tool that returns those bytes. LawyeredOS does not assume or
bundle such a tool, and the checkpoint does not advance past that message.

Current connector capabilities, authorization steps, data handling, and plan
controls are documented by Anthropic in [Use Google Workspace
connectors](https://support.claude.com/en/articles/10166901-use-google-workspace-connectors).

### Experimental local REST adapter

`gmail-api-readonly` uses the Gmail REST API to run the exact bounded matter
query and retrieve current bodies plus attachment bytes within acquisition
limits. The
caller must supply a token scoped no more broadly than `gmail.readonly`. The
shared core sanitizes and hashes attachments, refuses active or oversized
content, external OOXML relationships, embedded objects, and unsafe paths;
saves without overwrite; extracts supported document text; and advances the
local checkpoint only after complete coverage and bounded review. Long content,
inline/unsupported parts, and unexplained provider matches remain partial. This
adapter does not mark read, label, archive, delete, create drafts,
or send. A result cap or next-page token makes coverage incomplete.

For offline demonstrations, `fixture-json` searches a fictional JSON message
list. It never contacts a service.

### Portable read-only IMAP adapter

`gmail-imap-readonly` supplies the attachment-byte path that a metadata-only
host connector cannot provide. It uses Gmail's localized IMAP All Mail folder,
the exact bounded `X-GM-RAW` matter query, stable Gmail IDs, and `BODY.PEEK` in a
read-only mailbox. It contains no send or mailbox-mutation operation.

Credentials remain user-mediated. The generated configuration names two
environment variables and leaves the optional macOS Keychain service blank.
Setup never creates an app password, reads an existing Keychain secret, or
writes a credential value or sidecar file. See [Portable Gmail IMAP
intake](IMAP-READONLY.md) for prerequisites, limits, and the exact live-test
boundary.

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
mail_adapter = "claude-gmail-connector"
calendar_adapter = "google-calendar-api"
practice_manager_adapter = "unavailable"

[credentials]
gmail_token_env = "LAWYEREDOS_GMAIL_TOKEN"
gmail_imap_account_env = "LAWYEREDOS_GMAIL_IMAP_ACCOUNT"
gmail_imap_secret_env = "LAWYEREDOS_GMAIL_IMAP_SECRET"
gmail_imap_keychain_service = ""
calendar_token_env = "LAWYEREDOS_CALENDAR_TOKEN"

[calendar]
calendar_id = "dedicated-calendar@example.invalid"
```

For the experimental local REST route, use
`mail_adapter = "gmail-api-readonly"` and provision only a `gmail.readonly`
token in the named environment variable. Never place token values in TOML. If
an adapter or its credential is missing,
the workflow stops with an unavailable result rather than falling back to a
different account, calendar, or provider.

For the portable full-body and attachment route, use
`mail_adapter = "gmail-imap-readonly"`, complete the user-mediated setup in
[IMAP-READONLY.md](IMAP-READONLY.md), and run `lawyeredos.mail_intake imap`.

Codex setup may instead write `mail_adapter = "codex-session-tools"`; that
mode uses no token from this config and remains unavailable unless the active
session exposes a supported authorized read tool.

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
