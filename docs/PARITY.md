# Workflow parity and deferred capabilities

Released 0.2.3 beta.1 adds an **instruction layer** described in the
[workflow catalog](WORKFLOW-CATALOG.md) and
[gap disposition matrix](WORKFLOW-COMPLETENESS.md). The table below records the
published baseline's mechanical/host evidence; it is not acceptance of the new
manual modules. Added semantic completion rules propose exact records rather
than infer or authorize automatic updates. Native discovery of the nine added
modules and broader acquisition remain separately unsupported. Read the
[release record](RELEASE-0.2.3.md) for completed package and installation checks.

This is a first private rewrite, not a drop-in replacement for an established
practice environment. “Tested” means fixture or structural testing in this
package; it does not mean a live account or real matter was used.

## Historical dual-host baseline evidence (2026-10-11)

The 0.2.2 integration baseline covers both Claude and Codex. Its portable
mechanical contracts are exercised with fictional executable tests, while
live accounts, genuine host-agent invocation, and private-practice artifacts
retain separate acceptance boundaries. This is reviewed hardening, not full
private-practice parity.

Substantially proven areas are bounded tracked-mail intake and conservative
reply state, attachment/content review, tracker commit receipts, hash-bound
four-lens review orchestration, letter generation, redline/clean-copy safety,
and installer ownership/fingerprint checks. The following limits remain:

- Matter orientation now fails closed unless the brief's sole first H1 matches
  the tracker file number, or an existing 0.2.1 brief's H1 matches the exact
  tracker client name. It fully hashes bounded sources, prioritizes complete
  sections or paragraphs within a disclosed output budget, recovers structured
  decision and communication locators, and reports selected and omitted
  coverage. This is a read-only compact view, not a frozen source snapshot or
  substantive verification of the returned evidence.
- One supported next action is required, and tracker mutations use explicit
  preview/commit receipts. An explicitly approved guarded matter-file write can
  atomically carry its timeline and next-action update through the tracker
  revision. Completed work is not inferred or reconciled automatically.
- Review packets are exact-path and hash frozen. Full review uses all four
  canonical lenses; targeted review requires one named principal lens; quick
  review requires exactly two distinct named principal lenses; and procedural
  review uses the dedicated micro-correspondence lens. The selected mode and
  exact ordered lens set are bound through the manifest, task bundle, and
  collected report. Actual reviewer-agent invocation is a host capability and
  is not established by synthetic result collection.
- Letter generation scans and uses the same immutable template bytes. A
  generated installed-core manifest binds the configured neutral template path
  and hash, and setup validation and letter creation fail closed if that
  binding is missing or changed. Private replacement templates are not
  automatically trusted; their topology, fonts, and full-page compatibility
  remain unverified until separately reviewed and bound.
- New app-owned config, tracker, scratch, mail-ledger, session-bundle, staging,
  and saved-attachment paths use exact private modes. Existing insecure or
  multiply linked confidential files fail closed with migration guidance;
  setup does not silently chmod user-owned paths.
- Guarded matter-file writes bind tracker identity, open status, source and
  target hashes, tracker revision, explicit existing-content disposition,
  backup/recovery journal state, and read-back. Those are mechanical safety
  guarantees: the package does not semantically understand a document diff or
  prove that live obligations were preserved. Codex can roll back the latest
  accepted managed upgrade only when current discovery, links, and core
  fingerprints still match the recorded transaction; it preserves tracker,
  configuration, unrelated files, and both versioned cores. Process-kill or
  power-loss durability acceptance and openat-style protection from a hostile
  concurrent local race remain unresolved.
- From/To/Cc reconciliation compares normalized retrieved headers with an
  explicitly proposed audience and records separate hash-bound evidence. It
  reports verified, mismatch, unknown, or ambiguous without using message
  content as audience evidence and never establishes authorization, delivery,
  filing, or service. Live connector/model use of this contract remains
  unverified.
- Private-template and complex contract coverage, broader connectors, OCR,
  other operating systems, and ordinary-host tool discovery remain unverified.

Neutral identity and the absence of standing send, file, serve, sign, or
external-account authority are intentional differences, not deferred success.

| Workflow | Preserved and tested | Intentional change | Deferred or missing | Live verification still required |
|---|---|---|---|---|
| Work on matter | Unique tracker resolution, folder confinement, section-aware bounded brief/decisions/communications recovery with identity and coverage checks, bounded file inventory and matter-email intake, normalized hash-bound From/To/Cc reconciliation, safe supported attachment filing/review, local memory search, guarded memory and matter-file writes, PDF extraction/OCR | Neutral paths and explicit adapters; read-only mailbox, local attachment and private review-ledger writes only; audience evidence never supplies send/service authority | Frozen orientation snapshot; semantic diff/live-obligation verification; background polling and automatic authoritative record update | Broader ordinary-host session-tool behavior; live use of audience reconciliation; broader IMAP plus live REST; live OCR. One exact user-created Gmail thread completed through portable IMAP in each supported desktop host; a separate bounded delegated-session self-test completed the connector/core and host-model review path without a real matter. |
| Matter tracker | SQLite schema, health check, find/show/list/history, party/name candidate screening across the local register, guarded mutations, preview-token migration, CSV/JSON export, XLSX projection | SQLite is the only authority; XLSX is derived; screening is not a legal clearance decision | Dedicated conflict-clearance decision/status, fuzzy or alias matching, external conflict sources, folder creation, practice-manager projection | Legacy mapping and concurrent use against a disposable copy |
| Correspondence | Neutral DOCX creation from immutable scanned template bytes bound by an installed-core path/hash manifest, package-wide marker/review-markup refusal, configured author, atomic no-overwrite save, renderer, configurable voice lint | New anonymous template; no logo or signature; private replacements require a separately reviewed binding | Advanced private-template topology, automatic outbound gate, sending | Private template compatibility, fonts, renderer, and full-page visual QA in target host |
| Contract redline | MIT engine and upstream tests, genuine text OOXML revisions, simple accepted-copy test, renderer | Author is configured; private rationale stays outside the external change set | Complete Word revision-class acceptance, automatic internal/external separation, outbound automation | Representative complex contracts and target Word version |
| Calendar sync | Deterministic plan; explicit dedicated-calendar adapter; bounded paginated reads; token-bound mutations | Disabled by default; credentials stay in named environment variables | Automatic retry and broader scheduling | Authorized token and disposable dedicated calendar |
| Adversarial panel | Full four-lens, targeted one-lens, quick two-lens, and procedural micro-correspondence modes; exact ordered lens set and source/deliverable hashes; task generator and result validator | Removed all cross-provider review; no risk label silently escalates scope | Offline contracts validate tasks/results without proving host invocation | Ordinary-host multi-agent runs for each mode in a disposable workspace on synthetic files |

## Private helper dependency parity

| Original helper class | Package replacement | Status |
|---|---|---|
| Tracker writer, schema, audit history | `tracker_cli.py` | Preserved for the neutral SQLite schema; tested |
| Matter folder resolver | Tracker mapping plus `matter_context.py` | Preserved for one configured root; tested |
| Brief index and decision search | `memory_search.py` FTS index/search | Preserved generically for Markdown sources; tested |
| Mail delta/cache, message extraction, attachment fetch | `mail_intake.py`, `content_review.py`, `integrations.py`, `imap_mail.py` | Stable-ID ledger and complete bounded-window query; fully retrieved bodies and attachment bytes through configured REST, portable read-only IMAP, or capable session tools; resumable paragraph/page/sheet chunks require hash-bound model acknowledgements, and long, ambiguous, visual/OCR-gapped, or partial retrieval never advances the complete checkpoint |
| PDF extraction and OCR | `document_helpers.py`, `pdf_assessment.py` | Page-level text receipts include expected/extracted counts, character counts, sparse/missing pages, and page-count verification. Sparse pages or an unknown/mismatched `pdfinfo` count require OCR or manual review, including cached review text; one dense page cannot clear the rest. Optional OCR uses a hash-bound report; tested without live OCR execution |
| Safe output writer | `safe_output.py` | Preserved with token-bound no-overwrite behavior; tested |
| Matter-memory writer | `memory_search.py` | Compare-and-swap write preserved; tested |
| DOCX renderer and rasterizer | `render_docx.py` | Preserved through LibreOffice/Poppler; tested on macOS |
| Voice/style linter | `voice_lint.py` | Anonymous configurable rules; tested |
| XLSX tracker projection | `tracker_xlsx.py` | Disposable projection preserved; tested |
| DOCX tracked-change acceptor | `accept_tracked_changes.py` | Inline insert/delete/move acceptance with package-wide cleanup validation; paragraph-mark/row deletions, comments and unsupported property revisions fail closed |
| DOCX metadata scrubber | `scrub_docx_metadata.py` | Clears core/custom metadata while preserving namespace bindings. Custom-property parts are found through validated package relationships/content types, including renamed or orphaned parts; unsafe or misdeclared targets fail closed. Comments, people records and revision-author metadata require a separate sanitization decision and produce no scrubbed output; review content is never silently removed |
| Calendar connector/writer | `calendar_plan.py` and `integrations.py` | Explicit opt-in adapter; network behavior tested with a fake transport only |
| Practice-management extension | None | Deferred; adapter reports unavailable |
| Cross-provider review runner | Claude Code plugin agent plus `review_orchestrator.py` | Intentionally replaced; deterministic synthetic orchestration tested |

Do not describe a deferred capability as degraded success. Report it as
unavailable, finish only work independent of it, and identify unverified
coverage in the result.
