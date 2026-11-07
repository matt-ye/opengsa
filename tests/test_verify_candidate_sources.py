"""候選來源連線檢查：記錄狀態、遵守預算、不連網。"""
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.verify_candidate_sources import collect, run

CONFIG = {"max_requests": 20, "minimum_host_interval_seconds": 0, "max_run_seconds": 180}


def transport(url, headers, limit):
    if url.endswith("/robots.txt"):
        return {"status": 404, "headers": {}, "body": b""}
    if url.endswith("/ok"):
        return {"status": 200, "headers": {}, "body": "<title>獎學金</title>".encode()}
    return {"status": 404, "headers": {}, "body": b""}


class SourceCheckTests(unittest.TestCase):
    def test_records_status_and_title(self):
        results, _, _ = run(["https://a.tw/ok", "https://a.tw/no"], CONFIG, {}, transport)
        self.assertEqual((results["https://a.tw/ok"]["status"], results["https://a.tw/ok"]["title"]), (200, "獎學金"))
        self.assertEqual(results["https://a.tw/no"]["status"], 404)

    def test_budget_leaves_rest_for_next_run(self):
        urls = [f"https://h{n}.tw/ok" for n in range(3)]
        first, _, used = run(urls, {**CONFIG, "max_requests": 4}, {}, transport)
        self.assertEqual((len(first), used), (2, 4))
        second, _, _ = run(urls, CONFIG, {"results": first}, transport)
        self.assertEqual(len(second), 3)

    def test_timeout_marks_host_dead_without_more_requests(self):
        calls = []

        def slow(url, headers, limit):
            calls.append(url)
            raise subprocess.TimeoutExpired("node", 23)

        results, dead, _ = run(["https://a.tw/1", "https://a.tw/2"], CONFIG, {}, slow)
        self.assertEqual(dead, {"a.tw": "transport_timeout"})
        self.assertEqual(results["https://a.tw/2"]["status"], "transport_timeout")
        self.assertEqual(len(calls), 1)

    def test_collect_covers_every_candidate(self):
        total = sum(len(rows) for rows in collect().values())
        self.assertEqual(total, 256)


if __name__ == "__main__":
    unittest.main()
