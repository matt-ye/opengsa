"""出處閘門：新的手寫候選要被擋下，真正萃取的候選不可誤判。"""
from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.check_provenance import BASELINE, MAX_BASELINE, all_candidates, check


class ProvenanceGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.candidates = all_candidates()
        cls.known = set(json.loads(BASELINE.read_text(encoding="utf-8"))["candidate_ids"])

    def test_current_data_passes_with_baseline(self):
        self.assertEqual(check(self.candidates, self.known), {})

    def test_baseline_cannot_grow_and_only_lists_existing_candidates(self):
        self.assertLessEqual(len(self.known), MAX_BASELINE)
        self.assertLessEqual(self.known, {c["candidate_id"] for c in self.candidates})

    def test_pending_extractor_cards_are_still_marked_hand_authored(self):
        pending = set(json.loads(BASELINE.read_text(encoding="utf-8")).get("pending_extractor", []))
        self.assertLessEqual(pending, self.known)

    def test_a_new_hand_authored_candidate_is_rejected(self):
        template = next(c for c in self.candidates if c["candidate_id"] in self.known)
        forged = deepcopy(template)
        forged["candidate_id"] = "cand-forged-00000000"
        forged["verification"]["status"] = "passed_automated_checks"
        forged["verification"]["errors"] = []
        self.assertIn("cand-forged-00000000", check([forged], self.known))

    def test_extracted_bundles_are_not_in_the_baseline(self):
        for name in ("source-review", "ai-tools-115"):
            rows = json.loads((ROOT / f"data/candidates/{name}.json").read_text(encoding="utf-8"))["candidates"]
            self.assertFalse({c["candidate_id"] for c in rows} & self.known, name)


if __name__ == "__main__":
    unittest.main()
