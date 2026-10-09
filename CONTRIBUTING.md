# Contributing

Contributions should improve a specific lawyer workflow without weakening
matter isolation, preview/approval boundaries, evidence handling, or honest
capability disclosure.

## Before opening a change

- Use fictional data only.
- Open a focused issue after publication for a behavioral change larger than a
  small bug fix.
- Do not add live credentials, account identifiers, private paths, branded
  templates, client material, telemetry, or a second model-provider route.
- Keep optional integrations disabled by default and fail closed.
- Avoid claiming support for a host or operating system without a reproducible
  acceptance run.

## Review expectations

A change should include the smallest relevant tests and update the lawyer-facing
documentation when behavior changes. For workflow changes, explain:

1. the exact user request;
2. evidence read;
3. writes or external effects;
4. approval and stale-state behavior;
5. failure and recovery; and
6. what remains unverified.

Run the core unit suite, affected vendored tests, wizard smoke test, strict
plugin validation, and a fictional end-to-end scenario proportionate to the
change. Test totals alone are not acceptance evidence.

## Licensing

By submitting a contribution, you agree that it may be distributed under the
project's `GPL-3.0-or-later` license. Material derived from the vendored
`legal-redline-tools` component remains subject to its MIT license and must keep
the existing attribution. Do not submit code you lack authority to contribute.

There is no CLA, copyright assignment, or DCO requirement. Adding one would
require a separate maintainer decision.

## Conduct

Be specific, professional, and respectful. A formal code of conduct has not
been added while the project has no established contributor community or
enforcement route; harassment or disclosure of confidential data is still not
acceptable.
