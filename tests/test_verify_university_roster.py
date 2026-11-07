"""名冊驗證：只有頁面實際驗得到才算獎助頁，不猜路徑、不離開同校網域，不連網。"""
import json
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.verify_university_roster import classify, run

CONFIG = {"max_requests": 40, "minimum_host_interval_seconds": 0, "max_run_seconds": 180}


def row(portal="https://osa.a.edu.tw/s", assistance="", affairs="", home="https://www.a.edu.tw/"):
    return {"id": "U001", "name": "甲大學", "url": portal, "scholarship_portal_url": portal,
            "assistance_office_url": assistance, "student_affairs_url": affairs, "official_website": home}


def html(title, *links):
    anchors = "".join(f'<a href="{href}">{label}</a>' for href, label in links)
    return f"<html><head><title>{title}</title></head><body>{anchors}</body></html>".encode()


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


class VerifyTests(unittest.TestCase):
    def test_working_portal_with_matching_heading_stops_immediately(self):
        pages = {"https://osa.a.edu.tw/s": (200, html("獎助學金專區"))}
        transport = transport_for(pages)
        results, _, _ = run([row()], CONFIG, {}, transport)
        self.assertEqual((results["U001"]["level"], results["U001"]["url"]), ("portal", "https://osa.a.edu.tw/s"))
        self.assertNotIn("https://www.a.edu.tw/", transport.calls)

    def test_200_without_scholarship_heading_is_not_called_a_portal(self):
        pages = {"https://osa.a.edu.tw/s": (200, html("首頁"))}
        results, _, _ = run([row(home="")], CONFIG, {}, transport_for(pages))
        self.assertEqual(results["U001"]["level"], "official_website")

    def test_broken_portal_walks_links_from_homepage(self):
        pages = {
            "https://www.a.edu.tw/": (200, html("甲大學", ("https://sa.a.edu.tw/", "學務處"), ("/about", "關於"))),
            "https://sa.a.edu.tw/": (200, html("學務處", ("/scholar", "獎助學金"))),
            "https://sa.a.edu.tw/scholar": (200, html("獎助學金")),
        }
        results, _, _ = run([row()], CONFIG, {}, transport_for(pages))
        self.assertEqual((results["U001"]["level"], results["U001"]["url"]), ("portal", "https://sa.a.edu.tw/scholar"))
        self.assertEqual(results["U001"]["checks"]["https://osa.a.edu.tw/s"], 404)

    def test_never_follows_links_outside_the_school_domain(self):
        pages = {"https://www.a.edu.tw/": (200, html("甲大學", ("https://other.example/x", "獎學金查詢")))}
        transport = transport_for(pages)
        results, _, _ = run([row()], CONFIG, {}, transport)
        self.assertEqual(results["U001"]["level"], "official_website")
        self.assertFalse([url for url in transport.calls if "other.example" in url])

    def test_nothing_reachable_reports_none_and_remembers_dead_host(self):
        def transport(url, headers, limit):
            raise subprocess.TimeoutExpired("node", 23)

        results, dead, _ = run([row(home="")], CONFIG, {}, transport)
        self.assertIsNone(results["U001"]["level"])
        self.assertIsNone(results["U001"]["url"])
        self.assertEqual(dead, {"osa.a.edu.tw": "transport_timeout"})

    def test_long_announcement_titles_and_files_are_not_portals(self):
        pages = {"https://www.a.edu.tw/": (200, html(
            "甲大學",
            ("/p/1.php", "教育部115學年度獎學金開始受理申請公告"),
            ("/f/a.pdf", "獎學金"),
            ("/course/9", "獎學金"),
        ))}
        transport = transport_for(pages)
        results, _, _ = run([row()], CONFIG, {}, transport)
        self.assertEqual(results["U001"]["level"], "official_website")
        self.assertFalse([url for url in transport.calls if url.endswith(("/p/1.php", ".pdf", "/course/9"))])

    def test_classify_prefers_deepest_level(self):
        self.assertEqual(classify("學務處獎助學金"), "portal")
        self.assertEqual(classify("生活輔導組"), "assistance")
        self.assertEqual(classify("學務處"), "student_affairs")
        self.assertIsNone(classify("招生資訊"))


class RosterDataTests(unittest.TestCase):
    def test_university_candidates_carry_no_hardcoded_dates_and_roster_status_is_honest(self):
        read = lambda name: json.loads((ROOT / "data" / name).read_text(encoding="utf-8"))
        for candidate in read("candidates/university-scholarships.json")["candidates"]:
            self.assertEqual(candidate["schedule"]["steps"][0]["deadline"]["kind"], "unknown")
        for record in read("university-temporal-observations.json")["records"].values():
            self.assertEqual(record["policy"]["rules"], [])
        statuses = {row["observation_status"] for row in read("source-expansion/university-source-inventory.json")["rows"]}
        self.assertNotIn("verified_university_portal", statuses)


if __name__ == "__main__":
    unittest.main()
