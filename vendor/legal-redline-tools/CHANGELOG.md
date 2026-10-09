# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Fixed (2026-10-07 skill-flow audit)
- A repeated span is no longer placed at its first match. Each `old`, `text`,
  `anchor` and `after_section` must occur exactly once in the body, counted over
  every paragraph including table cells, and including text inside an existing
  insertion, hyperlink or content control (deleted text is not counted);
  `apply_redlines` reports a repeat as `AMBIGUOUS` and the CLI refuses the whole
  set before writing anything. Headers, footers and notes are not counted.
  `section` only labels the schedule. A non-string span is an `ERROR`. New
  `span_occurrences` and `placement_problems` helpers (contracts-lit-4).
- `add_section` no longer anchors on the last paragraph containing
  `after_section`, and an empty or missing `after_section` is an error instead
  of matching every paragraph (contracts-lit-3).
- A span that straddles an existing tracked change, hyperlink, simple or
  complex field, content control, footnote, endnote or comment reference, image,
  text box, object or symbol raises `SpanCrossesHiddenContent` and is reported as
  `ERROR`, instead of relocating the counterparty's revision or the linked text
  or removing the field or reference untracked. Spans across proofing marks and
  bookmarks still apply (contracts-lit-1).
- `apply` exits 2 when any change is not applied and removes the partial
  `.docx`; the PDF, summary, memo and markdown are no longer built from the JSON
  for changes the document did not take. Each unapplied change is listed with
  its status. The output path may not be the input. Schedule-only runs
  (`--no-docx` or no output path) are unchanged (contracts-lit-2).

## [0.2.0] - 2026-02-20

### Added
- Full-document redline PDF with inline strikethrough/underline, change bars, and summary page
- Internal memo PDF with tier-grouped analysis (rationale, walkaway, precedent)
- Markdown output with external/internal modes
- Document diff — compare two `.docx` files and auto-generate redlines
- Cross-agreement comparison — flag inconsistencies across related agreements
- Placeholder scanner — find blank fields, `$X`, `TBD`, and missing exhibit references
- Section remapping — remap redline section references between document versions
- `add_section` redline type for inserting new paragraphs/sections
- Subcommand CLI: `apply`, `diff`, `scan`, `remap`, `compare`
- AI agent skill prompt (`skill.md`)
- Normalized text matching for PDF-converted documents (smart quotes, whitespace, en/em dashes)

### Changed
- Summary PDF now supports `external` and `internal` modes
- `_find_text_across_runs` returns matched document text for accurate tracked changes
- Paragraph-level filtering uses normalized matching consistently

## [0.1.1] - 2026-02-18

### Fixed
- Summary PDF table formatting — use block layout instead of cramped columns

## [0.1.0] - 2026-02-17

### Added
- Initial release
- Tracked-changes `.docx` generation via OOXML manipulation
- Summary-only redline PDF
- CLI with JSON input and inline change flags (`--replace`, `--delete`, `--insert-after`)
- Python API: `apply_redlines`, `generate_summary_pdf`, `render_redline_pdf`

[0.2.0]: https://github.com/evolsb/legal-redline-tools/compare/v0.1.1...v0.2.0
[0.1.1]: https://github.com/evolsb/legal-redline-tools/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/evolsb/legal-redline-tools/releases/tag/v0.1.0
