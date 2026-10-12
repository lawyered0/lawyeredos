# Guided setup wizard

The project-local `lawyeredos-setup` skill is the recommended first-time path
for **Claude Code inside the Claude desktop app**. An ordinary setup request
selects it; users do not need to know its slash command. It gathers choices and then
delegates all writes to the wizard. The wizard is a local terminal interface built only with Python's
standard library. It does not run a web server, collect credentials, install
system software, modify global Claude settings, or select the plugin in the app.

## First-time path

Open the extracted `lawyeredos` folder in the app's Code tab, select the
**Local** environment, accept normal workspace trust, and paste:

```text
Set up LawyeredOS for me. Follow the setup instructions in this folder, ask me what you need, and check with me before changing existing files.
```

The root `SETUP.md` and project-local skill support that request. The skill will show and seek
approval for runtime creation or dependency installation when needed, then show
the exact JSON setup preview and seek a separate approval before applying it.

The initial read-only terminal preview from an extracted package is:

```bash
python3 scripts/setup_wizard.py
```

Create a retained `.venv` and install only the dependencies required by the
selected modules when the preview reports they are missing, after explicit
approval. Rerun the preview with that venv before applying; the preview and
apply interpreter must match.

The wizard asks for:

1. a project workspace;
2. neutral, individual, or firm branding and one local display label;
3. no jurisdiction profile or the bundled Ontario workflow-boundary profile;
4. optional letters, redline, calendar, and review modules;
5. one explicit email choice: Claude Gmail connector, safe skip, the
   experimental local `gmail.readonly` REST adapter, or the experimental
   host-neutral read-only IMAP adapter; and
6. an optional experimental dedicated Google Calendar adapter.

Choose a project directory outside the home folder itself and outside `~/.claude`,
`~/.codex`, and `~/.agents`. Both host installers reject those global locations,
including paths that resolve there through symlinks.

Matter orientation and the tracker are required core modules. Selecting a
jurisdiction profile does not install current law or replace primary-law
verification. For the supported Claude route, the user authenticates directly
with Google in Claude's **+ > Connectors > Gmail** interface and reviews
Google's consent screen. The wizard never sees a credential and cannot prove
that an active session is connected; it records only that the connector was
configured. A successful bounded read is required before a workflow may report
it connected. The connector can expose write actions, but LawyeredOS does not
auto-send and does not treat connection as approval to draft, send, reply,
forward, label, archive, or delete. The experimental REST route is narrower
(`gmail.readonly`) but requires the user to provision a token independently and
has only fake-transport acceptance. Token values remain environment-only. The
portable IMAP route supplies complete bodies and attachment bytes through
localized All Mail discovery and `BODY.PEEK`; setup writes only credential
source names and never creates or reads a credential. See
[IMAP-READONLY.md](IMAP-READONLY.md). The wizard asks only for an exact dedicated
calendar identifier, never a token.

## Preview and apply

Before writing anything, the wizard prints every target path, every planned
operation, dependency status with fixes, and the exact TOML it would create.
Type `APPLY` only after reviewing that preview. Pressing Enter or any other
answer cancels without creating the workspace.

The default project-local layout is:

```text
<workspace>/.lawyeredos/
  config.toml
  data/matters.sqlite3
  scratch/
  plugins/lawyeredos-<version>-<build>-<selection>/
  launch-lawyeredos.sh
  setup-state.json
  backups/
<workspace>/.claude/
  skills/lawyeredos-*/
  agents/lawyeredos-legal-review-lens.md
  settings.local.json
```

Only selected skill modules are present in the installed plugin copy. Config,
data, backups, and custom branding remain outside that versioned copy, so an
upgrade does not overwrite them.

## Open the installed workspace

After a successful apply, open the chosen workspace folder in the Claude
desktop app's Code tab. The generated launcher is an optional convenience:

```bash
<workspace>/.lawyeredos/launch-lawyeredos.sh
```

It changes to the chosen workspace, sets `LAWYEREDOS_CONFIG` to the private
project-local config, binds `LAWYEREDOS_PYTHON` to the virtual-environment
interpreter used for setup. It also installs collision-safe project skills and
the selected review agent into Claude's documented `.claude/` project
locations, and merges only the three LawyeredOS path variables into
`.claude/settings.local.json`. The default launcher uses macOS to open the
workspace folder directly in Claude Desktop and does not require a separate CLI
login. The optional terminal launcher invokes `claude`. Neither changes
user-global or account settings. Review the normal workspace-trust and
permission prompts.
Retain the extracted package and the recorded runtime. If setup used `.venv`,
retain that directory too. Moving or deleting the recorded runtime makes the
launcher stop with recovery instructions instead of silently using another
Python installation.

## Repeat runs, replacement, and rollback

The default `reuse` policy validates and preserves an existing config
byte-for-byte. Reapplying the same build and module selection is idempotent.
A different build or selection gets a new versioned plugin directory; the old
copy remains available for rollback.

Choose `replace` only when you intend to replace the generated configuration.
The wizard first stores the exact prior config under `backups/`. `error` stops
if a config already exists.

Roll back the most recent applied transaction with:

Run `scripts/setup_wizard.py --workspace /absolute/project/path --rollback`
with the same retained Python used for setup (`python3` or
`.venv/bin/python`).

Rollback proceeds only when every managed artifact still matches the
fingerprints recorded by that transaction. If config, tracker, launcher, or
plugin content has changed, the entire rollback is refused before any changes
and the drift is reported under `preserved_modified`. It does not remove
unrelated workspace files, later matter activity, or older versioned plugin
copies.

Managed fingerprints are typed hashes, not raw file SHA-256 values. A regular
file is recorded as `SHA-256(b"file\\0" + file_bytes)`; directories and
symlinks use their own typed representations. A different raw file digest is
therefore expected and is not evidence of drift. Rollback recomputes the same
typed representation.

## Automation and smoke test

For a scripted fictional/disposable setup, provide every choice and add
`--apply --yes`. Never use `--yes` until the generated preview has already been
reviewed for that exact target.

Run the bundled disposable smoke test with:

```bash
.venv/bin/python scripts/smoke_setup_wizard.py
```

The smoke test verifies side-effect-free preview, first apply, config loading,
repeat idempotency, and rollback inside a temporary fictional workspace.

## Dependency results

Python 3.11+ and a Local Claude Desktop Code session on macOS are required. The
terminal Claude Code command is an optional fallback. `openpyxl` is optional for
XLSX projection. `python-docx` is required when letters or redlines are selected;
`lxml` and `fpdf2` are additionally required for redlines. LibreOffice and
Poppler enable visual document checks; OCRmyPDF enables OCR. Missing optional
tools are reported with fixes but are never installed automatically.

The Claude Gmail connector is a supported Claude feature, but LawyeredOS cannot
verify its authorization locally and has not completed a real-mail acceptance
run. The bundled Gmail REST and Google Calendar adapters remain experimental
and fail closed when their named credential source is absent. The portable IMAP
route has comprehensive fake-transport coverage but no live-IMAP or ordinary
host acceptance. Email is
never silently disabled: `skip` is an explicit, safe choice. The
practice-manager adapter is unavailable.
