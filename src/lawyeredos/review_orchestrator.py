from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .common import emit
from .review_bundle import (
    PRINCIPAL_REVIEW_LENSES,
    PROCEDURAL_REVIEW_LENS,
    resolve_review_lenses,
    verify_manifest,
)


LENSES = {
    "opposing-reader": "Identify arguments, ambiguities, and concessions an adverse reader could exploit.",
    "fact-and-source-check": "Check material factual propositions against the supplied sources and identify unsupported claims.",
    "privilege-admissions-and-authority": "Identify privilege, admission, confidentiality, settlement, and authority risks.",
    "pre-mortem-and-operational-risk": "Assume the communication fails and identify concrete legal or operational failure modes.",
}
ALL_LENSES = {
    **LENSES,
    PROCEDURAL_REVIEW_LENS: (
        "Review one to three coordinated short procedural messages for audience, "
        "thread, transmission, authority, court-control, attribution, service/filing, "
        "admission, and sequencing defects that are actually engaged."
    ),
}
SEVERITIES = {"critical", "material", "optional"}


def _manifest_review_contract(manifest: dict[str, Any]) -> tuple[str, list[str]]:
    # Older full manifests did not carry review_mode. Their canonical four-lens
    # declaration remains a full review for backwards compatibility.
    mode = manifest.get("review_mode", "full")
    lenses = manifest.get("review_lenses")
    if not isinstance(lenses, list):
        raise ValueError("review manifest does not declare a lens set")
    expected = resolve_review_lenses(mode, lenses)
    if lenses != expected:
        raise ValueError("review manifest lens order does not match its review mode")
    return mode, expected


def _validate_manifest_host(manifest: dict[str, Any], host: str) -> tuple[str, list[str]]:
    if manifest.get("schema") != f"{host}-review-bundle-v1":
        raise ValueError("review manifest schema does not match the review host")
    if manifest.get("provider_boundary") != f"{host.title()} only; no external model provider":
        raise ValueError("review manifest provider boundary does not match the review host")
    return _manifest_review_contract(manifest)


def _canonical_tasks(manifest: dict[str, Any], focus: str, host: str) -> list[dict[str, Any]]:
    agent = "lawyeredos-legal-review-lens" if host == "claude" else "independent-codex-reviewer"
    tasks = []
    for lens in manifest["review_lenses"]:
        instruction = ALL_LENSES[lens]
        tasks.append({
            "lens": lens, "agent": agent,
            "read_only": True, "focus": focus, "instruction": instruction,
            "deliverable": manifest["deliverable"], "sources": manifest["sources"],
            "result_schema": {
                "lens": lens,
                "severity_allowed": sorted(SEVERITIES),
                "findings": [{"severity": "material", "title": "short title", "observation": "supported observation", "source_path": "exact supplied path", "location": "page/section/line", "countervailing_evidence": "strongest contrary evidence checked", "consequence": "why it matters"}],
                "coverage_gaps": ["anything not reviewed"],
                "questions": ["material question requiring human resolution"],
            },
        })
    return tasks


def prepare(manifest_path: Path, output: Path, focus: str = "", host: str = "claude") -> dict[str, Any]:
    if output.exists():
        raise ValueError("review task output already exists")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    checks = verify_manifest(manifest_path)
    if not checks["unchanged"]:
        raise ValueError("review sources or deliverable changed before orchestration")
    if host not in {"claude", "codex"}:
        raise ValueError("review host must be claude or codex")
    mode, selected_lenses = _validate_manifest_host(manifest, host)
    agent = "lawyeredos-legal-review-lens" if host == "claude" else "independent-codex-reviewer"
    tasks = _canonical_tasks(manifest, focus, host)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({
        "schema": f"{host}-review-tasks-v1", "host": host,
        "manifest": str(manifest_path.resolve()), "review_mode": mode,
        "review_lenses": selected_lenses, "tasks": tasks,
    }, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"ok": True, "tasks": str(output), "task_count": len(tasks),
            "agent": agent, "host": host, "review_mode": mode,
            "review_lenses": selected_lenses}


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


def _text_items(value: dict[str, Any], field: str, lens: str) -> list[str]:
    items = value.get(field, [])
    if not isinstance(items, list):
        raise ValueError(f"{lens} {field} must be a list")
    return [str(item).strip() for item in items if str(item).strip()]


def _validate_task_bundle(task_bundle: dict[str, Any], manifest: dict[str, Any]) -> None:
    host = task_bundle.get("host")
    if host not in {"claude", "codex"}:
        raise ValueError("review task bundle has an invalid host")
    if task_bundle.get("schema") != f"{host}-review-tasks-v1":
        raise ValueError("review task bundle has an invalid schema")
    mode, expected_lenses = _validate_manifest_host(manifest, host)
    bundle_mode = task_bundle.get("review_mode", "full")
    bundle_lenses = task_bundle.get("review_lenses", list(PRINCIPAL_REVIEW_LENSES))
    if bundle_mode != mode or bundle_lenses != expected_lenses:
        raise ValueError("review task bundle mode or lens contract does not match the manifest")
    tasks = task_bundle.get("tasks")
    if not isinstance(tasks, list):
        raise ValueError("review task bundle tasks must be a list")
    lenses = [task.get("lens") if isinstance(task, dict) else None for task in tasks]
    if lenses != expected_lenses:
        raise ValueError("review task bundle must contain each expected lens exactly once, in selected order")
    focus = tasks[0].get("focus")
    if not isinstance(focus, str):
        raise ValueError("review task bundle has an invalid focus")
    if tasks != _canonical_tasks(manifest, focus, host):
        raise ValueError("review task bundle content does not match the canonical host manifest tasks")


def collect(tasks_path: Path, results_dir: Path, output: Path) -> dict[str, Any]:
    if output.exists():
        raise ValueError("review report output already exists")
    task_bundle = json.loads(tasks_path.read_text(encoding="utf-8"))
    manifest_path = Path(task_bundle["manifest"])
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    _validate_task_bundle(task_bundle, manifest)
    integrity = verify_manifest(manifest_path)
    if not integrity["unchanged"]:
        raise ValueError("review sources or deliverable changed during review")
    allowed_sources = {item["path"] for item in manifest["sources"]} | {manifest["deliverable"]["path"]}
    findings: list[dict[str, Any]] = []
    gaps: list[str] = []
    questions: list[str] = []
    completed = []
    selected_lenses = list(manifest["review_lenses"])
    result_files = sorted(path.stem for path in results_dir.glob("*.json") if path.is_file())
    unexpected_results = sorted(set(result_files) - set(selected_lenses))
    if unexpected_results:
        raise ValueError("review results contain unrequested lenses: " + ", ".join(unexpected_results))
    for lens in selected_lenses:
        path = results_dir / f"{lens}.json"
        if not path.is_file():
            gaps.append(f"missing reviewer result: {lens}")
            continue
        value = json.loads(path.read_text(encoding="utf-8"))
        findings.extend(_validate_result(value, lens, allowed_sources))
        gaps.extend(f"{lens}: {item}" for item in _text_items(value, "coverage_gaps", lens))
        questions.extend(f"{lens}: {item}" for item in _text_items(value, "questions", lens))
        completed.append(lens)
    findings.sort(key=lambda item: ({"critical": 0, "material": 1, "optional": 2}[item["severity"]], item["title"], item["lens"]))
    collection_complete = completed == selected_lenses
    readiness_reasons: list[str] = []
    if not collection_complete:
        readiness_reasons.append("review collection is incomplete")
    if not manifest["sources"]:
        readiness_reasons.append("no controlling sources were supplied")
    if gaps:
        readiness_reasons.append("review coverage gaps remain")
    if questions:
        readiness_reasons.append("review questions remain unresolved")
    blocking_findings = [
        item for item in findings if item["severity"] in {"critical", "material"}
    ]
    if blocking_findings:
        readiness_reasons.append("critical or material findings remain unresolved")
    ready = not readiness_reasons
    report = {
        "schema": f"{task_bundle.get('host', 'claude')}-review-report-v2",
        "provider_boundary": f"{task_bundle.get('host', 'claude').title()} only",
        "review_mode": manifest.get("review_mode", "full"),
        "requested_lenses": selected_lenses,
        "collection_complete": collection_complete,
        "ready": ready,
        "authorizes_action": False,
        "readiness_reasons": readiness_reasons,
        "completed_lenses": completed,
        "coverage_gaps": gaps,
        "questions": questions,
        "findings": findings,
        "integrity": integrity,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"ok": ready, "collection_complete": collection_complete,
            "ready": ready, "authorizes_action": False,
            "review_mode": manifest.get("review_mode", "full"),
            "requested_lenses": selected_lenses,
            "readiness_reasons": readiness_reasons, "report": str(output),
            "completed_lenses": completed, "finding_count": len(findings),
            "blocking_finding_count": len(blocking_findings),
            "coverage_gaps": gaps, "questions": questions,
            "deliverable_unchanged": integrity["deliverable_unchanged"]}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Prepare and validate deterministic host-scoped review jobs")
    sub = parser.add_subparsers(dest="command", required=True)
    prep = sub.add_parser("prepare"); prep.add_argument("--manifest", required=True); prep.add_argument("--output", required=True); prep.add_argument("--focus", default=""); prep.add_argument("--host", choices=("claude", "codex"), default="claude")
    done = sub.add_parser("collect"); done.add_argument("--tasks", required=True); done.add_argument("--results-dir", required=True); done.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    try:
        result = prepare(Path(args.manifest), Path(args.output), args.focus, args.host) if args.command == "prepare" else collect(Path(args.tasks), Path(args.results_dir), Path(args.output))
        emit(result); return 0 if result["ok"] else 3
    except (ValueError, OSError, KeyError, json.JSONDecodeError) as exc:
        emit({"ok": False, "error": str(exc)}); return 2


if __name__ == "__main__":
    raise SystemExit(main())
