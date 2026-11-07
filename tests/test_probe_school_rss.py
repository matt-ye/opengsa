"""RSS盤點試跑：只認頁面宣告的feed，預算用完留到下一輪，不連網。"""
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.probe_school_rss import feed_titles, find_feed_links, run

RSS = "<rss version='2.0'><channel><title>站名</title><item><title>115學年度獎學金申請</title></item><item><title>停車公告</title></item></channel></rss>".encode()
CONFIG = {"max_requests": 20, "minimum_host_interval_seconds": 0, "max_run_seconds": 180}


def row(number, url):
    return {"id": f"U{number:03d}", "name": f"學校{number}", "url": url}


def transport_for(pages):
    calls = []

    def transport(url, headers, limit):
        calls.append(url)
        if url.endswith("/robots.txt"):
            return {"status": 404, "headers": {}, "body": b""}
        status, body = pages.get(url, (404, b""))
        return {"status": status, "headers": {}, "body": body}

    transport.calls = calls
    return transport


class FeedLinkTests(unittest.TestCase):
    def test_finds_declared_links_and_ignores_unrelated_anchors(self):
        html = """<link rel="alternate" type="application/rss+xml" href="/news.xml">
        <link rel="stylesheet" href="/rss.css"><a href="feed/">訂閱</a><a href="/about">關於</a>"""
        self.assertEqual(find_feed_links(html, "https://a.edu.tw/s/"),
                         ["https://a.edu.tw/news.xml", "https://a.edu.tw/s/feed/"])

    def test_titles_only_from_items_and_html_or_dtd_is_not_a_feed(self):
        self.assertEqual(feed_titles(RSS), ["115學年度獎學金申請", "停車公告"])
        self.assertIsNone(feed_titles(b"<html><body>rss</body></html>"))
        self.assertIsNone(feed_titles(b"<!DOCTYPE rss [<!ENTITY a 'b'>]><rss/>"))
        self.assertIsNone(feed_titles(b"not xml"))


class RunTests(unittest.TestCase):
    def test_feed_is_counted_and_keyword_items_are_matched(self):
        url = "https://a.edu.tw/s"
        transport = transport_for({url: (200, b'<a href="/rss.xml">RSS</a>'), "https://a.edu.tw/rss.xml": (200, RSS)})
        results, _ = run([row(1, url)], CONFIG, {}, transport)
        self.assertEqual(results["U001"]["status"], "feed_found")
        self.assertEqual((results["U001"]["items"], results["U001"]["keyword_items"]), (2, 1))

    def test_does_not_guess_paths_or_follow_other_hosts(self):
        url = "https://a.edu.tw/s"
        transport = transport_for({url: (200, b'<a href="https://other.example/rss.xml">RSS</a>')})
        results, _ = run([row(1, url)], CONFIG, {}, transport)
        self.assertEqual(results["U001"]["status"], "no_feed")
        self.assertEqual(transport.calls, ["https://a.edu.tw/robots.txt", url])

    def test_robots_denied_skips_the_page(self):
        url = "https://a.edu.tw/s"
        calls = []

        def transport(target, headers, limit):
            calls.append(target)
            return {"status": 200, "headers": {}, "body": b"User-agent: *\nDisallow: /\n"}

        results, _ = run([row(1, url)], CONFIG, {}, transport)
        self.assertEqual(results["U001"], {"name": "學校1", "url": url, "status": "skipped", "reason": "robots_denied"})
        self.assertEqual(calls, ["https://a.edu.tw/robots.txt"])

    def test_transport_timeout_skips_school_instead_of_crashing_the_run(self):
        def transport(target, headers, limit):
            raise subprocess.TimeoutExpired("node", 23)

        results, _ = run([row(1, "https://a.edu.tw/s")], CONFIG, {}, transport)
        self.assertEqual((results["U001"]["status"], results["U001"]["reason"]), ("skipped", "transport_timeout"))

    def test_budget_exhaustion_leaves_remaining_schools_for_next_run(self):
        rows = [row(n, f"https://s{n}.edu.tw/p") for n in range(1, 4)]
        pages = {r["url"]: (200, b"<p>none</p>") for r in rows}
        first, used = run(rows, {**CONFIG, "max_requests": 4}, {}, transport_for(pages))
        self.assertEqual((sorted(first), used), (["U001", "U002"], 4))
        transport = transport_for(pages)
        second, _ = run(rows, CONFIG, first, transport)
        self.assertEqual(sorted(second), ["U001", "U002", "U003"])
        self.assertEqual(transport.calls, ["https://s3.edu.tw/robots.txt", "https://s3.edu.tw/p"])


if __name__ == "__main__":
    unittest.main()
