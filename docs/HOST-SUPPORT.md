# Host support

LawyeredOS keeps host discovery and instructions separate while reusing one
deterministic Python, SQLite, document, redline, and guarded-workflow core.
The required tested target for the released Claude package is Claude Desktop Code
Local on macOS; the Codex package has the separate accepted scope below.

| Host | Accepted scope |
|---|---|
| Claude Desktop 2.31226.0, Code tab, Local environment, macOS | Claude beta.2 with Python 3.12.7; configured runtime, validator, read-only tracker checks, fresh-session project skill discovery, and the documented fictional workflow were verified. |
| Codex local project on macOS | Codex beta.1 with Python 3.12.7 and Codex CLI 0.147.0; project-local skill discovery, guarded fictional tracker update, fresh-session persistence, and four-agent review collection were verified. A user-created Desktop task reported the expected read-only persisted state; the evidence boundary is recorded in [CODEX-ACCEPTANCE.md](CODEX-ACCEPTANCE.md). |
| Terminal Claude Code | Optional fallback using Claude's project-local discovery layer; not a substitute release target. |
| Other surfaces, operating systems, or versions | Not accepted. No compatibility claim. |

## Capability matrix

| Area | Status | Boundary |
|---|---|---|
| Local matter register and orientation | Core | SQLite is authoritative; reads and writes fail closed on missing or ambiguous state. |
| DOCX letters and redlines | Optional selected modules | Require the pinned Python document packages. Visual verification additionally requires LibreOffice and Poppler. |
| Claude Gmail connector | Configurable, not live-account accepted | The user authorizes it in Claude. Only a successful bounded read proves availability for that request. LawyeredOS does not send or mutate mail. |
| Codex session mail tools | Configurable, not assumed available | Setup cannot install or authorize a connector. The workflow uses a supported, already-authorized read/search tool only when the active session exposes one. |
| Local Gmail read-only and dedicated Calendar REST adapters | Experimental | Explicit opt-in; fake-transport tests only. Token values stay in named environment variables. |
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
