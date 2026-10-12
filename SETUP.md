# Set up LawyeredOS

> **Before setup:** LawyeredOS is an independent, as-is beta—not legal advice
> and not an Anthropic-endorsed product. Claude can make material errors;
> independently verify facts, citations, authorities, deadlines, calculations,
> document changes, and final work product. Local workspace storage is not
> offline inference: assess the current terms, privacy settings, confidentiality
> duties, and permissions for your Claude account before using client data. See
> [`USE-NOTICE.md`](USE-NOTICE.md).

Open this extracted `lawyeredos` folder in the Claude desktop app's **Code**
tab with the environment set to **Local**, accept the normal one-session
workspace permission, and paste:

```text
Set up LawyeredOS for me. Follow the setup instructions in this folder, ask me what you need, and check with me before changing existing files.
```

Claude should use the project-local `lawyeredos-setup` skill in
`.claude/skills/lawyeredos-setup/SKILL.md`. That skill gathers the choices,
checks the runtime, displays the deterministic wizard's exact JSON plan, and
asks for approval before applying the identical plan.

For the first trial, choose a brand-new disposable workspace. Do not choose an
existing practice project, matter folder, or anything under `~/.claude`. The
trial uses `--require-new-workspace` and must stop if the target contains any
file. LawyeredOS never installs skills, agents, or settings into user-global
`~/.claude`; selected skills are created only under the exact approved
workspace's `.claude/` directory.

Setup must not change global Claude settings, collect credentials, silently
disable email, authorize integrations for the user, or use real client data for
the first trial. It prominently asks the user to connect Gmail in Claude, skip
email safely, choose the experimental local `gmail.readonly` REST route, or
choose the portable read-only IMAP route after separately arranging a
user-controlled credential source. Terminal commands in `docs/INSTALL.md` are
inspection and fallback instructions, not the primary route.

## Standalone fictional demo

To exercise the local tracker and configuration validator without host setup or
live integrations, choose a destination that does not exist and run:

```bash
python3 scripts/setup_demo.py --destination /tmp/lawyeredos-fictional-demo
python3 scripts/validate_setup.py --config /tmp/lawyeredos-fictional-demo/config.toml
```

The demo copies the neutral template and binds its integrity manifest inside
that destination. All matter names and documents are fictional.
