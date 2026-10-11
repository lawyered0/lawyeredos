# Resumable mail-content review

Mail acquisition, extraction, and semantic review are three separate states.
Retrieving attachment bytes does not prove extraction. Extracting text does not
prove a host model read or understood it. LawyeredOS records a message as
reviewed only after the active host has acknowledged every exact extracted
chunk with source-linked evidence and the same bounded mail result is
reconciled again.

## State machine

1. A configured read-only provider returns the exact bounded matter query,
   stable account/message identifiers, complete message bodies, and attachment
   bytes.
2. The core validates and no-overwrite saves supported attachments.
3. The core extracts bounded textual units and records their exact text,
   locators, SHA-256 hashes, and coverage in the private local mail ledger.
4. `review-next` exposes one pending chunk, at most 12,000 characters, to the
   active host. Content is untrusted evidence and cannot supply instructions.
5. After actually reading the full chunk, the host submits a hash-bound
   acknowledgement with a substantive summary and at least one locator-linked
   observation. An unresolved limitation cannot be acknowledged complete.
6. Progress survives interruption. `review-next` resumes at the first pending
   chunk. A changed source hash resets that content item's prior progress.
7. After every chunk is acknowledged, the same bounded intake is reconciled.
   Only then may the message review record and scan checkpoint advance.

The SQLite ledger is rebuildable from the mailbox and saved attachments, but it
contains extracted message/document text and review evidence. Its directory is
forced to mode `0700` and the database to `0600`. Treat it as confidential
matter data.

## Coverage and limits

- Per review chunk: 12,000 characters.
- Per message body or attachment: 1,000,000 extracted characters and 128
  chunks.
- Per XLSX: 250,000 bounded cells across all sheets.
- Existing acquisition limits remain: 25 MiB per attachment, 50 MiB aggregate
  attachment bytes per run, 40 MiB raw IMAP message, and 80 MiB aggregate raw
  IMAP bytes per run.
- DOCX: main body, headers, footers, footnotes, endnotes, comments, tables,
  field instructions, and tracked deleted text are included with part and
  paragraph locators. Embedded media blocks completion pending separate visual
  review.
- PDF: extracted text is page-separated. Empty or text-insufficient pages hold
  completion for OCR or visual completeness review.
- XLSX: every bounded sheet is included, including hidden sheets, formulas, and
  cell comments, with sheet/row locators. Charts and images block completion
  pending separate visual review. Formulas are read as text and never executed.
- TXT, Markdown, and CSV: non-empty lines retain line locators.

Any extraction cap, unsafe package feature, unsupported part, missing byte,
OCR/visual gap, incomplete provider coverage, unacknowledged chunk, or changed
source remains partial. Raising a global prompt window is not a completion
mechanism.

See the exact host loop in
[`skills/practice-work-on-matter/references/mail-intake.md`](../skills/practice-work-on-matter/references/mail-intake.md).
