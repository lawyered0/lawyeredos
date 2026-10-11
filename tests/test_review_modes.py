from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from lawyeredos.review_bundle import (
    PRINCIPAL_REVIEW_LENSES,
    PROCEDURAL_REVIEW_LENS,
    create_manifest,
)
from lawyeredos.review_orchestrator import collect, prepare


class ProportionalReviewModeTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.source = self.root / "fictional-source.txt"
        self.source.write_text("Fictional controlling source.\n", encoding="utf-8")
        self.draft = self.root / "fictional-draft.txt"
        self.draft.write_text("Fictional draft.\n", encoding="utf-8")

    def tearDown(self):
        self.temporary.cleanup()

    def make_tasks(self, mode="full", lenses=None):
        manifest = self.root / f"{mode}-manifest.json"
        manifest.write_text(json.dumps(create_manifest(
            self.draft, [self.source], self.root, mode=mode, lenses=lenses,
        )), encoding="utf-8")
        tasks = self.root / f"{mode}-tasks.json"
        prepared = prepare(manifest, tasks, focus="fictional bounded issue")
        return manifest, tasks, prepared, json.loads(tasks.read_text(encoding="utf-8"))

    def write_clear_results(self, bundle, directory):
        directory.mkdir()
        for lens in bundle["review_lenses"]:
            (directory / f"{lens}.json").write_text(json.dumps({
                "lens": lens, "coverage_gaps": [], "questions": [], "findings": [],
            }), encoding="utf-8")

    def test_default_is_backwards_compatible_full_review(self):
        manifest, tasks, prepared, bundle = self.make_tasks()
        self.assertEqual(prepared["review_mode"], "full")
        self.assertEqual(prepared["task_count"], 4)
        self.assertEqual(bundle["review_lenses"], list(PRINCIPAL_REVIEW_LENSES))

        # A pre-mode manifest and task bundle remain collectible as a full review.
        old_manifest = json.loads(manifest.read_text(encoding="utf-8"))
        old_manifest.pop("review_mode")
        manifest.write_text(json.dumps(old_manifest), encoding="utf-8")
        bundle.pop("review_mode")
        bundle.pop("review_lenses")
        tasks.write_text(json.dumps(bundle), encoding="utf-8")
        results = self.root / "old-results"
        self.write_clear_results({"review_lenses": list(PRINCIPAL_REVIEW_LENSES)}, results)
        report = collect(tasks, results, self.root / "old-report.json")
        self.assertTrue(report["ready"])
        self.assertFalse(report["authorizes_action"])

    def test_each_mode_generates_only_its_exact_lens_set(self):
        cases = (
            ("targeted", ["fact-and-source-check"]),
            ("procedural", None),
            ("quick", ["opposing-reader", "privilege-admissions-and-authority"]),
            ("full", None),
        )
        for mode, lenses in cases:
            with self.subTest(mode=mode):
                _, tasks, prepared, bundle = self.make_tasks(mode, lenses)
                expected = (
                    [PROCEDURAL_REVIEW_LENS] if mode == "procedural"
                    else list(PRINCIPAL_REVIEW_LENSES) if mode == "full"
                    else lenses
                )
                self.assertEqual(prepared["task_count"], len(expected))
                self.assertEqual(bundle["review_lenses"], expected)
                self.assertEqual([task["lens"] for task in bundle["tasks"]], expected)
                results = self.root / f"{mode}-results"
                self.write_clear_results(bundle, results)
                collected = collect(tasks, results, self.root / f"{mode}-report.json")
                self.assertTrue(collected["ready"])
                self.assertFalse(collected["authorizes_action"])
                self.assertEqual(collected["review_mode"], mode)
                self.assertEqual(collected["requested_lenses"], expected)

    def test_codex_targeted_mode_stays_host_scoped_and_does_not_auto_escalate(self):
        selected = ["privilege-admissions-and-authority"]
        manifest = self.root / "codex-targeted-manifest.json"
        manifest.write_text(json.dumps(create_manifest(
            self.draft, [self.source], self.root, host="codex",
            mode="targeted", lenses=selected,
        )), encoding="utf-8")
        tasks = self.root / "codex-targeted-tasks.json"
        prepared = prepare(
            manifest, tasks, focus="fictional high-risk label", host="codex",
        )
        bundle = json.loads(tasks.read_text(encoding="utf-8"))
        self.assertEqual(prepared["review_mode"], "targeted")
        self.assertEqual(prepared["task_count"], 1)
        self.assertEqual(bundle["schema"], "codex-review-tasks-v1")
        self.assertEqual(bundle["review_lenses"], selected)
        self.assertEqual(bundle["tasks"][0]["agent"], "independent-codex-reviewer")

    def test_invalid_or_implicit_narrow_lens_sets_fail_closed(self):
        cases = (
            ("targeted", None, "one named principal lens"),
            ("targeted", [PROCEDURAL_REVIEW_LENS], "one named principal lens"),
            ("quick", ["opposing-reader"], "exactly two distinct"),
            ("quick", ["opposing-reader", "opposing-reader"], "distinct"),
            ("full", ["opposing-reader"], "all four principal lenses"),
            ("procedural", ["opposing-reader"], "procedural micro-correspondence"),
        )
        for mode, lenses, message in cases:
            with self.subTest(mode=mode, lenses=lenses):
                with self.assertRaisesRegex(ValueError, message):
                    create_manifest(
                        self.draft, [self.source], self.root,
                        mode=mode, lenses=lenses,
                    )

    def test_collection_blocks_gaps_questions_and_material_findings_in_narrow_mode(self):
        _, tasks, _, bundle = self.make_tasks("targeted", ["opposing-reader"])
        lens = bundle["review_lenses"][0]
        results = self.root / "blocking-results"
        results.mkdir()
        (results / f"{lens}.json").write_text(json.dumps({
            "lens": lens,
            "coverage_gaps": ["fictional attachment omitted"],
            "questions": ["Which fictional date controls?"],
            "findings": [{
                "severity": "material", "title": "Fictional ambiguity",
                "observation": "The fictional draft is ambiguous.",
                "source_path": str(self.draft.resolve()), "location": "line 1",
                "countervailing_evidence": "The supplied source was checked.",
                "consequence": "A fictional recipient could misunderstand it.",
            }],
        }), encoding="utf-8")
        collected = collect(tasks, results, self.root / "blocking-report.json")
        self.assertFalse(collected["ready"])
        self.assertIn("review coverage gaps remain", collected["readiness_reasons"])
        self.assertIn("review questions remain unresolved", collected["readiness_reasons"])
        self.assertIn("critical or material findings remain unresolved", collected["readiness_reasons"])

    def test_task_and_result_lens_sets_cannot_be_expanded_or_substituted(self):
        _, tasks, _, bundle = self.make_tasks("quick", [
            "opposing-reader", "pre-mortem-and-operational-risk",
        ])
        tampered = json.loads(json.dumps(bundle))
        tampered["review_lenses"] = list(PRINCIPAL_REVIEW_LENSES)
        tasks.write_text(json.dumps(tampered), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "mode or lens contract"):
            collect(tasks, self.root / "absent-results", self.root / "tampered-report.json")

        tasks.write_text(json.dumps(bundle), encoding="utf-8")
        results = self.root / "expanded-results"
        self.write_clear_results(bundle, results)
        (results / "fact-and-source-check.json").write_text(json.dumps({
            "lens": "fact-and-source-check", "coverage_gaps": [],
            "questions": [], "findings": [],
        }), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "unrequested lenses"):
            collect(tasks, results, self.root / "expanded-report.json")

    def test_hash_drift_blocks_prepare_and_collection_for_narrow_modes(self):
        manifest, _, _, _ = self.make_tasks("procedural")
        self.draft.write_text("Changed fictional draft.\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "changed before orchestration"):
            prepare(manifest, self.root / "drifted-prepare.json")

        self.draft.write_text("Fictional draft.\n", encoding="utf-8")
        _, tasks, _, bundle = self.make_tasks("targeted", ["opposing-reader"])
        results = self.root / "drifted-results"
        self.write_clear_results(bundle, results)
        self.source.write_text("Changed fictional source.\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "changed during review"):
            collect(tasks, results, self.root / "drifted-report.json")


if __name__ == "__main__":
    unittest.main()
