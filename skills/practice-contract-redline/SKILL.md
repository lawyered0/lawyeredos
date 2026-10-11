---
name: practice-contract-redline
description: Apply established edits as genuine Word tracked changes, verify marked and clean DOCX outputs, and save internal artifacts. Use only when substantive positions are already decided.
---

# Contract Redline

This skill applies established changes; it does not decide negotiation or legal
positions. Require an editable `.docx`. Do not reconstruct a contract from PDF.

The pinned MIT engine is under
`${LAWYEREDOS_ROOT}/vendor/legal-redline-tools`. Preserve its `LICENSE` and
attribution. Run it on `PYTHONPATH`; do not install another copy implicitly.

```bash
PKG="${LAWYEREDOS_ROOT}/vendor/legal-redline-tools"
PYTHONPATH="$PKG" "${LAWYEREDOS_PYTHON:-python3}" -m legal_redline.cli apply \
  source.docx redlined.docx --author "<configured author>" \
  --from-json redlines.json
```

Use exact, unique text spans. The change-set JSON remains scratch material and
must not contain internal rationale in a counterparty artifact. A failed or
partial apply is not repaired by hand-editing OOXML. A source containing any
pre-existing revision or comment markup is a distinct review state: stop and
have the user choose an authoritative clean source or separately resolve the
existing review. The engine refuses existing, duplicate, symlinked, or
source-colliding output paths and stages all requested outputs before publishing.

Verification requires:

1. Exit zero and `Applied: N/N`.
2. Structural `w:ins`/`w:del` counts and configured revision author.
3. Accepted text comparison against the intended change set.
4. Full-page render of marked and clean DOCX files.
5. Placeholder, comment, metadata, party, signature, and concession checks.
6. Claude-only adversarial review when the outbound risk warrants it.

Generate a clean copy and verify it separately:

```bash
"${LAWYEREDOS_PYTHON:-python3}" "${LAWYEREDOS_ROOT}/scripts/accept_tracked_changes.py" \
  redlined.docx --output clean.docx
"${LAWYEREDOS_PYTHON:-python3}" "${LAWYEREDOS_ROOT}/scripts/render_docx.py" clean.docx \
  --output-dir "<empty clean render directory>"
```

The clean-copy helper accepts insertion/deletion/move wrappers, removes the
track-revisions setting, validates the entire Word XML package, and fails
without output if comments, unsupported property revisions, or any residual
revision/tracking marker remain.

Persist only requested, verified, versioned outputs with the
guarded writer. Never send or negotiate.

Read [`references/change-set.md`](references/change-set.md) before building a
change list.
