# 0.2.4 beta.1 release record

[Published prerelease](https://github.com/lawyered0/lawyeredos/releases/tag/v0.2.4-beta.1),
2026-11-20. Tag target: `3fe97a099d02042a29de74dc662065ea1d7ef111`, the protected merge of
[PR #20](https://github.com/lawyered0/lawyeredos/pull/20).

| Host | Immutable download |
|---|---|
| Claude Desktop Code Local | [lawyeredos-0.2.4-macos-beta.1.zip](https://github.com/lawyered0/lawyeredos/releases/download/v0.2.4-beta.1/lawyeredos-0.2.4-macos-beta.1.zip) |
| Codex local project | [lawyeredos-0.2.4-macos-codex-beta.1.zip](https://github.com/lawyered0/lawyeredos/releases/download/v0.2.4-beta.1/lawyeredos-0.2.4-macos-codex-beta.1.zip) |

Both files contain the same **181-member, 1,575,131-byte** shared package.
SHA-256 for either:

```text
3c76e74fa3903bdb4bbee3c1dbcb8efa5f5d1e5d1d08b6b7ec0422e886939795
```

[Generated manifest](https://github.com/lawyered0/lawyeredos/releases/download/v0.2.4-beta.1/release-manifest.json)
and [SHA256SUMS](https://github.com/lawyered0/lawyeredos/releases/download/v0.2.4-beta.1/SHA256SUMS)
are separate assets. Anonymous HTTP 200 transfer of all four exact assets was
verified against local bytes after publication. Prior release asset metadata
and all eleven historical mirror ZIP hashes were unchanged.

## Changes and verification

Read-only tracker connections keep SQLite temporary sorting in memory, retain
`mode=ro`, and use escaped database URIs. The release builder requires an exact
file manifest, inspects staged content and recursively reads completed ZIPs,
metadata and nested containers, then compares every member with source.
Selected reviewed PR #18 metadata helpers preserve namespace bindings, discover
renamed/orphaned declared custom-property parts, refuse unsafe review metadata,
and avoid partial outputs. Public PR #15 contact-pattern coverage informed the
gate. Broader changes in PRs #15–19 are not included.

- [Required reviewed-head CI](https://github.com/lawyered0/lawyeredos/actions/runs/44762733333) passed.
- [Exact protected-merge CI](https://github.com/lawyered0/lawyeredos/actions/runs/44763005123) passed.
- The exact extracted publication ZIP passed 278 project tests and 103 vendored
  tests, fictional host-route acceptance, setup smoke, strict plugin validation,
  recursive privacy/archive checks and complete member/source comparison.
- Fresh installs for each host layout validated all 181 installed member hashes,
  six native skills and nine manual modules. Fictional guarded tracker creation,
  fresh-subprocess readback and orientation passed without changing database
  bytes during reads. Mail and calendar were disabled; no live account was used.
- The earlier reviewed candidate was rebuilt solely to use the supported macOS
  15 CI runner and remove a trailing blank line in a synthetic test. All other
  179 members, including runtime and template content, were unchanged.

The archive retains its candidate-time documentation. This record, the release
page and generated external manifest record publication. Later source README
or documentation edits do not replace these immutable archives.

These checks do not establish legal correctness, live Gmail/Calendar capability,
private-practice parity, fresh interactive desktop-host acceptance or broader
OS compatibility. Existing stale-write rejection and interrupted-save recovery
remain; additional open-PR fixes are not silently accepted by these results.
