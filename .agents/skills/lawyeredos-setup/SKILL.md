---
name: lawyeredos-setup
description: Preview and install this LawyeredOS Codex candidate into a new private project workspace without changing global Codex settings.
---

# Set up LawyeredOS for Codex

Use only the bundled deterministic `scripts/setup_codex.py` writer. Do not edit
the target workspace yourself and do not change `~/.codex`, `~/.agents`, an
existing project `.codex/config.toml`, credentials, or connector permissions.

Read `CODEX.md` and `USE-NOTICE.md`. Confirm this is macOS with Python 3.11 or
newer and either Codex CLI or the ChatGPT desktop app. For the acceptance trial,
require a brand-new disposable workspace containing only fictional data.

Collect and repeat back:

1. an absolute private workspace path;
2. branding mode and a non-identifying display label;
3. jurisdiction profile (`none` or `ontario`);
4. modules (`matter,tracker` are required);
5. one explicit mail choice: `session-tools`, `skip`, experimental
   `gmail-readonly`, or experimental host-neutral `gmail-imap`; and
6. existing config policy.

`session-tools` does not install or authorize Gmail. It means the workflow must
inspect the active session for a supported authorized mail read/search tool and
report mail unavailable if none exists. Never request credentials, enable an
app, broaden permissions, or run a real-inbox acceptance test during setup.

`gmail-imap` retrieves complete bodies and attachment bytes through read-only
IMAP independently of session tools. Credential creation and configuration are
separate user actions: setup writes no secret, creates no app password, and
leaves the optional Keychain service blank. Never ask the user to paste a
credential into the chat.

Preview with one exact argument list and `--json`. For a first trial include
`--require-new-workspace --existing-config error`. Show the complete JSON plan
and receive explicit approval before repeating the identical arguments with
`--apply --yes --json`. If the interpreter or any argument changes, preview
again. Never install Python packages without separately showing the exact
command and receiving approval.

After apply, run the bundled validator against
`<workspace>/.lawyeredos/config.toml`, then use a new Codex session opened at
the workspace root to confirm the `lawyeredos-*` project skills appear. Use
only a fictional tracker and matter. Reads do not authorize writes.
