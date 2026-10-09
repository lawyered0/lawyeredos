# Provenance

## Owner-reported original material

The skills, shared Python toolkit, configuration example, neutral template
generator, fictional fixtures, tests, and documentation in this project were
created for a private rewrite. They are behaviorally informed by a read-only
local workflow inventory, including tracker safety, bounded mail search, OCR
reports, guarded memory/output writes, style lint, and independent review
orchestration. The implementation is a clean neutral rewrite and does not copy
client data, private credentials, account identifiers, branded templates,
transcript text, or repository history.

These original LawyeredOS materials are licensed as `GPL-3.0-or-later`. The
owner reports that all of them were created by the owner with AI assistance and
that no other contributors supplied original material. The public notice uses
the owner's pseudonym: `Copyright (C) 2026 Lawyered`. This is a provenance and
licensing statement, not a legal conclusion about the copyrightability of any
particular AI-assisted contribution. No personal, firm, employer, or client
identity is inferred from the development environment, local account, or
package history.

## Neutral template

`assets/neutral-letterhead.docx` was generated from a new `python-docx`
document by `scripts/build_neutral_template.py`, then scrubbed by
`scripts/scrub_docx_metadata.py`. It contains only generic placeholder text,
uses named system fonts without embedding them, and contains no document media,
logos, macros, OLE objects, ActiveX controls, custom XML, signatures, or
identifying author/company/template metadata. Its package thumbnail is blank.

A fresh run of the bundled generator reproduced the template's content and
OOXML structure. One XML part differed only in namespace-prefix serialization,
so this is semantic-generation evidence rather than a claim of byte-for-byte
reproducibility or independent legal clearance.

## Third-party material

`vendor/legal-redline-tools/` is an MIT-licensed derivative of upstream
`legal-redline-tools` tag `v0.2.0`, commit
`eef61a0cb6afe2867fde70335c179d4a6ad298c8`. It was previously present in the
private local workflow. Direct comparison with that tag confirmed that the
upstream MIT `LICENSE` is byte-identical, while several source and documentation
files were modified and a test suite was added locally. It must not be described
as a verbatim upstream copy. See the vendored `LICENSE`,
`VENDOR-MODIFICATIONS.md`, and `THIRD_PARTY_NOTICES.md`.

## Not included

- Original branded letterhead and signature assets.
- Original trust-account templates.
- Original client or matter files, trackers, briefs, emails, logs, transcripts,
  prompts, caches, backups, evaluations, or project names.
- Original account IDs, connector UUIDs, calendar IDs, Keychain service names,
  credentials, API keys, or tokens.
- Original full-panel cross-provider review code.
