# LawyeredOS for Codex

This source branch adds unreleased manual workflow instructions listed in
[WORKFLOW-CATALOG.md](docs/WORKFLOW-CATALOG.md). The existing six projectized
skills remain the only native installed entries. New modules are read at their
source paths through the current matter entrypoint; their frontmatter is not
evidence of `.agents/skills` discovery. Resolve manual references from
`.lawyeredos/current-codex` and use installed Codex instructions for commands.
No installer/configuration or Python behavior changes accompany these additions.
Exact archive and installed-reference checks are separate release evidence;
they do not establish new substantive model behavior or live-connector coverage.

The Codex beta reuses the LawyeredOS Python, SQLite, document,
redline, and guarded workflow core. Its Codex integration is separate from the
Claude integration: Codex discovers selected project skills under
`.agents/skills`, while the Claude beta continues to use `.claude/`.

Reviewed release: [Codex 0.2.1 beta.1](https://raw.githubusercontent.com/lawyered0/lawyered0.github.io/main/downloads/lawyeredos-0.2.1-macos-codex-beta.1.zip),
SHA-256
`1e7d886c76e2e6cbfeee33bf14833995db91fde2b4a7d1e1565dcb4769d14856`.
The source branch may be newer; rebuilding it does not replace that archive.

## Safe fictional trial

Open the extracted Codex package as a local Codex project and ask:

```text
Set up LawyeredOS for me in a new private workspace. Use fictional data, show me the complete plan, and check with me before changing files.
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
- `gmail-imap`: experimental portable read-only IMAP adapter for complete
  bodies and attachment bytes. The user separately provisions the named
  environment variables or an explicitly configured macOS Keychain service;
  setup never creates, retrieves, or stores a credential.

Do not use a real inbox or matter for installation acceptance. Calendar, OCR,
and live Gmail remain experimental or unverified as described in the existing
documentation.

## Verified host boundary

The Codex beta's core and project-skill discovery target the tested macOS
environment with Python 3.12.7 and Codex CLI 0.147.0. In a user-created fresh
Codex desktop task, the installed fictional matter workflow returned the exact
saved action, date, revision, unverified date, and unavailable-email boundary.
That user-reported functional result is not an independent GUI observation,
forensic no-write verification, or proof of session-start catalog registration.
The candidate makes no Windows, Linux, other Python-version, cloud-host, or
live-connector compatibility claim.

The 0.2.1 beta.1 portable read-only IMAP path also completed one exact
self-addressed, user-created Gmail test thread in an ordinary Codex Desktop /
GPT-5 session: the body and three hash-bound DOCX chunks were acknowledged,
the checkpoint completed, the repeat deduplicated, and guarded bundle deletion
succeeded. This is bounded evidence for that account, thread, launcher, and
host—not general Gmail, OAuth/REST, sending, mutation, or session-tool
acceptance.

Project skill discovery follows Codex's documented `.agents/skills` mechanism.
Codex can delegate independent reviewers when that capability is exposed in
the active host. Repository skills cannot technically reduce a delegated
reviewer's tool set, so the four-lens workflow remains hash-verified and must
report itself unavailable when independent delegation is absent.

The acceptance record, including the distinction between Codex CLI
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
