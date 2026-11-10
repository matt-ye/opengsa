"""入口頁巡檢：合併掃描提案與入口頁提案、沒有新方案時沿用掃描提案、已知來源不再跟。不連外。"""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts import watch_entry_pages as watch
from scripts.expand_sources import INTAKE_OPTIONS, initial_state, run_batch


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def proposal(directory, files, accepted):
    for name, value in files.items():
        save(directory / "repo" / name, value)
    save(directory / "summary.json", {"accepted_for_radar_proposal": accepted, "withheld_failed_checks": 0, "temporal_records": accepted,
                                      "dropped_not_distinct": [{"title": f"drop-{accepted}"}]})
    return directory


class WatchEntryPagesTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.root = self.dir / "repo"
        save(self.root / watch.REGISTRY, {"pages": [{"url": "https://osa.demo.edu.tw/aid", "category": "living_tuition"}]})

    def test_entry_files_win_and_scan_only_files_are_kept(self):
        base = proposal(self.dir / "base", {"data/a.json": "scan", "data/b.json": "scan"}, 2)

        def proposer(output, targets, preview):
            proposal(Path(output) / "proposal", {"data/b.json": "scan+entry"}, 1)
            return {"accepted_for_radar_proposal": 1}
        with mock.patch.object(watch, "apply_proposal") as apply:
            result = watch.watch(self.dir / "out", base, root=self.root, runner=lambda *a, **k: None, proposer=proposer)
        apply.assert_called_once()  # 入口頁提案要建在掃描結果之上
        final = self.dir / "out/proposal"
        self.assertEqual(json.loads((final / "repo/data/a.json").read_text(encoding="utf-8")), "scan")
        self.assertEqual(json.loads((final / "repo/data/b.json").read_text(encoding="utf-8")), "scan+entry")
        summary = json.loads((final / "summary.json").read_text(encoding="utf-8"))
        self.assertEqual((summary["accepted_for_radar_proposal"], summary["entry_pages_accepted"]), (3, 1))
        self.assertEqual(len(summary["dropped_not_distinct"]), 2)
        self.assertEqual((result["has_proposal"], result["entry_pages_accepted"]), (True, 1))

    def test_no_new_programs_keeps_the_scan_proposal(self):
        base = proposal(self.dir / "base", {"data/a.json": "scan"}, 2)

        def nothing(output, targets, preview):
            raise ValueError("no_candidates_to_propose")
        with mock.patch.object(watch, "apply_proposal"):
            result = watch.watch(self.dir / "out", base, root=self.root, runner=lambda *a, **k: None, proposer=nothing)
        self.assertTrue(result["has_proposal"])
        self.assertTrue((self.dir / "out/proposal/repo/data/a.json").exists())

    def test_nothing_anywhere_means_no_proposal(self):
        def nothing(output, targets, preview):
            raise ValueError("no_candidates_to_propose")
        result = watch.watch(self.dir / "out", self.dir / "missing", root=self.root, runner=lambda *a, **k: None, proposer=nothing)
        self.assertFalse(result["has_proposal"])

    def test_runner_gets_the_entry_pages_and_skips_known_children(self):
        seen = {}

        def runner(output, targets, max_requests, options):
            seen.update(targets=targets, options=options)
        def nothing(output, targets, preview):
            raise ValueError("no_candidates_to_propose")
        watch.watch(self.dir / "out", None, root=self.root, runner=runner, proposer=nothing)
        self.assertEqual(seen["targets"], [{"url": "https://osa.demo.edu.tw/aid", "category": "living_tuition", "cards": []}])
        self.assertTrue(seen["options"]["skip_known_children"])


class SkipKnownChildrenTests(unittest.TestCase):
    PAGE = ('<html><head><title>獎助學金專區</title></head><body><main><h1>獎助學金專區</h1>'
            '<a href="/known">校內獎學金申請辦法</a><a href="/new">清寒助學金申請辦法</a></main></body></html>')

    def run_page(self, options):
        fetched = []

        def transport(url, headers, limit):
            fetched.append(url)
            if url.endswith("robots.txt"):
                return {"status": 404, "headers": {}, "body": b""}
            if url.endswith("/aid"):
                return {"status": 200, "headers": {"content-type": "text/html"}, "body": self.PAGE.encode()}
            return {"status": 404, "headers": {}, "body": b""}
        inventory = {"rows": [{"id": "E", "url": "https://osa.demo.edu.tw/aid", "title": "", "batch": "B1", "category": "living_tuition", "restrictions": []}]}
        config = {"sources": [{"id": "k", "url": "https://osa.demo.edu.tw/known", "enabled": True}]}
        with tempfile.TemporaryDirectory() as tmp, mock.patch("scripts.scan_sources.pause"):
            run_batch(inventory, initial_state(inventory), "B1", Path(tmp) / "state.json", config, transport=transport,
                      progress=lambda *a, **k: None, options=options)
        return fetched

    def test_known_sources_are_not_followed(self):
        fetched = self.run_page({**INTAKE_OPTIONS, "skip_known_children": True})
        self.assertIn("https://osa.demo.edu.tw/new", fetched)
        self.assertNotIn("https://osa.demo.edu.tw/known", fetched)

    def test_default_still_follows_known_sources(self):
        self.assertIn("https://osa.demo.edu.tw/known", self.run_page(INTAKE_OPTIONS))


if __name__ == "__main__":
    unittest.main()
