# Architecture and safety model

LawyeredOS separates conversational instructions from deterministic state
changes.

## Layers

1. **Host entrypoints.** Claude discovers `.claude/skills`; Codex discovers
   `.agents/skills`. Setup copies or links selected `lawyeredos-*` skills into
   the approved project only. Host instructions decide what evidence to read,
   when to stop, and what approval is required.
2. **Shared Python core.** Modules under `src/lawyeredos/` implement tracker,
   orientation, document, redline, output, migration, integration, and review
   operations. They do not provide a second chat interface or silently choose a
   model provider.
3. **Local state.** `.lawyeredos/config.toml` names the workspace and adapters.
   SQLite is the authoritative matter register. XLSX/JSON/CSV outputs are
   projections, never write inputs.
4. **Optional external adapters.** Mail and Calendar are disabled or explicitly
   selected. Credentials remain in named environment variables or in the
   user's host-authorized connector; token values are not written to config.

## Guarded write flow

Tracker mutations read the current register revision, produce a dry-run
proposal, and return a token bound to that revision and exact change. Commit
repeats the operation with that token, so stale register state fails closed.
Safe file outputs bind the proposed destination and content hash and refuse an
existing destination. Calendar mutations bind the exact action and payload,
then re-read creates and updates; that token does not represent a remote
calendar revision.

Setup uses a related but different guard: the host skill must repeat the exact
approved arguments, while the installer performs apply-time preflight and
fails on unmanaged collisions. The preview and apply are not joined by a
machine-verified token. Setup retains ownership records for updates or removal.
Neither host installer modifies global skills, credentials, OAuth state, or
real matter data during the fictional trial.

## Review boundary

Review jobs use bounded source paths, schemas, and before/after hashes. A skill
can instruct an independent agent to remain read-only, but cannot technically
remove tools from that agent. When the host cannot provide independent agents,
the panel reports itself unavailable instead of emulating independence.
