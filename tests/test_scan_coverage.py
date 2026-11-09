"""排程巡檢涵蓋網站上的流程卡：每張卡的網址都有一個啟用中的來源在掃。不連外。

2026-11-08 使用者決定網站上的卡都要能由 Actions 標準流程產出並持續巡檢。手寫卡不在此限，它們的設定沒驗證過。
"""
import glob
import json
from pathlib import Path
import unittest
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


class ScanCoverageTests(unittest.TestCase):
    def test_every_pipeline_card_is_on_a_scanned_url(self):
        config = read(ROOT / "data/scan-sources.json")
        hand = set(read(ROOT / "data/known-hand-authored-candidates.json")["candidate_ids"])
        profiles = {s["id"]: s for s in config["sources"]}
        scanned = {s["url"] for s in config["sources"] if s.get("enabled", True)}
        trusted = set(config["allowed_hosts"])
        missing = []
        for path in sorted(glob.glob(str(ROOT / "data/candidates/*.json"))):
            for card in read(path)["candidates"]:
                profile = profiles.get(card["source_metadata"]["source_id"])
                # 新網域（例如民眾提交）等維護者核可後才巡檢；手寫卡的設定沒驗證過，不巡檢。
                if card["candidate_id"] in hand or (profile and urlsplit(profile["url"]).hostname not in trusted):
                    continue
                if not profile or profile["url"] not in scanned:
                    missing.append(card["candidate_id"])
        self.assertEqual(missing, [])


if __name__ == "__main__":
    unittest.main()
