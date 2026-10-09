# Workflow parity and deferred capabilities

This is a first private rewrite, not a drop-in replacement for an established
practice environment. “Tested” means fixture or structural testing in this
package; it does not mean a live account or real matter was used.

| Workflow | Preserved and tested | Intentional change | Deferred or missing | Live verification still required |
|---|---|---|---|---|
| Work on matter | Unique tracker resolution, folder confinement, bounded brief/file inventory, local memory search, guarded memory writes, PDF extraction/OCR | Neutral paths and explicit adapters; read-only start | Automatic attachment filing and automatic record update | Claude Code permissions, OCR tools, and a disposable private tracker copy |
| Matter tracker | SQLite schema, health check, find/show/list/history, guarded mutations, preview-token migration, CSV/JSON export, XLSX projection | SQLite is the only authority; XLSX is derived | Full legal conflict-clearance workflow, folder creation, practice-manager projection | Legacy mapping and concurrent use against a disposable copy |
| Correspondence | Neutral DOCX creation, placeholder failure, configured author, no-overwrite save, renderer, configurable voice lint | New anonymous template; no logo or signature | Advanced private-template topology, automatic outbound gate, sending | Private template compatibility, fonts, renderer, and full-page visual QA in target host |
| Contract redline | MIT engine and upstream tests, genuine text OOXML revisions, simple accepted-copy test, renderer | Author is configured; private rationale stays outside the external change set | Complete Word revision-class acceptance, automatic internal/external separation, outbound automation | Representative complex contracts and target Word version |
| Calendar sync | Deterministic plan; explicit dedicated-calendar adapter; bounded paginated reads; token-bound mutations | Disabled by default; credentials stay in named environment variables | Automatic retry and broader scheduling | Authorized token and disposable dedicated calendar |
| Adversarial panel | Four lenses, explicit read-only agent, source/deliverable hashes, task generator and result validator | Removed all cross-provider review | Claude Code launches the agents; the offline test validates tasks/results without a live model | Four-agent run in a disposable Claude Code workspace on synthetic files |

## Private helper dependency parity

| Original helper class | Package replacement | Status |
|---|---|---|
| Tracker writer, schema, audit history | `tracker_cli.py` | Preserved for the neutral SQLite schema; tested |
| Matter folder resolver | Tracker mapping plus `matter_context.py` | Preserved for one configured root; tested |
| Brief index and decision search | `memory_search.py` FTS index/search | Preserved generically for Markdown sources; tested |
| Mail delta/cache, message extraction, attachment fetch | `integrations.py` | Bounded metadata/snippet search preserved; attachment filing deferred |
| PDF extraction and OCR | `document_helpers.py` | Text extraction and optional OCR with hash-bound report; tested without live OCR execution |
| Safe output writer | `safe_output.py` | Preserved with token-bound no-overwrite behavior; tested |
| Matter-memory writer | `memory_search.py` | Compare-and-swap write preserved; tested |
| DOCX renderer and rasterizer | `render_docx.py` | Preserved through LibreOffice/Poppler; tested on macOS |
| Voice/style linter | `voice_lint.py` | Anonymous configurable rules; tested |
| XLSX tracker projection | `tracker_xlsx.py` | Disposable projection preserved; tested |
| DOCX tracked-change acceptor | `accept_tracked_changes.py` | Text insert/delete/move wrappers only; simple round trip tested |
| Calendar connector/writer | `calendar_plan.py` and `integrations.py` | Explicit opt-in adapter; network behavior tested with a fake transport only |
| Practice-management extension | None | Deferred; adapter reports unavailable |
| Cross-provider review runner | Claude Code plugin agent plus `review_orchestrator.py` | Intentionally replaced; deterministic synthetic orchestration tested |

Do not describe a deferred capability as degraded success. Report it as
unavailable, finish only work independent of it, and identify unverified
coverage in the result.
