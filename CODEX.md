# LawyeredOS Codex candidate

This private candidate reuses the released LawyeredOS Python, SQLite, document,
redline, and guarded workflow core. Its Codex integration is separate from the
Claude integration: Codex discovers selected project skills under
`.agents/skills`, while the Claude beta continues to use `.claude/`.

## Safe fictional trial

Open this extracted candidate folder as a local Codex project and ask:

```text
Set up this LawyeredOS Codex candidate in a new disposable workspace. Use only fictional data, show me the exact JSON plan, and wait for approval before applying it.
```

The `lawyeredos-setup` bootstrap skill must use `scripts/setup_codex.py`. For a
first trial it passes `--require-new-workspace --existing-config error`. The
installer writes only the approved workspace's `.lawyeredos` and
`.agents/skills` paths. It does not write `~/.codex`, `~/.agents`, project
`.codex/config.toml`, credentials, OAuth state, or connector permissions.

Choose one mail mode explicitly:

- `session-tools`: configure workflows to inspect the active Codex session for
  a supported authorized read/search tool. Setup cannot install, authorize, or
  verify one. A successful bounded read is the only connection evidence.
- `skip`: continue without email and disclose that email was not checked.
- `gmail-readonly`: experimental local REST adapter using a separately
  provisioned `gmail.readonly` token; no live-account acceptance is claimed.

Do not use a real inbox or matter for acceptance. Calendar, OCR, and live Gmail
remain experimental or unverified as described in the existing documentation.

## Verified host boundary

The candidate's core and project-skill discovery target the tested macOS
environment with Python 3.12.7 and Codex CLI 0.147.0. In a user-created fresh
Codex desktop task, the installed fictional matter workflow returned the exact
saved action, date, revision, unverified date, and unavailable-email boundary.
That user-reported functional result is not an independent GUI observation,
forensic no-write verification, or proof of session-start catalog registration.
The candidate makes no Windows, Linux, other Python-version, cloud-host, or
live-connector compatibility claim.

Project skill discovery follows Codex's documented `.agents/skills` mechanism.
Codex can delegate independent reviewers when that capability is exposed in
the active host. Repository skills cannot technically reduce a delegated
reviewer's tool set, so the four-lens workflow remains hash-verified and must
report itself unavailable when independent delegation is absent.

The private acceptance record, including the distinction between Codex CLI
and Codex desktop coverage, is in [`docs/CODEX-ACCEPTANCE.md`](docs/CODEX-ACCEPTANCE.md).
The release-gate matrix is in
[`docs/CODEX-COVERAGE-MATRIX.md`](docs/CODEX-COVERAGE-MATRIX.md).

## Terminal preview

The normal flow is conversational. For inspection, the equivalent preview is:

```bash
python3 scripts/setup_codex.py \
  --workspace '/absolute/disposable/workspace' \
  --branding-mode neutral --branding-label 'Northstar Legal Lab' \
  --jurisdiction none --modules matter,tracker,review \
  --mail skip --calendar off --existing-config error \
  --require-new-workspace --json
```

Applying additionally requires `--apply --yes` after the exact preview is
approved. Re-running the same approved setup is idempotent. A colliding
pre-existing `lawyeredos-*` skill or modified managed launcher fails closed.
