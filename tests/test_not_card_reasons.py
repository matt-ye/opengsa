"""讀到了卻不成卡的頁面要記下卡在哪一關，整批摘要要統計得出來。不連外。"""
import tempfile
import unittest
from unittest.mock import patch

from scripts.expand_sources import NOT_CARD_REASONS, not_card_reason
from scripts.run_hand_replacement import run

ELIGIBLE = [{"locator": "p", "text": "申請資格：本校博士班在學學生。", "kind": "paragraph"}]


def row(url="https://x.test/news/1", category="scholarship"):
    return {"url": url, "category": category}


def page(title, blocks=ELIGIBLE, kind="html"):
    return {"title": title, "blocks": blocks, "kind": kind}


class NotCardReasonTests(unittest.TestCase):
    def test_each_gate_names_itself(self):
        cases = [
            (row(category="rights"), page("某某獎學金"), "category_not_carded"),
            (row(), page("某某獎學金", kind="pdf"), "document_not_html"),
            (row("https://x.test/"), page("某某獎學金"), "site_root_page"),
            (row(), page("獎學金"), "listing_title"),
            (row(), page("某某獎學金說明會"), "information_title"),
            (row(), page("最新消息與活動"), "title_not_a_program"),
            (row(), page("某某獎學金", blocks=[{"locator": "p", "text": "歡迎踴躍參加。", "kind": "paragraph"}]), "no_eligibility_sentence"),
            (row(), page("某某獎學金"), None),
        ]
        for r, p, expected in cases:
            with self.subTest(expected=expected):
                self.assertEqual(not_card_reason(r, p, None), expected)
        self.assertTrue(all(code in NOT_CARD_REASONS for _, _, code in cases if code))

    def test_bare_category_title_gets_the_site_name_so_a_real_program_is_kept(self):
        from scripts.expand_sources import prepare_response
        from scripts.propose_radar_update import GENERIC_TITLE
        html = ("<html><head><title>五大志業∣行天宮五大志業網</title></head><body><main><h2>急難濟助</h2>"
                "<p>申請對象：家庭遭逢變故之在學學生，得向本會申請。</p></main></body></html>")
        response = {"body": html.encode(), "headers": {"content-type": "text/html"}, "url": "https://x.test/p"}
        title = prepare_response(response, {}, {"x.test"}, link_limit=None, broad_links=True, category="living")["title"]
        self.assertEqual(title, "急難濟助（行天宮五大志業網）")
        self.assertFalse(GENERIC_TITLE.search(title))
        self.assertTrue(GENERIC_TITLE.search("急難濟助"))

    def test_stored_bare_title_is_upgraded_so_the_card_can_be_refreshed(self):
        from scripts.expand_sources import profile_for
        known = {"id": "s", "title": "急難濟助", "url": "https://x.test/p"}
        self.assertEqual(profile_for(row(), {"title": "急難濟助（行天宮五大志業網）"}, known)["title"], "急難濟助（行天宮五大志業網）")
        self.assertEqual(profile_for(row(), {"title": "急難濟助"}, known)["title"], "急難濟助")
        named = {**known, "title": "某某獎學金"}
        self.assertEqual(profile_for(row(), {"title": "別的標題獎學金"}, named)["title"], "某某獎學金")

    @patch("socket.getaddrinfo", return_value=[(2, 1, 6, "", ("93.184.216.34", 443))])
    def test_batch_summary_counts_where_pages_stopped(self, _):
        body = "<html><head><title>最新消息</title></head><body><main><h1>最新消息與活動</h1><p>" + "校園活動與公告。" * 20 + "</p></main></body></html>"

        def transport(url, headers, limit):
            if url.endswith("/robots.txt"):
                return {"status": 200, "headers": {"content-type": "text/plain"}, "body": b"User-agent: *\nAllow: /\n"}
            return {"status": 200, "headers": {"content-type": "text/html"}, "body": body.encode()}
        with tempfile.TemporaryDirectory() as tmp:
            summary = run(tmp, [{"url": "https://x.test/news/1", "category": "scholarship", "cards": []}],
                          transport=transport, spacing=0, progress=lambda *a, **k: None)
        self.assertEqual(summary["not_card_reasons"], {"title_not_a_program": 1})


if __name__ == "__main__":
    unittest.main()
