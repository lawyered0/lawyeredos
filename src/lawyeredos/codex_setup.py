from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shlex
import shutil
import sqlite3
import sys
from dataclasses import asdict
from pathlib import Path

from .config import load_config
from .setup_wizard import (
    MODULES,
    MODULE_SKILLS,
    PROJECT_SKILLS,
    VERSION,
    Answers,
    _ignored,
    package_digest,
    package_root,
    render_config,
    validate_answers,
)
from .tracker_cli import initialize


DISCOVERY_FILE = "codex-project-discovery.json"
RUNNER_FILE = "lawyeredos-run"
CURRENT_LINK = "current-codex"


def _inside(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def dependency_report(modules: tuple[str, ...]) -> list[dict[str, str | bool]]:
    selected = set(modules)
    checks: list[dict[str, str | bool]] = [{
        "name": "Python 3.11+",
        "required": True,
        "available": sys.version_info >= (3, 11),
        "detail": platform.python_version(),
        "fix": "Install Python 3.11 or newer, then rerun this wizard.",
    }]
    for module, label, fix, required in (
        ("openpyxl", "openpyxl", "Install openpyxl to enable optional XLSX projection.", False),
        ("docx", "python-docx", "Install requirements-documents.txt for letters or redlines.", bool(selected & {"letters", "redline"})),
        ("lxml", "lxml", "Install requirements-documents.txt for redlines.", "redline" in selected),
        ("fpdf", "fpdf2", "Install requirements-documents.txt for redlines.", "redline" in selected),
    ):
        import importlib.util
        checks.append({
            "name": label,
            "required": required,
            "available": importlib.util.find_spec(module) is not None,
            "detail": "Python module",
            "fix": fix,
        })
    codex_cli = shutil.which("codex")
    desktop = next((path for path in (
        Path("/Applications/ChatGPT.app"),
        Path.home() / "Applications" / "ChatGPT.app",
    ) if path.is_dir()), None)
    checks.append({
        "name": "Codex host",
        "required": True,
        "available": bool(codex_cli or desktop),
        "detail": codex_cli or (str(desktop) if desktop else "Codex CLI or ChatGPT desktop app not found"),
        "fix": "Install Codex CLI or the ChatGPT desktop app and sign in normally.",
    })
    for commands, label, fix in (
        (("libreoffice", "soffice"), "LibreOffice", "Install LibreOffice for visual DOCX rendering."),
        (("pdftoppm",), "Poppler", "Install Poppler for PDF page images."),
        (("ocrmypdf",), "OCRmyPDF", "Install OCRmyPDF only if OCR is needed."),
    ):
        found = next((shutil.which(command) for command in commands if shutil.which(command)), None)
        checks.append({"name": label, "required": False, "available": found is not None,
                       "detail": found or "command not found", "fix": fix})
    return checks


def normalize_answers(
    workspace: Path,
    branding_mode: str,
    branding_label: str,
    jurisdiction: str,
    modules_raw: str,
    mail: str,
    calendar: str,
    calendar_id: str,
    existing: str,
) -> Answers:
    modules = tuple(dict.fromkeys(item.strip() for item in modules_raw.split(",") if item.strip()))
    return Answers(
        workspace=workspace.expanduser().resolve(),
        branding_mode=branding_mode.strip().lower(),
        branding_label=branding_label.strip(),
        jurisdiction=jurisdiction.strip().lower(),
        modules=modules,
        mail_adapter={
            "session-tools": "codex-session-tools",
            "skip": "unavailable",
            "gmail-readonly": "gmail-api-readonly",
        }.get(mail, mail),
        calendar_adapter={"off": "unavailable", "google-calendar": "google-calendar-api"}.get(calendar, calendar),
        calendar_id=calendar_id.strip(),
        existing_config=existing.strip().lower(),
    )


def _projectize_skill(source: Path, destination: Path, project_name: str) -> None:
    shutil.copytree(source, destination)
    skill_path = destination / "SKILL.md"
    text = skill_path.read_text(encoding="utf-8")
    replacements = {
        "lawyeredos:practice-work-on-matter": "lawyeredos-work-on-matter",
        "lawyeredos:practice-matter-tracker": "lawyeredos-matter-tracker",
        "lawyeredos:practice-letterhead": "lawyeredos-letterhead",
        "lawyeredos:practice-contract-redline": "lawyeredos-contract-redline",
        "lawyeredos:practice-calendar-sync": "lawyeredos-calendar-sync",
        "lawyeredos:practice-adversarial-panel": "lawyeredos-adversarial-panel",
        "${LAWYEREDOS_ROOT}": f".lawyeredos/{CURRENT_LINK}",
        "$LAWYEREDOS_ROOT": f".lawyeredos/{CURRENT_LINK}",
        "${LAWYEREDOS_PYTHON:-python3}": f".lawyeredos/{RUNNER_FILE}",
        "$LAWYEREDOS_CONFIG": ".lawyeredos/config.toml",
        "Claude-only": "Codex-only",
        "Claude-Only": "Codex-Only",
        "Claude reviewers": "Codex reviewers",
        "Claude Code": "Codex",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    old_name = project_name.replace("lawyeredos-", "practice-", 1)
    text = text.replace(f"name: {old_name}", f"name: {project_name}", 1)
    if project_name == "lawyeredos-work-on-matter":
        text = text.replace(
            "Require the `LAWYEREDOS_CONFIG` environment variable.",
            "Require the project-local `.lawyeredos/config.toml` file; do not require or modify a global environment variable.",
        ).replace(
            "When `claude-gmail-connector` is configured, use Claude's Gmail connector only",
            "When `codex-session-tools` is configured, first inspect the tools actually exposed in this Codex session. Use a supported mail read/search tool only",
        )
        start = text.index("- When `codex-session-tools` is configured")
        end = text.index("- When `gmail-api-readonly` is configured", start)
        text = text[:start] + (
            "- When `codex-session-tools` is configured, inspect the tools actually exposed in "
            "the active session. Use only a supported, authorized mail read/search tool. A "
            "configured value is not proof that a tool is present or connected. Treat a missing "
            "tool, authorization prompt, or failed read as unavailable; only a successful bounded "
            "read establishes coverage for that request. Never draft, send, reply, forward, label, "
            "archive, or delete mail from this workflow.\n"
        ) + text[end:]
    if project_name == "lawyeredos-adversarial-panel":
        text = text.replace("through four read-only Claude lenses", "through four independent Codex lenses")
        text = text.replace("`lawyeredos:legal-review-lens` agent", "independent Codex reviewer delegation")
        text = text.replace("`lawyeredos-legal-review-lens` agent", "independent Codex reviewer delegation")
        text = text.replace("lawyeredos:legal-review-lens", "independent-codex-reviewer")
        text = text.replace("review_bundle create ", "review_bundle create --host codex ", 1)
        text = text.replace("review_orchestrator prepare ", "review_orchestrator prepare --host codex ", 1)
        text = text.replace("four independent independent Codex reviewer delegations", "four independent Codex reviewers")
        text = text.replace(
            "Reviewers\nhave only read/search tools, cannot write, browse, call connectors, run shell,\nor spawn agents.",
            "Instruct reviewers to use only bounded read/search access and not to write, browse, "
            "call connectors, execute commands, or spawn agents. Treat these as behavioral "
            "constraints and verify the source and deliverable hashes after every review.",
        )
        boundary = (
            "\n## Codex reviewer boundary\n\n"
            "A full panel requires the active Codex host to expose independent agent delegation. "
            "Give each reviewer exactly one generated task and instruct it to remain read-only. "
            "A repository skill cannot technically reduce a delegated reviewer's tools, so hash "
            "verification is mandatory. If delegation is unavailable, report the full panel as "
            "unavailable; a single-thread review is not equivalent.\n"
        )
        text = text.replace("\n## Review\n", boundary + "\n## Review\n")
    skill_path.write_text(text, encoding="utf-8")


def _prepare_payload(plugin: Path, modules: set[str]) -> None:
    root = plugin / ".lawyeredos-codex-project" / "skills"
    root.mkdir(parents=True, exist_ok=True)
    for module in modules:
        _projectize_skill(plugin / "skills" / MODULE_SKILLS[module], root / PROJECT_SKILLS[module], PROJECT_SKILLS[module])


def render_runner(plan: dict) -> str:
    python = shlex.quote(plan["runtime_python"])
    return "\n".join([
        "#!/bin/sh", "set -eu",
        f"runtime={python}",
        'base=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)',
        f'core="$base/{CURRENT_LINK}/src"',
        'if [ ! -x "$runtime" ]; then',
        '  echo "LawyeredOS runtime is unavailable; rerun setup from the retained candidate." >&2',
        "  exit 1", "fi",
        'if [ -n "${PYTHONPATH:-}" ]; then',
        '  export PYTHONPATH="$core:$PYTHONPATH"',
        "else", '  export PYTHONPATH="$core"', "fi",
        'exec "$runtime" "$@"', "",
    ])


def render_launcher(plan: dict) -> str:
    return "\n".join([
        "#!/bin/sh", "set -eu",
        f"cd {shlex.quote(plan['workspace'])}",
        'if ! command -v codex >/dev/null 2>&1; then',
        '  echo "Codex CLI is unavailable. Open this workspace in the ChatGPT desktop app instead." >&2',
        "  exit 1", "fi", "exec codex", "",
    ])


def build_plan(answers: Answers, require_new_workspace: bool = False) -> dict:
    source = package_root()
    validate_answers(answers, source)
    workspace = answers.workspace.expanduser().resolve()
    for forbidden in (Path.home() / ".codex", Path.home() / ".agents"):
        forbidden = forbidden.resolve()
        if workspace == forbidden or _inside(workspace, forbidden):
            raise ValueError(f"workspace must not be inside the user-global {forbidden}")
    if workspace == source or _inside(workspace, source):
        raise ValueError("workspace must be outside the extracted LawyeredOS package")
    if require_new_workspace and workspace.exists() and any(workspace.iterdir()):
        raise ValueError(f"trial workspace must be new or empty: {workspace}")
    setup_root = workspace / ".lawyeredos"
    config = setup_root / "config.toml"
    managed_directories = (
        workspace, setup_root, setup_root / "scratch", setup_root / "data",
        setup_root / "plugins", workspace / ".agents", workspace / ".agents" / "skills",
    )
    for path in managed_directories:
        if path.is_symlink():
            raise ValueError(f"managed Codex directory must not be a symlink: {path}")
        if path.exists() and not path.is_dir():
            raise ValueError(f"managed Codex directory path is not a directory: {path}")
    if config.is_symlink():
        raise ValueError(f"managed config must not be a symlink: {config}")
    effective = answers
    reused = False
    if config.exists():
        if answers.existing_config == "error":
            raise ValueError(f"configuration already exists: {config}")
        if answers.existing_config == "reuse":
            loaded = load_config(config)
            if loaded.workspace_root != workspace:
                raise ValueError("existing configuration belongs to a different workspace")
            effective = Answers(
                workspace=workspace, branding_mode=loaded.branding_mode,
                branding_label=loaded.branding_label, jurisdiction=loaded.jurisdiction_profile,
                modules=tuple(name for name in MODULES if loaded.modules[name]),
                mail_adapter=loaded.mail_adapter, calendar_adapter=loaded.calendar_adapter,
                calendar_id=loaded.calendar_id, existing_config="reuse",
            )
            reused = True
        elif answers.existing_config == "replace":
            raise ValueError(
                "the Codex candidate does not replace an existing config; use reuse or a new workspace"
            )
    elif (setup_root / "data" / "matters.sqlite3").exists():
        raise ValueError("unmanaged tracker data exists without a LawyeredOS config; refusing to overwrite")
    digest = package_digest(source)
    selection = hashlib.sha256(",".join(effective.modules).encode()).hexdigest()
    plugin = setup_root / "plugins" / f"lawyeredos-{VERSION}-{digest[:8]}-{selection[:6]}-codex"
    agents_root = workspace / ".agents" / "skills"
    discovery = setup_root / DISCOVERY_FILE
    prior = {}
    if discovery.is_file():
        prior = json.loads(discovery.read_text(encoding="utf-8"))
    prior_managed = set(prior.get("managed_paths", []))
    project_skills = {module: agents_root / PROJECT_SKILLS[module] for module in effective.modules}
    current = setup_root / CURRENT_LINK
    runner = setup_root / RUNNER_FILE
    launcher = setup_root / "launch-lawyeredos-codex.sh"
    managed_candidates = {*map(str, project_skills.values()), str(current), str(runner), str(launcher)}
    for raw in managed_candidates:
        path = Path(raw)
        if (path.exists() or path.is_symlink()) and raw not in prior_managed:
            raise ValueError(f"Codex discovery/runtime target exists but is not managed by LawyeredOS: {path}")
    runtime = Path(os.path.abspath(sys.executable)).expanduser()
    config_preview = None if reused else render_config(effective, plugin)
    operations = []
    for path in (workspace, setup_root, setup_root / "scratch", setup_root / "data", setup_root / "plugins", agents_root):
        if not path.exists():
            operations.append({"action": "create_directory", "path": str(path)})
    if not plugin.exists():
        operations.append({"action": "install_versioned_core", "path": str(plugin)})
    operations.append({"action": "reuse" if reused else "create_or_replace_config", "path": str(config)})
    for path in project_skills.values():
        operations.append({"action": "install_codex_project_skill", "path": str(path)})
    operations.extend([
        {"action": "link_current_codex_core", "path": str(current)},
        {"action": "write_runtime_wrapper", "path": str(runner)},
        {"action": "write_codex_launcher", "path": str(launcher)},
    ])
    return {
        "schema_version": 1, "host": "codex", "require_new_workspace": require_new_workspace,
        "source": str(source), "workspace": str(workspace), "setup_root": str(setup_root),
        "config": str(config), "plugin": str(plugin), "current": str(current),
        "runner": str(runner), "launcher": str(launcher), "discovery": str(discovery),
        "runtime_python": str(runtime), "package_digest": digest, "selection_digest": selection,
        "project_skills": {module: str(path) for module, path in project_skills.items()},
        "prior_managed": sorted(prior_managed),
        "answers": {**asdict(effective), "workspace": str(workspace), "modules": list(effective.modules)},
        "dependencies": dependency_report(effective.modules), "config_preview": config_preview,
        "operations": operations,
        "notes": [
            "No user-global ~/.codex or ~/.agents files will be changed.",
            "No project .codex/config.toml file will be created or changed.",
            "Existing unrelated project skills are preserved; name collisions fail closed.",
            "Session mail tools are configured, not assumed connected; only a successful bounded read proves availability."
            if effective.mail_adapter == "codex-session-tools" else
            "Email was explicitly skipped; email-dependent workflows will disclose that email was not checked."
            if effective.mail_adapter == "unavailable" else
            "The experimental local Gmail REST adapter requires a separately provisioned gmail.readonly token.",
        ],
    }


def apply_plan(plan: dict) -> dict:
    missing = [item["name"] for item in plan["dependencies"] if item["required"] and not item["available"]]
    if missing:
        raise ValueError(f"required dependencies missing: {', '.join(missing)}")
    workspace = Path(plan["workspace"])
    if plan.get("require_new_workspace") and workspace.exists() and any(workspace.iterdir()):
        raise ValueError(f"trial workspace is no longer empty: {workspace}")
    source, setup_root, plugin = Path(plan["source"]), Path(plan["setup_root"]), Path(plan["plugin"])
    config, current = Path(plan["config"]), Path(plan["current"])
    runner, launcher, discovery = Path(plan["runner"]), Path(plan["launcher"]), Path(plan["discovery"])
    created: list[Path] = []
    replaced_links: list[tuple[Path, str]] = []
    replaced_files: list[tuple[Path, bytes, int]] = []
    changed: list[str] = []
    try:
        for path in (
            workspace, setup_root, setup_root / "scratch", setup_root / "data",
            setup_root / "plugins", workspace / ".agents", workspace / ".agents" / "skills",
        ):
            if not path.exists():
                path.mkdir(parents=True, exist_ok=False)
                created.append(path)
        if not plugin.exists():
            created.append(plugin)
            shutil.copytree(source, plugin, ignore=_ignored)
            selected = set(plan["answers"]["modules"])
            for module, skill in MODULE_SKILLS.items():
                if module not in selected:
                    shutil.rmtree(plugin / "skills" / skill)
            _prepare_payload(plugin, selected)
            (plugin / ".lawyeredos-package.json").write_text(json.dumps({
                "version": VERSION, "digest": plan["package_digest"], "modules": plan["answers"]["modules"],
                "host": "codex",
            }, indent=2) + "\n", encoding="utf-8")
            changed.append(str(plugin))
        marker = plugin / ".lawyeredos-package.json"
        if not marker.is_file() or json.loads(marker.read_text(encoding="utf-8")).get("digest") != plan["package_digest"]:
            raise ValueError(f"installed core does not match this candidate: {plugin}")
        desired = {Path(path) for path in plan["project_skills"].values()}
        desired.update({current, runner, launcher})
        prior_managed = set(plan.get("prior_managed", []))
        stale = [Path(raw) for raw in prior_managed if Path(raw) not in desired and (Path(raw).exists() or Path(raw).is_symlink())]
        if stale:
            raise ValueError(f"managed paths require a separate reviewed migration: {', '.join(map(str, stale))}")

        def install_link(target: Path, destination: Path, label: str) -> None:
            if target.is_symlink() and target.resolve() == destination.resolve():
                return
            if target.is_symlink() and str(target) in prior_managed:
                previous = os.readlink(target)
                target.unlink()
                try:
                    target.symlink_to(destination, target_is_directory=True)
                except Exception:
                    target.symlink_to(previous, target_is_directory=True)
                    raise
                replaced_links.append((target, previous))
                changed.append(str(target))
                return
            if target.exists() or target.is_symlink():
                raise ValueError(f"refusing to overwrite {label}: {target}")
            target.symlink_to(destination, target_is_directory=True)
            created.append(target)
            changed.append(str(target))

        for module, raw in plan["project_skills"].items():
            source_skill = plugin / ".lawyeredos-codex-project" / "skills" / PROJECT_SKILLS[module]
            install_link(Path(raw), source_skill, "project skill")
        install_link(current, plugin, "current core link")
        for path, content in ((runner, render_runner(plan)), (launcher, render_launcher(plan))):
            if path.exists() and path.read_text(encoding="utf-8") != content:
                raise ValueError(f"refusing to overwrite modified managed launcher: {path}")
            if not path.exists():
                created.append(path)
                path.write_text(content, encoding="utf-8")
                path.chmod(0o700)
                changed.append(str(path))
        if plan["config_preview"] is not None:
            if config.exists():
                raise ValueError("Codex candidate does not replace an existing config without a separate reviewed migration")
            created.append(config)
            config.write_text(plan["config_preview"], encoding="utf-8")
            tracker = setup_root / "data" / "matters.sqlite3"
            created.append(tracker)
            initialize(tracker)
            changed.extend([str(config), str(tracker)])
        managed = sorted(str(path) for path in desired)
        discovery_text = json.dumps({
            "schema_version": 1, "host": "codex", "package_digest": plan["package_digest"],
            "managed_paths": managed,
        }, indent=2, sort_keys=True) + "\n"
        if not discovery.exists() or discovery.read_text(encoding="utf-8") != discovery_text:
            if discovery.exists():
                replaced_files.append((discovery, discovery.read_bytes(), discovery.stat().st_mode))
            else:
                created.append(discovery)
            discovery.write_text(discovery_text, encoding="utf-8")
            changed.append(str(discovery))
        with sqlite3.connect(load_config(config).tracker_database) as connection:
            if connection.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                raise ValueError("tracker quick_check failed")
    except BaseException as exc:
        rollback_problems: list[str] = []
        for path, content, mode in reversed(replaced_files):
            try:
                path.write_bytes(content)
                path.chmod(mode)
            except OSError as rollback_exc:
                rollback_problems.append(f"restore {path}: {rollback_exc}")
        for path, previous in reversed(replaced_links):
            try:
                path.unlink(missing_ok=True)
                path.symlink_to(previous, target_is_directory=True)
            except OSError as rollback_exc:
                rollback_problems.append(f"restore {path}: {rollback_exc}")
        for path in reversed(created):
            try:
                if path.is_symlink() or path.is_file():
                    path.unlink(missing_ok=True)
                elif path.is_dir():
                    if path == plugin:
                        shutil.rmtree(path)
                    else:
                        path.rmdir()
            except OSError as rollback_exc:
                rollback_problems.append(f"remove {path}: {rollback_exc}")
        if rollback_problems:
            raise RuntimeError(
                "setup failed and automatic rollback was incomplete: "
                + "; ".join(rollback_problems)
            ) from exc
        raise
    return {"ok": True, "idempotent": not changed, "changed": changed, "workspace": str(workspace),
            "config": str(config), "plugin": str(plugin), "launcher": str(launcher),
            "skills": plan["project_skills"], "discovery": str(discovery)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Preview and apply a project-local LawyeredOS setup for Codex")
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--branding-mode", choices=("neutral", "individual", "firm"), default="neutral")
    parser.add_argument("--branding-label", default="Organization")
    parser.add_argument("--jurisdiction", choices=("none", "ontario"), default="none")
    parser.add_argument("--modules", default=",".join(MODULES))
    parser.add_argument("--mail", choices=("session-tools", "skip", "gmail-readonly"), required=True)
    parser.add_argument("--calendar", choices=("off", "google-calendar"), default="off")
    parser.add_argument("--calendar-id", default="")
    parser.add_argument("--existing-config", choices=("reuse", "error"), default="error")
    parser.add_argument("--require-new-workspace", action="store_true")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--yes", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        answers = normalize_answers(Path(args.workspace), args.branding_mode, args.branding_label,
                                    args.jurisdiction, args.modules, args.mail, args.calendar,
                                    args.calendar_id, args.existing_config)
        plan = build_plan(answers, args.require_new_workspace)
        if not args.apply:
            print(json.dumps(plan, indent=2, sort_keys=True, default=str))
            return 0
        if not args.yes:
            raise ValueError("apply requires --yes after the exact JSON preview was approved")
        print(json.dumps(apply_plan(plan), indent=2, sort_keys=True))
        return 0
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
