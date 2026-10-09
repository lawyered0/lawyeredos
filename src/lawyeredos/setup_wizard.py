from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import platform
import shlex
import shutil
import sqlite3
import sys
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from lawyeredos.config import load_config
from lawyeredos.tracker_cli import initialize


VERSION = "0.2.0"
MODULES = ("matter", "tracker", "letters", "redline", "calendar", "review")
MODULE_SKILLS = {
    "matter": "practice-work-on-matter",
    "tracker": "practice-matter-tracker",
    "letters": "practice-letterhead",
    "redline": "practice-contract-redline",
    "calendar": "practice-calendar-sync",
    "review": "practice-adversarial-panel",
}
PROJECT_SKILLS = {
    "matter": "lawyeredos-work-on-matter",
    "tracker": "lawyeredos-matter-tracker",
    "letters": "lawyeredos-letterhead",
    "redline": "lawyeredos-contract-redline",
    "calendar": "lawyeredos-calendar-sync",
    "review": "lawyeredos-adversarial-panel",
}
PROJECT_AGENT = "lawyeredos-legal-review-lens"
EXCLUDE = {".venv", ".demo", ".git", "__pycache__", ".pytest_cache", "qa"}


@dataclass(frozen=True)
class Answers:
    workspace: Path
    branding_mode: str
    branding_label: str
    jurisdiction: str
    modules: tuple[str, ...]
    mail_adapter: str
    calendar_adapter: str
    calendar_id: str
    existing_config: str


def _inside(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def package_root() -> Path:
    for candidate in Path(__file__).resolve().parents:
        if (candidate / ".claude-plugin" / "plugin.json").is_file():
            return candidate
    raise ValueError(
        "cannot locate the LawyeredOS package root; run the bundled "
        "scripts/setup_wizard.py from an extracted package"
    )


def _ignored(_directory: str, names: list[str]) -> set[str]:
    return {name for name in names if name in EXCLUDE or name.endswith((".pyc", ".egg-info"))}


def package_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if not path.is_file() or any(part in EXCLUDE for part in path.relative_to(root).parts):
            continue
        if path.name.endswith((".pyc", ".egg-info")):
            continue
        relative = path.relative_to(root).as_posix().encode()
        digest.update(len(relative).to_bytes(4, "big"))
        digest.update(relative)
        content = path.read_bytes()
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)
    return digest.hexdigest()


def managed_fingerprint(path: Path) -> str:
    """Hash a managed file or directory without following symlinks."""
    digest = hashlib.sha256()
    if path.is_symlink():
        digest.update(b"symlink\0")
        digest.update(os.readlink(path).encode())
        return digest.hexdigest()
    if path.is_file():
        digest.update(b"file\0")
        digest.update(path.read_bytes())
        return digest.hexdigest()
    if not path.is_dir():
        raise ValueError(f"managed path is unavailable: {path}")
    digest.update(b"directory\0")
    for item in sorted(path.rglob("*")):
        relative_path = item.relative_to(path)
        if any(part in EXCLUDE for part in relative_path.parts):
            continue
        if item.name.endswith((".pyc", ".pyo", ".egg-info")):
            continue
        relative = relative_path.as_posix().encode()
        if item.is_symlink():
            raise ValueError(f"managed directory contains a symlink: {item}")
        if not item.is_file():
            continue
        digest.update(len(relative).to_bytes(4, "big"))
        digest.update(relative)
        content = item.read_bytes()
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)
    return digest.hexdigest()


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
        "lawyeredos:legal-review-lens": PROJECT_AGENT,
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    text = text.replace(f"name: {project_name.replace('lawyeredos-', 'practice-', 1)}", f"name: {project_name}")
    skill_path.write_text(text, encoding="utf-8")


def _prepare_project_payload(plugin: Path, modules: set[str]) -> Path:
    root = plugin / ".lawyeredos-project"
    skills_root = root / "skills"
    skills_root.mkdir(parents=True)
    for module in modules:
        source_name = MODULE_SKILLS[module]
        project_name = PROJECT_SKILLS[module]
        _projectize_skill(plugin / "skills" / source_name, skills_root / project_name, project_name)
    if "review" in modules:
        agents_root = root / "agents"
        agents_root.mkdir(parents=True)
        agent_text = (plugin / "agents" / "legal-review-lens.md").read_text(encoding="utf-8")
        agent_text = agent_text.replace("name: legal-review-lens", f"name: {PROJECT_AGENT}", 1)
        (agents_root / f"{PROJECT_AGENT}.md").write_text(agent_text, encoding="utf-8")
    return root


def dependency_report(modules: tuple[str, ...] = ()) -> list[dict[str, str | bool]]:
    checks: list[dict[str, str | bool]] = []
    selected = set(modules)
    python_ok = sys.version_info >= (3, 11)
    checks.append({
        "name": "Python 3.11+", "required": True, "available": python_ok,
        "detail": platform.python_version(),
        "fix": "Install Python 3.11 or newer, then rerun this wizard.",
    })
    for module, label, fix, required in (
        ("openpyxl", "openpyxl", "Install openpyxl to enable the optional XLSX tracker projection.", False),
        ("docx", "python-docx", "Install requirements-documents.txt to enable selected letters or redlines.", bool(selected & {"letters", "redline"})),
        ("lxml", "lxml", "Install requirements-documents.txt to enable the selected redline module.", "redline" in selected),
        ("fpdf", "fpdf2", "Install requirements-documents.txt to enable the selected redline module.", "redline" in selected),
    ):
        checks.append({
            "name": label, "required": required,
            "available": importlib.util.find_spec(module) is not None,
            "detail": "Python module", "fix": fix,
        })
    desktop_candidates = (
        Path("/Applications/Claude.app"),
        Path.home() / "Applications" / "Claude.app",
    )
    desktop = next((path for path in desktop_candidates if path.is_dir()), None)
    checks.append({
        "name": "Claude Desktop", "required": True,
        "available": desktop is not None,
        "detail": str(desktop) if desktop else "application not found",
        "fix": "Install or update the Claude desktop app for macOS.",
    })
    for commands, label, fix in (
        (("claude",), "Terminal Claude Code", "Install Claude Code only if the optional terminal fallback is needed."),
        (("libreoffice", "soffice"), "LibreOffice", "Install LibreOffice to enable visual DOCX rendering."),
        (("pdftoppm",), "Poppler", "Install Poppler to enable PDF page-image rendering."),
        (("ocrmypdf",), "OCRmyPDF", "Install OCRmyPDF and its platform dependencies to enable OCR."),
    ):
        found = next((shutil.which(command) for command in commands if shutil.which(command)), None)
        checks.append({
            "name": label, "required": False, "available": found is not None,
            "detail": found or "command not found", "fix": fix,
        })
    return checks


def validate_answers(answers: Answers, source: Path) -> None:
    if answers.branding_mode not in {"neutral", "individual", "firm"}:
        raise ValueError("branding mode must be neutral, individual, or firm")
    if answers.jurisdiction not in {"none", "ontario"}:
        raise ValueError("jurisdiction must be none or ontario")
    if answers.existing_config not in {"reuse", "replace", "error"}:
        raise ValueError("existing-config must be reuse, replace, or error")
    unknown = sorted(set(answers.modules) - set(MODULES))
    if unknown:
        raise ValueError(f"unknown modules: {', '.join(unknown)}")
    if not {"matter", "tracker"}.issubset(answers.modules):
        raise ValueError("matter and tracker are required core modules")
    if answers.mail_adapter not in {
        "unavailable", "claude-gmail-connector", "codex-session-tools", "gmail-api-readonly",
    }:
        raise ValueError(
            "mail adapter must be unavailable, claude-gmail-connector, codex-session-tools, "
            "or gmail-api-readonly"
        )
    if answers.calendar_adapter not in {"unavailable", "google-calendar-api"}:
        raise ValueError("calendar adapter must be unavailable or google-calendar-api")
    if answers.calendar_adapter == "google-calendar-api":
        if not answers.calendar_id or answers.calendar_id == "primary":
            raise ValueError("Google Calendar requires an exact dedicated calendar ID; primary is refused")
        if "calendar" not in answers.modules:
            raise ValueError("enable the calendar module before selecting its integration")
    workspace = answers.workspace.expanduser().resolve()
    if workspace.exists() and not workspace.is_dir():
        raise ValueError(f"workspace exists but is not a directory: {workspace}")
    setup_root = workspace / ".lawyeredos"
    if _inside(setup_root, source):
        raise ValueError("workspace cannot place the managed setup inside the source package")


def _toml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def render_config(answers: Answers, plugin_target: Path) -> str:
    workspace = answers.workspace.expanduser().resolve()
    setup_root = workspace / ".lawyeredos"
    enabled = set(answers.modules)
    label = answers.branding_label.strip() or {
        "neutral": "Organization",
        "individual": "Independent practice",
        "firm": "Organization",
    }[answers.branding_mode]
    lines = [
        "# Generated by LawyeredOS setup. Keep this file private and outside the plugin.",
        "# Credentials belong only in the named environment variables, never here.",
        "schema_version = 1", "", "[workspace]",
        f"root = {_toml_string(str(workspace))}",
        f"scratch = {_toml_string(str(setup_root / 'scratch'))}",
        'timezone = "UTC"', "", "[tracker]",
        f"database = {_toml_string(str(setup_root / 'data' / 'matters.sqlite3'))}",
        "", "[documents]",
        f"template = {_toml_string(str(plugin_target / 'assets' / 'neutral-letterhead.docx'))}",
        'author = "Authorized reviewer"', "", "[branding]",
        f"mode = {_toml_string(answers.branding_mode)}",
        f"label = {_toml_string(label)}", "", "[jurisdiction]",
        f"profile = {_toml_string(answers.jurisdiction)}",
        "# Profiles define workflow boundaries only; they do not bundle current legal advice.",
        "", "[modules]",
    ]
    lines.extend(f"{name} = {'true' if name in enabled else 'false'}" for name in MODULES)
    lines.extend([
        "", "[integrations]",
        f"mail_adapter = {_toml_string(answers.mail_adapter)}",
        f"calendar_adapter = {_toml_string(answers.calendar_adapter)}",
        'practice_manager_adapter = "unavailable"',
        "# Host session connectors/tools are user-authorized; setup cannot verify session access.",
        "# gmail-api-readonly and the live Calendar adapter are experimental and not live-account accepted.",
        "", "[credentials]",
        'gmail_token_env = "LAWYEREDOS_GMAIL_TOKEN"',
        'calendar_token_env = "LAWYEREDOS_CALENDAR_TOKEN"',
        "", "[calendar]",
        f"calendar_id = {_toml_string(answers.calendar_id)}",
        'api_base = "https://www.googleapis.com/calendar/v3"',
        "", "[review]", "external_ai = false", "",
    ])
    return "\n".join(lines)


def build_plan(answers: Answers, require_new_workspace: bool = False) -> dict:
    source = package_root()
    validate_answers(answers, source)
    workspace = answers.workspace.expanduser().resolve()
    global_claude = (Path.home() / ".claude").resolve()
    if workspace == global_claude or _inside(workspace, global_claude):
        raise ValueError("workspace must not be the user-global ~/.claude directory")
    if workspace == source or _inside(workspace, source):
        raise ValueError("workspace must be outside the extracted LawyeredOS package")
    if require_new_workspace and workspace.exists() and any(workspace.iterdir()):
        raise ValueError(f"trial workspace must be new or empty: {workspace}")
    setup_root = workspace / ".lawyeredos"
    config_path = setup_root / "config.toml"
    config_exists = config_path.exists()
    effective = answers
    reused_existing = False
    if config_exists and answers.existing_config == "error":
        raise ValueError(f"configuration already exists: {config_path}")
    if config_exists and answers.existing_config == "reuse":
        loaded = load_config(config_path)
        if loaded.workspace_root != workspace:
            raise ValueError(
                "existing configuration belongs to a different workspace; "
                "choose that workspace or use --existing-config replace"
            )
        effective = Answers(
            workspace=workspace,
            branding_mode=loaded.branding_mode,
            branding_label=loaded.branding_label,
            jurisdiction=loaded.jurisdiction_profile,
            modules=tuple(name for name in MODULES if loaded.modules[name]),
            mail_adapter=loaded.mail_adapter,
            calendar_adapter=loaded.calendar_adapter,
            calendar_id=loaded.calendar_id,
            existing_config="reuse",
        )
        reused_existing = True
    digest = package_digest(source)
    selection_digest = hashlib.sha256(",".join(effective.modules).encode()).hexdigest()
    plugin_target = setup_root / "plugins" / f"lawyeredos-{VERSION}-{digest[:8]}-{selection_digest[:6]}"
    launcher = setup_root / "launch-lawyeredos.sh"
    terminal_launcher = setup_root / "launch-lawyeredos-terminal.sh"
    claude_root = workspace / ".claude"
    managed_directories = (
        setup_root,
        setup_root / "scratch",
        setup_root / "data",
        setup_root / "plugins",
        setup_root / "backups",
        claude_root,
        claude_root / "skills",
        claude_root / "agents",
    )
    for path in managed_directories:
        if path.is_symlink():
            raise ValueError(f"managed directory must not be a symlink: {path}")
        if path.exists() and not path.is_dir():
            raise ValueError(f"managed directory path is not a directory: {path}")
    for path in (config_path, launcher, terminal_launcher, setup_root / "project-discovery.json"):
        if path.is_symlink():
            raise ValueError(f"managed file must not be a symlink: {path}")
    project_skill_paths = {
        module: claude_root / "skills" / PROJECT_SKILLS[module]
        for module in effective.modules
    }
    project_agent = claude_root / "agents" / f"{PROJECT_AGENT}.md"
    settings_local = claude_root / "settings.local.json"
    if settings_local.is_symlink():
        raise ValueError(f"Claude project settings must not be a symlink: {settings_local}")
    discovery_state = setup_root / "project-discovery.json"
    prior_discovery = {}
    if discovery_state.is_file():
        prior_discovery = json.loads(discovery_state.read_text(encoding="utf-8"))
    prior_managed = set(prior_discovery.get("managed_paths", []))
    candidate_paths = set(str(path) for path in project_skill_paths.values())
    if "review" in effective.modules:
        candidate_paths.add(str(project_agent))
    for path in candidate_paths:
        candidate = Path(path)
        if (candidate.exists() or candidate.is_symlink()) and path not in prior_managed:
            raise ValueError(f"project discovery target exists but is not managed by LawyeredOS: {candidate}")
    if settings_local.is_file():
        settings_data = json.loads(settings_local.read_text(encoding="utf-8"))
        if not isinstance(settings_data, dict):
            raise ValueError(f"Claude project settings must contain a JSON object: {settings_local}")
        if "env" in settings_data and not isinstance(settings_data["env"], dict):
            raise ValueError(f"Claude project settings env must contain a JSON object: {settings_local}")
        managed_env = {"LAWYEREDOS_ROOT", "LAWYEREDOS_CONFIG", "LAWYEREDOS_PYTHON"}
        if managed_env.intersection(settings_data.get("env", {})) and not prior_discovery:
            raise ValueError("Claude project settings already define LawyeredOS variables without managed state")
    # Preserve the virtual-environment entrypoint itself. Resolving the final
    # symlink would bypass pyvenv.cfg and lose the packages checked above.
    runtime_python = Path(os.path.abspath(sys.executable)).expanduser()
    operations = []
    if not workspace.exists():
        operations.append({"action": "create_directory", "path": str(workspace)})
    for path in (setup_root / "scratch", setup_root / "data", setup_root / "plugins", setup_root / "backups"):
        if not path.exists():
            operations.append({"action": "create_directory", "path": str(path)})
    if not plugin_target.exists():
        operations.append({"action": "install_versioned_plugin", "path": str(plugin_target)})
    config_action = "reuse" if config_exists and answers.existing_config == "reuse" else ("replace_with_backup" if config_exists else "create")
    operations.append({"action": config_action, "path": str(config_path)})
    tracker = setup_root / "data" / "matters.sqlite3"
    if not tracker.exists() and config_action != "reuse":
        operations.append({"action": "initialize_empty_tracker", "path": str(tracker)})
    operations.append({"action": "create_or_update_launcher_with_backup", "path": str(launcher)})
    operations.append({"action": "create_or_update_terminal_launcher_with_backup", "path": str(terminal_launcher)})
    for path in project_skill_paths.values():
        operations.append({"action": "install_project_skill", "path": str(path)})
    if "review" in effective.modules:
        operations.append({"action": "install_project_agent", "path": str(project_agent)})
    operations.append({"action": "merge_project_local_environment", "path": str(settings_local)})
    return {
        "schema_version": 1,
        "require_new_workspace": require_new_workspace,
        "package_version": VERSION,
        "package_digest": digest,
        "selection_digest": selection_digest,
        "source": str(source),
        "workspace": str(workspace),
        "setup_root": str(setup_root),
        "config": str(config_path),
        "plugin": str(plugin_target),
        "launcher": str(launcher),
        "terminal_launcher": str(terminal_launcher),
        "project_skills": {module: str(path) for module, path in project_skill_paths.items()},
        "project_agent": str(project_agent) if "review" in effective.modules else "",
        "settings_local": str(settings_local),
        "discovery_state": str(discovery_state),
        "prior_managed": sorted(prior_managed),
        "runtime_python": str(runtime_python),
        "answers": {**asdict(effective), "workspace": str(workspace), "modules": list(effective.modules)},
        "dependencies": dependency_report(effective.modules),
        "operations": operations,
        "config_preview": None if config_action == "reuse" else render_config(effective, plugin_target),
        "notes": [
            "No global Claude settings will be changed.",
            "No credentials or token values will be collected or written.",
            (
                "Gmail connector selected: authorization stays in Claude/Google and is verified only by a successful bounded read in the active session."
                if effective.mail_adapter == "claude-gmail-connector"
                else "Codex session tools selected: setup stores no credential and only a successful bounded read in the active session proves availability."
                if effective.mail_adapter == "codex-session-tools"
                else "Gmail was explicitly skipped; email-dependent workflows will disclose that email was not checked."
                if effective.mail_adapter == "unavailable"
                else "Experimental Gmail REST adapter selected: it requires a separately provisioned gmail.readonly token in the named environment variable."
            ),
            "LawyeredOS never treats mail access as authority to send, reply, forward, label, archive, or delete.",
            "The live Google Calendar adapter remains optional and experimental.",
            "The installed plugin is versioned; private configuration and data remain outside it.",
            "The launcher records the Python interpreter used for setup so the installed dependencies remain available at runtime.",
            *( ["Existing configuration governs branding, modules, jurisdiction, and integrations for this run."] if reused_existing else [] ),
        ],
    }


def render_launcher(plan: dict) -> str:
    workspace = shlex.quote(plan["workspace"])
    runtime_python = shlex.quote(plan["runtime_python"])
    return "\n".join([
        "#!/bin/sh", "set -eu",
        f"if [ ! -x {runtime_python} ]; then",
        '  echo "LawyeredOS runtime is unavailable. Restore the setup virtual environment or rerun the wizard from a retained package copy." >&2',
        "  exit 1",
        "fi",
        'if [ ! -d "/Applications/Claude.app" ] && [ ! -d "$HOME/Applications/Claude.app" ]; then',
        '  echo "Claude Desktop is unavailable. Install it, then rerun this launcher." >&2',
        "  exit 1",
        "fi",
        f"exec open -a Claude {workspace}", "",
    ])


def render_terminal_launcher(plan: dict) -> str:
    workspace = shlex.quote(plan["workspace"])
    runtime_python = shlex.quote(plan["runtime_python"])
    return "\n".join([
        "#!/bin/sh", "set -eu",
        f"if [ ! -x {runtime_python} ]; then",
        '  echo "LawyeredOS runtime is unavailable. Restore the setup virtual environment or rerun the wizard from a retained package copy." >&2',
        "  exit 1",
        "fi",
        'if ! command -v claude >/dev/null 2>&1; then',
        '  echo "Terminal Claude Code is unavailable. Use the Desktop launcher or install the optional CLI." >&2',
        "  exit 1",
        "fi",
        f"cd {workspace}",
        "exec claude", "",
    ])


def print_preview(plan: dict) -> None:
    print("\nLawyeredOS setup preview")
    print("=" * 26)
    print(f"Workspace: {plan['workspace']}")
    print(f"Config:    {plan['config']}")
    print(f"Plugin:    {plan['plugin']}")
    print(f"Launcher:  {plan['launcher']}")
    print(f"Terminal:  {plan['terminal_launcher']}")
    print(f"Runtime:   {plan['runtime_python']}")
    print("\nOperations:")
    for operation in plan["operations"]:
        print(f"  - {operation['action']}: {operation['path']}")
    print("\nDependency checks:")
    for check in plan["dependencies"]:
        status = "OK" if check["available"] else ("MISSING (required)" if check["required"] else "missing (optional)")
        print(f"  - {check['name']}: {status} — {check['detail']}")
        if not check["available"]:
            print(f"    Fix: {check['fix']}")
    if plan["config_preview"] is not None:
        print("\nExact configuration to write:\n")
        print(plan["config_preview"])
    else:
        print("\nExisting configuration will be reused byte-for-byte.")
    print("\nNo changes have been made.")


def _backup(path: Path, backup_root: Path, backups: list[dict[str, str]]) -> None:
    if not path.exists() and not path.is_symlink():
        return
    backup_root.mkdir(parents=True, exist_ok=True)
    destination = backup_root / path.name
    counter = 1
    while destination.exists():
        destination = backup_root / f"{path.name}.{counter}"
        counter += 1
    if path.is_symlink():
        destination = destination.with_name(destination.name + ".symlink")
        destination.write_text(os.readlink(path), encoding="utf-8")
        kind = "symlink"
    elif path.is_dir():
        shutil.copytree(path, destination)
        kind = "directory"
    else:
        shutil.copy2(path, destination)
        kind = "file"
    backups.append({"original": str(path), "backup": str(destination), "kind": kind})


def apply_plan(plan: dict) -> dict:
    required_missing = [item["name"] for item in plan["dependencies"] if item["required"] and not item["available"]]
    if required_missing:
        raise ValueError(f"required dependencies missing: {', '.join(required_missing)}")
    source = Path(plan["source"])
    workspace = Path(plan["workspace"])
    if plan.get("require_new_workspace") and workspace.exists() and any(workspace.iterdir()):
        raise ValueError(f"trial workspace is no longer empty: {workspace}")
    setup_root = Path(plan["setup_root"])
    plugin = Path(plan["plugin"])
    config = Path(plan["config"])
    launcher = Path(plan["launcher"])
    terminal_launcher = Path(plan["terminal_launcher"])
    settings_local = Path(plan["settings_local"])
    discovery_state = Path(plan["discovery_state"])
    tracker = setup_root / "data" / "matters.sqlite3"
    if workspace.exists() and not workspace.is_dir():
        raise ValueError(f"workspace exists but is not a directory: {workspace}")
    marker = plugin / ".lawyeredos-package.json"
    if plugin.exists() and (
        not marker.is_file()
        or json.loads(marker.read_text(encoding="utf-8")).get("digest") != plan["package_digest"]
        or json.loads(marker.read_text(encoding="utf-8")).get("modules") != plan["answers"]["modules"]
    ):
        raise ValueError(f"plugin target exists but does not match this build: {plugin}")
    if plan["config_preview"] is None:
        loaded_existing = load_config(config)
        if not loaded_existing.tracker_database.is_file():
            raise ValueError(
                "existing configuration points to a missing tracker database; "
                "repair it or choose --existing-config replace"
            )
    transaction_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%S.%fZ")
    backup_root = setup_root / "backups" / transaction_id
    created: list[str] = []
    backups: list[dict[str, str]] = []
    changed: list[str] = []
    workspace.mkdir(parents=True, exist_ok=True)
    for directory in (
        setup_root / "scratch", setup_root / "data", setup_root / "plugins", setup_root / "backups",
        workspace / ".claude", workspace / ".claude" / "skills", workspace / ".claude" / "agents",
    ):
        if not directory.exists():
            directory.mkdir(parents=True)
            created.append(str(directory))
    if plugin.exists():
        pass
    else:
        shutil.copytree(source, plugin, ignore=_ignored)
        selected = set(plan["answers"]["modules"])
        for module, skill in MODULE_SKILLS.items():
            if module not in selected:
                shutil.rmtree(plugin / "skills" / skill)
        if "review" not in selected:
            shutil.rmtree(plugin / "agents")
        _prepare_project_payload(plugin, selected)
        marker.write_text(json.dumps({
            "version": VERSION, "digest": plan["package_digest"],
            "modules": plan["answers"]["modules"],
        }, indent=2) + "\n", encoding="utf-8")
        created.append(str(plugin))
        changed.append(str(plugin))

    project_paths = {Path(path) for path in plan["project_skills"].values()}
    if plan["project_agent"]:
        project_paths.add(Path(plan["project_agent"]))
    for raw in plan.get("prior_managed", []):
        path = Path(raw)
        if path in project_paths or (not path.exists() and not path.is_symlink()):
            continue
        _backup(path, backup_root, backups)
        if path.is_dir() and not path.is_symlink():
            shutil.rmtree(path)
        else:
            path.unlink()
    for module, raw in plan["project_skills"].items():
        target = Path(raw)
        source_skill = plugin / ".lawyeredos-project" / "skills" / PROJECT_SKILLS[module]
        if target.is_symlink() and Path(os.readlink(target)) == source_skill:
            continue
        if target.exists() or target.is_symlink():
            _backup(target, backup_root, backups)
            if target.is_dir() and not target.is_symlink():
                shutil.rmtree(target)
            else:
                target.unlink()
        else:
            created.append(str(target))
        target.symlink_to(source_skill, target_is_directory=True)
        changed.append(str(target))
    if plan["project_agent"]:
        target = Path(plan["project_agent"])
        source_agent = plugin / ".lawyeredos-project" / "agents" / f"{PROJECT_AGENT}.md"
        if target.is_file() and target.read_bytes() == source_agent.read_bytes():
            source_agent = None
        if source_agent is None:
            pass
        elif target.exists() or target.is_symlink():
            _backup(target, backup_root, backups)
            shutil.copy2(source_agent, target)
            changed.append(str(target))
        else:
            created.append(str(target))
            shutil.copy2(source_agent, target)
            changed.append(str(target))

    settings = {}
    settings_existed = settings_local.is_file()
    if settings_existed:
        settings = json.loads(settings_local.read_text(encoding="utf-8"))
    env = settings.setdefault("env", {})
    env.update({
        "LAWYEREDOS_ROOT": str(plugin),
        "LAWYEREDOS_CONFIG": str(config),
        "LAWYEREDOS_PYTHON": plan["runtime_python"],
    })
    settings_text = json.dumps(settings, indent=2, sort_keys=True) + "\n"
    if not settings_existed or settings_local.read_text(encoding="utf-8") != settings_text:
        if settings_existed:
            _backup(settings_local, backup_root, backups)
        else:
            created.append(str(settings_local))
        settings_local.write_text(settings_text, encoding="utf-8")
        changed.append(str(settings_local))

    discovery = {
        "schema_version": 1,
        "package_digest": plan["package_digest"],
        "managed_paths": sorted(str(path) for path in project_paths),
    }
    discovery_text = json.dumps(discovery, indent=2, sort_keys=True) + "\n"
    if not discovery_state.exists() or discovery_state.read_text(encoding="utf-8") != discovery_text:
        if discovery_state.exists():
            _backup(discovery_state, backup_root, backups)
        else:
            created.append(str(discovery_state))
        discovery_state.write_text(discovery_text, encoding="utf-8")
        changed.append(str(discovery_state))
    if plan["config_preview"] is not None:
        if config.exists():
            _backup(config, backup_root, backups)
        else:
            created.append(str(config))
        new_config = plan["config_preview"]
        if not config.exists() or config.read_text(encoding="utf-8") != new_config:
            config.write_text(new_config, encoding="utf-8")
            changed.append(str(config))
        if not tracker.exists():
            initialize(tracker)
            created.append(str(tracker))
            changed.append(str(tracker))
    launcher_text = render_launcher(plan)
    if launcher.exists() and launcher.read_text(encoding="utf-8") != launcher_text:
        _backup(launcher, backup_root, backups)
    elif not launcher.exists():
        created.append(str(launcher))
    if not launcher.exists() or launcher.read_text(encoding="utf-8") != launcher_text:
        launcher.write_text(launcher_text, encoding="utf-8")
        launcher.chmod(0o700)
        changed.append(str(launcher))
    terminal_text = render_terminal_launcher(plan)
    if terminal_launcher.exists() and terminal_launcher.read_text(encoding="utf-8") != terminal_text:
        _backup(terminal_launcher, backup_root, backups)
    elif not terminal_launcher.exists():
        created.append(str(terminal_launcher))
    if not terminal_launcher.exists() or terminal_launcher.read_text(encoding="utf-8") != terminal_text:
        terminal_launcher.write_text(terminal_text, encoding="utf-8")
        terminal_launcher.chmod(0o700)
        changed.append(str(terminal_launcher))
    state_path = setup_root / "setup-state.json"
    if changed or backups:
        fingerprint_targets = {
            *(Path(raw) for raw in changed),
            *(Path(raw) for raw in created if Path(raw).is_file() or Path(raw).is_symlink()),
            plugin,
        }
        state = {
            "schema_version": 1, "transaction_id": transaction_id,
            "package_version": VERSION, "package_digest": plan["package_digest"],
            "selection_digest": plan["selection_digest"],
            "created": created, "backups": backups, "changed": changed,
            "managed_fingerprints": {
                str(path): managed_fingerprint(path)
                for path in sorted(fingerprint_targets)
                if path.exists()
            },
            "config": str(config), "plugin": str(plugin), "launcher": str(launcher),
            "terminal_launcher": str(terminal_launcher),
        }
        state_path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    loaded = load_config(config)
    with sqlite3.connect(loaded.tracker_database) as connection:
        connection.execute("PRAGMA quick_check").fetchone()
    return {
        "ok": True, "idempotent": not changed and not backups,
        "changed": changed, "config": str(config), "plugin": str(plugin),
        "launcher": str(launcher), "runtime_python": plan["runtime_python"],
        "terminal_launcher": str(terminal_launcher),
        "rollback_state": str(state_path),
    }


def rollback(workspace: Path) -> dict:
    workspace = workspace.expanduser().resolve()
    setup_root = workspace / ".lawyeredos"
    state_path = setup_root / "setup-state.json"
    if not state_path.is_file():
        raise ValueError(f"no rollback state found: {state_path}")
    state = json.loads(state_path.read_text(encoding="utf-8"))
    restored: list[str] = []
    removed: list[str] = []
    preserved_modified: list[str] = []
    fingerprints = state.get("managed_fingerprints", {})

    def unchanged(path: Path) -> bool:
        expected = fingerprints.get(str(path))
        if expected is None or not path.exists():
            return False
        try:
            return managed_fingerprint(path) == expected
        except (OSError, ValueError):
            return False

    # Rollback is deliberately atomic. Once any managed artifact differs from
    # the applied transaction, another managed artifact may depend on it (for
    # example, the tracker depends on the generated config and launcher). A
    # partial rollback could strand user data or make it harder to reopen, so
    # refuse the entire operation before changing anything.
    if fingerprints:
        preserved_modified = sorted(
            path for path in fingerprints if not unchanged(Path(path))
        )
    else:
        # Older state files cannot prove that managed artifacts are unchanged.
        # Fail closed and leave the complete setup in place.
        preserved_modified = sorted({
            *state.get("changed", []),
            state.get("config", ""),
            state.get("plugin", ""),
            state.get("launcher", ""),
            state.get("terminal_launcher", ""),
        } - {""})
    if preserved_modified:
        return {
            "ok": False,
            "status": "modified_managed_state",
            "restored": [],
            "removed": [],
            "preserved_modified": preserved_modified,
            "state": str(state_path),
        }

    for item in state.get("backups", []):
        original = Path(item["original"])
        backup = Path(item["backup"])
        if not (_inside(original.absolute(), setup_root) or _inside(original.absolute(), workspace / ".claude")):
            continue
        if original.exists() and not unchanged(original):
            preserved_modified.append(str(original))
            continue
        kind = item.get("kind", "file")
        if backup.exists():
            if original.exists() or original.is_symlink():
                if original.is_dir() and not original.is_symlink():
                    shutil.rmtree(original)
                else:
                    original.unlink()
            original.parent.mkdir(parents=True, exist_ok=True)
            if kind == "directory":
                shutil.copytree(backup, original)
            elif kind == "symlink":
                original.symlink_to(backup.read_text(encoding="utf-8"), target_is_directory=True)
            else:
                shutil.copy2(backup, original)
            restored.append(str(original))
    backup_originals = {item["original"] for item in state.get("backups", [])}
    for raw in reversed(state.get("created", [])):
        path = Path(raw)
        if not (_inside(path.absolute(), setup_root) or _inside(path.absolute(), workspace / ".claude")) or str(path) in backup_originals:
            continue
        if path.is_file() or path.is_symlink():
            if not unchanged(path):
                preserved_modified.append(str(path))
                continue
            path.unlink()
            removed.append(str(path))
        elif path.is_dir():
            if path.name.startswith("lawyeredos-") and path.parent == setup_root / "plugins":
                if not unchanged(path):
                    preserved_modified.append(str(path))
                    continue
                shutil.rmtree(path)
                removed.append(str(path))
            else:
                try:
                    path.rmdir()
                    removed.append(str(path))
                except OSError:
                    pass
    state["rolled_back_at"] = datetime.now(UTC).isoformat()
    state_path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {
        "ok": True,
        "restored": restored,
        "removed": removed,
        "preserved_modified": sorted(set(preserved_modified)),
        "state": str(state_path),
    }


def _ask(prompt: str, default: str) -> str:
    value = input(f"{prompt} [{default}]: ").strip()
    return value or default


def _ask_required_choice(prompt: str, choices: tuple[str, ...]) -> str:
    allowed = "/".join(choices)
    while True:
        value = input(f"{prompt} ({allowed}): ").strip().lower()
        if value in choices:
            return value
        print(f"Choose one of: {', '.join(choices)}. No mail choice is applied by default.")


def interactive_answers(args: argparse.Namespace) -> Answers:
    print("LawyeredOS guided setup for Claude Code inside the Claude desktop app")
    print("No global Claude settings or credentials will be changed.\n")
    workspace = Path(args.workspace or _ask("Project workspace path", str(Path.cwd() / "lawyeredos-workspace")))
    branding_mode = args.branding_mode or _ask("Branding mode (neutral/individual/firm)", "neutral")
    branding_label = args.branding_label
    if branding_label is None:
        branding_label = _ask("Local display label (no address, email, logo, or signature)", "Organization")
    jurisdiction = args.jurisdiction or _ask("Jurisdiction profile (none/ontario)", "none")
    modules_raw = args.modules or _ask("Modules (comma separated)", ",".join(MODULES))
    if args.mail:
        mail = args.mail
    else:
        print("\nChoose how LawyeredOS should handle email:")
        print("  claude-gmail  Connect Gmail in Claude with Google's consent screen; setup stores no credential.")
        print("                 The setup can record this choice but cannot verify the active session connection.")
        print("  skip           Continue safely without email; workflows will say email was not checked.")
        print("  gmail-readonly Experimental local REST adapter using a separately provisioned gmail.readonly token.")
        print("                 It has only fake-transport acceptance and no live-account acceptance.")
        mail = _ask_required_choice("Mail choice", ("claude-gmail", "skip", "gmail-readonly"))
    calendar = args.calendar or _ask("Calendar integration (off/google-calendar experimental)", "off")
    calendar_id = args.calendar_id or ""
    if calendar == "google-calendar" and not calendar_id:
        calendar_id = _ask("Exact dedicated Google Calendar ID (not primary)", "")
    existing = args.existing_config or _ask("Existing config handling (reuse/replace/error)", "reuse")
    return normalize_answers(workspace, branding_mode, branding_label, jurisdiction, modules_raw, mail, calendar, calendar_id, existing)


def normalize_answers(workspace: Path, branding_mode: str, branding_label: str, jurisdiction: str,
                      modules_raw: str, mail: str, calendar: str, calendar_id: str,
                      existing: str) -> Answers:
    modules = tuple(dict.fromkeys(item.strip() for item in modules_raw.split(",") if item.strip()))
    return Answers(
        workspace=workspace.expanduser().resolve(), branding_mode=branding_mode.strip().lower(),
        branding_label=branding_label.strip(), jurisdiction=jurisdiction.strip().lower(),
        modules=modules,
        mail_adapter={
            "off": "unavailable",  # accepted for older scripted invocations
            "skip": "unavailable",
            "claude-gmail": "claude-gmail-connector",
            "gmail-readonly": "gmail-api-readonly",
        }.get(mail, mail),
        calendar_adapter={"off": "unavailable", "google-calendar": "google-calendar-api"}.get(calendar, calendar),
        calendar_id=calendar_id.strip(), existing_config=existing.strip().lower(),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Preview and apply a project-local LawyeredOS setup")
    parser.add_argument("--workspace")
    parser.add_argument("--branding-mode", choices=("neutral", "individual", "firm"))
    parser.add_argument("--branding-label")
    parser.add_argument("--jurisdiction", choices=("none", "ontario"))
    parser.add_argument("--modules")
    parser.add_argument(
        "--mail", choices=("claude-gmail", "skip", "gmail-readonly", "off"),
        help="required explicit mail choice; 'off' is retained only for older scripted invocations",
    )
    parser.add_argument("--calendar", choices=("off", "google-calendar"))
    parser.add_argument("--calendar-id", default="")
    parser.add_argument("--existing-config", choices=("reuse", "replace", "error"))
    parser.add_argument(
        "--require-new-workspace", action="store_true",
        help="refuse a trial target that already contains any files",
    )
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--yes", action="store_true", help="accept the preview without the APPLY prompt")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--rollback", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.rollback:
            if not args.workspace:
                raise ValueError("--rollback requires --workspace")
            result = rollback(Path(args.workspace))
            print(json.dumps(result, indent=2, sort_keys=True))
            return 0
        fully_supplied = all((args.workspace, args.branding_mode, args.branding_label is not None,
                              args.jurisdiction, args.modules, args.mail, args.calendar,
                              args.existing_config))
        answers = (
            normalize_answers(Path(args.workspace), args.branding_mode, args.branding_label,
                              args.jurisdiction, args.modules, args.mail, args.calendar,
                              args.calendar_id, args.existing_config)
            if fully_supplied else interactive_answers(args)
        )
        plan = build_plan(answers, require_new_workspace=args.require_new_workspace)
        if args.json:
            print(json.dumps(plan, indent=2, sort_keys=True))
        else:
            print_preview(plan)
        if not args.apply:
            return 0
        if not args.yes and input("\nType APPLY to make exactly these changes, or press Enter to cancel: ").strip() != "APPLY":
            print("Cancelled; no changes were made.")
            return 1
        result = apply_plan(plan)
        if args.json:
            print(json.dumps(result, indent=2, sort_keys=True))
        else:
            print("\nSetup complete")
            print("==============")
            print(f"Desktop launch: {result['launcher']}")
            print(f"Optional terminal launch: {result['terminal_launcher']}")
            print(f"Config: {result['config']}")
            print(f"Plugin: {result['plugin']}")
            print("\nNext: launch Desktop Code, accept the normal workspace-trust prompt, and confirm")
            print("the lawyeredos-* project skills before linking one existing fictional matter folder")
            print("through a previewed tracker create, then run a read-only orientation.")
            print("Keep this extracted package and its .venv at the current path.")
        return 0
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
