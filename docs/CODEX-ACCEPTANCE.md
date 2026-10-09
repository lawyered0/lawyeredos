# Codex candidate acceptance record

This record applies to the private Codex candidate only. It is not a public
release claim and does not change the released Claude package or download.

## Accepted host and artifact

Acceptance was performed on macOS with Python 3.12.7 and Codex CLI 0.147.0.
The candidate archive was extracted, installed into a new disposable workspace,
and tested only with fictional matter data. No global Codex configuration,
global skill directory, real matter, inbox, credential, or OAuth state was
changed.

The extracted archive passed:

- 65 LawyeredOS unit and distribution tests;
- 97 vendored redline tests;
- the repository privacy audit; and
- an exact repeat install with `idempotent: true` and no changed paths.

The installer also passed a simulated mid-apply interruption with complete
rollback of only newly created paths, while preserving an unrelated private
file. A retained installation was upgraded to a new versioned core by changing
only installer-managed skill and current-core links; the old core remained
available, and the next identical run was idempotent.

## Codex CLI end-to-end result

A fresh Codex CLI session discovered the installed project-local skills under
`.agents/skills`. In its normal auto-reviewed workspace-write mode, the session:

1. read revision 1 of a fictional tracker record;
2. previewed an update to only `next_action` and `next_action_date`;
3. inspected the revision-bound dry-run diff;
4. committed with the returned confirmation token;
5. read the record back at revision 2; and
6. verified that no other user-controlled field changed.

A separate fresh read-only Codex session recovered the saved action, date,
open status, and revision 2. It correctly disclosed that email was not checked.

An earlier read-only acceptance attempt was expectedly unable to write SQLite
and returned `attempt to write a readonly database`. That attempt was not
treated as write acceptance. The successful run used Codex's supported
auto-reviewed workspace-write mode; no sandbox bypass was used.

## Review-agent result and limits

Four actual independent Codex agents performed the opposing-reader,
fact-and-source, privilege/admissions/authority, and pre-mortem/operational-risk
lenses on a fictional options note. They were not scripted result fixtures.
One invalid source path was rejected and corrected before collection. The
collector completed all four lenses, reported one optional operational finding
and explicit coverage gaps, and confirmed that the deliverable and supplied
source hashes were unchanged. The collection command returned `ok: false`
because source and authority gaps remained; that result was preserved rather
than relabelled as a complete substantive review.

The `read_only` review instruction is behavioral. A repository skill cannot
technically remove tools from a delegated agent. The enforceable controls are
bounded inputs, schema validation, source-path validation, and before/after
hash verification. If the host cannot provide independent agents, the skill
must report the review panel unavailable rather than emulate independence.

## Fictional document render

The generated fictional response DOCX was rendered to a one-page PDF and PNG
with the document verifier and inspected at full resolution. The page had no
clipping, overlap, broken glyphs, footer collision, or unexpected page break.
The rendered copy remained acceptance evidence only; it was not added to the
release archive.

## Desktop status

The CLI tests above do not establish a separate Codex desktop UI acceptance.
Desktop acceptance requires opening the disposable installed workspace itself
as the project root, starting a fresh task there, and invoking an installed
skill. The task must not be rooted at the extracted source package or a parent
directory because project-local skill discovery is rooted in the task's
workspace.

Minimal read-only desktop prompt:

```text
Use $lawyeredos-work-on-matter to orient to fictional matter 2030-001. Read the
local tracker, matter brief, and source note. Report the saved next action,
next-action date, tracker revision, any unverified deadline, and whether email
was checked. Do not write or modify anything.
```

Passing requires discovery of the named project skill, successful use of the
installed launcher and SQLite tracker, accurate fictional values, an explicit
email-coverage statement, and no writes.

## Unaccepted capabilities

- Live Gmail and other live connectors were not tested.
- Codex session tools are available only when an active, user-authorized tool
  is present; setup alone does not prove availability.
- OCR creation was unavailable because OCRmyPDF was not installed.
- Windows, Linux, other Python versions, cloud execution, and other Codex
  versions were not tested.
- No public release, site publication, or merge was performed.
