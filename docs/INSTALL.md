# Installation

For this unreleased instruction candidate, setup still accepts only the existing
six modules. After opening the installed workspace, use the matter entrypoint
and [workflow catalog](WORKFLOW-CATALOG.md) to read one requested manual module.
Do not add new setup flags, TOML module keys or global skills to discover it.
An instruction module does not enable an unselected renderer, reviewer, adapter
or broad mailbox route. Exact archive and installed-reference checks are
reported separately; substantive instruction behavior and broader host/account
coverage remain unverified.

## Before you start

LawyeredOS targets Claude Desktop Code Local or a Codex local project on macOS.
You need:

- the current app for the selected host, or the documented optional CLI;
- Python 3.11 or newer;
- one private parent folder for the extracted package; and
- one private workspace containing only the matters you intend the selected
  host (Claude or Codex) to access.

LibreOffice and Poppler are recommended for document rendering. OCRmyPDF is
optional. Setup makes email a required explicit choice: connect through
Claude's supported Gmail connector, skip email safely, select the experimental
local read-only REST adapter, or select the portable read-only IMAP adapter.
Calendar remains experimental.

The selected host may transmit workspace content to Anthropic or OpenAI under
the user's account and settings. Do not treat local storage as offline
processing.

## Codex quick start

Open the extracted Codex package as a local Codex project and paste:

```text
Set up LawyeredOS for me in a new private workspace. Use fictional data, show me the complete plan, and check with me before changing files.
```

Codex discovers `.agents/skills/lawyeredos-setup/SKILL.md`. The skill previews
one exact `scripts/setup_codex.py` argument list and waits for approval before
repeating it with `--apply --yes`. For the first trial it must use a new empty
workspace, `--require-new-workspace`, `--existing-config error`, and fictional
data. It does not change global Codex skills/settings, project
`.codex/config.toml`, credentials, OAuth state, or connector permissions.

Choose `session-tools` only to permit bounded use of an already-authorized
read/search tool exposed by the active session; setup cannot install or verify
one. Choose `skip` to proceed without mail, `gmail-readonly` only for the
experimental separately provisioned local REST route, or `gmail-imap` for the
portable read-only IMAP route after completing its separate user-mediated
credential setup. See [CODEX.md](../CODEX.md) and
[Portable Gmail IMAP intake](IMAP-READONLY.md) for the exact boundaries.

The remaining sections describe the released Claude Desktop setup. Shared
runtime, fictional-first, validation, retention, and professional-review rules
apply to both hosts.

## Claude Desktop Code Local

## 1. Extract and retain the package

Extract the release archive into a stable private location. Do not run it from
Downloads if that folder is routinely cleaned. The generated launcher binds to
the exact Python used for the approved setup plan, whether that is a stable host
runtime or the retained virtual environment described below.

## 2. Ask Claude to set it up

Open the extracted `lawyeredos` folder in the Claude desktop app's Code tab,
choose the **Local** environment, accept the normal workspace-trust prompt, and
paste:

```text
Set up LawyeredOS for me. Follow the setup instructions in this folder, ask me what you need, and check with me before changing existing files.
```

Claude can discover the root `SETUP.md` and the setup skill under
`.claude/skills/lawyeredos-setup/`. It gathers choices, checks the runtime, and
delegates all changes to the deterministic wizard. It must display the exact
JSON plan and receive explicit approval before applying it. It does not edit
the target workspace itself. `/lawyeredos-setup` remains an optional explicit
invocation, not the primary installation route.

Do not use Cowork or a Cloud Code environment for this macOS package. Their
isolated runtimes cannot be assumed to see or execute the Python path selected
on the Mac.

For the fictional acceptance run, give Claude a brand-new disposable target
and require `--require-new-workspace` with `--existing-config error`. Never use
an existing practice project, matter folder, or a path under `~/.claude`. The
wizard checks again immediately before apply and stops if any file appeared
after the preview.

## 3. Terminal fallback: preview before creating a runtime

When the Mac's `python3` is version 3.11 or newer, the setup preview itself uses
only the standard library:

```bash
python3 scripts/setup_wizard.py
```

This makes no changes. If the preview reports missing dependencies required by
the modules you selected, create the retained runtime only after reviewing the
commands:

From the extracted `lawyeredos` folder:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-lock.txt
```

The lock contains the exact Python package versions tested for version 0.2.0.
It does not install Claude Code, LibreOffice, Poppler, or OCRmyPDF.

## 4. Terminal fallback: preview setup with the chosen runtime

Use the same interpreter for preview and apply. If no required dependency was
missing, `python3` may be the chosen runtime. If you created `.venv`, rerun the
full preview with `.venv/bin/python` before applying because the recorded
runtime has changed.

```bash
python3 scripts/setup_wizard.py
# or, after an approved venv setup:
.venv/bin/python scripts/setup_wizard.py
```

For the first run, choose:

- the parent workspace that contains or will contain matter folders;
- neutral branding unless you have reviewed a private template;
- no jurisdiction profile unless the Ontario boundary notes are useful;
- matter and tracker modules, plus only the optional modules you need; and
- one explicit mail choice after reviewing the access and action boundaries;
  use `skip` if you do not want email access; and
- calendar off unless you are deliberately testing its experimental adapter.

Review the paths, dependency report, selected modules, and exact configuration.
Type `APPLY` only when they are correct. Any other response cancels.

## 5. Open the installed workspace

Open the target workspace folder in the Claude desktop app's Code tab. Review
the app's workspace trust and permission prompts. Confirm the project skills
appear as `lawyeredos-*` and the review agent, when selected, as
`lawyeredos-legal-review-lens`.

The generated Desktop launcher is an optional convenience, normally:

```bash
/absolute/path/to/workspace/.lawyeredos/launch-lawyeredos.sh
```

Do not credit an older `legal-practice`
namespace or an account-level `practice-*` skill as current-package evidence.

The Desktop launcher asks macOS to open the workspace folder directly in the
Claude app; it does not require a separate terminal CLI login. Project discovery comes from
`.claude/skills/` and `.claude/agents/`, while `.claude/settings.local.json`
supplies the private absolute runtime paths. The optional terminal launcher uses
the same project-local discovery layer and requires the separately installed
and authenticated `claude` command.

## 6. Link a fictional first matter

Before client use, create a fictional folder inside the workspace:

```text
2030-001-northstar/
  _matter-brief.md
  source-note.txt
```

Start the brief with one identity heading, such as
`# 2030-001 — Northstar Bakery Ltd.`. The read-only orientation refuses a
missing, duplicate, or conflicting matter heading.

Ask Claude to link that existing folder as matter `2030-001`, show the exact
tracker preview, and wait for approval. Then ask for a read-only orientation.
The expected result identifies one exact folder, summarizes only the sources it
actually read, reports uncertainty, and recommends one next step without making
a file or tracker change.

## 7. Validate before client use

From the retained extracted package:

```bash
.venv/bin/python scripts/validate_setup.py \
  --config /absolute/path/to/workspace/.lawyeredos/config.toml
```

Resolve every error. Warnings identify unavailable optional capabilities; they
must remain disclosed rather than silently bypassed.

See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for failures and
[LIFECYCLE.md](LIFECYCLE.md) before updating, rolling back, or uninstalling.
