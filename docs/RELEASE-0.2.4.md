# 0.2.4 beta.1 local candidate

This is an unpublished candidate for review. Earlier releases remain immutable.
The shared tracker read connection now sets connection-local SQLite temporary
storage to memory, retaining `mode=ro`; URI escaping also supports punctuation
in database names. It does not change the database schema or persistent PRAGMA
settings. This adaptation was reimplemented against the public connection helper.

Stale-write rejection and previewed interrupted-save recovery already exist in
the public implementation and are retained. Fictional host-route tests exercise
the existing bounded review and deduplication protocol; they do not test a live
Gmail connection or prove model/desktop behavior or private-practice parity.

Selected reviewed public PR #18 metadata helpers preserve namespace bindings,
remove declared custom properties even under renamed parts, refuse review
metadata requiring a separate decision, and avoid publishing partial scrub
outputs. Its reviewed neutral template and selected fictional tests are included.
Broader document/PDF/redline changes are not imported. Public PR #15 contact
pattern coverage informed the extended gate; its broader installer work is not
merged. PRs #16, #17 and #19 remain separate and unintegrated.

The release builder now enforces an exact file manifest and recursively scans
staged bytes, completed ZIP bytes and metadata. Synthetic negative tests cover
the gate. See [the gate procedure](PUBLIC-RELEASE-GATE.md). The candidate also
uses generic publisher identity setup instructions without embedding an account
identifier. This prospective change makes no decision about material already
public, which requires a separate owner review.

Version and checksum metadata are derived from one candidate ZIP by
`scripts/candidate_metadata.py`. Both host filenames contain those identical
bytes. Consult the adjacent `release-manifest.json` and `SHA256SUMS`; the archive
does not embed its own checksum. Test results and publication approval belong
in a separate review report, rather than inherited historical acceptance claims.

No new legal rule, live connector, model workflow or operating-system acceptance
is claimed. Clean local installer and reference checks do not establish a fresh
interactive host trial. Publication, tags, hosting changes and any response to
historical public identity metadata require separate approval.
