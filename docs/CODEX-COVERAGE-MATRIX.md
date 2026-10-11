# Codex beta.2 coverage matrix

> **0.2.1 beta.1 addendum (2026-10-11):** one exact self-addressed,
> user-created Gmail test thread completed through portable read-only IMAP in
> an ordinary Codex Desktop / GPT-5 session. The body and three hash-bound DOCX
> chunks were acknowledged, the checkpoint completed, the repeat deduplicated,
> and guarded bundle deletion succeeded. This accepts only that account,
> thread, launcher, and host—not broader Gmail, OAuth/REST, sending, mutation,
> or session-tool behavior. The matrix below preserves the earlier beta.2 gate.

This matrix records the private gate completed before Codex 0.2.0 beta.1 was
published. `Pass` identifies actual evidence; `Pending` is not accepted; and
`Excluded` records an intentional boundary. Publication rows describe that
historical checkpoint, not the current visibility of the source repository.
Current publication state is recorded by the immutable Git tag, GitHub
release, asset hashes, and protected merge; none of those expands the
acceptance evidence below.

| Area | Layer | Status | Evidence |
| --- | --- | --- | --- |
| New disposable setup | Deterministic installer and local host | Pass | Exact JSON preview/apply, required dependency checks, project-local config and skills only. |
| Project skill discovery | Fresh Codex CLI process | Pass | `$lawyeredos-work-on-matter` and `$lawyeredos-matter-tracker` were discovered from `.agents/skills`. |
| Desktop functional orientation and persistence | User-created fresh Codex desktop task | Pass with evidence boundary | User reported the exact fictional action, date, revision 2, unverified October 20 request, unavailable email, and no file changes. This is functional evidence, not independent GUI observation, forensic no-write verification, or proof of session-start automatic catalog registration. A delegated task's injected catalog omitted repo-local skills and is recorded as a host-specific caveat, not a substitute GUI test. |
| Fictional intake and bounded files | Local CLI/core | Pass | Created one fictional tracker record linked to a bounded matter folder; orientation returned only the brief and recent local files and disclosed unavailable email. |
| Guarded tracker write | Codex CLI host | Pass | Fresh auto-reviewed workspace-write session performed read, dry-run, exact-diff inspection, token-bound commit, and verification. |
| New-session persistence | Fresh read-only Codex CLI process | Pass | Separate session recovered the saved action, date, status, and revision. |
| Full matter lifecycle | Local CLI/core | Pass | Fictional create, next-action update, close, reopen, history, and database verification advanced cleanly through revision 4. |
| Draft generation | Local document workflow and render QA | Pass | Generated a neutral fictional DOCX from the installed template, rendered and inspected its one-page output with no clipping, overlap, broken glyphs, footer collision, or unexpected page break, and created a bounded Markdown options note for review. |
| Independent review | Four actual Codex agents plus deterministic collector | Pass with reported gaps | Four lenses completed. One optional operational finding and explicit source/authority gaps were reported. Deliverable and source hashes remained unchanged. Collector `ok: false` is expected whenever coverage gaps remain. |
| Reviewer write prevention | Repository skill | Excluded as technically unenforceable | Instructions are behavioral. Enforced controls are bounded paths, result schema validation, source-path validation, and before/after hashes. |
| Repeat install | Installer | Pass | Identical reapply returned `idempotent: true` with no changed paths. |
| Managed upgrade | Installer and local host | Pass | New versioned core installed; only installer-owned links and discovery metadata changed; prior core and matter data remained. Identical rerun was idempotent. |
| Unmanaged collision and symlink attacks | Deterministic tests | Pass | Existing private skill collisions, symlinked managed directories/config, unmanaged tracker data, and config replacement fail closed. |
| Interrupted installation | Deterministic fault injection | Pass | Simulated failure after partial tracker creation removed only paths created by that attempt and preserved an unrelated private file. |
| Claude behavior | Shared regression suite | Pass | Existing Claude setup, settings merge, rollback, connector selection, document, tracker, and distribution tests remain green. |
| Redline engine | Vendored regression suite | Pass | 97 vendored tests pass. |
| Exact archive | Extracted archive and docs-only successor checks | Pass | The runtime-equivalent RC3 archive passed 65 project tests, 97 vendored tests, privacy audit, GPL/MIT notices, and the deterministic allowlist. Later docs-only candidates retained the same member set, changed only the recorded acceptance documents, and passed targeted setup/distribution, ZIP integrity, and privacy checks. |
| Global private state | Before/after hashes and installer tests | Pass | No user-global Codex configuration or skill directory is written; unrelated project-local private skills/config are preserved. |
| Live Gmail or other live connectors | External integration | Delegated path pass; ordinary host pending | One bounded user-created Gmail self-test used the already-authorized connector in the delegated development session. Search, message read, attachment retrieval, actual model acknowledgement of all three DOCX chunks plus the body, final reconciliation, and repeat deduplication passed. This is not ordinary-host or portable-IMAP acceptance. Setup never treats configuration as proof of connection. |
| OCR creation | Optional dependency | Excluded | OCRmyPDF was not installed on the accepted host. |
| Other operating systems, Python versions, Codex versions, or cloud hosts | Platform coverage | Excluded | No compatibility claim without an actual host run. |
| Public release, site download, or merge | Publication | Excluded | The repository and draft pull request are public, but the candidate is unreleased and unmerged; no site download points to it. |

## Release gate

The historical candidate passed its recorded gates within the stated
macOS, Python, Codex CLI, fictional-data, and user-reported Desktop evidence
boundaries. A later release must preserve the exclusions above. Any review
coverage gap remains a
matter-specific caution rather than a software failure, provided it is shown
to the user and the integrity checks pass.
