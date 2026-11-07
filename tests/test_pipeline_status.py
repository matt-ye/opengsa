"""來源狀態檔：CSV 與 JSON 同一份資料、不含執行時間、來源沒變就不改檔。不連外。"""
import csv
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.pipeline_status import render, write

CONFIG = {"sources": [{"id": "a", "url": "https://a.test/x"}, {"id": "b", "url": "https://b.test/y"},
                      {"id": "c", "url": "https://c.test/z", "enabled": False}, {"id": "d", "url": "https://d.test/w"}]}
STATE = {"documents": {"https://a.test/x": {"semantic_sha256": "1" * 64, "last_checked_at": "2026-11-08T00:00:00+00:00",
                                            "attachments": [{"url": "https://a.test/x.pdf"}]},
                       "https://a.test/x.pdf": {"semantic_sha256": "2" * 64, "last_checked_at": "2026-11-08T00:00:00+00:00"}},
         "failures": {"https://b.test/y": {"count": 2, "status": "http_404", "last_failed_at": "2026-11-08T00:00:00+00:00", "skips_left": 1}},
         "pending": {"r1": {"source_id": "a", "url": "https://a.test/x"}}, "last_run_at": "2026-11-08T00:00:00+00:00"}


class PipelineStatusTests(unittest.TestCase):
    def test_csv_and_json_carry_the_same_rows(self):
        text, document = render(CONFIG, STATE)
        table = list(csv.DictReader(io.StringIO(text)))
        sources = json.loads(document)["sources"]
        self.assertEqual([r["source_id"] for r in table], [s["source_id"] for s in sources])
        self.assertEqual([(r["status"], r["failures"], r["pending"]) for r in table],
                         [("ok", "0", "1"), ("http_404", "2", "0"), ("disabled", "0", "0"), ("not_checked", "0", "0")])
        self.assertEqual(sources[0]["chain"], [{"url": "https://a.test/x.pdf", "status": "ok", "failures": 0, "revision": "2" * 12}])

    def test_no_run_time_so_an_unchanged_scan_writes_nothing(self):
        text, document = render(CONFIG, STATE)
        self.assertNotIn("2026-11-08", text + document)
        with tempfile.TemporaryDirectory() as folder:
            self.assertTrue(write(CONFIG, STATE, folder))
            later = {**STATE, "last_run_at": "2026-11-09T00:00:00+00:00",
                     "documents": {url: {**doc, "last_checked_at": "2026-11-09T00:00:00+00:00"} for url, doc in STATE["documents"].items()}}
            self.assertFalse(write(CONFIG, later, folder))
            changed = {**STATE, "documents": {**STATE["documents"], "https://a.test/x": {**STATE["documents"]["https://a.test/x"], "semantic_sha256": "3" * 64}}}
            self.assertTrue(write(CONFIG, changed, folder))


    def test_status_job_only_writes_status_files(self):
        workflow = (ROOT / ".github/workflows/scan-sources.yml").read_text(encoding="utf-8")
        job = workflow.split("\n  status:")[1].split("\n  review-workspace:")[0]
        self.assertIn("needs: scan", job)
        self.assertIn("contents: write", job)
        self.assertNotIn("pull-requests", job)
        self.assertNotIn("secrets.", job)
        self.assertNotIn("scan_sources", job)  # 不抓公開網頁
        self.assertIn("persist-credentials: false", job)
        self.assertIn("git add -- status", job)
        self.assertNotIn("restore-keys", job)  # 只讀這一輪的狀態


if __name__ == "__main__":
    unittest.main()
