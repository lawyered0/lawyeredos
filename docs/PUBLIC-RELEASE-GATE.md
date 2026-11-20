# Public release gate

`scripts/build_release.py` now refuses the build unless the staged input set
matches `release-policy.json` exactly and both that content and the completed
ZIP pass `scripts/public_release_check.py`. The completed ZIP is read back,
recursively decompressed and compared byte for byte with its source. ZIP
comments, extra fields, unsafe/duplicate paths, symlinks, encrypted or malformed
containers, invalid text, unknown binary data and inspection-limit exhaustion
fail closed. Nested containers are identified by bytes, regardless of suffix.
Office properties and archive/member metadata are inspected as content.

The file allowlist is reviewed, versioned input. New files require a deliberate
policy diff; the builder never updates it. The only opaque allowlist is two
exact PNG hashes, reviewed as fictional product illustrations, and the exact
blank JPEG thumbnail embedded in the neutral DOCX. A changed image
must be inspected visually and its metadata reviewed before a policy change.
Only `example.invalid` and `example.test` email domains are treated as fictional.
There are no credential, personal-address or account-identifier exceptions.
Third-party copyright names in required notices remain attribution, not an
anonymity claim.

From the reviewed source tree:

```bash
python scripts/public_release_check.py
python -m unittest discover -s tests
python scripts/build_release.py --output /tmp/lawyeredos-candidate.zip
python scripts/public_release_check.py --archive /tmp/lawyeredos-candidate.zip
python scripts/candidate_metadata.py --archive /tmp/lawyeredos-candidate.zip --output /tmp/reviewed-candidate
```

The last command creates absent host aliases, `release-manifest.json` and
`SHA256SUMS` from one inspected ZIP. It verifies all four package-version fields
and records each member hash. README links to that external checksum manifest,
avoiding a self-referential archive hash inside its own README. Website checksum
copy must be generated from this same manifest and checked before publication.
Never rebuild one host alias separately or replace an earlier versioned ZIP.

Synthetic tests inject nested secrets, metadata leaks, account identifiers,
paths, stale binary approvals, malformed archives, traversal, duplicates,
symlinks, extra staged/bundled files and inspection-limit failures. They also
round-trip the real staged tree. The existing basic privacy audit remains a
separate compatibility check; it is not the release gate.

This gate checks a bounded set of recognizable leaks. It cannot identify every
real person or client, text hidden in image pixels, or obfuscated secrets.
Review the complete public diff, images, metadata and Git identities separately.
Use task-specific `--forbid` values locally when appropriate; findings contain
categories rather than matched values. Never add private scanning terms to a
public policy or test. No success here establishes legal correctness, live mail
support, host model behavior, or equivalence with a private practice setup.
