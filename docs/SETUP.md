# Setup

For a new installation, use the guided workflow in `docs/WIZARD.md`. The manual
steps below remain available for inspection, troubleshooting, and controlled
migrations.

## 1. Choose private locations

Keep the plugin, workspace, scratch directory, and configuration separate.
The configuration should not be committed.

```text
private-plugins/lawyeredos/
practice-workspace/
practice-scratch/
private-config/lawyeredos.toml
```

## 2. Install Python dependencies

Use a project-local virtual environment and install `requirements-lock.txt` for
the tested build and runtime dependency set. Install `requirements-test.txt`
when running the bundled upstream redline tests. The lock includes the build
backend required for local package builds. The guided wizard runs directly from
the extracted package. OCRmyPDF, Poppler, and LibreOffice remain separate
platform commands; the setup validator reports which are missing.

## 3. Create configuration

Copy `config.example.toml` outside the repository. Use absolute paths. Leave an
integration set to `unavailable` until its adapter is installed and verified.
The validator refuses unknown jurisdiction profiles and `external_ai = true`.
Tokens belong only in the environment variable names configured under
`[credentials]`; never place token values in TOML. See `docs/ADAPTERS.md`.

## 4. Initialize a private tracker

```bash
PYTHONPATH=src python3 -m lawyeredos.tracker_cli \
  init --database /absolute/path/to/matters.sqlite3
```

`init` refuses a pre-existing file. All later writes use preview tokens.
For an existing register, do not initialize over it. Follow
`docs/MIGRATION.md` to build and verify a new database without changing the
source.

## 5. Validate

```bash
PYTHONPATH=src python3 scripts/validate_setup.py \
  --config /absolute/path/to/private-config.toml
```

Fix every error before enabling skills. Warnings identify optional features.

## 6. Open in a Desktop Code workspace

Do not copy over existing global skills. Make a private versioned copy and run
`claude plugin validate --strict <directory>` as an offline build check. The
guided wizard places collision-safe project skills in `.claude/skills/`, the
selected review agent in `.claude/agents/`, and private runtime paths in
`.claude/settings.local.json`. These documented project sources are read by
local Desktop Code sessions after workspace trust. No global/account plugin is
installed. Keep the live private package unchanged until the demo, adapter
mocks, review task bundle, and tracker migration sample all pass.

## Upgrade and rollback

Install each build into a new versioned directory, update the plugin pointer,
and keep the prior directory until the new version passes fixture tests. Data
stores and private configuration stay outside plugin directories.

The guided wizard implements this layout automatically. Its default `reuse`
policy preserves existing configuration byte-for-byte, while `replace` creates
a backup first. Its rollback command affects only paths recorded in the most
recent managed transaction and preserves any managed artifact that changed
after setup. See `LIFECYCLE.md` for update, rollback, disable, and uninstall
procedures that preserve matter data by default.
