# Troubleshooting

## The launcher says the runtime is unavailable

The retained extracted package or its `.venv` moved or was deleted. Do not edit
the launcher by hand. Restore that folder at its original path or extract the
same/new release to a stable location, recreate its `.venv`, and rerun the
wizard for the same workspace using the default `reuse` policy.

## The skill is missing in Claude Code

Confirm that you opened the exact configured workspace through
`.lawyeredos/launch-lawyeredos.sh` or directly with Claude Desktop. Accept the
normal one-session workspace prompt. The expected project skill names begin
with `lawyeredos-`. Run the following offline check only if the optional Claude
Code command is installed:

```bash
claude plugin validate --strict /absolute/path/to/versioned/plugin
```

If an older `legal-practice` skill appears, stop: that is not evidence that the
current renamed package loaded. A crowded personal skill catalog can shorten
skill descriptions. Personal skills with the same name override project skills,
which is why this package uses collision-safe `lawyeredos-*` names.

## The skill is missing in Codex

Open a new Codex session at the exact installed workspace root. Confirm the
expected links exist under `.agents/skills/lawyeredos-*` and are recorded in
`.lawyeredos/codex-project-discovery.json`. Do not copy a personal skill into
the project or change `~/.codex`, `~/.agents`, or `.codex/config.toml`.

Rerun `scripts/setup_codex.py` as a preview with the same workspace and
`--existing-config reuse`. An unmanaged collision, modified launcher, symlinked
managed directory, missing config, or changed module selection is a safety
stop; inspect it instead of overwriting it.

## The first orientation says matter not found

The wizard creates an empty register. First link the existing folder through
the matter-tracker skill, preview the row, approve it, and re-read it. Confirm
the folder path is relative to the configured workspace.

## The orientation says folder unavailable

The registered folder is missing, is a symlink, or resolves outside the
workspace. Do not guess another folder. Correct the workspace or preview a
tracker update to the exact intended relative folder.

## Letters or redlines fail with an import error

Launch through the generated launcher and confirm `LAWYEREDOS_PYTHON` points to
the retained package's `.venv/bin/python`. Reinstall the tested lock into that
same virtual environment, then rerun `validate_setup.py`.

## Document rendering is unavailable

DOCX creation can succeed without visual QA, but the letter/redline skills must
not claim visual verification without LibreOffice and Poppler. Install those
tools separately, rerun validation, and render every page before external use.

## OCR is unavailable

OCR is optional and fails closed. Install OCRmyPDF and its system dependencies,
then test on a disposable fictional document. Do not replace a source PDF; the
helper creates a separate OCR copy and hash-bound report.

## Rollback reports `preserved_modified`

This is a safety refusal, not a partial deletion failure. At least one managed
artifact no longer matches the setup transaction, so rollback left the entire
setup untouched. Inspect and back it up before any manual removal. A changed
tracker may contain matter activity and must never be deleted merely to complete
rollback.

## Gmail or Calendar is unavailable

Check the configured mail state first. `unavailable` means setup explicitly
skipped email. `claude-gmail-connector` means the user chose Claude's connector,
but the local validator cannot prove it is authorized in this session: open
Claude's **+ > Connectors**, enable Gmail, authenticate directly with Google,
and review the account and consent screen. On Team or Enterprise an owner may
need to enable it first. Only a successful bounded read establishes connection
for that request. Do not use connector send or mailbox-mutation actions.

`gmail-api-readonly` is the experimental local REST route. It requires a valid,
separately provisioned `gmail.readonly` token in the named environment variable;
the value never belongs in TOML. Missing credentials fail closed. Calendar is
also experimental. Never substitute a different account, primary calendar, or
connector.

For Codex, `codex-session-tools` means setup may inspect the active session for
a supported authorized read/search tool. It does not prove one exists. If the
tool is absent or unauthorized, report that email was not checked; do not start
OAuth, request a token, open a browser workaround, or substitute another
account.

## Asking for help

Follow [SUPPORT.md](../SUPPORT.md). Never paste client content, credentials,
private paths, or an unredacted config into an issue.
