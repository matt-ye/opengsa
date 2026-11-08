"""申請期間的起訖：起日後接時間或寫「開始申辦」時，截止日要取迄日，不能把起日當截止。不連外。"""
import unittest

from scripts.extract_candidates import extract_from_in_memory_blocks, parse_date_range_from_text


class DateRangeTests(unittest.TestCase):
    def test_start_time_between_the_dates_still_reads_as_a_range(self):
        self.assertEqual(parse_date_range_from_text("申請期間：115年8月26日(週三)上午9:00起至115年9月9日(週三)16:30止。"), ("2026-08-26", "2026-09-09"))
        self.assertEqual(parse_date_range_from_text("2026年3月1日 9時起至2026年3月15日17時止"), ("2026-03-01", "2026-03-15"))
        self.assertEqual(parse_date_range_from_text("於115/08/26開始申辦至115/09/9 16:30截止"), ("2026-08-26", "2026-09-09"))
        self.assertEqual(parse_date_range_from_text("申請期間：115年2月1日至2月28日"), ("2026-02-01", "2026-02-28"))

    def test_deadline_is_the_end_of_the_period_with_its_time(self):
        source = {"id": "t", "title": "t", "url": "https://x.test/a", "evidence_mode": "short_excerpt"}
        blocks = [{"locator": "b1", "text": "申請資格：本校在學學生。"},
                  {"locator": "b2", "text": "一、申請期間：115年8月26日(週三)上午9:00起至115年9月9日(週三)16:30止。"}]
        card = extract_from_in_memory_blocks(source, blocks, "a" * 64, "2026-08-01T00:00:00+08:00", as_of="2026-08-01", extraction_strategy="rules_only")[0]
        deadlines = [s["deadline"]["value"] for s in card["schedule"]["steps"] if s["deadline"]["kind"] != "unknown"]
        self.assertEqual(deadlines, ["2026-09-09T16:30:00+08:00"])
        self.assertEqual(card["schedule"]["application_start"]["value"], "2026-08-26")


if __name__ == "__main__":
    unittest.main()
