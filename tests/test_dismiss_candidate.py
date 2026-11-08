"""駁回：台帳要留原因和問題來源，打錯 id 不寫入，只有 dismissed 會下架。不連外。"""
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.dismiss_candidate import dismiss
from scripts.review_candidates import dismissed_candidate_ids

REV = "a" * 64


def card(candidate_id, revision=REV, source="s"):
    return {"candidate_id": candidate_id, "source_metadata": {"revision_id": revision, "source_id": source}}


class DismissTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        (self.root / "data/candidates").mkdir(parents=True)
        (self.root / "data/candidates/a.json").write_text(json.dumps({"candidates": [card("cand-1")]}), encoding="utf-8")
        self.ledger = self.root / "data/scan-reviews.json"
        self.ledger.write_text(json.dumps({"schema_version": "1.1.0", "reviews": []}), encoding="utf-8")

    def test_records_reason_and_problem_source(self):
        dismiss("cand-1", "日期抽錯", "extraction", "matt-ye", self.root, today="2026-11-08")
        entry = json.loads(self.ledger.read_text(encoding="utf-8"))["reviews"][0]
        self.assertEqual((entry["action"], entry["reason"], entry["problem_source"], entry["revision_id"]), ("dismissed", "日期抽錯", "extraction", REV))

    def test_unknown_card_or_problem_writes_nothing(self):
        for candidate, problem in (("cand-x", "extraction"), ("cand-1", "typo")):
            with self.assertRaises(ValueError):
                dismiss(candidate, "r", problem, "matt-ye", self.root, today="2026-11-08")
        self.assertEqual(json.loads(self.ledger.read_text(encoding="utf-8"))["reviews"], [])

    def test_same_card_cannot_be_dismissed_twice(self):
        dismiss("cand-1", "r", "other", "matt-ye", self.root, today="2026-11-08")
        with self.assertRaises(ValueError):
            dismiss("cand-1", "r", "other", "matt-ye", self.root, today="2026-11-08")

    def test_only_dismissed_entries_take_a_card_down(self):
        cards = [card("named"), card("whole-a", "b" * 64), card("noted", "c" * 64), card("other-source", "b" * 64, "t")]
        reviews = {"reviews": [{"action": "dismissed", "revision_id": REV, "source_id": "s", "candidate_id": "named"},
                               {"action": "dismissed", "revision_id": "b" * 64, "source_id": "s"},
                               {"action": "noted", "revision_id": "c" * 64, "source_id": "s"}]}
        self.assertEqual(dismissed_candidate_ids(cards, reviews), {"named", "whole-a"})


if __name__ == "__main__":
    unittest.main()
