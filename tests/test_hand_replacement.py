"""整批換新工具：可續跑、單一失敗不中斷、只有抽到候選的來源才取代手寫卡。不連外。"""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.expand_sources import INTAKE_OPTIONS, initial_state, run_batch
from scripts.run_hand_replacement import build_proposal, hand_targets, load_targets, run, spread

PAGE = ("<article><h1>{title}</h1><p>申請資格：國內大學碩士班、博士班在學學生。</p>"
        "<p>獎助金額：每名新臺幣五萬元。</p><p>申請期間：自115年3月1日起至115年4月15日止。</p></article>")


def row(url):
    return {"url": url, "category": "scholarship", "cards": [{"candidate_id": "x", "title": "x", "program_key": "x", "bundle": "x"}]}


def fake_repo(tmp, count=2):
    """正式資料的手寫卡會撤光：在暫存副本裡另建一個卡片檔，放幾張合成的手寫卡當素材（固定標題與網址），
    不動來源鏈索引綁定的卡片檔。"""
    root = Path(tmp) / "repo"
    for name in ("data", "schema", "docs"):
        shutil.copytree(ROOT / name, root / name)
    index_file = json.loads((root / "data/source-chain-index.json").read_text(encoding="utf-8"))["candidate_file"]
    template = next(c for path in sorted((root / "data/candidates").glob("*.json")) if not path.as_posix().endswith(index_file)
                    for c in json.loads(path.read_text(encoding="utf-8"))["candidates"])
    cards = []
    for i in range(count):
        card = json.loads(json.dumps(template))
        card.update(candidate_id=f"cand-test-hand-{i}", program_key=f"test-hand-{i}", title=f"測試第{i}號基金會清寒獎學金")
        card["source_metadata"] = {**card["source_metadata"], "url": f"https://hand{i}.test/scholarship", "source_id": f"test-hand-{i}"}
        cards.append(card)
    bundle = json.loads((root / "data/candidates/ai-tools-115.json").read_text(encoding="utf-8"))
    (root / "data/candidates/test-hand.json").write_text(json.dumps({**bundle, "candidates": cards}, ensure_ascii=False), encoding="utf-8")
    path = root / "data/known-hand-authored-candidates.json"
    baseline = json.loads(path.read_text(encoding="utf-8"))
    baseline["candidate_ids"] = baseline["candidate_ids"] + [c["candidate_id"] for c in cards]
    path.write_text(json.dumps(baseline, ensure_ascii=False), encoding="utf-8")
    return root


def public(*_):
    return [(2, 1, 6, "", ("93.184.216.34", 443))]


@patch("socket.getaddrinfo", side_effect=public)
class HandReplacementTests(unittest.TestCase):
    def test_targets_cover_every_hand_card_once_per_url(self, _):
        with tempfile.TemporaryDirectory() as tmp:
            root = fake_repo(tmp)
            known = json.loads((root / "data/known-hand-authored-candidates.json").read_text(encoding="utf-8"))["candidate_ids"]
            targets = hand_targets(root)
        self.assertEqual(len({t["url"] for t in targets}), len(targets))
        self.assertEqual(sorted(c["candidate_id"] for t in targets for c in t["cards"]), sorted(known))
        self.assertEqual(len(spread(targets, 2)), 2)

    def test_rerun_skips_finished_sources_and_a_failure_does_not_stop_the_batch(self, _):
        calls = []
        def transport(url, headers, limit):
            calls.append(url)
            if "boom" in url:
                raise RuntimeError("unexpected")
            return {"status": 404, "headers": {}, "body": b""}
        targets = [row("https://a.test/1"), row("https://boom.test/2"), row("http://plain.test/3"), row("https://b.test/4")]
        with tempfile.TemporaryDirectory() as tmp:
            summary = run(tmp, targets, transport=transport, spacing=0, progress=lambda *a, **k: None)
            self.assertEqual(summary["finished"], 4)
            self.assertEqual(summary["statuses"]["invalid_url"], 1)
            self.assertEqual(summary["statuses"]["unexpected_RuntimeError"], 1)
            first = len(calls)
            run(tmp, targets, transport=transport, spacing=0, progress=lambda *a, **k: None)
            self.assertEqual(len(calls), first)

    def test_research_targets_skip_duplicates_and_urls_already_run(self, _):
        # 手寫卡撤光後沒有「已跑過」的網址可用，這一段就只測去重。
        already = [{"url": t["url"], "category": "scholarship"} for t in hand_targets()[:1]]
        rows = already + [{"url": "https://a.test/x", "category": "living"}, {"url": "https://a.test/x", "category": "living"}]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "targets.json"
            path.write_text(json.dumps(rows), encoding="utf-8")
            self.assertEqual(load_targets(path), [{"url": "https://a.test/x", "category": "living", "cards": []}])

    def test_blocked_host_is_not_asked_again(self, _):
        calls = []
        def transport(url, headers, limit):
            calls.append(url)
            return {"status": 403, "headers": {}, "body": b""}
        with tempfile.TemporaryDirectory() as tmp:
            summary = run(tmp, [row("https://a.test/1"), row("https://a.test/2")], transport=transport, spacing=0, progress=lambda *a, **k: None)
        self.assertEqual(len(calls), 1)
        self.assertEqual(summary["statuses"]["host_paused"], 1)

    def test_only_sources_with_a_candidate_replace_their_hand_card(self, _):
        with tempfile.TemporaryDirectory() as tmp:
            root = fake_repo(tmp)
            hit, miss = hand_targets(root)[:2]
            single = [hit, miss]
            # 頁面標題要含「獎學金」才會成卡；手寫卡標題沒有就補在後面，仍認得出是同一方案。
            title = hit["cards"][0]["title"] + ("" if "獎學金" in hit["cards"][0]["title"] else "獎學金")
            def transport(url, headers, limit):
                if url == hit["url"]:
                    return {"status": 200, "headers": {"content-type": "text/html"}, "body": PAGE.format(title=title).encode()}
                return {"status": 404, "headers": {}, "body": b""}
            out = Path(tmp) / "out"
            with patch("scripts.propose_radar_update.ROOT", root), patch("scripts.run_hand_replacement.ROOT", root):
                run(out, single, transport=transport, spacing=0, progress=lambda *a, **k: None)
                summary = build_proposal(out, single, preview=False)
            self.assertTrue((out / "proposal/repo/data/candidates/source-review.json").exists())
        retired = {r["candidate_id"] for r in summary["retired_hand_cards"]}
        self.assertEqual(retired, {c["candidate_id"] for c in hit["cards"]})
        self.assertFalse(retired & {c["candidate_id"] for c in miss["cards"]})
        self.assertEqual((summary["human_approvals"], summary["published"]), (0, False))

    def test_request_timeout_is_recorded_for_that_page(self, _):
        def transport(url, headers, limit):
            raise subprocess.TimeoutExpired("node", 23)
        inventory = {"rows": [{"id": "R", "url": "https://a.test/1", "title": "", "batch": "B1", "category": "scholarship", "restrictions": []}]}
        with tempfile.TemporaryDirectory() as tmp:
            state = run_batch(inventory, initial_state(inventory), "B1", Path(tmp) / "state.json", {"sources": []}, transport=transport, progress=lambda *a, **k: None, options=INTAKE_OPTIONS)
        self.assertEqual(state["records"]["https://a.test/1"]["status"], "TimeoutExpired")


if __name__ == "__main__":
    unittest.main()
