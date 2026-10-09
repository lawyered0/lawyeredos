from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path

from .common import emit, sha256_file


def available() -> dict[str, str | None]:
    return {name: shutil.which(name) for name in ("pdftotext", "pdfinfo", "ocrmypdf", "tesseract")}


def extract_pdf(source: Path, output: Path) -> dict:
    if output.exists():
        raise ValueError("text output already exists")
    command = available()["pdftotext"]
    if not command:
        raise ValueError("pdftotext is unavailable")
    output.parent.mkdir(parents=True, exist_ok=True)
    completed = subprocess.run([command, "-layout", str(source), str(output)], capture_output=True, text=True)
    if completed.returncode:
        raise ValueError(f"pdftotext failed with exit {completed.returncode}")
    text = output.read_text(encoding="utf-8", errors="replace")
    return {"ok": True, "source_sha256": sha256_file(source), "output": str(output),
            "characters": len(text), "needs_ocr": len(text.strip()) < 40}


def ocr_pdf(source: Path, output: Path, report: Path, languages: str = "eng") -> dict:
    if output.exists() or report.exists():
        raise ValueError("OCR output and report must not exist")
    command = available()["ocrmypdf"]
    if not command:
        raise ValueError("ocrmypdf is unavailable; install the optional OCR dependency")
    output.parent.mkdir(parents=True, exist_ok=True)
    completed = subprocess.run(
        [command, "--skip-text", "--deskew", "--rotate-pages", "-l", languages, str(source), str(output)],
        capture_output=True, text=True,
    )
    if completed.returncode:
        raise ValueError(f"ocrmypdf failed with exit {completed.returncode}")
    value = {
        "schema": "lawyeredos-ocr-v1", "engine": "ocrmypdf",
        "source": str(source.resolve()), "source_sha256": sha256_file(source),
        "output": str(output.resolve()), "output_sha256": sha256_file(output),
        "status": "usable-with-human-review", "languages": languages,
    }
    report.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"ok": True, **value}


def verify_ocr(report: Path) -> dict:
    value = json.loads(report.read_text(encoding="utf-8"))
    source = Path(value["source"]); output = Path(value["output"])
    source_ok = source.is_file() and sha256_file(source) == value["source_sha256"]
    output_ok = output.is_file() and sha256_file(output) == value["output_sha256"]
    return {"ok": source_ok and output_ok, "source_unchanged": source_ok,
            "output_unchanged": output_ok, "status": value.get("status", "unknown")}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fail-closed PDF text and OCR helpers")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("probe")
    extract = sub.add_parser("extract"); extract.add_argument("--input", required=True); extract.add_argument("--output", required=True)
    ocr = sub.add_parser("ocr"); ocr.add_argument("--input", required=True); ocr.add_argument("--output", required=True); ocr.add_argument("--report", required=True); ocr.add_argument("--languages", default="eng")
    verify = sub.add_parser("verify-ocr"); verify.add_argument("--report", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "probe": result = {"ok": True, "commands": available()}
        elif args.command == "extract": result = extract_pdf(Path(args.input), Path(args.output))
        elif args.command == "ocr": result = ocr_pdf(Path(args.input), Path(args.output), Path(args.report), args.languages)
        else: result = verify_ocr(Path(args.report))
        emit(result); return 0 if result.get("ok") else 3
    except (ValueError, OSError, json.JSONDecodeError, KeyError) as exc:
        emit({"ok": False, "error": str(exc)}); return 2


if __name__ == "__main__":
    raise SystemExit(main())
