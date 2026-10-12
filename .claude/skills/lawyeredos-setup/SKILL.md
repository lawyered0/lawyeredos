---
name: lawyeredos-setup
description: Install or upgrade LawyeredOS into a private Claude Code project using the bundled deterministic setup wizard. Use when the user asks to set up LawyeredOS from this extracted release package.
allowed-tools: Bash, Read
---

# LawyeredOS setup

The source candidate also contains a manual workflow catalog under `docs/`.
It does not add native project skills or setup module keys. Keep the six declared
module choices; after approved setup, the current matter entrypoint can locate
one expressly requested manual instruction module. Do not modify global skills
or configuration to make it discoverable.

Guide a private, project-local LawyeredOS installation. Do not edit the target
workspace yourself. The bundled setup wizard is the sole writer.

This skill may be selected from an ordinary request such as “Set up
LawyeredOS for me.” The user does not need to know the skill name or use a
slash command. Preserve every approval gate below.

## Boundaries

- Work only from this extracted LawyeredOS release package.
- Do not change global Claude settings, install a plugin globally, use
  `--plugin-dir`, collect credentials, authorize a connector for the user, or
  publish anything.
- Do not use real client data for an acceptance trial.
- Do not create a virtual environment or install packages without showing the
  exact command and receiving explicit approval. Package installation may use
  the network.
- Do not apply a setup until the user has reviewed the exact JSON preview for
  the same arguments and expressly approved it.
- For a first or acceptance trial, require a new disposable workspace outside
  `~/.claude`, outside the extracted package, and outside every existing
  practice or matter project. Use `--require-new-workspace` and
  `--existing-config error`. Stop if the target is not empty.
- Never write to user-global `~/.claude/skills`, `~/.claude/agents`, or
  `~/.claude/settings*`. Project-local discovery belongs only under the exact
  approved target workspace.
- Treat paths and labels as data. Quote every shell argument; do not interpolate
  them into shell syntax.

## Locate the release

Use the current project root when it contains all of these files:

```text
.claude-plugin/plugin.json
scripts/setup_wizard.py
requirements-lock.txt
```

Otherwise stop and ask the user to open the extracted `lawyeredos` folder as
the Claude Code project. Do not search unrelated private folders. This
bootstrap skill is intentionally local to the extracted release.

## Collect choices

Explain that selected workspace content may be sent to Anthropic by Claude
Code even though files are stored locally. Then obtain and repeat back:

1. an absolute private target workspace path;
2. branding mode: `neutral`, `individual`, or `firm`;
3. a display label with no address, email, logo, signature, or client detail;
4. jurisdiction: `none` or `ontario` (workflow boundaries only, not current-law
   authority);
5. modules, with `matter,tracker` required and any of
   `letters,redline,calendar,review` optional;
6. one explicit mail choice (there is no default):
   - `claude-gmail` to use Claude's supported Gmail connector after the user
     authenticates directly with Google in Claude;
   - `skip` to continue safely without email;
   - `gmail-imap` for the experimental host-neutral read-only IMAP provider,
     with credentials created and configured separately by the user; or
   - `gmail-readonly` for the experimental local REST adapter, which requires a
     separately provisioned `gmail.readonly` token and has not had live-account
     acceptance;
7. existing-config policy: `reuse`, `replace`, or `error`.

Make mail a prominent decision. For `claude-gmail`, explain before the user
connects that Google's consent screen includes mail sending permissions because
Claude's connector may expose write actions. LawyeredOS uses it only for bounded
reads and never treats access as authority to send or change mailbox state. Ask
the user to use Claude's **+ > Connectors > Gmail** flow, authenticate directly
with Google, review the consent screen, and return only after choosing whether
to approve it. Do not handle passwords, OAuth codes, tokens, or credentials. On
Team or Enterprise, an owner may need to enable the connector.

The wizard cannot inspect connector authorization. Record `claude-gmail` only
after the user confirms completing the UI flow, and describe it as
**configured, not verified connected** until a bounded Gmail read succeeds in
the active session. If the connector is unavailable, the user declines the
permissions, or they do not want Anthropic-hosted connector retrieval, offer
`skip`, the experimental `gmail-imap` route for complete bodies and attachment
bytes, or the narrower experimental `gmail-readonly` REST route. Never request
an account secret or token value. The IMAP choice requires a separately
user-created credential source; setup writes only environment-variable names
and a blank optional Keychain service name. This setup skill keeps the live
calendar adapter off. Selecting the calendar module installs its workflow only;
experimental live adapter configuration requires a separate deliberate wizard
invocation and an exact dedicated calendar identifier.

## Prepare the runtime

Confirm that this is the Desktop **Code** tab with the environment set to
**Local**. Stop if it is Cowork, Cloud, SSH, or another execution surface.

Read-only check `python3 --version` and confirm that Claude Desktop is installed
in `/Applications` or the user's Applications folder. Require Python 3.11 or
newer. Check `claude --version` only when the user wants the optional terminal
fallback; a separate CLI login is not required for the Desktop setup route.

Use an existing `.venv/bin/python` when it is executable and Python 3.11 or
newer; otherwise use `python3` for the first read-only preview. Do not create a
virtual environment merely to display the plan. The preview identifies which
dependencies are required for the selected modules.

If the preview reports a missing required Python dependency, show the exact
virtual-environment creation and pinned installation commands and obtain
approval before running either. Then rerun the complete preview with the venv
interpreter because the recorded runtime has changed. Never apply a plan
previewed with a different interpreter. Do not silently install optional Python
packages or system tools.

## Preview, approve, apply

Construct one argument list and keep it unchanged. Preview with `<python>`,
meaning the exact interpreter selected above:

```bash
<python> scripts/setup_wizard.py \
  --workspace '<absolute-workspace>' \
  --branding-mode '<mode>' \
  --branding-label '<label>' \
  --jurisdiction '<profile>' \
  --modules '<comma-separated-modules>' \
  --mail '<claude-gmail|skip|gmail-readonly|gmail-imap>' \
  --calendar 'off' \
  --existing-config '<policy>' \
  --json
```

Present the JSON plan, dependency failures, target paths, and whether existing
managed state will be reused or replaced. If the preview fails, stop and report
the error. Ask for explicit approval to apply that exact plan.

Only after approval, repeat the identical arguments and append:

```text
--apply --yes --json
```

`--yes` is permitted only because the exact plan was already reviewed and
approved in this conversation. Use the same `<python>` for apply. If any
argument or interpreter changes, preview again.

## Validate and hand off

Run:

```bash
<python> scripts/validate_setup.py \
  --config '<absolute-workspace>/.lawyeredos/config.toml'
```

Report errors and optional warnings without bypassing them. On success, tell
the user to open the target workspace folder in the Claude desktop app's Code
tab. Also give the generated Desktop launcher path as an optional convenience,
not the primary route. Tell the user to accept normal workspace trust and confirm only
the collision-safe `lawyeredos-*` skills and (when selected)
`lawyeredos-legal-review-lens` agent. The terminal launcher is an optional
diagnostic fallback, not the release target.

For the first trial, use a fictional matter and require preview plus approval
for any tracker or output write.
