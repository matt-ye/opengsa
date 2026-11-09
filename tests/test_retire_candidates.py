"""撤卡工具：卡片、基準、時程觀察、來源鏈要一起清；打錯 id 要報錯。不連外。

正式資料的手寫卡會越撤越少，所以測試在暫存副本裡挑一張有來源鏈、有時程紀錄、來源只給它用的卡，
自己標成手寫卡（含「萃取方式待補」），不依賴正式資料還剩幾張手寫卡。
"""
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.retire_candidates import retire, scrub


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


class RetireCandidatesTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        shutil.copytree(ROOT / "data", self.root / "data")
        data = self.root / "data"
        bundles = {path: read(path)["candidates"] for path in sorted((data / "candidates").glob("*.json"))}
        sources = [c["source_metadata"]["source_id"] for cards in bundles.values() for c in cards]
        timed = {cid: path for path in data.glob("*temporal-observations.json") for cid in read(path).get("records", {})}
        # 挑兩張：一張有時程紀錄、在副本裡綁進一個登記過的批次，測清乾淨；一張來源只給它用，測排程停掉。
        self.bundle, self.card = next((path, c) for path, cards in bundles.items() for c in cards if c["candidate_id"] in timed)
        self.lone = next(c for cards in bundles.values() for c in cards if sources.count(c["source_metadata"]["source_id"]) == 1)
        self.card_id = self.card["candidate_id"]
        self.temporal = timed[self.card_id]
        registry_path = data / "source-chain-batches/batch-registry.json"
        registry = read(registry_path)
        entry = registry["batches"][0]
        self.batch = self.root / entry["file"]
        batch = read(self.batch)
        batch["candidate_bindings"] = batch.get("candidate_bindings", []) + [{"candidate_id": self.card_id, "program_key": self.card["program_key"]}]
        batch["documents"] = batch["documents"] + [{"id": "doc-test-only", "candidate_ids": [self.card_id]}]
        batch["total_documents"] = len(batch["documents"])
        save(self.batch, batch)
        entry.update(documents=batch["total_documents"], candidates=len(batch["candidate_bindings"]))
        save(registry_path, {**registry, "total_documents": sum(e["documents"] for e in registry["batches"]),
                             "total_schemes_covered": sum(e["candidates"] for e in registry["batches"])})
        marked = [self.card_id, self.lone["candidate_id"]]
        baseline = read(data / "known-hand-authored-candidates.json")
        save(data / "known-hand-authored-candidates.json", {**baseline, "candidate_ids": baseline["candidate_ids"] + marked,
                                                            "pending_extractor": baseline.get("pending_extractor", []) + marked})

    def test_card_is_removed_everywhere_and_totals_follow(self):
        before = read(self.root / "data/source-chain-batches/batch-registry.json")
        self.assertEqual([c["candidate_id"] for c in retire([self.card_id], self.root)], [self.card_id])
        self.assertNotIn(self.card_id, [c["candidate_id"] for c in read(self.bundle)["candidates"]])
        self.assertNotIn(self.card_id, read(self.temporal)["records"])
        batch = read(self.batch)
        self.assertNotIn(self.card_id, [b["candidate_id"] for b in batch["candidate_bindings"]])
        self.assertFalse([d for d in batch["documents"] if self.card_id in d.get("candidate_ids", [])])
        alive = {d["id"] for d in batch["documents"]}
        self.assertTrue(all(e["from"] in alive and e["to"] in alive for e in batch["edges"]))
        after = read(self.root / "data/source-chain-batches/batch-registry.json")
        self.assertEqual(after["total_schemes_covered"], before["total_schemes_covered"] - 1)
        self.assertEqual(after["total_documents"], sum(e["documents"] for e in after["batches"]))

    def test_hand_card_source_leaves_the_schedule_and_the_intake(self):
        retire([self.lone["candidate_id"]], self.root)
        source = next(s for s in read(self.root / "data/scan-sources.json")["sources"] if s["id"] == self.lone["source_metadata"]["source_id"])
        self.assertIs(source["enabled"], False)
        # 手寫卡的 profile 沒驗證過，撤卡後提交流程也不能再拿來用。
        self.assertEqual(source["automation"], "not_enabled")

    def test_retired_card_leaves_every_baseline_list(self):
        retire([self.card_id], self.root)
        after = read(self.root / "data/known-hand-authored-candidates.json")
        self.assertNotIn(self.card_id, after["candidate_ids"])
        self.assertNotIn(self.card_id, after["pending_extractor"])

    def test_scrub_clears_references_left_by_an_automatic_replacement(self):
        # 提案自動取代手寫卡時，卡片檔已不含它；scrub 要清掉時程紀錄與來源鏈的參照，會議批次的合成 id 不動。
        bundle = read(self.bundle)
        save(self.bundle, {**bundle, "candidates": [c for c in bundle["candidates"] if c["candidate_id"] != self.card_id]})
        conference = read(self.root / "data/source-chain-batches/batch-conference.json")
        scrub([self.card_id], self.root)
        self.assertNotIn(self.card_id, read(self.temporal)["records"])
        self.assertNotIn(self.card_id, [b["candidate_id"] for b in read(self.batch)["candidate_bindings"]])
        self.assertEqual(read(self.root / "data/source-chain-batches/batch-conference.json"), conference)

    def test_unknown_id_changes_nothing(self):
        before = (self.root / "data/known-hand-authored-candidates.json").read_bytes()
        with self.assertRaises(ValueError):
            retire([self.card_id, "cand-does-not-exist"], self.root)
        self.assertEqual((self.root / "data/known-hand-authored-candidates.json").read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
