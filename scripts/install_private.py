from __future__ import annotations

import argparse
import shutil
from pathlib import Path


EXCLUDE = {".venv", ".demo", ".git", "__pycache__", ".pytest_cache", "qa"}


def ignored(_directory: str, names: list[str]) -> set[str]:
    return {
        name for name in names
        if name in EXCLUDE or name.endswith((".pyc", ".egg-info"))
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Make a reversible private plugin copy")
    parser.add_argument("--target", required=True)
    args = parser.parse_args()
    source = Path(__file__).resolve().parents[1]
    target = Path(args.target).expanduser().resolve()
    if target.exists():
        print("error: target already exists; refusing to overwrite")
        return 2
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, target, ignore=ignored)
    print(target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
