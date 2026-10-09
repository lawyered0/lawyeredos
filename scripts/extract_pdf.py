from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path


def run(args: argparse.Namespace) -> dict:
    source = Path(args.input).expanduser().resolve()
    output = Path(args.output).expanduser().resolve()
    if not source.is_file() or source.is_symlink() or source.suffix.casefold() != ".pdf":
        raise ValueError("input must be a regular PDF file")
    if output.exists():
        raise ValueError("output already exists")
    pdftotext = shutil.which(args.pdftotext)
    if not pdftotext:
        raise ValueError("pdftotext command not found")
    output.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [pdftotext, "-layout", str(source), str(output)],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=120,
    )
    if result.returncode != 0 or not output.is_file():
        raise ValueError(f"pdftotext failed: {result.stderr.strip()}")
    text = output.read_text(encoding="utf-8", errors="replace")
    non_space = len("".join(text.split()))
    status = "usable" if non_space >= args.minimum_characters else "review"
    return {
        "ok": True,
        "status": status,
        "input": str(source),
        "output": str(output),
        "non_space_characters": non_space,
        "warning": None if status == "usable" else "Sparse extraction; OCR or manual review may be required.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract PDF text and report whether it is usable")
    parser.add_argument("input")
    parser.add_argument("--output", required=True)
    parser.add_argument("--pdftotext", default="pdftotext")
    parser.add_argument("--minimum-characters", type=int, default=80)
    args = parser.parse_args()
    try:
        result = run(args)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if result["status"] == "usable" else 3
    except (ValueError, OSError, subprocess.SubprocessError) as exc:
        print(json.dumps({"ok": False, "status": "error", "error": str(exc)}, indent=2))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
