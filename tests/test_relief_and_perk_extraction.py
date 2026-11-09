"""急難救助、家庭補助與學生優惠的成卡規則：只在這兩類來源放寬，獎學金來源維持原規則。不連外、不呼叫模型。"""
import unittest

from scripts.expand_sources import clean_title, named_candidate, resource_title
from scripts.propose_radar_update import FORM_DOCUMENT, GENERIC_TITLE, distinct_named_cards
from scripts.semantic_facts import discover_identity


def blocks(*texts, kind="paragraph"):
    return [{"locator": f"SYNTH/{i}", "text": text, "kind": kind} for i, text in enumerate(texts)]


RELIEF = blocks("申請對象：本校學生家庭遭逢重大變故，經濟陷入困境者。", "檢附證明文件向生活輔導組申請。")
PERK = blocks("Students get free access with a verified school email.")


class ReliefAndPerkTests(unittest.TestCase):
    def test_relief_titles_count_only_for_living_sources(self):
        self.assertTrue(resource_title("學生急難濟助實施辦法", "living"))
        self.assertFalse(resource_title("學生急難濟助實施辦法", "scholarship"))
        self.assertTrue(resource_title("Tableau for Students", "ai"))
        self.assertFalse(resource_title("Tableau for Students", None))

    def test_household_eligibility_is_found_only_for_living_sources(self):
        self.assertIsNone(discover_identity(RELIEF))
        found = discover_identity(RELIEF, "living")
        self.assertEqual(found["kind"], "eligibility_clause")
        self.assertIn("請核對來源", found["text"])
        row = {"category": "living", "url": "https://example.test/relief"}
        self.assertTrue(named_candidate(row, {"title": "學生急難濟助", "kind": "html", "blocks": RELIEF}, None))
        self.assertFalse(named_candidate({**row, "category": "scholarship"}, {"title": "學生急難濟助", "kind": "html", "blocks": RELIEF}, None))

    def test_perk_page_uses_body_rule_or_the_title_that_names_students(self):
        self.assertIn("看來源", discover_identity(PERK, "ai")["text"])
        marketing = blocks("Build anything together.", "Plans for every team.")
        self.assertIsNone(discover_identity(marketing, "ai"))
        titled = blocks("Figma for Education", kind="heading") + marketing
        self.assertEqual(discover_identity(titled, "ai")["units"][0]["text"], "Figma for Education")
        self.assertIsNone(discover_identity(titled, "living"))

    def test_english_phd_students_read_as_eligibility(self):
        found = discover_identity(blocks("Eligible applicants are PhD students enrolled at a university in the region."))
        self.assertEqual(found["kind"], "eligibility_clause")
        self.assertIn("phd", found["degrees"])

    def test_titles_drop_attachment_numbers_dates_and_law_system_names(self):
        self.assertEqual(clean_title("附件1：115年單親培力計畫"), "115年單親培力計畫")
        self.assertEqual(clean_title("國立清華大學學生急難貸款辦法1140514"), "國立清華大學學生急難貸款辦法")
        self.assertEqual(clean_title("教育部主管法規共用系統-法規內容-低收入戶學生助學金實施要點"), "低收入戶學生助學金實施要點")
        self.assertEqual(clean_title("2026 鴻海科技獎"), "2026 鴻海科技獎")

    def test_resource_lists_and_attachment_tables_do_not_become_cards(self):
        self.assertTrue(GENERIC_TITLE.search("政府機關急難救助資源"))
        for title in ("急難扶助辦法-附表檢附證明及補助標準表", "辦理各項扶助慰問金申辦說明表", "單親培力計畫就學助費申請QA"):
            self.assertTrue(FORM_DOCUMENT.search(title), title)
        self.assertFalse(FORM_DOCUMENT.search("單親培力計畫"))

    def test_attachment_with_a_year_is_the_same_program_as_the_page(self):
        card = lambda i, title, url: {"candidate_id": i, "title": title, "source_metadata": {"url": url}}
        kept, dropped = distinct_named_cards([card("a", "115年單親培力計畫", "https://x.test/a.odt"), card("b", "單親培力計畫", "https://x.test/p")])
        self.assertEqual([c["candidate_id"] for c in kept], ["b"])
        self.assertEqual(dropped[0]["reason"], "same_title_same_site")


if __name__ == "__main__":
    unittest.main()
