import unittest
from unittest import mock

from scripts import discover_universities as du

# 合成網站（非真實學校）：首頁 -> 學務處 -> 獎助索引頁；另有一頁只是單篇公告。
PAGES = {
    "https://www.demo.edu.tw/": '<html><head><title>示範大學</title></head><body><nav>'
        '<a href="https://osa.demo.edu.tw/">學務處</a><a href="/news">最新消息</a></nav><main><p>歡迎</p></main></body></html>',
    "https://osa.demo.edu.tw/": '<html><head><title>學務處</title></head><body><nav><a href="/aid">獎助學金專區</a>'
        '<a href="/notice">獎學金得獎名單</a><a href="/one">獎學金公告</a></nav><main><p>學務處首頁</p></main></body></html>',
    "https://osa.demo.edu.tw/aid": '<html><head><title>獎助學金專區</title></head><body><main><h1>獎助學金專區</h1>'
        '<a href="/aid/a">校內獎學金</a><a href="/aid/b">弱勢助學金</a><a href="/aid/c">急難救助金</a><a href="/aid/d">學雜費減免</a></main></body></html>',
    "https://osa.demo.edu.tw/one": '<html><head><title>公告</title></head><body><main><h1>最新公告</h1>'
        '<p>本週行政公告一則。</p></main></body></html>',
}


def transport(url, headers, limit):
    if url.endswith("/robots.txt"):
        return {"status": 404, "headers": {}, "body": b""}
    body = PAGES.get(url)
    if body is None:
        return {"status": 404, "headers": {"content-type": "text/html"}, "body": b"not found"}
    return {"status": 200, "headers": {"content-type": "text/html; charset=utf-8"}, "body": body.encode()}


SCHOOL = {"id": "T001", "name": "示範大學", "url": "https://www.demo.edu.tw/"}


def browser():
    return du.Browser(50, transport=transport, sleeper=lambda seconds: None)


class DiscoverTest(unittest.TestCase):
    def test_rule_path_finds_index_page_through_student_affairs(self):
        result = du.discover(SCHOOL, browser(), None, None, {"model_calls": 0})
        self.assertEqual(result["status"], "found")
        self.assertEqual(result["source"], "rule")
        self.assertEqual([e["url"] for e in result["entries"]], ["https://osa.demo.edu.tw/aid"])
        # 得獎名單被排除；單篇公告不是索引頁也不成卡，不會被採用。
        self.assertNotIn("https://osa.demo.edu.tw/notice", [l["url"] for l in result["rule"]["links"]])

    def test_navigation_links_do_not_make_every_page_an_index(self):
        ok, basis = du.verify(browser(), "https://osa.demo.edu.tw/one", "demo.edu.tw")
        self.assertFalse(ok, basis)

    def test_model_answer_is_used_when_verified(self):
        answers = iter([{"action": "open", "n": 1}, {"action": "answer", "n": [1]}])
        fake = lambda provider, messages, cache: ({"raw": "{}", "action": next(answers)}, False)
        with mock.patch.object(du, "ask_model", fake), mock.patch.object(du.time, "sleep"):
            result = du.discover(SCHOOL, browser(), "groq", None, {"model_calls": 5})
        self.assertEqual(result["source"], "model")
        self.assertEqual([e["url"] for e in result["entries"]], ["https://osa.demo.edu.tw/aid"])

    def test_unverified_model_answer_falls_back_to_rules(self):
        answers = iter([{"action": "open", "n": 1}, {"action": "answer", "n": [3]}])  # 第 3 個是單篇公告
        fake = lambda provider, messages, cache: ({"raw": "{}", "action": next(answers)}, False)
        with mock.patch.object(du, "ask_model", fake), mock.patch.object(du.time, "sleep"):
            result = du.discover(SCHOOL, browser(), "groq", None, {"model_calls": 5})
        self.assertEqual(result["source"], "rule")
        self.assertEqual(result["model"]["accepted"], 0)

    def test_model_error_falls_back_to_rules(self):
        def broken(provider, messages, cache):
            raise TimeoutError
        with mock.patch.object(du, "ask_model", broken):
            result = du.discover(SCHOOL, browser(), "groq", None, {"model_calls": 5})
        self.assertEqual(result["source"], "rule")
        self.assertEqual(result["model"]["steps"], [{"stop": "model_error:TimeoutError"}])

    def test_off_site_links_are_refused(self):
        with self.assertRaises(du.ScanError):
            browser().open("https://evil.example.com/", "demo.edu.tw")

    def test_issue_lists_found_and_missing(self):
        text = du.issue_markdown([
            {"id": "T001", "name": "示範大學", "status": "found", "source": "rule",
             "entries": [{"label": "獎助學金專區", "url": "https://osa.demo.edu.tw/aid", "basis": "索引頁"}]},
            {"id": "T002", "name": "另一所", "status": "not_found", "entries": []}])
        self.assertIn("- [ ] T001 示範大學（rule）網域：osa.demo.edu.tw", text)
        self.assertIn("- T002 另一所（not_found）", text)

    def test_issue_escapes_page_text(self):
        text = du.issue_markdown([{"id": "T001", "name": "示範", "status": "found", "source": "rule",
                                   "entries": [{"label": "@someone [x](y) #5", "url": "https://osa.demo.edu.tw/aid", "basis": "索引頁"}]}])
        self.assertNotIn("@someone", text)
        self.assertNotIn("#5", text)

    def test_only_ticked_schools_become_targets(self):
        results = [{"id": "T001", "status": "found", "entries": [{"url": "https://osa.demo.edu.tw/aid"}]},
                   {"id": "T002", "status": "found", "entries": [{"url": "https://osa.other.edu.tw/aid"}]}]
        body = "- [x] T001 示範（rule）網域：osa.demo.edu.tw\n- [ ] T002 另一所（rule）網域：osa.other.edu.tw\n"
        self.assertEqual(du.approved_targets(body, results), [{"url": "https://osa.demo.edu.tw/aid", "category": du.CATEGORY}])


if __name__ == "__main__":
    unittest.main()
