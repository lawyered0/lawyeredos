# LawyeredOS

**Claude with the right legal-work skills—not another legal SaaS dashboard.**

LawyeredOS is a free, open-source macOS beta for Claude Desktop Code. It works
with the matter files you choose, records matter history and state in your
workspace, and helps identify and execute the next step under lawyer oversight.
It includes guarded workflows for matter orientation and tracking, letters,
decided contract redlines, calendar planning, and independent draft review.

![Fictional LawyeredOS matter flow](docs/images/website-matter-flow.png)

## Try the macOS beta

Download **[LawyeredOS 0.2.0 beta.1](https://lawyered0.github.io/downloads/lawyeredos-0.2.0-macos-beta.1.zip)**
and verify its SHA-256:

```text
f949d6d33d449b674c5fd1e290646b1b53b2cdf497e2c48d60ab88f09c8177cc
```

1. Extract the ZIP into a private folder you will retain.
2. Open the extracted `lawyeredos` folder in the Claude desktop app's
   **Code** tab and choose **Local**.
3. Paste:

```text
Set up LawyeredOS for me. Follow the setup instructions in this folder, ask me what you need, and check with me before changing existing files.
```

Claude gathers your choices, shows the exact setup plan, and asks before the
bundled deterministic installer writes anything. For a first trial, use a new,
empty workspace and fictional data. You do not need a terminal or slash command
for the normal setup flow.

Full instructions: [installation](docs/INSTALL.md) ·
[setup](docs/SETUP.md) · [host support](docs/HOST-SUPPORT.md) ·
[troubleshooting](docs/TROUBLESHOOTING.md)

## Pick up a matter where you left it

LawyeredOS uses the selected matter's files plus recorded workspace history and
state—not an assumption that chat memory is complete. A typical read-only first
request is:

> Open matter 2030-001. Review the matter brief and source note. Tell me the
> current position, what is uncertain, and one recommended next step. Do not
> change any files.

From there, ask separately for a draft, a decided redline, or a proposed tracker
update. Material changes are previewed for approval. You remain responsible for
checking the sources, exercising professional judgment, and deciding what to do.

## Included skills

- `lawyeredos-work-on-matter`: orient to one exact matter and bounded sources.
- `lawyeredos-matter-tracker`: preview and verify guarded register changes.
- `lawyeredos-letterhead`: create and verify a neutral branded DOCX draft.
- `lawyeredos-contract-redline`: apply already-decided Word tracked changes.
- `lawyeredos-calendar-sync`: preview dedicated-calendar changes; live sync is
  experimental and off by default.
- `lawyeredos-adversarial-panel`: experimental multi-lens draft review.
- `/lawyeredos-setup`: guide installation through the deterministic installer.

The local toolkit also provides an SQLite matter register, collision-safe saved
outputs, PDF extraction, optional OCR and local search, versioned upgrades, and
conservative rollback. See [examples](docs/EXAMPLES.md) and the
[lifecycle guide](docs/LIFECYCLE.md).

## Current platform and limits

This beta requires **macOS**, a **Local** session in Claude Desktop Code, and
Python 3.11 or newer. Python 3.12 is the fully tested runtime. The separate
terminal launcher is an optional fallback documented in
[installation](docs/INSTALL.md).

Windows and other operating systems are not currently supported. Live Gmail and
Google Calendar, OCR, and the complete multi-lens review remain experimental or
optional; the practice-manager adapter is not implemented. See
[host support](docs/HOST-SUPPORT.md), [dependencies](docs/DEPENDENCIES.md), and
[the roadmap](ROADMAP.md).

## Confidentiality and professional responsibility

Matter files and recorded state stay in the workspace you choose, but this is
**not offline inference**. Claude Code may send selected content to Anthropic
under your account, plan, settings, and applicable terms. Review those controls
and your professional obligations before using client data.

LawyeredOS is software, not legal advice or an autonomous lawyer. It never
treats reading a file as permission to send, sign, file, serve, or change an
external account. Claude can make material errors. Independently verify facts,
authorities, deadlines, calculations, document changes, and final work before
relying or acting. See the full [safety and use notice](USE-NOTICE.md),
[security policy](SECURITY.md), and [support guidance](SUPPORT.md).

LawyeredOS is an independent project and is not affiliated with, sponsored by,
or endorsed by Anthropic. Claude access and any Anthropic plan or API usage are
separate costs governed by Anthropic's terms.

## Development

```bash
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m pytest vendor/legal-redline-tools/tests -q
.venv/bin/python scripts/smoke_setup_wizard.py
claude plugin validate --strict .
```

See [CONTRIBUTING.md](CONTRIBUTING.md), [CHANGELOG.md](CHANGELOG.md), and the
[release checklist](RELEASE-CHECKLIST.md). Automated tests use fictional files
and injected connector transports; they do not replace professional review.

## License

Original LawyeredOS material is `GPL-3.0-or-later`; see [LICENSE](LICENSE) and
[LICENSE-DECISION.md](LICENSE-DECISION.md). The bundled `legal-redline-tools`
derivative retains its MIT license and attribution. See
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md), [ATTRIBUTION.md](ATTRIBUTION.md),
and [PROVENANCE.md](PROVENANCE.md).

LawyeredOS is the package name, not the name of the Claude assistant or a
separate assistant persona.
