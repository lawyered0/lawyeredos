# Changelog

All notable changes will be recorded here. The project has not yet made a public
release.

## 0.2.0 beta.2

- Made email a required explicit onboarding decision instead of silently
  defaulting it off.
- Added an honest configured-but-unverified route for Claude's Gmail connector,
  retained safe skip behavior, and kept the narrower token-based REST adapter
  clearly experimental.
- Documented connector permissions, direct user authentication, bounded reads,
  runtime connection verification, and the separate approval boundary for all
  send or mailbox-write actions.

## 0.2.0 — private macOS beta candidate

- Renamed the package and plugin namespace to LawyeredOS / `lawyeredos`.
- Added a guided project-local setup wizard with preview, versioned plugin
  copies, runtime binding, upgrade reuse, and conservative rollback.
- Added a manually invoked `/lawyeredos-setup` bootstrap skill that delegates
  writes to the deterministic wizard after an exact-plan approval.
- Changed the Desktop launcher to open the workspace folder directly in Claude
  Desktop, avoiding a separate CLI-login requirement.
- Added fail-closed preflight checks for symlinked managed paths and malformed
  project environment settings.
- Made the first setup preview standard-library-only, made dependency gates
  follow selected modules, and documented the required Local Code environment.
- Qualified plugin skill-to-skill references with the `lawyeredos:` namespace
  while preserving collision-safe `lawyeredos-*` project references.
- Added guarded matter tracking, exact-folder orientation, no-overwrite output,
  letter and tracked-redline workflows, optional integrations, local memory and
  document helpers, and Claude-only review instructions.
- Added neutral fixtures, template provenance, GPL licensing, third-party MIT
  attribution, privacy scanning, and fictional acceptance coverage.
- Documented that local storage does not mean offline Claude processing.
- Runtime-accepted one bounded current-name source-fidelity reviewer invocation
  on the tested Mac; the complete four-lens workflow remains experimental.

No public compatibility promise applies to earlier private builds.
