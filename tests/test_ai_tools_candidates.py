"""Offline synthetic counterexamples plus contract checks of the pending public snapshots."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from scripts.check_data import validate_candidate_snapshot
from scripts.evaluate_deadlines import evaluate_application_window, evaluate_eligibility, make_p1_profile
from scripts.extract_candidates import extract_from_in_memory_blocks
from scripts.verify_candidates import verify_candidate

ROOT=Path(__file__).resolve().parents[1]


class AIToolCandidateTests(unittest.TestCase):
    def setUp(self):
        self.config=json.loads((ROOT/"data/scan-sources.json").read_text(encoding="utf-8"))
        self.source=next(s for s in self.config["sources"] if s["id"]=="hsinchu-ai-tools")
        # All text below is synthetic, not a copy of an official application.
        texts=["合成測試：受理申請期間", "116年4月2日起至116年11月30日，申請額滿或經費用罄止。",
               "自116年8月14日起，設籍本市16歲(含)至40歲(含)青年。",
               "購買日期", "自116年4月2日起至116年10月31日止。",
               "一、一般青年", "補助購買金額50%，每人補助上限3,500元。",
               "二、特定對象", "補助購買金額90%，每人補助上限7,000元。",
               "三、文化語言保存者", "補助購買金額90%，每人補助上限7,000元。",
               "月費制購買後1個月內，年費制購買後2個月內提出申請。",
               "至數位申辦平台進行線上申請，申請人應親筆簽名後上傳至平台。",
               "申請人重複申請或其他單位相同補助者不予補助。"]
        self.blocks=[{"locator":f"SYNTH/{i}","text":text} for i,text in enumerate(texts)]

    def candidate(self,blocks=None):
        return extract_from_in_memory_blocks(self.source,blocks or self.blocks,"e"*64,"2026-10-30T18:00:00+08:00",as_of="2026-10-30")[0]

    def test_named_snapshots_are_bounded_unapproved_and_source_bound(self):
        bundle=json.loads((ROOT/"data/candidates/ai-tools-115.json").read_text(encoding="utf-8"))
        self.assertEqual(validate_candidate_snapshot(bundle,self.config),[])
        self.assertEqual(len(bundle["candidates"]),2)
        for cand in bundle["candidates"]:
            self.assertEqual(cand["verification"]["status"],"passed_with_gaps")
            self.assertEqual(cand["review"]["status"],"pending")
            self.assertFalse(cand["review"]["promotion_ready"])
            self.assertEqual(cand["application"]["state"],"unknown")
            self.assertLessEqual(sum(len(e.get("excerpt") or "") for e in cand["field_evidence"]),120)
        wrong=deepcopy(bundle);wrong["candidates"][0]["source_metadata"]["url"]="https://example.test/wrong"
        self.assertTrue(validate_candidate_snapshot(wrong,self.config))

    def test_year_and_amounts_follow_changed_source_and_tier_headings(self):
        cand=self.candidate()
        self.assertEqual(cand["cycle"]["year"],116)
        self.assertEqual([i["amount_max"] for i in cand["benefit"]["items"]],[3500,7000,7000])
        self.assertIn("特定",cand["benefit"]["items"][1]["branch_or_tier"])
        self.assertIn("文化語言",cand["benefit"]["items"][2]["branch_or_tier"])
        self.assertEqual(cand["verification"]["errors"],[])
        self.assertEqual(cand["application_method"]["handwritten_signature"],"required")
        self.assertEqual(cand["application_method"]["paper_delivery"],"unknown")

    def test_wrong_tier_amount_and_dropped_tier_are_detected(self):
        cand=self.candidate();wrong=deepcopy(cand)
        wrong["benefit"]["items"][0]["amount_max"]=7000
        self.assertIn("ai_tools:benefit_tier_or_amount_not_supported",verify_candidate(wrong,in_memory_blocks=self.blocks)["verification"]["errors"])
        cand["benefit"]["items"].pop()
        checked=verify_candidate(cand,in_memory_blocks=self.blocks)
        self.assertIn("coverage_gap:ai_tools:omitted_benefit_tier",checked["verification"]["warnings"])

    def test_expense_and_channel_revision_dates_are_not_application_dates(self):
        cand=self.candidate()
        self.assertEqual(cand["expense_period"]["ends_on"],"2027-10-31")
        self.assertEqual(cand["schedule"]["application_start"]["value"],"2027-04-02")
        self.assertEqual(cand["schedule"]["steps"][0]["deadline"]["value"],"2027-11-30")
        self.assertEqual(evaluate_application_window(cand,"2027-10-30")["state"],"unknown")
        self.assertEqual(evaluate_application_window(cand,"2027-12-01")["state"],"closed")
        self.assertNotEqual(evaluate_eligibility(cand,make_p1_profile())["criteria"],"meets_recorded_rules")

    def test_missing_year_is_not_filled_from_current_date(self):
        blocks=deepcopy(self.blocks)
        for b in blocks:b["text"]=b["text"].replace("116年","")
        cand=self.candidate(blocks)
        self.assertIsNone(cand["cycle"]["year"])
        self.assertIsNone(cand["schedule"]["steps"][0]["deadline"]["value"])
        self.assertIn("ai_tools:unambiguous_cycle_year",cand["gaps_and_conflicts"]["missing_fields"])

    def test_tool_status_uses_card_info_before_fixed_sentence(self):
        cand=self.candidate()
        fixed="年度期限是最晚上限；購買／達成條件後的相對期限及經費餘額仍須確認，不推定目前受理。"
        # 有年度上限且已開放：維持固定句（購買後相對期限的情境）。
        self.assertEqual(evaluate_application_window(cand,"2027-10-30")["reason"],fixed)
        # 卡片自己的開始日未到：顯示開始日。
        early=evaluate_application_window(cand,"2027-03-01")
        self.assertEqual((early["state"],early["reason_code"]),("unknown","tool_start_date_not_reached"))
        self.assertIn("2027-04-02",early["reason"])
        # 只有開始日、沒有截止日，且已開放：說明截止日未載明。
        no_cap=deepcopy(cand)
        for s in no_cap["schedule"]["steps"]:s["deadline"].update(kind="unknown",value=None)
        opened=evaluate_application_window(no_cap,"2027-05-01")
        self.assertEqual(opened["reason_code"],"tool_opened_no_deadline")
        self.assertIn("截止日未載明",opened["reason"])
        # 機構申請／簽約的方案：個人沒有申請期間。
        inst=deepcopy(no_cap);inst["participants"]["applicant"]="institution"
        self.assertEqual(evaluate_application_window(inst,"2027-05-01")["reason_code"],"institution_plan_no_individual_window")
        # 什麼都沒寫：退回固定句。
        bare=deepcopy(no_cap);bare["schedule"]["application_start"].update(kind="unknown",value=None)
        self.assertEqual(evaluate_application_window(bare,"2027-05-01")["reason"],fixed)
        # 計畫主持人申請：有未到的開始日仍顯示尚未開放，否則說明由 PI 申請。
        pi=deepcopy(bare);pi["participants"]["applicant"]="principal_investigator"
        self.assertEqual(evaluate_application_window(pi,"2027-05-01")["reason_code"],"pi_applies_team_members_added")
        pi_dated=deepcopy(no_cap);pi_dated["participants"]["applicant"]="principal_investigator"
        self.assertEqual(evaluate_application_window(pi_dated,"2027-03-01")["reason_code"],"tool_start_date_not_reached")


if __name__=="__main__":unittest.main()
