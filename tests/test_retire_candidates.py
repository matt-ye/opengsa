"""撤卡工具：卡片、基準、時程觀察、來源鏈要一起清；打錯 id 要報錯。不連外。"""
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.retire_candidates import retire


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


class RetireCandidatesTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        shutil.copytree(ROOT / "data", self.root / "data")
        self.card_id = read(ROOT / "data/candidates/enterprise-scholarships.json")["candidates"][0]["candidate_id"]

    def test_card_is_removed_everywhere_and_totals_follow(self):
        before = read(self.root / "data/source-chain-batches/batch-registry.json")
        self.assertEqual([c["candidate_id"] for c in retire([self.card_id], self.root)], [self.card_id])
        self.assertNotIn(self.card_id, [c["candidate_id"] for c in read(self.root / "data/candidates/enterprise-scholarships.json")["candidates"]])
        self.assertNotIn(self.card_id, read(self.root / "data/known-hand-authored-candidates.json")["candidate_ids"])
        self.assertNotIn(self.card_id, read(self.root / "data/enterprise-temporal-observations.json")["records"])
        batch = read(self.root / "data/source-chain-batches/batch-enterprise.json")
        self.assertNotIn(self.card_id, [b["candidate_id"] for b in batch["candidate_bindings"]])
        self.assertFalse([d for d in batch["documents"] if self.card_id in d.get("candidate_ids", [])])
        alive = {d["id"] for d in batch["documents"]}
        self.assertTrue(all(e["from"] in alive and e["to"] in alive for e in batch["edges"]))
        after = read(self.root / "data/source-chain-batches/batch-registry.json")
        self.assertEqual(after["total_schemes_covered"], before["total_schemes_covered"] - 1)
        self.assertEqual(after["total_documents"], sum(e["documents"] for e in after["batches"]))

    def test_source_without_cards_leaves_the_schedule(self):
        cards = read(self.root / "data/candidates/enterprise-scholarships.json")["candidates"]
        card = next(c for c in cards if sum(o["source_metadata"]["source_id"] == c["source_metadata"]["source_id"] for o in cards) == 1)
        retire([card["candidate_id"]], self.root)
        source = next(s for s in read(self.root / "data/scan-sources.json")["sources"] if s["id"] == card["source_metadata"]["source_id"])
        self.assertIs(source["enabled"], False)
        # 企業卡都是手寫卡：它的 profile 沒驗證過，撤卡後提交流程也不能再拿來用。
        self.assertIn(card["candidate_id"], read(ROOT / "data/known-hand-authored-candidates.json")["candidate_ids"])
        self.assertEqual(source["automation"], "not_enabled")

    def test_retired_card_leaves_every_baseline_list(self):
        baseline = read(self.root / "data/known-hand-authored-candidates.json")
        pending = baseline["pending_extractor"][0]
        retire([pending], self.root)
        after = read(self.root / "data/known-hand-authored-candidates.json")
        self.assertNotIn(pending, after["candidate_ids"])
        self.assertNotIn(pending, after["pending_extractor"])

    def test_unknown_id_changes_nothing(self):
        before = (self.root / "data/known-hand-authored-candidates.json").read_bytes()
        with self.assertRaises(ValueError):
            retire([self.card_id, "cand-does-not-exist"], self.root)
        self.assertEqual((self.root / "data/known-hand-authored-candidates.json").read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
