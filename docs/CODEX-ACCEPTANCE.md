# Codex candidate acceptance record

This is the pre-publication acceptance record for the code packaged as Codex
0.2.0 beta.1. References below to a private candidate or no public publication
describe the gate at the time the evidence was collected. They do not change
the released Claude package or either published download.

## Accepted host and artifact

Acceptance was performed on macOS with Python 3.12.7 and Codex CLI 0.147.0.
The candidate archive was extracted, installed into a new disposable workspace,
and tested only with fictional matter data. No global Codex configuration,
global skill directory, real matter, inbox, credential, or OAuth state was
changed.

The runtime-equivalent extracted RC3 archive passed:

- 65 LawyeredOS unit and distribution tests;
- 97 vendored redline tests;
- the repository privacy audit; and
- an exact repeat install with `idempotent: true` and no changed paths.

Later candidate revisions changed only this Codex acceptance documentation.
Their release archives were compared member-by-member with the fully tested
archive, then checked with the targeted setup/distribution suite, ZIP integrity
test, and privacy audit. No runtime file changed.

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

## Desktop result and evidence boundary

At 17:39 UTC on October 9, 2026, the user reported the result of a new task
created in the Codex desktop project rooted at the disposable installed
workspace. The task used this read-only prompt:

```text
Use $lawyeredos-work-on-matter to orient to fictional matter 2030-001. Read the
local tracker, matter brief, and source note. Report the saved next action,
next-action date, tracker revision, any unverified deadline, and whether email
was checked. Do not write or modify anything.
```

The reported response identified fictional matter `2030-001`, returned the
saved next action `Review the controlling agreement and prepare a factual
options note`, the date October 10, 2030, tracker revision 2, and the requested
October 20, 2030 response date as unverified because no governing legal basis
was identified. It also stated that email was not checked because the mail
adapter was unavailable and that no files were changed. These values match the
fixture and the prior fresh-session CLI persistence result.

This is accepted as user-reported Desktop functional orientation and
persistence evidence. It is not an independent screen observation, a forensic
before/after no-write verification, or proof that the skill name appeared in
the task's session-start catalog. A separate delegated task rooted at the same
workspace did not receive repository-local skill descriptions in its injected
catalog; that host-specific delegated-catalog result is not substituted for,
or treated as a contradiction of, the user-created Desktop task.

## Unaccepted capabilities

- A later candidate exercised one bounded, user-created Gmail self-test through
  the connector exposed in a delegated development session. After the review
  protocol was corrected, the active model reviewed and acknowledged all three
  hash-bound DOCX chunks plus the message body; final reconciliation and repeat
  deduplication passed. Ordinary-host live mail and the portable IMAP provider
  remain unaccepted.
- Codex session tools are available only when an active, user-authorized tool
  is present; setup alone does not prove availability.
- OCR creation was unavailable because OCRmyPDF was not installed.
- Windows, Linux, other Python versions, cloud execution, and other Codex
  versions were not tested.
- No public release, site publication, or merge was performed.
