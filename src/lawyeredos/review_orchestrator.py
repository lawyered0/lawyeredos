from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .common import emit
from .review_bundle import verify_manifest


LENSES = {
    "opposing-reader": "Identify arguments, ambiguities, and concessions an adverse reader could exploit.",
    "fact-and-source-check": "Check material factual propositions against the supplied sources and identify unsupported claims.",
    "privilege-admissions-and-authority": "Identify privilege, admission, confidentiality, settlement, and authority risks.",
    "pre-mortem-and-operational-risk": "Assume the communication fails and identify concrete legal or operational failure modes.",
}
SEVERITIES = {"critical", "material", "optional"}


def prepare(manifest_path: Path, output: Path, focus: str = "") -> dict[str, Any]:
    if output.exists():
        raise ValueError("review task output already exists")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    checks = verify_manifest(manifest_path)
    if not checks["unchanged"]:
        raise ValueError("review sources or deliverable changed before orchestration")
    tasks = []
    for lens, instruction in LENSES.items():
        tasks.append({
            "lens": lens, "agent": "lawyeredos-legal-review-lens",
            "read_only": True, "focus": focus, "instruction": instruction,
            "deliverable": manifest["deliverable"], "sources": manifest["sources"],
            "result_schema": {
                "lens": lens,
                "severity_allowed": sorted(SEVERITIES),
                "findings": [{"severity": "material", "title": "short title", "observation": "supported observation", "source_path": "exact supplied path", "location": "page/section/line", "countervailing_evidence": "strongest contrary evidence checked", "consequence": "why it matters"}],
                "coverage_gaps": ["anything not reviewed"],
            },
        })
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({"schema": "claude-review-tasks-v1", "manifest": str(manifest_path.resolve()), "tasks": tasks}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"ok": True, "tasks": str(output), "task_count": len(tasks), "agent": "lawyeredos-legal-review-lens"}


def _validate_result(value: dict[str, Any], lens: str, allowed_sources: set[str]) -> list[dict[str, Any]]:
    if value.get("lens") != lens or not isinstance(value.get("findings"), list):
        raise ValueError(f"invalid result schema for {lens}")
    findings = []
    for index, finding in enumerate(value["findings"], 1):
        if not isinstance(finding, dict):
            raise ValueError(f"{lens} finding {index} is not an object")
        required = {"severity", "title", "observation", "source_path", "location", "countervailing_evidence", "consequence"}
        missing = required - finding.keys()
        if missing:
            raise ValueError(f"{lens} finding {index} is incomplete")
        if finding["severity"] not in SEVERITIES:
            allowed = ", ".join(sorted(SEVERITIES))
            raise ValueError(f"{lens} finding {index} has invalid severity; expected one of: {allowed}")
        if finding["source_path"] not in allowed_sources:
            raise ValueError(f"{lens} finding {index} cites a path outside the supplied sources")
        findings.append({**finding, "lens": lens})
    return findings


def collect(tasks_path: Path, results_dir: Path, output: Path) -> dict[str, Any]:
    if output.exists():
        raise ValueError("review report output already exists")
    task_bundle = json.loads(tasks_path.read_text(encoding="utf-8"))
    manifest_path = Path(task_bundle["manifest"])
    integrity = verify_manifest(manifest_path)
    if not integrity["unchanged"]:
        raise ValueError("review sources or deliverable changed during review")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    allowed_sources = {item["path"] for item in manifest["sources"]} | {manifest["deliverable"]["path"]}
    findings: list[dict[str, Any]] = []
    gaps: list[str] = []
    completed = []
    for task in task_bundle["tasks"]:
        lens = task["lens"]
        path = results_dir / f"{lens}.json"
        if not path.is_file():
            gaps.append(f"missing reviewer result: {lens}")
            continue
        value = json.loads(path.read_text(encoding="utf-8"))
        findings.extend(_validate_result(value, lens, allowed_sources))
        gaps.extend(f"{lens}: {item}" for item in value.get("coverage_gaps", []) if str(item).strip())
        completed.append(lens)
    findings.sort(key=lambda item: ({"critical": 0, "material": 1, "optional": 2}[item["severity"]], item["title"], item["lens"]))
    report = {
        "schema": "claude-review-report-v1", "provider_boundary": "Claude only",
        "completed_lenses": completed, "coverage_gaps": gaps, "findings": findings,
        "integrity": integrity,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"ok": not gaps and len(completed) == len(LENSES), "report": str(output),
            "completed_lenses": completed, "finding_count": len(findings), "coverage_gaps": gaps,
            "deliverable_unchanged": integrity["deliverable_unchanged"]}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Prepare and validate deterministic Claude-only review jobs")
    sub = parser.add_subparsers(dest="command", required=True)
    prep = sub.add_parser("prepare"); prep.add_argument("--manifest", required=True); prep.add_argument("--output", required=True); prep.add_argument("--focus", default="")
    done = sub.add_parser("collect"); done.add_argument("--tasks", required=True); done.add_argument("--results-dir", required=True); done.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    try:
        result = prepare(Path(args.manifest), Path(args.output), args.focus) if args.command == "prepare" else collect(Path(args.tasks), Path(args.results_dir), Path(args.output))
        emit(result); return 0 if result["ok"] else 3
    except (ValueError, OSError, KeyError, json.JSONDecodeError) as exc:
        emit({"ok": False, "error": str(exc)}); return 2


if __name__ == "__main__":
    raise SystemExit(main())
