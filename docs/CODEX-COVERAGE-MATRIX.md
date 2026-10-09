# Codex candidate coverage matrix

This matrix is the private pre-release gate. `Pass` identifies actual evidence;
`Pending` is not accepted; and `Excluded` records an intentional boundary.

| Area | Layer | Status | Evidence |
| --- | --- | --- | --- |
| New disposable setup | Deterministic installer and local host | Pass | Exact JSON preview/apply, required dependency checks, project-local config and skills only. |
| Project skill discovery | Fresh Codex CLI process | Pass | `$lawyeredos-work-on-matter` and `$lawyeredos-matter-tracker` were discovered from `.agents/skills`. |
| Desktop project discovery | Fresh Codex desktop task | Pending | Requires opening the installed disposable workspace itself as the project root and running the prompt in the desktop section of `CODEX-ACCEPTANCE.md`. CLI evidence is not substituted. |
| Fictional intake and bounded files | Local CLI/core | Pass | Created one fictional tracker record linked to a bounded matter folder; orientation returned only the brief and recent local files and disclosed unavailable email. |
| Guarded tracker write | Codex CLI host | Pass | Fresh auto-reviewed workspace-write session performed read, dry-run, exact-diff inspection, token-bound commit, and verification. |
| New-session persistence | Fresh read-only Codex CLI process | Pass | Separate session recovered the saved action, date, status, and revision. |
| Full matter lifecycle | Local CLI/core | Pass | Fictional create, next-action update, close, reopen, history, and database verification advanced cleanly through revision 4. |
| Draft generation | Local document workflow | Pass | Generated a neutral fictional DOCX from the installed template and created a bounded Markdown options note for review. |
| Independent review | Four actual Codex agents plus deterministic collector | Pass with reported gaps | Four lenses completed. One optional operational finding and explicit source/authority gaps were reported. Deliverable and source hashes remained unchanged. Collector `ok: false` is expected whenever coverage gaps remain. |
| Reviewer write prevention | Repository skill | Excluded as technically unenforceable | Instructions are behavioral. Enforced controls are bounded paths, result schema validation, source-path validation, and before/after hashes. |
| Repeat install | Installer | Pass | Identical reapply returned `idempotent: true` with no changed paths. |
| Managed upgrade | Installer and local host | Pass | New versioned core installed; only installer-owned links and discovery metadata changed; prior core and matter data remained. Identical rerun was idempotent. |
| Unmanaged collision and symlink attacks | Deterministic tests | Pass | Existing private skill collisions, symlinked managed directories/config, unmanaged tracker data, and config replacement fail closed. |
| Interrupted installation | Deterministic fault injection | Pass | Simulated failure after partial tracker creation removed only paths created by that attempt and preserved an unrelated private file. |
| Claude behavior | Shared regression suite | Pass | Existing Claude setup, settings merge, rollback, connector selection, document, tracker, and distribution tests remain green. |
| Redline engine | Vendored regression suite | Pass | 97 vendored tests pass. |
| Exact archive | Extracted archive tests | Pass | Archive contents, 65 project tests, 97 vendored tests, privacy audit, GPL/MIT notices, and deterministic build allowlist pass. |
| Global private state | Before/after hashes and installer tests | Pass | No user-global Codex configuration or skill directory is written; unrelated project-local private skills/config are preserved. |
| Live Gmail or other live connectors | External integration | Excluded | User withdrew live Gmail testing. Setup never treats configuration as proof of connection. |
| OCR creation | Optional dependency | Excluded | OCRmyPDF was not installed on the accepted host. |
| Other operating systems, Python versions, Codex versions, or cloud hosts | Platform coverage | Excluded | No compatibility claim without an actual host run. |
| Public release, site download, or merge | Publication | Excluded | Candidate remains private, draft, and unmerged. |

## Release gate

The candidate is not ready for a public Codex release until the one `Pending`
desktop row passes in a fresh desktop task. Any review coverage gap remains a
matter-specific caution rather than a software failure, provided it is shown
to the user and the integrity checks pass.
