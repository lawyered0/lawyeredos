# 0.2.3 beta.1 release record

[Published prerelease](https://github.com/lawyered0/lawyeredos/releases/tag/v0.2.3-beta.1),
2026-10-11. Tag target: `c2dca1a7028bd77f0e69de9a9f9fec3a42e4e218`, the protected
merge of PR #13. Its source tree equals reviewed head
`adfb72b8cb24019c2b0d738fbe0c5e15e079e9e2`.

| Host | Immutable download |
|---|---|
| Claude | [lawyeredos-0.2.3-macos-beta.1.zip](https://github.com/lawyered0/lawyeredos/releases/download/v0.2.3-beta.1/lawyeredos-0.2.3-macos-beta.1.zip) |
| Codex | [lawyeredos-0.2.3-macos-codex-beta.1.zip](https://github.com/lawyered0/lawyeredos/releases/download/v0.2.3-beta.1/lawyeredos-0.2.3-macos-codex-beta.1.zip) |

Both filenames contain the same reviewed shared package: 172 members and
1,554,842 bytes. SHA-256 for either:

```text
c5b28fb086f18dc09c2ec89062a578e06469036538d71953cb8134f59312ce35
```

## Scope and evidence

Nine manual workflow modules and five supporting references live under
`docs/workflow-modules/`. The existing matter skill routes a requested task
through `docs/WORKFLOW-CATALOG.md`; six native installer options remain.
Shared contracts cover sources, advice, dates, records, intake and review.
No Python behavior, tracker schema, adapter, test, CI workflow or jurisdiction
rule changed; four literal package-version values were aligned to 0.2.3.

- [Reviewed-head required CI](https://github.com/lawyered0/lawyeredos/actions/runs/38184612005) passed.
- [Exact protected-merge CI](https://github.com/lawyered0/lawyeredos/actions/runs/38185021503) passed.
- Local unchanged project tests: 254 passed; vendored tests: 103 passed.
- Fictional host-route acceptance, setup smoke and strict plugin validation passed.
- Independently built archives passed privacy scanning and ZIP integrity; every
  member matched the reviewed source. Binary assets, script entrypoints, tests,
  vendor code, configuration and optional jurisdiction profiles matched 0.2.2.
  Core Python differences were the declared static version values.
- Fresh installs from the exact archive passed both configuration validators.
  Each installed core contained six native skills, nine manual modules and nine
  contracts. Generated matter entrypoints and module references reached the
  installed documentation paths. Mail/calendar were disabled; OCR was unavailable.
- GitHub release metadata reports the reviewed sizes and SHA-256 digests.
  Anonymous transfer verification did not complete in the publication environment;
  no anonymous-download success is claimed.

These checks establish package/reference consistency, not substantive model
behavior, legal correctness, live connectors or broader host compatibility.
Practice-wide acquisition still needs bounded supplied material or an actually
authorized active tool. Existing optional profiles and historical assets remain
unchanged; there are no new jurisdiction-specific calculations.

The source README and release pointers may be updated after this immutable
snapshot. Rebuilding newer source does not replace either published archive.
