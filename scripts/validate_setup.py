from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from lawyeredos.config import load_config
from lawyeredos.tracker_cli import verify


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a private plugin configuration")
    parser.add_argument("--config", required=True)
    args = parser.parse_args()
    errors: list[str] = []
    warnings: list[str] = []
    try:
        config = load_config(args.config)
    except (ValueError, OSError) as exc:
        print(json.dumps({"ok": False, "errors": [str(exc)]}, indent=2))
        return 2
    if not config.workspace_root.is_dir():
        errors.append("workspace root is not a directory")
    if not config.scratch.is_dir():
        errors.append("scratch directory is not a directory")
    if not config.tracker_database.is_file():
        errors.append("tracker database is missing")
    else:
        health = verify(config.tracker_database)
        if not health["ok"]:
            errors.extend(f"tracker: {item}" for item in health["problems"])
    if not config.document_template.is_file():
        warnings.append("document template is missing; correspondence unavailable")
    if importlib.util.find_spec("docx") is None:
        warnings.append("python-docx is not installed; correspondence and redline features unavailable")
    if importlib.util.find_spec("lxml") is None:
        warnings.append("lxml is not installed; redline features unavailable")
    if importlib.util.find_spec("openpyxl") is None:
        warnings.append("openpyxl is not installed; XLSX tracker projection unavailable")
    if shutil.which("libreoffice") is None and shutil.which("soffice") is None:
        warnings.append("LibreOffice command not found; visual DOCX rendering unavailable")
    if shutil.which("pdftoppm") is None:
        warnings.append("pdftoppm not found; page-image rendering unavailable")
    if shutil.which("ocrmypdf") is None:
        warnings.append("ocrmypdf not found; OCR creation unavailable")
    for label, adapter in (
        ("mail", config.mail_adapter),
        ("calendar", config.calendar_adapter),
        ("practice manager", config.practice_manager_adapter),
    ):
        if adapter == "unavailable":
            warnings.append(f"{label} adapter unavailable")
    if config.calendar_adapter != "unavailable" and not config.calendar_id:
        errors.append("calendar adapter is configured but calendar_id is blank")
    if config.calendar_adapter == "google-calendar-api" and config.calendar_id == "primary":
        errors.append("calendar adapter refuses the primary calendar; configure a dedicated calendar_id")
    if config.mail_adapter == "fixture-json" and (config.mail_fixture is None or not config.mail_fixture.is_file()):
        errors.append("fixture-json mail adapter requires an existing integrations.mail_fixture")
    if config.mail_adapter == "gmail-api-readonly" and not os.environ.get(config.gmail_token_env):
        errors.append(f"Gmail token environment variable is not set: {config.gmail_token_env}")
    if config.mail_adapter == "claude-gmail-connector":
        warnings.append(
            "Claude Gmail connector is configured but local validation cannot prove that it is "
            "authorized or available in the active Claude session; a successful bounded read is required"
        )
    if config.mail_adapter == "codex-session-tools":
        warnings.append(
            "Codex session mail tools are configured but local validation cannot prove that a "
            "supported authorized read/search tool is present; a successful bounded read is required"
        )
    if config.calendar_adapter == "google-calendar-api" and not os.environ.get(config.calendar_token_env):
        errors.append(f"Calendar token environment variable is not set: {config.calendar_token_env}")
    result = {"ok": not errors, "errors": errors, "warnings": warnings}
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if not errors else 2


if __name__ == "__main__":
    raise SystemExit(main())
