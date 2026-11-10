"""讀到了卻不成卡的頁面要記下卡在哪一關，整批摘要要統計得出來。不連外。"""
import tempfile
import unittest
from unittest.mock import patch

from scripts.expand_sources import NOT_CARD_REASONS, not_card_reason
from scripts.run_hand_replacement import run

ELIGIBLE = [{"locator": "p", "text": "申請資格：本校博士班在學學生。", "kind": "paragraph"}]


def setUpModule():
    # 假網站不用等同站間隔（每站 3 秒）；間隔規則本身由 test_scanner 檢查。
    import unittest.mock
    from scripts import scan_sources
    patcher = unittest.mock.patch.object(scan_sources, "pause", lambda seconds: None)
    patcher.start()
    unittest.addModuleCleanup(patcher.stop)


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

    def test_school_pages_rejected_in_pr134(self):
        """#134 人工駁回的三類學校頁：往年公告、學校的行政規定；本年度與還沒到的學年度照常成卡。"""
        from datetime import date
        from scripts import expand_sources
        living = row(category="living")
        with patch.object(expand_sources, "today", lambda: date(2026, 11, 11)):
            cases = [
                # 早兩個學年度以上：往年公告。
                (page("113 學年度清寒獎學金"), "past_year_title"),
                # 早一個學年度、申請日期也在去年（114 年）：往年公告。
                (page("114學年度「余傳韜校長紀念獎助學金」申請自114年4月15日起至6月3日止"), "past_year_title"),
                # 早一個學年度常是「上一學年成績」的獎學金，今年才申請；看不出是往年就照常成卡。
                (page("114學年度周惠慈獎學金收件期間:11月3日至11月21日"), None),
                (page("115-1 台北市東莞同鄉會-114學年度獎學金(截止日11/30)"), None),
                # 審查結果公告不是方案。
                (page("【生活輔導組】114學年度弱勢助學金-所得/財產查核結果"), "information_title"),
                (page("115學年度「余傳韜校長紀念獎助學金」申請自115年4月13日起"), None),
                (page("113-115學年度某某獎學金"), None),
                # 西元年不是民國學年度。
                (page("2026學年度某某獎學金"), None),
                (page("「接受捐贈獎學金行政運作及管理作業要點」115-5"), "admin_title"),
                (page("接受捐贈獎學金作業規定110-3"), "admin_title"),
                (page("某某校友接受捐贈之清寒獎學金"), None),
            ]
            for p, expected in cases:
                with self.subTest(title=p["title"]):
                    self.assertEqual(not_card_reason(living, p, None), expected)
        # 八月起是新學年度：2026-07 還在 114 學年度，113 只早一年，112 才早兩年。
        with patch.object(expand_sources, "today", lambda: date(2026, 7, 31)):
            self.assertIsNone(not_card_reason(living, page("113學年度清寒獎學金"), None))
            self.assertEqual(not_card_reason(living, page("112學年度清寒獎學金"), None), "past_year_title")
        self.assertIn("past_year_title", NOT_CARD_REASONS)
        self.assertEqual(not_card_reason(living, page("碩博士論文獎助最新公告"), None), "listing_title")

    def test_school_titles_drop_office_prefix_but_keep_school(self):
        from scripts.expand_sources import clean_title
        self.assertEqual(clean_title("國立嘉義大學-學生事務處生活輔導組-115學年度「余傳韜校長紀念獎助學金」申請"),
                         "國立嘉義大學115學年度「余傳韜校長紀念獎助學金」申請")
        self.assertEqual(clean_title("【生活輔導組】115學年度不利處境助學金申請公告"), "115學年度不利處境助學金申請公告")

    def test_school_category_relaxes_title_and_audience_rules(self):
        """探索與入口頁用來源類別 living：學校的助學金、紓困金頁不寫「獎學金」，資格寫的是學生身分。"""
        from scripts import discover_universities
        self.assertEqual(discover_universities.CATEGORY, "living")
        blocks = [{"locator": "p", "text": "申請對象：本校家境清寒之在學學生，得向生活輔導組申請。", "kind": "paragraph"}]
        self.assertIsNone(not_card_reason(row(category="living"), page("暖陽紓困助學金", blocks=blocks), None))
        self.assertEqual(not_card_reason(row(category="living_tuition"), page("暖陽紓困助學金", blocks=blocks), None),
                         "title_not_a_program")

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
