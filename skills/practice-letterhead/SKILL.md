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
  --template "<configured template>" --body-file "<body.txt>" \
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
than flattening, accepting, or overwriting them implicitly.

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
and does not authorize sending, signing, filing, or service.
