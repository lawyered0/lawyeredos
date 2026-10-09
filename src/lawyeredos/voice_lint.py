from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from .common import emit


DEFAULT_RULES = {
    "email": {"sentence_warn": 32, "sentence_fail": 45, "word_warn": 250, "word_fail": 400, "forbid_headings": True},
    "letter": {"sentence_warn": 38, "sentence_fail": 55, "word_warn": 800, "word_fail": 1600, "forbid_headings": False},
}


def lint(text: str, register: str, rules: dict[str, Any] | None = None) -> dict[str, Any]:
    settings = dict(DEFAULT_RULES[register])
    if rules:
        settings.update(rules)
    findings: list[dict[str, Any]] = []
    lines = text.splitlines()
    for index, line in enumerate(lines, 1):
        if "—" in line:
            findings.append({"severity": "FAIL", "line": index, "rule": "em-dash", "message": "replace an em dash with ordinary punctuation"})
        if settings["forbid_headings"] and re.match(r"^\s{0,3}#{1,6}\s+", line):
            findings.append({"severity": "FAIL", "line": index, "rule": "email-heading", "message": "email body contains a Markdown heading"})
        if settings["forbid_headings"] and re.match(r"^\s*[-*+]\s+", line):
            findings.append({"severity": "WARN", "line": index, "rule": "email-list", "message": "confirm the email needs a list"})
        for match in re.finditer(r"(?<![$A-Z])\b\d{1,3}(?:,\d{3})+(?:\.\d{2})?\b", line):
            context = line[max(0, match.start() - 24):match.end() + 24].casefold()
            if re.search(r"\b(?:pay|paid|payment|amount|fee|invoice|cost|damages|rent|settlement|balance)\b", context):
                findings.append({"severity": "FAIL", "line": index, "rule": "currency", "message": "money figure appears to lack a currency marker"})
    sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", text) if part.strip()]
    for sentence in sentences:
        words = re.findall(r"\b[\w'-]+\b", sentence)
        if len(words) > settings["sentence_fail"]:
            findings.append({"severity": "FAIL", "line": 0, "rule": "sentence-length", "message": f"sentence has {len(words)} words"})
        elif len(words) > settings["sentence_warn"]:
            findings.append({"severity": "WARN", "line": 0, "rule": "sentence-length", "message": f"sentence has {len(words)} words"})
    word_count = len(re.findall(r"\b[\w'-]+\b", text))
    if word_count > settings["word_fail"]:
        findings.append({"severity": "FAIL", "line": 0, "rule": "overall-length", "message": f"draft has {word_count} words"})
    elif word_count > settings["word_warn"]:
        findings.append({"severity": "WARN", "line": 0, "rule": "overall-length", "message": f"draft has {word_count} words"})
    fails = sum(item["severity"] == "FAIL" for item in findings)
    return {"ok": fails == 0, "register": register, "words": word_count, "fails": fails,
            "warns": len(findings) - fails, "findings": findings}


def load_rules(path: Path | None, register: str) -> dict[str, Any] | None:
    if path is None:
        return None
    value = json.loads(path.read_text(encoding="utf-8"))
    selected = value.get(register, value)
    if not isinstance(selected, dict):
        raise ValueError("voice rules must be a JSON object")
    return selected


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Configurable, anonymous correspondence style lint")
    parser.add_argument("path"); parser.add_argument("--register", choices=["email", "letter"], default="email"); parser.add_argument("--rules")
    args = parser.parse_args(argv)
    try:
        text = Path(args.path).read_text(encoding="utf-8") if args.path != "-" else __import__("sys").stdin.read()
        result = lint(text, args.register, load_rules(Path(args.rules) if args.rules else None, args.register))
        emit(result); return 0 if result["ok"] else 3
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        emit({"ok": False, "error": str(exc)}); return 2


if __name__ == "__main__":
    raise SystemExit(main())
