# Host support

This package uses Claude Code skills, one read-only agent, local Python
commands, local SQLite, and local document tools.

| Host | Status |
|---|---|
| Claude Desktop 2.31226.0 Code tab, Local environment, on macOS | Required tested target; configured Python 3.12.7, validator, read-only tracker checks, and fresh-session project discovery are verified |
| Terminal Claude Code | Optional fallback using the same project-local discovery layer; not a substitute release target |
| Any other Claude surface | Outside this release's acceptance target; no compatibility claim |

## Platform and capability matrix

| Area | Status | Release treatment |
|---|---|---|
| macOS Local Code session with Python 3.12 | Core runtime, validator, read-only tracker checks, fresh-session skill/agent discovery, and one bounded current-name source-fidelity agent invocation verified without file changes | Initial Desktop target; complete four-lens orchestration remains experimental |
| macOS with Python 3.11 or 3.13+ | Declared range or plausible compatibility, not accepted | No release claim beyond `>=3.11` package metadata |
| Windows or Linux | Not tested | Unsupported for the first release |
| Local matter register/orientation | Core | Required and fail-closed |
| DOCX letters/redlines | Optional selected modules | Require Python document packages; visual verification additionally requires LibreOffice and Poppler |
| Claude Gmail connector | Configurable, not locally verifiable | User authenticates directly in Claude; only a successful bounded read proves connection for that request; no real-mail acceptance claim |
| Local Gmail read-only / dedicated Calendar REST adapters | Experimental | Explicit opt-in; fake-transport tests only |
| OCR | Experimental optional | Unverified on the test host |
| Practice manager | Unavailable | No adapter bundled |

## Runtime gate

Before any real matter work, confirm all of the following in the launched
Desktop Code workspace:

1. `LAWYEREDOS_ROOT` resolves to the versioned private package copy.
2. `LAWYEREDOS_CONFIG` resolves to a private configuration file.
3. The configured tracker and matter workspace are visible.
4. `LAWYEREDOS_PYTHON` is executable and reports Python 3.11 or newer.
5. Optional DOCX/PDF commands and Python packages pass `validate_setup.py`.
6. The fictional demo completes without a live connector.
7. The `lawyeredos-legal-review-lens` agent is available before claiming a
   full four-lens adversarial review.
8. Only `lawyeredos-*` project skills are credited as current-package behavior;
   similarly named personal or synced skills are not.

If any gate fails, the affected workflow is unavailable. Do not substitute a
different host, connector, or model provider.

The renamed RC13 build was validated with `claude plugin validate --strict`,
ZIP-only Python tests, and a genuine Local Desktop session. The configured
runtime, validator, tracker verification/listing, and unchanged workspace hashes
passed. A fresh Local session registered the three selected `lawyeredos-*`
project skills and `lawyeredos-legal-review-lens` agent. Similarly named personal
skills were present and were not credited. The agent has not yet been invoked
under its renamed identity. An attempted exact-build Desktop launch also
established that `claude --desktop --plugin-dir ...` is rejected by CLI 2.1.288;
the wizard therefore uses project `.claude/` discovery and opens the workspace
folder directly in the app without requiring a separate terminal CLI login.
