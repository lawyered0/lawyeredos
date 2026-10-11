# Workflow parity and deferred capabilities

This is a first private rewrite, not a drop-in replacement for an established
practice environment. “Tested” means fixture or structural testing in this
package; it does not mean a live account or real matter was used.

## Current dual-host candidate boundary (2026-10-11)

The draft integration candidate covers both Claude and Codex. Across 15
assessed risk areas, eight are substantially proven by fictional executable
tests, three remain partial or host-dependent, two remain blocked design gaps,
and two are intentional neutral-package differences. This is reviewed
hardening, not full private-practice parity.

Substantially proven areas are bounded tracked-mail intake and conservative
reply state, attachment/content review, tracker commit receipts, hash-bound
four-lens review orchestration, letter generation, redline/clean-copy safety,
and installer ownership/fingerprint checks. The following limits remain:

- Matter orientation still returns a bounded prefix plus hash, length, and
  truncation metadata. Instructions require targeted follow-up reads, but there
  is no compact section-aware loader, first-H1 identity check, decisions or
  communications synthesis, or frozen source snapshot.
- One supported next action is required, and tracker mutations use explicit
  preview/commit receipts. Completed work is not automatically reconciled into
  timeline and next-action records; that remains a separate approved mutation.
- Review packets are exact-path and hash frozen and require all four canonical
  lenses. Quick, procedural, one- or two-lens, and exact Gmail freeze-packet
  variants are not implemented. Actual reviewer-agent invocation is a host
  capability and is not established by synthetic result collection.
- Letter generation scans and uses the same immutable template bytes. A
  persistent installed-template manifest and private-template/font/full-page
  compatibility remain unverified.
- Mail ledgers and transient session bundles require private modes. Filed
  attachment and staging directories still inherit the process umask, so
  attachment confidentiality modes are not proven.
- Durable matter-file writes do not yet bind tracker identity/open state,
  preservation of live obligations, backup, audit, and read-back in one guarded
  transaction. Safe private-mode migration without chmodding user-owned paths,
  Codex successful-upgrade rollback and hard-interruption journaling, and
  openat-style protection from a hostile concurrent local race also remain
  unresolved.
- Current From/To/Cc audience reconciliation, private-template and complex
  contract coverage, broader connectors, OCR, other operating systems, and
  ordinary-host tool discovery remain unverified.

Neutral identity and the absence of standing send, file, serve, sign, or
external-account authority are intentional differences, not deferred success.

| Workflow | Preserved and tested | Intentional change | Deferred or missing | Live verification still required |
|---|---|---|---|---|
| Work on matter | Unique tracker resolution, folder confinement, bounded brief/file inventory, bounded matter-email intake, safe supported attachment filing/review, local memory search, guarded memory writes, PDF extraction/OCR | Neutral paths and explicit adapters; read-only mailbox, local attachment and private review-ledger writes only | Section-aware orientation; atomic guarded matter-memory updates; background polling and automatic authoritative record update | Broader ordinary-host session-tool behavior; broader IMAP plus live REST; live OCR. One exact user-created Gmail thread completed through portable IMAP in each supported desktop host; a separate bounded delegated-session self-test completed the connector/core and host-model review path without a real matter. |
| Matter tracker | SQLite schema, health check, find/show/list/history, party/name candidate screening across the local register, guarded mutations, preview-token migration, CSV/JSON export, XLSX projection | SQLite is the only authority; XLSX is derived; screening is not a legal clearance decision | Dedicated conflict-clearance decision/status, fuzzy or alias matching, external conflict sources, folder creation, practice-manager projection | Legacy mapping and concurrent use against a disposable copy |
| Correspondence | Neutral DOCX creation from immutable scanned template bytes, package-wide marker/review-markup refusal, configured author, atomic no-overwrite save, renderer, configurable voice lint | New anonymous template; no logo or signature | Installed-template manifest, advanced private-template topology, automatic outbound gate, sending | Private template compatibility, fonts, renderer, and full-page visual QA in target host |
| Contract redline | MIT engine and upstream tests, genuine text OOXML revisions, simple accepted-copy test, renderer | Author is configured; private rationale stays outside the external change set | Complete Word revision-class acceptance, automatic internal/external separation, outbound automation | Representative complex contracts and target Word version |
| Calendar sync | Deterministic plan; explicit dedicated-calendar adapter; bounded paginated reads; token-bound mutations | Disabled by default; credentials stay in named environment variables | Automatic retry and broader scheduling | Authorized token and disposable dedicated calendar |
| Adversarial panel | Four canonical lenses, exact source/deliverable hashes, task generator and result validator | Removed all cross-provider review | Quick/procedural/one- or two-lens packets; the offline test validates tasks/results without proving host invocation | Ordinary-host multi-agent run in a disposable workspace on synthetic files |

## Private helper dependency parity

| Original helper class | Package replacement | Status |
|---|---|---|
| Tracker writer, schema, audit history | `tracker_cli.py` | Preserved for the neutral SQLite schema; tested |
| Matter folder resolver | Tracker mapping plus `matter_context.py` | Preserved for one configured root; tested |
| Brief index and decision search | `memory_search.py` FTS index/search | Preserved generically for Markdown sources; tested |
| Mail delta/cache, message extraction, attachment fetch | `mail_intake.py`, `content_review.py`, `integrations.py`, `imap_mail.py` | Stable-ID ledger and complete bounded-window query; fully retrieved bodies and attachment bytes through configured REST, portable read-only IMAP, or capable session tools; resumable paragraph/page/sheet chunks require hash-bound model acknowledgements, and long, ambiguous, visual/OCR-gapped, or partial retrieval never advances the complete checkpoint |
| PDF extraction and OCR | `document_helpers.py` | Text extraction and optional OCR with hash-bound report; tested without live OCR execution |
| Safe output writer | `safe_output.py` | Preserved with token-bound no-overwrite behavior; tested |
| Matter-memory writer | `memory_search.py` | Compare-and-swap write preserved; tested |
| DOCX renderer and rasterizer | `render_docx.py` | Preserved through LibreOffice/Poppler; tested on macOS |
| Voice/style linter | `voice_lint.py` | Anonymous configurable rules; tested |
| XLSX tracker projection | `tracker_xlsx.py` | Disposable projection preserved; tested |
| DOCX tracked-change acceptor | `accept_tracked_changes.py` | Insert/delete/move acceptance with package-wide cleanup validation; comments and unsupported property revisions fail closed |
| Calendar connector/writer | `calendar_plan.py` and `integrations.py` | Explicit opt-in adapter; network behavior tested with a fake transport only |
| Practice-management extension | None | Deferred; adapter reports unavailable |
| Cross-provider review runner | Claude Code plugin agent plus `review_orchestrator.py` | Intentionally replaced; deterministic synthetic orchestration tested |

Do not describe a deferred capability as degraded success. Report it as
unavailable, finish only work independent of it, and identify unverified
coverage in the result.
