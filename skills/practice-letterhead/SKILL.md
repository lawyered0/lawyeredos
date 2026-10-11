---
name: practice-letterhead
description: Create formal DOCX correspondence from the configured neutral or private template, render and inspect it, and save a versioned internal draft. Never sends, signs, files, or serves.
---

# Correspondence

Resolve the matter through `lawyeredos:practice-work-on-matter`. An unresolved matter may
receive conversation-only text but no persisted matter artifact.

## Create

Use the configured template and author identity. Write the body in a scratch
UTF-8 text file with no template markers. Then run:

```bash
"${LAWYEREDOS_PYTHON:-python3}" "${LAWYEREDOS_ROOT}/scripts/create_letter.py" \
  --template "<configured template>" \
  --template-manifest "<configured template_manifest>" --body-file "<body.txt>" \
  --output "<scratch.docx>" --organization "<configured branding label>" \
  --date "<date>" --recipient "<recipient>" \
  --address "<address>" --subject "<subject>" --signoff "<signoff>" \
  --author "<configured author>"
```

Do not invent facts, legal propositions, amounts, commitments, or dates. Do not
leave placeholders, drafting notes, comments, or template directions. A neutral
public template must not contain a real signature, logo, personal contact data,
or identifying metadata. The helper preserves the formatting of unaffected
runs when a placeholder spans multiple runs or appears in a header/footer table.
It refuses templates containing pre-existing tracked revisions or comments and
refuses every existing or symlinked output path; resolve those conditions rather
than flattening, accepting, or overwriting them implicitly. It scans the whole
generated Word package for `{{PLACEHOLDER}}` plus exact drafting markers such as
`[VERIFY]`, `[CITE]`, `[TBD]`, `[INSERT…]`, `[LAWYER TO CONFIRM]`, and standalone
`TK`; ordinary verified bracketed citations are not rejected.
Template snapshots are capped at 100 MiB compressed, 50 MiB per package entry,
and 200 MiB total uncompressed; body text is capped at 5 MiB. Oversized,
duplicate-member, unsafe-path, truncated, or non-DOCX packages fail without an
output and require separate inspection rather than bypassing the limit.
The installed neutral template is also bound to its persistent SHA-256 manifest;
a missing, malformed, path-mismatched, or hash-mismatched manifest fails before
document creation. This integrity check does not approve a private replacement
template; such a template requires a separately reviewed manifest and config.

Run the bundled linter on the final body before insertion and again after any
substantive revision:

```bash
PYTHONPATH="${LAWYEREDOS_ROOT}/src" "${LAWYEREDOS_PYTHON:-python3}" -m lawyeredos.voice_lint \
  "<body.txt>" --register letter
```

Correct every FAIL in original prose; a finding in a verbatim quotation may be
disclosed and retained, but is not a general bypass.

## Verify

Render the DOCX to PDF and page PNGs with the bundled wrapper (or a configured
equivalent):

```bash
"${LAWYEREDOS_PYTHON:-python3}" "${LAWYEREDOS_ROOT}/scripts/render_docx.py" "<scratch.docx>" \
  --output-dir "<empty render directory>"
```

Inspect
every page at 100% for clipping, overlap, font substitution, page breaks,
headers, footers, and signature area. Structurally inspect OOXML core/custom
properties and comments because rendering cannot prove metadata cleanliness.

Run `lawyeredos:practice-adversarial-panel` for consequential legal positions, settlement
positions, admissions, waivers, deadline commitments, or when the user asks.
Re-hash after review.

Persist only through the no-overwrite writer. Saving produces an internal draft
and does not authorize sending, signing, filing, or service. A collision or
changed target requires a fresh read and a new preview; never overwrite newer
work or rename around a protected-path or symlink refusal.
