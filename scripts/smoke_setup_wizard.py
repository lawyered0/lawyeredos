from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from lawyeredos.config import load_config
from lawyeredos.setup_wizard import Answers, apply_plan, build_plan, rollback


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="lawyeredos-wizard-smoke-") as temporary:
        workspace = Path(temporary) / "fictional-workspace"
        answers = Answers(
            workspace=workspace,
            branding_mode="firm",
            branding_label="Northstar Legal Lab",
            jurisdiction="none",
            modules=("matter", "tracker", "letters", "redline", "review"),
            mail_adapter="unavailable",
            calendar_adapter="unavailable",
            calendar_id="",
            existing_config="reuse",
        )
        plan = build_plan(answers)
        if workspace.exists():
            raise RuntimeError("preview unexpectedly changed the workspace")
        first = apply_plan(plan)
        config = load_config(first["config"])
        second = apply_plan(build_plan(answers))
        if not second["idempotent"]:
            raise RuntimeError("repeat application was not idempotent")
        rolled_back = rollback(workspace)
        result = {
            "ok": True,
            "preview_side_effect_free": True,
            "config_loaded": config.branding_label == "Northstar Legal Lab",
            "repeat_idempotent": True,
            "rollback_removed_plugin": not Path(first["plugin"]).exists(),
            "fictional_workspace": str(workspace),
            "rollback": rolled_back,
        }
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
