from __future__ import annotations

import json
import sys
from pathlib import Path


def require_supported_python(version=None):
    current = version or sys.version_info[:2]
    if current >= (3, 11):
        return
    message = (
        f"LawyeredOS requires Python 3.11 or newer; this interpreter is "
        f"Python {current[0]}.{current[1]}."
    )
    if "--json" in sys.argv:
        print(json.dumps({"ok": False, "error": message}, indent=2, sort_keys=True))
    else:
        print(f"error: {message}", file=sys.stderr)
    raise SystemExit(2)


require_supported_python()

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from lawyeredos.setup_wizard import main


if __name__ == "__main__":
    raise SystemExit(main())
