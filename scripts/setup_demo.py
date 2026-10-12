from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from lawyeredos.tracker_cli import initialize
from lawyeredos.private_fs import create_private_file, ensure_private_directory


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a fictional local demo workspace")
    parser.add_argument("--destination", required=True)
    args = parser.parse_args()
    destination = Path(args.destination).expanduser().resolve()
    if destination.exists():
        print("error: destination already exists")
        return 2
    ensure_private_directory(destination)
    workspace = destination / "workspace"
    scratch = destination / "scratch"
    matter_folder = workspace / "2030-001-northstar-bakery"
    matter_folder.mkdir(parents=True)
    scratch.mkdir(parents=True)
    (matter_folder / "_matter-brief.md").write_text(
        "# 2030-001 — Northstar Bakery Ltd.\n\n"
        "## Status\n\nReviewing a fictional commercial supply agreement.\n\n"
        "## Next action\n\nConfirm whether the revised delivery clause is acceptable.\n",
        encoding="utf-8",
    )
    (matter_folder / "source-note.txt").write_text(
        "Fictional source note. No real person, client, or account is represented.\n",
        encoding="utf-8",
    )
    database = workspace / "matters.sqlite3"
    initialize(database)
    timestamp = datetime.now(UTC).replace(microsecond=0).isoformat()
    with sqlite3.connect(database) as connection:
        connection.execute(
            """INSERT INTO matters(
                file_number, client, description, matter_folder, status,
                opposing_party, other_parties, primary_email,
                next_action, next_action_date, limitation_date, court_deadlines,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, 'open', ?, '', ?, ?, '', '', '[]', ?, ?)""",
            (
                "2030-001", "Northstar Bakery Ltd.",
                "Fictional commercial supply agreement", matter_folder.name,
                "Harbor Paper Co.", "legal@example.invalid",
                "Confirm revised delivery clause", timestamp, timestamp,
            ),
        )
    assets = destination / "assets"
    ensure_private_directory(assets)
    template = assets / "neutral-letterhead.docx"
    create_private_file(template, (PROJECT_ROOT / "assets" / "neutral-letterhead.docx").read_bytes())
    manifest = assets / "template-manifest.json"
    create_private_file(manifest, (json.dumps({
        "schema_version": 1, "algorithm": "sha256", "template": template.name,
        "sha256": hashlib.sha256(template.read_bytes()).hexdigest(),
    }, indent=2) + "\n").encode("utf-8"))
    config = destination / "config.toml"
    config_text = "\n".join([
            "schema_version = 1",
            "",
            "[workspace]",
            f'root = {json.dumps(str(workspace))}',
            f'scratch = {json.dumps(str(scratch))}',
            'timezone = "UTC"',
            "",
            "[tracker]",
            f'database = {json.dumps(str(database))}',
            "",
            "[documents]",
            f'template = {json.dumps(str(template))}',
            f'template_manifest = {json.dumps(str(manifest))}',
            'author = "Authorized reviewer"',
            "",
            "[branding]",
            'mode = "neutral"',
            'label = "Northstar Legal Lab"',
            "",
            "[modules]",
            "matter = true", "tracker = true", "letters = true",
            "redline = false", "calendar = false", "review = false",
            "",
            "[jurisdiction]",
            'profile = "none"',
            "",
            "[integrations]",
            'mail_adapter = "unavailable"',
            'calendar_adapter = "unavailable"',
            'practice_manager_adapter = "unavailable"',
            "",
            "[calendar]",
            "# Reserved for a future audited live adapter.",
            'calendar_id = ""',
            "",
            "[review]",
            "external_ai = false",
            "",
        ]) + "\n"
    create_private_file(config, config_text.encode("utf-8"))
    print(config)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
