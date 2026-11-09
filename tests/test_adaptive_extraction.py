"""萃取適應性：標題來源、名稱欄位、小標題下的資格、索引頁判斷、標題雜訊、同站去重、單位不明的金額。不連外、不呼叫模型。"""
import unittest

from bs4 import BeautifulSoup

from scripts.expand_sources import clean_title, labelled_name, prepare_response
from scripts.extract_candidates import withhold_unsure_generic_fields
from scripts.propose_radar_update import FORM_DOCUMENT, GENERIC_TITLE, distinct_named_cards
from scripts.semantic_facts import discover_identity

HOSTS = {"x.test"}


def page(html, category):
    response = {"body": html.encode(), "headers": {"content-type": "text/html"}, "url": "https://x.test/p"}
    return prepare_response(response, {}, HOSTS, link_limit=None, broad_links=True, category=category)


class AdaptiveExtractionTests(unittest.TestCase):
    def test_empty_h1_falls_back_to_a_title_that_names_a_program(self):
        html = "<html><head><title>某某市急難救助要點</title></head><body><main><h1></h1><p>設籍本市之市民得向區公所申請急難救助。</p></main></body></html>"
        self.assertEqual(page(html, "living")["title"], "某某市急難救助要點")

    def test_labelled_name_field_gives_the_title_with_site_for_short_names(self):
        soup = BeautifulSoup("<title>某市福利查詢</title><div>福利名稱：</div><div>申請急難救助</div>", "html.parser")
        self.assertEqual(labelled_name(soup, "living"), "申請急難救助（某市福利查詢）")
        soup = BeautifulSoup("<title>法規查詢</title><div>名　　稱 某市急難救助金核發作業要點</div>", "html.parser")
        self.assertEqual(labelled_name(soup, "living"), "某市急難救助金核發作業要點")
        self.assertEqual(labelled_name(soup, "scholarship"), "")

    def test_repeated_perk_heading_beats_a_one_off_faq(self):
        html = ("<html><head><title>Music</title></head><body><main><h1>Music</h1><h3>學生方案</h3><p>學生享優惠價。</p>"
                "<h3>學生方案</h3><h3>是否提供學生方案？</h3></main></body></html>")
        self.assertEqual(page(html, "ai")["title"], "Music 學生方案")

    def test_eligibility_under_a_heading_and_apply_wording(self):
        under = [{"locator": "a", "text": "四、申請資格", "kind": "heading"},
                 {"locator": "b", "text": "家境清寒之國小、國中、高中在學學生。", "kind": "paragraph"}]
        self.assertEqual(discover_identity(under, "living")["units"][0]["locator"], "b")
        apply = [{"locator": "a", "text": "本校學生在學期間發生重大變故者，得檢具證明申請急難慰問金。", "kind": "paragraph"}]
        self.assertIsNotNone(discover_identity(apply, "living"))
        english = [{"locator": "a", "text": "For eligible students at universities pursuing research.", "kind": "paragraph"}]
        self.assertEqual(discover_identity(english)["kind"], "eligibility_clause")

    def test_title_noise_is_removed_but_month_numbers_stay(self):
        self.assertEqual(clean_title("01-1急難扶助辦法施行細則11150310"), "急難扶助辦法施行細則")
        self.assertEqual(clean_title("大專校院不利處境學生助學計畫115.6.30"), "大專校院不利處境學生助學計畫")
        self.assertEqual(clean_title("生活助學金申請公告📅"), "生活助學金申請公告")
        self.assertEqual(clean_title("10月份獎學金公告"), "10月份獎學金公告")
        self.assertEqual(clean_title("急難救助  - 學生安全組"), "急難救助")

    def test_warning_and_explainer_tails_are_removed_but_deadlines_stay(self):
        self.assertEqual(clean_title("115學年度大專校院「不利處境學生助學計畫-助學金」申辦公告更新⛔逾時視同放棄！"),
                         "115學年度大專校院「不利處境學生助學計畫-助學金」申辦公告更新")
        self.assertEqual(clean_title("2026鴻海獎學鯨｜高中、國中、國小申請說明"), "2026鴻海獎學鯨")
        self.assertEqual(clean_title("NQU清寒優秀勵學獎學金要點-1141231"), "NQU清寒優秀勵學獎學金要點")
        self.assertEqual(clean_title("01.三重東區扶輪社獎學金"), "三重東區扶輪社獎學金")
        self.assertEqual(clean_title("學產基金助學金申辦延至10/9截止收件"), "學產基金助學金申辦延至10/9截止收件")
        self.assertEqual(clean_title("Figma for Education | Free tools"), "Figma for Education | Free tools")

    def test_stored_titles_get_the_current_cleanup(self):
        from scripts.expand_sources import profile_for
        known = {"id": "s", "title": "2026鴻海獎學鯨｜高中、國中、國小申請說明"}
        self.assertEqual(profile_for({"category": "living"}, {"title": "x"}, known)["title"], "2026鴻海獎學鯨")
        bare = {"id": "s", "title": "急難救助  - 學生安全組"}
        self.assertEqual(profile_for({"category": "living"}, {"title": "急難救助"}, bare)["title"], "急難救助  - 學生安全組")

    def test_bare_category_titles_and_paperwork_do_not_become_cards(self):
        self.assertTrue(GENERIC_TITLE.search("急難救助"))
        self.assertFalse(GENERIC_TITLE.search("臺北市急難救助金核發作業要點"))
        self.assertTrue(FORM_DOCUMENT.search("家庭經濟條件應計列範圍說明及切結書"))

    def test_one_title_inside_another_on_the_same_site_is_one_program(self):
        card = lambda i, title, url: {"candidate_id": i, "title": title, "source_metadata": {"url": url}}
        kept, dropped = distinct_named_cards([card("a", "不利處境學生助學金", "https://x.test/a"),
                                              card("b", "大專校院不利處境學生助學金申請簡介", "https://x.test/b"),
                                              card("c", "不利處境學生助學金", "https://y.test/c")])
        self.assertEqual([c["candidate_id"] for c in kept], ["a", "c"])
        self.assertEqual(dropped[0]["reason"], "same_program_same_site")

    def test_amount_without_a_unit_is_left_for_the_source(self):
        cand = {"benefit": {}, "field_evidence": [], "cycle": {}, "eligibility": {"degrees": [], "nationality": "unknown", "identity": {"text": "", "refs": []}}}
        units = [{"locator": "a", "text": "學生急難救助金至多50,000元。", "kind": "paragraph"}]
        withhold_unsure_generic_fields(cand, units, "s", "r" * 64, "hash_only")
        self.assertEqual(cand["benefit"]["items"], [])


if __name__ == "__main__":
    unittest.main()
