# Instruction candidate release plan

This candidate is a documentation/instruction addition to the published
`v0.2.2-beta.1` baseline. It is presented as a draft pull request for exact-source
review. It changes no Python runtime, native installer/config mappings, database
schema, published archive/checksum or website. No version is assigned here.

## Candidate review performed in this scope

Inspect the full Markdown change set, reference routes, skill frontmatter and
catalog, and the before/after Git file list. Independent editorial reviewers
check coverage, authority, unavailable dependencies and Claude/Codex wording;
independent private-identity/text review checks publishable prose. The maintainer
separately inspects new author/committer metadata before push. Static
interface/catalog review checks named operations against
declared public interfaces and the six existing host mappings. Diff whitespace
checks do not substitute for runtime validation.

The repository's ordinary test/build/host-acceptance procedure is deliberately
not executed under this prose-only task. No runtime, regression/security test,
installer, host trial or live connector result is claimed. The original published
release remains available unchanged. A source PR is reviewable independently of
new package acceptance.

## Proposed next release steps

1. Review the exact draft PR and the fifteen-area
   [disposition matrix](WORKFLOW-COMPLETENESS.md). Resolve editorial findings;
   do not infer unsupported operations from the new prose.
2. Choose whether the next artifact is an explicitly manual instruction
   supplement or a new host package. Native discovery of added modules needs
   separately scoped installer/config/projectization work; it is not implemented
   by this candidate. Keep broader mail, legal computation and other integrations
   unavailable unless their own support is established.
3. For a package, review its exact version, immutable files/checksum and an
   authorized validation scope before building or installing it. Any ordinary
   executable acceptance that cannot be performed within allowed scope remains
   a disclosed release limitation, not a pass. Broader executable validation
   requires its own allowed scope rather than being inferred from prose review.
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
