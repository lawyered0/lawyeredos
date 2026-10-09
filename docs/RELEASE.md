# Release procedure

This procedure prepares a candidate. It does not authorize publication.

## Identity gate

Use repository-local Git configuration only, before the first commit:

```bash
git config user.name "Lawyered"
git config user.email "4802498+lawyered0@users.noreply.github.com"
git config --local --get user.name
git config --local --get user.email
```

The ID-based noreply address is derived from the verified `lawyered0` account
metadata. Confirm it in GitHub email settings before relying on commit
attribution. Do not change global Git configuration. Before pushing, inspect the
complete local history for author and committer metadata; a later config change
does not rewrite an earlier identity leak.

## Build from an allowlist

Never initialize or publish the development directory. It can contain `.venv`,
QA output, caches, symlinks, and task history that are deliberately excluded.

Build an absent archive path:

```bash
.venv/bin/python scripts/build_release.py \
  --output /private/tmp/lawyeredos-0.2.0.zip
```

The builder includes only the declared root files and source directories,
rejects symlinks, strips filesystem extended attributes by writing fresh ZIP
entries, and uses fixed archive timestamps.

## Inspect the exact candidate

```bash
unzip -t /private/tmp/lawyeredos-0.2.0.zip
.venv/bin/python scripts/privacy_audit.py \
  /private/tmp/lawyeredos-0.2.0.zip
shasum -a 256 /private/tmp/lawyeredos-0.2.0.zip
```

Also inspect image pixels and metadata, Office Open XML relationships and
properties, filenames, URLs, dependency notices, issue templates, and every Git
author/committer identity. Keyword scanning alone cannot prove anonymity.

## Acceptance gate

Extract the exact candidate, create a fresh virtual environment, install its
lock, run all tests, run strict plugin validation, and use its wizard-generated
Desktop launcher, which opens the project folder directly in the app. Confirm
the `lawyeredos-*` project skills and agent, link a fictional
matter, complete the website prompt, create and visually inspect one fictional
DOCX, quit, relaunch, and confirm the same matter remains available. Exercise a
failure and conservative rollback. Verify discovery through the installed
project `.claude/` sources, not through the incompatible `--plugin-dir` flag.

## Publication gate

Publication still requires explicit approval of:

- version and immutable checksum;
- `lawyered0/lawyeredos` destination and public visibility;
- name/trademark risk acceptance;
- GitHub Issues support wording and enabled GitHub Private vulnerability
  reporting; and
- final website source, download, and evidence links.
