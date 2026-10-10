# Contributing

Contributions should improve a specific lawyer workflow without weakening
matter isolation, preview/approval boundaries, evidence handling, or honest
capability disclosure. LawyeredOS has one shared core and separate Claude and
Codex integration layers; identify which layer a change affects.

## Before opening a change

- Use fictional or fully sanitized data only.
- Never submit authentic client names, matter numbers, document or email text,
  credentials, token fragments, account identifiers, private paths, hostnames,
  branded templates, confidential screenshots, or unredacted logs.
- Keep provider-specific discovery and setup under the correct namespace:
  `.claude/` for Claude and `.agents/` for Codex.
- Do not change shared behavior to simulate parity that the active host cannot
  provide. Report unsupported capabilities explicitly.
- Keep optional integrations disabled by default and fail closed.
- Do not add telemetry or sending behavior.
- Do not claim support for a host, provider feature, or operating system
  without a reproducible fictional acceptance run.
- Open a focused issue for a behavioral change larger than a small bug fix.
  Security concerns follow [SECURITY.md](SECURITY.md), not public issues.

## Pull requests

Keep changes focused. Explain:

1. the lawyer task and host scope (`shared`, `Claude`, or `Codex`);
2. evidence or fixtures read;
3. writes or external effects;
4. approval and stale-state behavior;
5. failure and recovery behavior;
6. tests and fictional acceptance performed; and
7. what remains experimental or unverified.

Update lawyer-facing documentation when behavior changes. Preserve released
ZIPs and their checksums; a source contribution does not authorize replacing a
published package or expanding its acceptance claim.

## Local verification

Use Python 3.12 on macOS for the accepted development path:

```bash
python3 -m pip install -r requirements-lock.txt -r requirements-test.txt
PYTHONPATH=src python3 -m unittest discover -s tests -v
python3 -m pytest vendor/legal-redline-tools/tests -q
python3 scripts/smoke_setup_wizard.py
release_dir="$(mktemp -d)"
python3 scripts/build_release.py --output "$release_dir/lawyeredos-source.zip"
python3 scripts/privacy_audit.py "$release_dir/lawyeredos-source.zip"
```

Run `claude plugin validate --strict .` for Claude integration changes. For
Codex changes, verify project-local `.agents/skills` discovery in a disposable
fictional workspace. Changes to host behavior require proportionate fictional
end-to-end evidence; test totals alone are not acceptance evidence.

The public CI workflow uses a macOS runner, read-only repository permissions,
no repository secrets, and the deterministic test/privacy commands above. It
does not perform live connector or real-practice tests.

## Licensing

By submitting a contribution, you agree that it may be distributed under the
project's `GPL-3.0-or-later` license. Material derived from the vendored
`legal-redline-tools` component remains subject to its MIT license and must
retain the existing attribution. Do not submit code you lack authority to
contribute.

There is no CLA, copyright assignment, or DCO requirement. Adding one would
require a separate maintainer decision.

## Conduct

Be specific, professional, and respectful. Harassment, doxxing, and disclosure
of confidential or privileged information are not acceptable. A formal code of
conduct may be added when the project has an established enforcement route.
