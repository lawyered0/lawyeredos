# Host support

LawyeredOS keeps host discovery and instructions separate while reusing one
deterministic Python, SQLite, document, redline, and guarded-workflow core.
The required tested target for the released Claude package is Claude Desktop Code
Local on macOS; the Codex package has the separate accepted scope below.

| Host | Accepted scope |
|---|---|
| Claude Desktop 2.31226.0, Code tab, Local environment, macOS | Beta.3 preserves the beta.2 host path verified with Python 3.12.7: configured runtime, validator, read-only tracker checks, fresh-session project skill discovery, and the documented fictional workflow. |
| Codex local project on macOS | Beta.2 preserves the beta.1 path verified with Python 3.12.7 and Codex CLI 0.147.0: project-local skill discovery, guarded fictional tracker update, fresh-session persistence, and four-agent review collection. A user-created Desktop task reported the expected read-only persisted state; the evidence boundary is recorded in [CODEX-ACCEPTANCE.md](CODEX-ACCEPTANCE.md). |
| Terminal Claude Code | Optional fallback using Claude's project-local discovery layer; not a substitute release target. |
| Other surfaces, operating systems, or versions | Not accepted. No compatibility claim. |

## Capability matrix

| Area | Status | Boundary |
|---|---|---|
| Local matter register and orientation | Core | SQLite is authoritative; reads and writes fail closed on missing or ambiguous state. |
| DOCX letters and redlines | Optional selected modules | Require the pinned Python document packages. Visual verification additionally requires LibreOffice and Poppler. |
| Claude Gmail connector | Configurable, not live-account accepted | The user authorizes it in Claude. Anthropic documents search/read access and attachment metadata, not direct attachment-content access. The shared intake requires full bodies and bytes, so messages with attachments remain partial unless the runtime separately provides an authorized byte-returning read tool. LawyeredOS does not send or mutate mail. |
| Codex session mail tools | Configurable, not assumed available | Setup cannot install or authorize a connector. Codex documents runtime MCP/plugin tool discovery, not a built-in Gmail contract. The workflow names no hypothetical tool and uses an already-authorized read/search tool only when the active session actually exposes one; metadata-only results are partial. |
| Local Gmail read-only and dedicated Calendar REST adapters | Experimental | Gmail full-message and attachment retrieval has fake GET-only transport coverage; no live mailbox was used. Calendar also has fake-transport coverage. Token values stay in named environment variables. |
| Portable Gmail read-only IMAP adapter | Experimental release capability | Host-neutral full-body and attachment acquisition has comprehensive fake-IMAP coverage using localized All Mail discovery, stable Gmail IDs, read-only selection, and `BODY.PEEK`. Credential creation is user-mediated; no live IMAP credential or ordinary-host acceptance is claimed. The owner waived that pending test as a beta.3/beta.2 publication prerequisite. |
| Matter attachment filing and review | Candidate core | Supported PDF, DOCX, XLSX, TXT, Markdown, and CSV attachments are size-, type-, signature-, hash-, relationship-, embedding-, and path-checked, saved without overwrite, and treated as untrusted evidence. Active, unsupported, incomplete, oversized, long, or OCR-needing items hold the checkpoint for review. |
| OCR | Experimental optional | OCRmyPDF was unavailable on the acceptance host. |
| Multi-lens review | Host-dependent | Codex four-agent collection was exercised on fictional files. Claude's complete four-lens orchestration remains experimental. If independent agents are unavailable, report the panel unavailable. |
| Practice manager | Unavailable | No adapter is bundled. |

## Runtime gate

Before any real matter work, confirm all of the following:

1. `.lawyeredos/config.toml` resolves to the intended workspace, tracker, and
   current versioned core.
2. The configured Python is executable and reports Python 3.11 or newer;
   Python 3.12 is the accepted runtime.
3. `scripts/validate_setup.py` reports no required-capability error.
4. The fictional demo completes without a live connector.
5. Only the current workspace's `lawyeredos-*` project skills are credited;
   similarly named personal or synced skills are not.
6. Optional render, OCR, mail, calendar, and independent-agent capabilities
   are claimed only after their own checks succeed.

If a gate fails, the affected workflow is unavailable. Do not substitute a
different host, connector, account, model provider, or matter.

## Host-specific discovery

Claude setup installs project skills under `.claude/skills`, the optional
review agent under `.claude/agents`, and private runtime paths in
`.claude/settings.local.json`. The Desktop launcher opens the workspace folder
directly; `claude --desktop --plugin-dir ...` is not a supported substitute.

Codex setup installs only installer-managed project skills under
`.agents/skills` and runtime files under `.lawyeredos`. It does not change
`~/.codex`, `~/.agents`, project `.codex/config.toml`, credentials, OAuth state,
or connector permissions.
