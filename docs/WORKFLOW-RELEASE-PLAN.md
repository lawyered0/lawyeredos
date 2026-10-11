# Instruction candidate release plan

This plan was completed for published `v0.2.3-beta.1`. The
[release record](RELEASE-0.2.3.md) identifies the immutable artifact and completed
checks. Retain the plan below as its preparation scope; it does not authorize
replacement of published bytes or expansion of acceptance claims.

This `0.2.3 beta.1` candidate is a documentation/instruction addition to the
published `v0.2.2-beta.1` baseline. It is presented as a draft pull request for
exact-source review. Only static package-version values change in Python;
runtime behavior, native installer/config mappings, database schema, published
archive/checksum and website remain unchanged.

## Candidate review performed in this scope

Inspect the full Markdown change set, reference routes, skill frontmatter and
catalog, and the before/after Git file list. Independent editorial reviewers
check coverage, authority, unavailable dependencies and Claude/Codex wording;
independent private-identity/text review checks publishable prose. The maintainer
separately inspects new author/committer metadata before push. Static
interface/catalog review checks named operations against
declared public interfaces and the six existing host mappings. Diff whitespace
checks do not substitute for runtime validation.

The initial prose-review phase did not execute project checks. Ordinary release
validation now uses the existing unchanged CI/build/install acceptance commands,
without adding an exploratory investigation. A planned or running check is not
a pass. Exact-head outcomes, archive hash and installed-reference coverage must
be reported before release approval. Live connectors and new substantive model
behavior remain unverified unless separately established. The original published
release remains available unchanged.

## Proposed next release steps

1. Review the exact draft PR and the fifteen-area
   [disposition matrix](WORKFLOW-COMPLETENESS.md). Resolve editorial findings;
   do not infer unsupported operations from the new prose.
2. Prepare host package candidate `v0.2.3-beta.1` with versioned Claude and Codex
   archive names. Native discovery of added modules needs
   separately scoped installer/config/projectization work; it is not implemented
   by this candidate. Keep broader mail, legal computation and other integrations
   unavailable unless their own support is established.
3. Review its exact source head, immutable archive checksum, the required strict
   `test` status and ordinary validation results. Keep branch protection intact.
   Any acceptance that cannot be performed within allowed scope remains a
   disclosed limitation. A platform denial is reported without moving the denied
   action to another execution route. Broader investigations remain separate.
4. Preserve 0.2.2 beta.1 and all historical assets. Publish a new artifact only
   after maintainer review of that exact candidate; never replace released bytes.
5. Update website/source/download links together only for the reviewed artifact.
   Describe nine new modules as manual prescribed workflows, six existing native
   skills as native entries, and unchanged runtime acceptance as unchanged. Do
   not advertise automatic broad inbox workup, legal-date calculation, new
   integrations or accepted host behavior from editorial review alone.

Website and external publication work are deferred until exact-candidate
maintainer review. This document records proposed release steps; it creates no
scheduled task or external account change.
