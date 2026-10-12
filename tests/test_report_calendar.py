"""Read-only fictional event regressions for report cal-1."""
import json
import tempfile
import unittest
from pathlib import Path

from lawyeredos.calendar_plan import load_events, plan


class ScopedCalendarReportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def event(self, key="m1:court", **extra):
        return {"sync_key": key, "date": "2035-01-02", "title": "Fictional", "timezone": "UTC", **extra}

    def test_calendar_metadata_is_unchanged_and_unrelated_is_not_removed(self):
        result = plan([self.event()], [self.event(event_id="event-1"), self.event("m2:court")])
        self.assertEqual(result["update"], [])
        self.assertEqual(len(result["unchanged"]), 1)
        self.assertEqual(result["remove"], [])

    def test_calendar_duplicates_are_reported_without_ambiguous_update(self):
        result = plan([self.event()], [self.event(event_id="a"), self.event(event_id="b")])
        self.assertEqual(len(result["duplicates"]), 1)
        self.assertEqual(result["update"], [])
        self.assertEqual(result["create"], [])

    def test_calendar_unowned_events_load_for_readonly_reporting(self):
        path = self.root / "existing.json"
        path.write_text(json.dumps([{"event_id": "unowned", "summary": "Fictional unrelated event"}]))
        result = plan([self.event()], load_events(path, required=False))
        self.assertEqual(len(result["unowned_or_unparseable"]), 1)
        self.assertEqual(result["remove"], [])

    def test_calendar_removals_require_scope_nonempty_complete_desired(self):
        existing = [self.event(), self.event("m1:other", event_id="remove-id"), self.event("m2:court")]
        result = plan([self.event()], existing, ["m1:"])
        self.assertEqual([item["event_id"] for item in result["remove"]], ["remove-id"])
        self.assertEqual(plan([], existing, ["m1:"])["remove"], [])
        self.assertEqual(plan([self.event()], existing, ["m1:"], complete=False)["remove"], [])
        with self.assertRaisesRegex(ValueError, "outside"):
            plan([self.event("m2:court")], existing, ["m1:"])
        with self.assertRaisesRegex(ValueError, "duplicate desired"):
            plan([self.event(), self.event()], existing)

