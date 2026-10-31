"""測試結構化候選 Schema、規則與模型 Adapter 萃取、獨立檢核、申請時間判斷、P1 資格比對與覆核流程。
所有測試皆使用離線合成樣本與記憶體 fixture，不發送外部網路請求，亦不呼叫真實外部模型。
"""
from copy import deepcopy
from pathlib import Path
import os
import tempfile
import unittest
import unittest.mock

from jsonschema import Draft202012Validator

from scripts.check_data import ROOT, read_json, validate as validate_pilot
from scripts.evaluate_deadlines import (
    add_days,
    evaluate_application_window,
    evaluate_compatibility_pair,
    evaluate_conference_schedule,
    evaluate_eligibility,
    make_p1_profile,
    months_before,
    previous_month_first_day,
)
from scripts.extract_candidates import (
    DisabledModelAdapter,
    MockModelAdapter,
    ModelPolicyError,
    OpenAICompatibleAdapter,
    extract_from_candidate_stub_without_memory,
    extract_from_in_memory_blocks,
    refetch_and_extract_candidates,
)
from scripts.review_candidates import (
    apply_review_ledger,
    build_review_report,
    compute_candidate_diff,
    export_pr_candidate_draft,
)
from scripts.scan_sources import Fetcher
from scripts.verify_candidates import load_candidate_schema, verify_bundle, verify_candidate


CONFIG = read_json(ROOT / "data/scan-sources.json")
PILOT = read_json(ROOT / "data/pilot.json")


def make_doctoral_blocks():
    return [
        {
            "locator": ".article-center / text-block 1",
            "text": "國立臺灣大學115學年度校級博士生獎學金申請說明（含國科會核配博士生獎學金及教育部博士生獎學金）。",
        },
        {
            "locator": ".article-center / text-block 2",
            "text": "一、國科會核配博士生獎學金：115學年度博士班不限年級，非在職學生得提出申請，每月新臺幣40,000元，不得重複支領政府同性質獎學金。",
        },
        {
            "locator": ".article-center / text-block 3",
            "text": "二、教育部博士生獎學金（第二梯次）：限本國籍、非在職學生，以115年9月博士班一至三年級為基準，每月新臺幣40,000元，不得重複支領。",
        },
        {
            "locator": ".article-center / text-block 4",
            "text": "教育部博士生獎學金第二梯次請於115年11月9日前由學院遞送推薦名單至研究生教務組（學生向系所申請截止日依各院系公告）。",
        },
    ]


def make_yuanxue_blocks():
    return [
        {
            "locator": ".card-text-info / text-block 1",
            "text": "國立臺灣大學115年遠學計畫申請說明：博士班學生一般補助與配合補助分流辦理。",
        },
        {
            "locator": ".card-text-info / text-block 2",
            "text": "博士生一般補助申請資格：本校博士班學生且通過博士學位候選人資格考核，並曾提出115年度國科會補助博士生赴國外研究計畫申請但未獲補助。",
        },
        {
            "locator": ".card-text-info / text-block 3",
            "text": "1.補助費用：每人新臺幣（下同）伍拾貳萬伍仟元以上、玖拾萬元以下（免稅），一般補助期間7至12個月，在學期間擇一申請一次。",
        },
        {
            "locator": ".card-text-info / text-block 4",
            "text": "申請期限：請學院於115年1月30日前彙整送達研究發展處。",
        },
    ]


def make_president_blocks():
    return [
        {
            "locator": ".article-center / text-block 1",
            "text": "國立臺灣大學114學年度研究生校長獎申請公告（依據112.3.31通過之設置辦法辦理）。",
        },
        {
            "locator": ".article-center / text-block 2",
            "text": "申請資格：當學年度畢業且已申請學位考試之在學碩博士生，每名獎勵新臺幣100,000元及獎狀。",
        },
        {
            "locator": ".article-center / text-block 3",
            "text": "申請時間：校級收件期間2026-07-08至2026-08-25，學生須先依所屬院系所規定提出申請。",
        },
    ]


def make_nstc_conference_blocks():
    return [
        {
            "locator": "#ctl00_cp_content_divLawContent08 / text-block 1",
            "text": "國家科學及技術委員會補助國內研究生出席國際學術會議作業要點（112.3.16修正）。",
        },
        {
            "locator": "#ctl00_cp_content_divLawContent08 / text-block 2",
            "text": "補助對象：申請機構之非在職專班博、碩士班在學研究生。申請機構應於會議舉行首日所屬月份之前一個月之首日前彙送本會；論文接受函至遲應於會議舉行首日四週前補送。",
        },
        {
            "locator": "#ctl00_cp_content_divLawContent08 / text-block 3",
            "text": "研究生得向申請機構再提出申請於同年度內出席其他國際學術會議，但每人每年原則補助一次，須揭露其他經費分攤。",
        },
    ]


def make_faos_blocks():
    return [
        {
            "locator": "body / text-block 1",
            "text": "優秀學生出國開會申請補助辦法〔113.05.29 修訂〕（註冊費適用114/01/01後申請者）。",
        },
        {
            "locator": "body / text-block 2",
            "text": "申請資格：公私立大學三年級以上，具有中華民國國籍之學生。由申請單位（學校負責人）於會議開始日前兩個月提出申請。",
        },
        {
            "locator": "body / text-block 3",
            "text": "兼領限制：已獲得補助者不得向本會申請出席同年度其他會議之經費。",
        },
    ]


class ExtractionVerificationDeadlineTests(unittest.TestCase):
    def test_candidate_schema_is_valid_and_enforces_version_and_review_gates(self):
        schema = load_candidate_schema()
        Draft202012Validator.check_schema(schema)
        self.assertIn("1.0.0-candidate", schema["properties"]["schema_version"]["enum"])
        self.assertIn("1.1.0-candidate", schema["properties"]["schema_version"]["enum"])

        source = CONFIG["sources"][0]  # ntu-doctoral-funding (hash_only)
        extracted = extract_from_in_memory_blocks(
            source,
            make_doctoral_blocks(),
            revision_id="a" * 64,
            observed_at="2026-10-29T09:17:00+08:00",
            as_of="2026-10-28",
        )
        self.assertEqual(len(extracted), 2)
        for cand in extracted:
            self.assertEqual(cand["verification"]["status"], "passed_automated_checks")
            self.assertEqual(cand["review"]["status"], "pending")
            self.assertFalse(cand["review"]["promotion_ready"])
            # hash_only 來源不得包含任何原文摘錄
            self.assertTrue(all(ev["excerpt"] is None for ev in cand["field_evidence"]))

    def test_year_and_round_and_branch_splitting_and_mixing_rejection(self):
        source = CONFIG["sources"][0]
        extracted = extract_from_in_memory_blocks(
            source,
            make_doctoral_blocks(),
            revision_id="b" * 64,
            observed_at="2026-10-29T09:17:00+08:00",
            as_of="2026-10-28",
        )
        by_prog = {c["program_key"]: c for c in extracted}
        self.assertIn("ntu-nstc-phd", by_prog)
        self.assertIn("ntu-moe-phd", by_prog)
        self.assertEqual(by_prog["ntu-nstc-phd"]["eligibility"]["year_limit"]["mode"], "unlimited")
        self.assertEqual(by_prog["ntu-moe-phd"]["eligibility"]["year_limit"]["mode"], "range")
        self.assertEqual(by_prog["ntu-moe-phd"]["eligibility"]["year_limit"]["min"], 1)
        self.assertEqual(by_prog["ntu-moe-phd"]["eligibility"]["year_limit"]["max"], 3)

        # 負向測試：若把 114 與 115 學年度或教育部與國科會混在同一筆，檢核必須攔截
        mixed = deepcopy(by_prog["ntu-nstc-phd"])
        mixed["title"] = "臺大114學年度及115學年度教育部與國科會博士生獎學金"
        mixed["cycle"]["label"] = "114學年度及115學年度"
        verified_mixed = verify_candidate(mixed, in_memory_blocks=make_doctoral_blocks())
        self.assertEqual(verified_mixed["verification"]["status"], "failed_automated_checks")
        self.assertFalse(verified_mixed["verification"]["checks"]["no_year_or_branch_mixing"])
        self.assertTrue(any("mixed_academic_years" in e for e in verified_mixed["verification"]["errors"]))
        self.assertTrue(any("mixed_moe_and_nstc" in e for e in verified_mixed["verification"]["errors"]))

    def test_student_vs_institution_and_college_deadlines_separation(self):
        source = CONFIG["sources"][0]
        extracted = extract_from_in_memory_blocks(
            source,
            make_doctoral_blocks(),
            revision_id="c" * 64,
            observed_at="2026-10-29T09:17:00+08:00",
            as_of="2026-10-28",
        )
        moe = next(c for c in extracted if c["program_key"] == "ntu-moe-phd")
        # 115/11/9 是學院送校期限，不可當成學生截止日，2026-10-28 評估時學生受理狀態必須為 unknown
        window = evaluate_application_window(moe, "2026-10-28")
        self.assertEqual(window["state"], "unknown")
        self.assertEqual(window["reason_code"], "student_deadline_unknown_only_upper_layer_known")
        self.assertIsNone(window["student_deadline"])
        self.assertEqual(window["upper_layer_deadlines"][0]["actor"], "college")
        self.assertEqual(window["upper_layer_deadlines"][0]["value"], "2026-11-09")

        # 負向測試：若誤把學院送件日掛在 student actor，檢核必須攔截
        bad_role = deepcopy(moe)
        bad_role["schedule"]["steps"][1]["actor"] = "student"
        verified_bad = verify_candidate(bad_role, in_memory_blocks=make_doctoral_blocks())
        self.assertEqual(verified_bad["verification"]["status"], "failed_automated_checks")
        self.assertTrue(
            any("institution_or_college_deadline_misassigned_to_student" in e for e in verified_bad["verification"]["errors"])
        )

        # 負向測試：若學生截止日晚於學院／機關截止日，檢核必須攔截
        inverted_dl = deepcopy(moe)
        inverted_dl["schedule"]["steps"][0]["deadline"] = {
            "kind": "date",
            "value": "2026-11-15",
            "timezone": "Asia/Taipei",
            "note": "晚於學院11/9的錯誤日期",
        }
        verified_inv = verify_candidate(inverted_dl)
        self.assertEqual(verified_inv["verification"]["status"], "failed_automated_checks")
        self.assertIn("student_deadline_after_institution_or_college_deadline", verified_inv["verification"]["errors"])

    def test_negated_eligibility_and_unknown_compatibility_rules(self):
        source = CONFIG["sources"][4]  # nstc-conference-rule
        extracted = extract_from_in_memory_blocks(
            source,
            make_nstc_conference_blocks(),
            revision_id="d" * 64,
            observed_at="2026-10-29T09:17:00+08:00",
            as_of="2026-10-28",
        )
        cand = extracted[0]
        self.assertEqual(cand["eligibility"]["employment_status"], "non_in_service_only")
        self.assertTrue(any(nc["field"] == "employment_status" for nc in cand["eligibility"]["negated_conditions"]))
        self.assertEqual(cand["participants"]["applicant"], "institution")
        self.assertNotIn("臺大",cand["organizations"]["receiver"]["text"])
        ntu_source=next(s for s in CONFIG['sources'] if s['id']=='nstc-ntu-conference')
        ntu=extract_from_in_memory_blocks(ntu_source,make_nstc_conference_blocks(),revision_id='e'*64,
            observed_at='2026-10-29T09:17:00+08:00',as_of='2026-10-28')[0]
        self.assertIn('臺大',ntu['organizations']['receiver']['text'])

        # 負向測試：原文含「非在職專班」卻標為 employment_status='allowed'，或申請人標為 student
        bad = deepcopy(cand)
        bad["eligibility"]["employment_status"] = "allowed"
        bad["participants"]["applicant"] = "student"
        bad["compatibility"]["mode"] = "allowed"
        verified_bad = verify_candidate(bad, in_memory_blocks=make_nstc_conference_blocks())
        self.assertEqual(verified_bad["verification"]["status"], "failed_automated_checks")
        self.assertIn("negated_in_service_condition_turned_into_allowed", verified_bad["verification"]["errors"])
        self.assertIn("institution_applied_program_misassigned_applicant:nstc-grad-conference-policy", verified_bad["verification"]["errors"])
        self.assertIn("negated_compatibility_turned_into_allowed", verified_bad["verification"]["errors"])

        # 雙邊兼領檢查：一方 allowed、另一方 unknown 或 prohibited 時，絕不可判為可兼領
        scheme_allowed = {"compatibility": {"mode": "allowed", "note": "單方允許", "refs": [{"source": "s1", "locator": "l1"}]}}
        scheme_unknown = {"compatibility": {"mode": "unknown", "note": "未載明", "refs": []}}
        scheme_prohibited = {"compatibility": {"mode": "prohibited", "note": "同期間不得兼領", "refs": [{"source": "s2", "locator": "l2"}]}}
        pair_unk = evaluate_compatibility_pair(scheme_allowed, scheme_unknown)
        self.assertEqual(pair_unk["mode"], "needs_clarification")
        self.assertFalse(pair_unk["can_assume_compatible"])
        pair_proh = evaluate_compatibility_pair(scheme_allowed, scheme_prohibited)
        self.assertEqual(pair_proh["mode"], "prohibited")
        self.assertFalse(pair_proh["can_assume_compatible"])

    def test_amount_units_and_chinese_numerals_extraction_and_validation(self):
        # 遠學：伍拾貳萬伍仟元以上、玖拾萬元以下 -> 525,000 ~ 900,000 TWD total_range (7-12 months)
        yuanxue_src = CONFIG["sources"][2]
        yx_cands = extract_from_in_memory_blocks(
            yuanxue_src,
            make_yuanxue_blocks(),
            revision_id="e" * 64,
            observed_at="2026-10-29T09:17:00+08:00",
            as_of="2026-10-28",
        )
        self.assertEqual(len(yx_cands), 1)
        yx = yx_cands[0]
        self.assertEqual(yx["verification"]["status"], "passed_with_gaps")
        b_item = yx["benefit"]["items"][0]
        self.assertEqual(b_item["amount_min"], 525000)
        self.assertEqual(b_item["amount_max"], 900000)
        self.assertEqual(b_item["currency"], "TWD")
        self.assertEqual(b_item["unit"], "total_range")
        self.assertEqual(b_item["duration_months_min"], 7)
        self.assertEqual(b_item["duration_months_max"], 12)

        # 校長獎：100,000 TWD lump_sum
        pres_src = CONFIG["sources"][1]
        pres_cands = extract_from_in_memory_blocks(
            pres_src,
            make_president_blocks(),
            revision_id="f" * 64,
            observed_at="2026-10-29T09:17:00+08:00",
            as_of="2026-10-28",
        )
        self.assertEqual(pres_cands[0]["benefit"]["items"][0]["amount_min"], 100000)
        self.assertEqual(pres_cands[0]["benefit"]["items"][0]["unit"], "lump_sum")

        # 負向測試：有金額數字但缺單位 (unit='unknown') 或幣別 (currency='unknown')，檢核必須攔截
        bad_unit = deepcopy(yx)
        bad_unit["benefit"]["items"][0]["unit"] = "unknown"
        bad_unit["benefit"]["items"][0]["currency"] = "unknown"
        verified_bad = verify_candidate(bad_unit, in_memory_blocks=make_yuanxue_blocks())
        self.assertEqual(verified_bad["verification"]["status"], "failed_automated_checks")
        self.assertIn("benefit_missing_unit:benefit.items/0", verified_bad["verification"]["errors"])
        self.assertIn("benefit_missing_currency:benefit.items/0", verified_bad["verification"]["errors"])

    def test_event_relative_conference_rules_cross_year_leap_year_and_holiday_calendar(self):
        # 1. 國科會／臺大：跨年 (2027-01-15 -> 機構 2026-12-01、臺大學生 2026-11-30 17:00、補送 2026-12-18)
        nstc_cross = evaluate_conference_schedule("nstc-ntu", "2027-01-15", acceptance_notice_date="2026-12-10", prepare_days=14)
        self.assertEqual(nstc_cross["agency_submit_base"], "2026-12-01")
        self.assertEqual(nstc_cross["student_submit"], "2026-11-30T17:00:00+08:00")
        self.assertEqual(nstc_cross["acceptance_supplement"], "2026-12-18")
        self.assertEqual(nstc_cross["personal_prepare_start"], "2026-11-16")
        self.assertFalse(nstc_cross["is_personal_prepare_official_start"])
        self.assertFalse(nstc_cross["is_acceptance_notice_official_result"])
        self.assertEqual(nstc_cross["calendar_status"], "unverified")
        self.assertEqual(nstc_cross["deadline_status"], "estimate_pending_calendar")
        self.assertEqual(nstc_cross["notice_risk"], "after_submission")

        # 2. 國科會／臺大：跨閏2月 (2028-03-01 -> 四週前補送為 2028-02-02)
        nstc_leap = evaluate_conference_schedule("nstc-ntu", "2028-03-01")
        self.assertEqual(nstc_leap["acceptance_supplement"], "2028-02-02")

        # 3. 國科會／臺大：提供官方假日曆時，遇週末／國定假日順延次一上班日（如 2027-06-15 前月首日 2027-05-01 為週六）
        cal = {"holidays": ["2027-05-01", "2027-05-02"], "make_up_workdays": []}
        nstc_cal = evaluate_conference_schedule("nstc-ntu", "2027-06-15", holiday_calendar=cal)
        self.assertEqual(nstc_cal["agency_submit_base"], "2027-05-01")
        self.assertEqual(nstc_cal["agency_submit"], "2027-05-03")
        self.assertEqual(nstc_cal["student_submit"], "2027-05-02T17:00:00+08:00")
        self.assertEqual(nstc_cal["calendar_status"], "verified")

        # 4. 醫學院國際事務：會前四週送件，無國科會補送條款
        med = evaluate_conference_schedule("ntu-med-oia", "2027-07-20", acceptance_notice_date="2027-06-25")
        self.assertEqual(med["student_submit"], "2027-06-22")
        self.assertIsNone(med["agency_submit"])
        self.assertIsNone(med["acceptance_supplement"])
        self.assertEqual(med["notice_risk"], "after_deadline")

        # 5. FAOS：會前兩個曆月由學校提出（月底對齊月末日，非減60天），學生校內期限保持 unknown
        faos_leap = evaluate_conference_schedule("faos-student", "2028-04-30", now_taipei="2028-01-15")
        self.assertEqual(faos_leap["agency_submit"], "2028-02-29")
        self.assertIsNone(faos_leap["student_submit"])
        self.assertEqual(faos_leap["state"], "unknown")
        self.assertEqual(faos_leap["reason_code"], "institution_deadline_known_student_internal_deadline_unknown")
        self.assertEqual(months_before("2027-04-30", 2), "2027-02-28")
        self.assertEqual(months_before("2027-08-31", 2), "2027-06-30")
        self.assertEqual(previous_month_first_day("2027-01-31"), "2026-12-01")

    def test_date_only_no_midnight_missing_start_policy_effective_date_and_stale_source(self):
        tuition = PILOT["opportunities"][0]  # ntu-tuition-115-1: start 2026-08-05, end 2026-08-13 (kind='date')
        # 開始日前 -> not_yet_open
        w_before = evaluate_application_window(tuition, "2026-08-01")
        self.assertEqual(w_before["state"], "not_yet_open")
        # 期間內 -> open
        w_open = evaluate_application_window(tuition, "2026-08-10")
        self.assertEqual(w_open["state"], "open")
        # 截止當日 (2026-08-13 18:00) -> 僅有日期，不可自造 23:59 午夜截止！
        w_due_day = evaluate_application_window(tuition, "2026-08-13T18:00:00+08:00")
        self.assertEqual(w_due_day["state"], "unknown")
        self.assertEqual(w_due_day["reason_code"], "due_today_time_unconfirmed")
        self.assertTrue(w_due_day["same_day_time_unconfirmed"])
        # 截止日後 -> closed，且不自動推算下學期
        w_after = evaluate_application_window(tuition, "2026-08-14")
        self.assertEqual(w_after["state"], "closed")
        self.assertFalse(w_after["next_cycle_inferred"])

        # 缺起日測試：已知未來學生截止日，但無開始日且非當日明示開放快照 -> unknown (missing_application_start)
        no_start_item = deepcopy(tuition)
        no_start_item.pop("start", None)
        no_start_item["steps"][0]["action"] = "碩博第二階段申請（未載開始日）"
        no_start_item["application"] = {"state": "unknown", "as_of": "2026-08-01", "reason": "待查", "refs": []}
        w_no_start = evaluate_application_window(no_start_item, "2026-08-10")
        self.assertEqual(w_no_start["state"], "unknown")
        self.assertEqual(w_no_start["reason_code"], "missing_application_start")

        # 來源過期測試：checked_on 距今超過 180 天
        sources_map = {"ntu-tuition": {"id": "ntu-tuition", "checked_on": "2025-01-01"}}
        w_stale = evaluate_application_window(tuition, "2026-08-10", sources_by_id=sources_map, freshness_days=180)
        self.assertEqual(w_stale["state"], "unknown")
        self.assertEqual(w_stale["reason_code"], "source_observation_stale")
        self.assertTrue(w_stale["source_stale"])

        # 法規修正日不得自動當成生效日
        faos_src = CONFIG["sources"][5]
        faos_cands = extract_from_in_memory_blocks(
            faos_src,
            make_faos_blocks(),
            revision_id="1" * 64,
            observed_at="2026-10-29T09:17:00+08:00",
            as_of="2026-10-28",
        )
        faos_cand = faos_cands[0]
        self.assertEqual(faos_cand["policy_version"]["amended_on"], "2024-05-29")
        self.assertIsNone(faos_cand["policy_version"]["effective_from"])
        bad_eff = deepcopy(faos_cand)
        bad_eff["policy_version"]["effective_from"] = "2024-05-29"
        verified_bad_eff = verify_candidate(bad_eff, in_memory_blocks=make_faos_blocks())
        self.assertEqual(verified_bad_eff["verification"]["status"], "failed_automated_checks")
        self.assertIn("amended_or_promulgated_date_copied_as_effective_date", verified_bad_eff["verification"]["errors"])

    def test_insufficient_evidence_stub_never_guesses_and_in_memory_refetch_succeeds(self):
        # 1. 僅有雜湊與殘句且不允許重取時：保持 needs_context，絕不猜測金額或年級
        stub_hash_only = {
            "id": "2" * 64,
            "source_id": "ntu-doctoral-funding",
            "url": CONFIG["sources"][0]["url"],
            "observed_at": "2026-10-29T09:17:00+08:00",
            "evidence_mode": "hash_only",
            "facts": [
                {
                    "field": "amount_text",
                    "normalized_value": None,
                    "evidence": None,
                    "evidence_sha256": "3" * 64,
                    "locator": ".article-center / text-block 2",
                    "status": "candidate_requires_human_review",
                }
            ],
        }
        bundle_no_refetch, statuses = refetch_and_extract_candidates(
            [stub_hash_only],
            CONFIG,
            allow_network_refetch=False,
        )
        self.assertEqual(statuses[CONFIG["sources"][0]["url"]], "skipped_no_fetcher")
        stub_cand = bundle_no_refetch["candidates"][0]
        self.assertEqual(stub_cand["verification"]["status"], "needs_context")
        self.assertEqual(stub_cand["benefit"]["items"], [])
        self.assertEqual(stub_cand["eligibility"]["year_limit"]["mode"], "unknown")

        # 若有人在無記憶體上下文時硬填猜測金額，檢核必須攔截
        guessed = deepcopy(stub_cand)
        guessed["Eligibility"] = guessed["eligibility"]
        guessed["eligibility"]["year_limit"]["mode"] = "unlimited"
        guessed["eligibility"]["year_limit"]["refs"] = [{"source": "ntu-doctoral-funding", "locator": "x"}]
        verified_guessed = verify_candidate(guessed)
        self.assertEqual(verified_guessed["verification"]["status"], "failed_automated_checks")
        self.assertIn("guessed_from_hash_without_in_memory_context", verified_guessed["verification"]["errors"])

        # 2. 當提供受限 Fetcher 重新取得 HTML 至記憶體時，完整萃取兩筆博士獎學金分支並通過檢核
        html_bytes = (
            '<html><body><div class="article-center">'
            "<p>國立臺灣大學115學年度教育部博士生獎學金及國科會核配博士生獎學金申請說明。</p>"
            "<p>國科會核配：115學年度博士班不限年級，非在職學生，每月新臺幣40,000元，不得重複支領。</p>"
            "<p>教育部博士生獎學金：本國籍、非在職，115年9月一至三年級，每月新臺幣40,000元，115年11月9日前學院送件。</p>"
            "</div></body></html>"
        ).encode("utf-8")

        def mock_transport(url, headers, limit):
            if url.endswith("robots.txt"):
                return {"status": 404, "headers": {}, "body": b""}
            return {"status": 200, "headers": {"content-type": "text/html"}, "body": html_bytes}

        cfg = deepcopy(CONFIG)
        cfg["minimum_host_interval_seconds"] = 0
        fetcher = Fetcher(cfg, transport=mock_transport, sleeper=lambda s: None)
        bundle_refetched, statuses2 = refetch_and_extract_candidates(
            [stub_hash_only],
            cfg,
            fetcher=fetcher,
            allow_network_refetch=True,
        )
        self.assertEqual(statuses2[CONFIG["sources"][0]["url"]], "refetched_in_memory")
        self.assertEqual(len(bundle_refetched["candidates"]), 2)
        self.assertTrue(all(c["verification"]["status"] == "passed_automated_checks" for c in bundle_refetched["candidates"]))
        self.assertTrue(all(ev["excerpt"] is None for c in bundle_refetched["candidates"] for ev in c["field_evidence"]))

    def test_source_conflict_detection_halts_auto_pass(self):
        # 同一區塊若同時出現「不限年級」與「一至三年級」衝突描述，必須標記 conflict_detected
        conflicting_blocks = [
            {
                "locator": ".article-center / text-block 1",
                "text": "115學年度國科會核配博士生獎學金：博士班不限年級，非在職學生，每月新臺幣40,000元。",
            },
            {
                "locator": ".article-center / text-block 2",
                "text": "同一段落矛盾記載：僅限博士班一至三年級申請，不得重複支領。",
            },
        ]
        source = deepcopy(CONFIG["sources"][0])
        cands = extract_from_in_memory_blocks(
            source,
            conflicting_blocks,
            revision_id="4" * 64,
            observed_at="2026-10-29T09:17:00+08:00",
            as_of="2026-10-28",
        )
        nstc_cand = next(c for c in cands if c["program_key"] == "ntu-nstc-phd")
        self.assertEqual(nstc_cand["verification"]["status"], "conflict_detected")
        self.assertFalse(nstc_cand["verification"]["checks"]["no_unresolved_conflicts"])
        self.assertTrue(len(nstc_cand["gaps_and_conflicts"]["conflicts"]) >= 1)

    def test_model_adapter_hallucination_caught_and_hash_only_blocked(self):
        # 1. 預設模型 Adapter 關閉 (0 calls)
        default_adapter = DisabledModelAdapter()
        self.assertFalse(default_adapter.enabled)

        # 2. 外部模型 Adapter 嚴格拒絕處理 hash_only 來源（如教務處）
        ext_mock = MockModelAdapter({"*": {"benefit": {"summary": "不應送出"}}}, simulate_external=True)
        with self.assertRaises(ModelPolicyError):
            ext_mock.extract_patch(CONFIG["sources"][0], make_doctoral_blocks(), {"candidate_id": "x"})

        ext_openai = OpenAICompatibleAdapter("https://api.example.test/v1", "test-model", allow_local_no_key=True)
        with self.assertRaises(ModelPolicyError):
            ext_openai.extract_patch(CONFIG["sources"][0], make_doctoral_blocks(), {"candidate_id": "x"})

        # 3. 模型捏造金額（原文 525,000~900,000，模型捏造 999,999）與捏造日期（原文 115/1/30，模型捏造 2026-12-31），且自稱 self_verified=True
        def hallucinating_patch(source, blocks, draft):
            return {
                "self_verified": True,
                "agent_confidence": 0.99,
                "benefit": {
                    "summary": "模型捏造金額",
                    "items": [
                        {
                            "branch_or_tier": "博士生一般補助",
                            "amount_min": 999999,
                            "amount_max": 999999,
                            "currency": "TWD",
                            "unit": "lump_sum",
                            "basis": "fixed",
                            "duration_months_min": None,
                            "duration_months_max": None,
                            "tax_note": None,
                            "refs": [{"source": source["id"], "locator": blocks[2]["locator"]}],
                        }
                    ],
                    "refs": [{"source": source["id"], "locator": blocks[2]["locator"]}],
                },
                "schedule": {
                    "application_start": draft["schedule"]["application_start"],
                    "result_date": draft["schedule"]["result_date"],
                    "relative_rule": draft["schedule"]["relative_rule"],
                    "steps": [
                        {
                            "actor": "student",
                            "action": "模型捏造學生截止日",
                            "deadline": {
                                "kind": "date",
                                "value": "2026-12-31",
                                "timezone": "Asia/Taipei",
                                "note": "原文不存在之日期",
                            },
                            "refs": [{"source": source["id"], "locator": blocks[3]["locator"]}],
                        }
                    ],
                },
                "field_evidence": [
                    {
                        "field_path": "schedule.steps/0/deadline",
                        "source": source["id"],
                        "revision_id": "5" * 64,
                        "locator": blocks[3]["locator"],
                        "evidence_mode": "short_excerpt",
                        "excerpt": "請學院於115年1月30日前彙整送達研究發展處。",
                        "excerpt_sha256": "e55b806f3ec985c5d602493056188fbbb172f7f74f0ebfecba2dc7635e29e280",
                        "extraction_method": "model_adapter",
                    }
                ],
            }

        mock_adapter = MockModelAdapter({"*": hallucinating_patch}, simulate_external=False)
        yx_cands = extract_from_in_memory_blocks(
            CONFIG["sources"][2],
            make_yuanxue_blocks(),
            revision_id="5" * 64,
            observed_at="2026-10-29T09:17:00+08:00",
            as_of="2026-10-28",
            model_adapter=mock_adapter,
        )
        hallucinated = yx_cands[0]
        self.assertEqual(mock_adapter.calls, 1)
        self.assertTrue(hallucinated["verification"]["model_self_claim_ignored"])
        self.assertNotIn("self_verified", hallucinated)
        self.assertEqual(hallucinated["verification"]["status"], "failed_automated_checks")
        self.assertTrue(any("hallucinated_amount_not_in_source" in e for e in hallucinated["verification"]["errors"]))
        self.assertTrue(any("hallucinated_date_not_in_source" in e for e in hallucinated["verification"]["errors"]))
        self.assertFalse(hallucinated["review"]["promotion_ready"])

    def test_failure_retains_old_data_and_review_workflow_protects_pilot_json(self):
        # 1. 重取失敗（如 403 / 500 / robots_denied）時，不毀損既有 pilot.json，且退回安全 stub
        stub = {
            "id": "6" * 64,
            "source_id": "ntu-yuanxue",
            "url": "https://ord.ntu.edu.tw/WebUPD/ordntu/GW/restricted.pdf",
            "observed_at": "2026-10-29T09:17:00+08:00",
            "evidence_mode": "short_excerpt",
            "facts": [],
        }

        def deny_robots(url, headers, limit):
            return {"status": 200, "headers": {"content-type": "text/plain"}, "body": b"User-agent: *\nDisallow: /WebUPD/"}

        cfg = deepcopy(CONFIG)
        cfg["minimum_host_interval_seconds"] = 0
        fetcher = Fetcher(cfg, transport=deny_robots, sleeper=lambda s: None)
        bundle, statuses = refetch_and_extract_candidates([stub], cfg, fetcher=fetcher, allow_network_refetch=True)
        self.assertEqual(statuses[stub["url"]], "robots_denied")
        self.assertFalse(bundle["official_data_modified"])
        self.assertEqual(bundle["candidates"][0]["verification"]["status"], "needs_context")

        # 2. 完整覆核報告與 PR 暫存匯出測試
        yx_cands = extract_from_in_memory_blocks(
            CONFIG["sources"][2],
            make_yuanxue_blocks(),
            revision_id="7" * 64,
            observed_at="2026-10-29T09:17:00+08:00",
            as_of="2026-10-28",
        )
        good_bundle = {
            "schema_version": "1.0.0-candidate",
            "generated_at": "2026-10-29T09:17:00+08:00",
            "as_of": "2026-10-28",
            "timezone": "Asia/Taipei",
            "model_enabled": False,
            "model_calls": 0,
            "official_data_modified": False,
            "candidates": yx_cands,
        }
        verified_bundle, summary, md = build_review_report(good_bundle, PILOT, in_memory_blocks_by_source={CONFIG["sources"][2]["url"]:make_yuanxue_blocks()})
        self.assertEqual(summary["passed_with_gaps"], 1)
        self.assertEqual(summary["promotion_ready"], 0)  # 尚未經人工獨立覆核
        self.assertIn("一、來源變更", md)
        self.assertIn("二、結構化萃取結果", md)
        self.assertIn("三、獨立檢核與申請時間", md)
        self.assertIn("四、與 `data/pilot.json` 差異及人工覆核處置", md)

        # 嚴格禁止直接覆寫 data/pilot.json
        with self.assertRaises(ValueError):
            export_pr_candidate_draft(verified_bundle, PILOT, ROOT / "data/pilot.json")

        # Incomplete review records must fail schema validation, not imply approval.
        with self.assertRaises(ValueError):
            build_review_report(good_bundle,PILOT,reviews_data={"reviews":[{"action":"applied"}]})

    def test_p1_phd5_ot_candidate_and_boundary_variants(self):
        # P1 基準：臺大職能治療所博士班五年級、已取得博士候選人資格（未提供國籍、在職、畢業時間、先前補助與9月基準年級）
        p1 = make_p1_profile()
        expected = {
            "ntu-tuition-115-1": ("needs_information", "closed"),
            "ntu-emergency-policy": ("needs_information", "unknown"),
            "ntu-nstc-phd-115": ("needs_information", "unknown"),
            "ntu-moe-phd-115-round2": ("needs_information", "unknown"),
            "ntu-med-publication-115": ("needs_manual_review", "open"),
            "ntu-president-114": ("needs_information", "closed"),
            "nstc-grad-conference-policy": ("needs_information", "unknown"),
            "nstc-abroad-116-ntu": ("needs_information", "closed"),
            "ntu-yuanxue-115-ordinary": ("needs_information", "closed"),
            "ntu-ta-policy": ("needs_information", "unknown"),
        }
        opp_by_id = {item["id"]: item for item in PILOT["opportunities"]}
        for opp_id, (exp_crit, exp_app) in expected.items():
            item = opp_by_id[opp_id]
            elig_res = evaluate_eligibility(item, p1, as_of="2026-10-28")
            win_res = evaluate_application_window(item, "2026-10-28")
            self.assertEqual(elig_res["criteria"], exp_crit, f"{opp_id} criteria mismatch")
            self.assertEqual(win_res["state"], exp_app, f"{opp_id} application state mismatch")
            self.assertFalse(elig_res["official_qualification_approved"])

        # P1-A：明示 2026-09-01 基準日也是博士五年級 -> 教育部一至三年級限制判 not_met，但絕不連帶排除國科會核配方案！
        p1_a = make_p1_profile(year_at_date={"2026-09-01": 5})
        moe_res = evaluate_eligibility(opp_by_id["ntu-moe-phd-115-round2"], p1_a, as_of="2026-10-28")
        nstc_res = evaluate_eligibility(opp_by_id["ntu-nstc-phd-115"], p1_a, as_of="2026-10-28")
        self.assertEqual(moe_res["criteria"], "not_met")
        self.assertEqual(nstc_res["criteria"], "needs_information")
        self.assertTrue(any("不限年級" in r for r in nstc_res["reasons"]))

        # P1-B：明示 2026-01-30 之後才通過候選人資格 -> 遠學 115 一般補助判 not_met（不將 10 月候選人身分回填至 1 月）
        p1_b = make_p1_profile(candidate_acquired_after="2026-01-30")
        yx_res = evaluate_eligibility(opp_by_id["ntu-yuanxue-115-ordinary"], p1_b, as_of="2026-10-28")
        self.assertEqual(yx_res["criteria"], "not_met")

        # P1-C：僅知當年經濟拮据，未提供正式清寒證明 -> 清寒限定方案不自動通過
        hardship_item = deepcopy(opp_by_id["ntu-tuition-115-1"])
        hardship_item["hardship"]["mode"] = "required"
        p1_c = make_p1_profile(financial_difficulty_informal=True, hardship_proof="unknown")
        hc_res = evaluate_eligibility(hardship_item, p1_c, as_of="2026-10-28")
        self.assertEqual(hc_res["criteria"], "needs_information")
        self.assertIn("official_hardship_proof", hc_res["missing_information"])

        # P2：一般碩士生 -> 博士專屬方案判 not_met
        p2 = make_p1_profile(profile_id="SYNTH-MASTER", degree="master", current_year=2, is_candidate=False)
        self.assertEqual(evaluate_eligibility(opp_by_id["ntu-nstc-phd-115"], p2)["criteria"], "not_met")
        self.assertEqual(evaluate_eligibility(opp_by_id["ntu-tuition-115-1"], p2)["criteria"], "needs_information")

        # P3：外籍博士生 -> 本國籍限定方案判 not_met；國科會核配須確認入學／國際處管道，不直接排除
        p3 = make_p1_profile(profile_id="SYNTH-INTL-PHD", nationality="non_roc", current_year=2, admission_route="unknown")
        self.assertEqual(evaluate_eligibility(opp_by_id["ntu-moe-phd-115-round2"], p3)["criteria"], "not_met")
        self.assertEqual(evaluate_eligibility(opp_by_id["nstc-abroad-116-ntu"], p3)["criteria"], "not_met")
        p3_nstc = evaluate_eligibility(opp_by_id["ntu-nstc-phd-115"], p3)
        self.assertEqual(p3_nstc["criteria"], "needs_information")
        self.assertIn("admission_route", p3_nstc["missing_information"])

    def test_r1_r2_r3_r4_r5_r6_r7_fixes_and_policy_snapshot_diff(self):
        from scripts.extract_candidates import (
            parse_amount_from_text,
            parse_baseline_year_month,
            parse_chinese_or_arabic_int,
        )
        from scripts.verify_candidates import evidence_digest

        # R1 & R2：小寫中文數字金額與中文民國年基準月解析
        self.assertEqual(parse_chinese_or_arabic_int("四萬"), 40000)
        self.assertEqual(parse_chinese_or_arabic_int("伍拾貳萬伍仟"), 525000)
        self.assertEqual(parse_chinese_or_arabic_int("玖拾萬"), 900000)
        self.assertEqual(parse_chinese_or_arabic_int("一一五"), 115)
        self.assertEqual(parse_chinese_or_arabic_int("2.5萬"), 25000)
        self.assertEqual(parse_baseline_year_month("以一一五年九月博士班一至三年級在學學生為基準"), "2026-09-01")

        amt_40k = parse_amount_from_text("每名每月四萬元，自一學年至多獎勵四學年。")
        self.assertIsNotNone(amt_40k)
        self.assertEqual(amt_40k["amount_min"], 40000)
        self.assertEqual(amt_40k["unit"], "per_month")

        # R3：設置辦法 PDF (policy_snapshot) 與當期公告分離，不與 pilot.json 當期機會產生假 application.state 差異
        pdf_blocks = [
            {"locator": "P1", "text": "國立臺灣大學博士生獎學金設置辦法（114年4月23日修正通過）。"},
            {"locator": "P2", "text": "國科會核配博士生獎學金：博士班在學學生，非在職生，每名每月四萬元，不得重複支領。"},
            {"locator": "P3", "text": "教育部博士生獎學金：本國籍非在職生，博士班一至三年級在學學生，每名每月四萬元，不得重複支領。"},
        ]
        pdf_cands = extract_from_in_memory_blocks(
            CONFIG["sources"][0],
            pdf_blocks,
            revision_id="8" * 64,
            observed_at="2026-10-29T09:17:00+08:00",
            url="https://www.aca.ntu.edu.tw/w/aca/國立臺灣大學博士生獎學金設置辦法1140423.pdf",
            as_of="2026-10-29",
        )
        for pc in pdf_cands:
            self.assertEqual(pc["cycle"]["kind"], "policy_snapshot")
            self.assertEqual(pc["benefit"]["items"][0]["amount_min"], 40000)
            diff_res = compute_candidate_diff(pc, PILOT)
            self.assertEqual(diff_res["diff_status"], "policy_regulation_snapshot")
            self.assertFalse(any(d["field"] == "application.state" for d in diff_res["field_diffs"]))

        # R5：提及未抓取第二份申請說明附件或對照 pilot.json 欄位退步時，標記 passed_with_gaps 與 coverage_ok=False
        gap_blocks = [
            {"locator": "H1", "text": "教育部博士生獎學金（115學年度）：本國籍非在職之博士班在學學生，以一一五年九月一至三年級為基準，每名每月四萬元，不得重複支領。"},
            {"locator": "H2", "text": "115學年度第2梯次教育部博士生獎學金申請說明詳見附件。"},
        ]
        gap_cands = extract_from_in_memory_blocks(
            CONFIG["sources"][0],
            gap_blocks,
            revision_id="9" * 64,
            observed_at="2026-10-29T09:17:00+08:00",
            as_of="2026-10-29",
        )
        moe_gap = next(c for c in gap_cands if c["program_key"] == "ntu-moe-phd")
        self.assertEqual(moe_gap["eligibility"]["year_limit"]["assessed_at"], "2026-09-01")
        self.assertEqual(moe_gap["verification"]["status"], "passed_with_gaps")
        self.assertFalse(moe_gap["verification"]["checks"]["coverage_ok"])

        # R6 & R7：所有非 unknown 欄位（含 eligibility.identity）皆須具備 field_evidence 與正確 source_block_sha256
        for ev in moe_gap["field_evidence"]:
            self.assertIn("source_block_sha256", ev)
        self.assertTrue(any(ev["field_path"] == "eligibility.identity" for ev in moe_gap["field_evidence"]))

        bad_identity_cand = deepcopy(moe_gap)
        bad_identity_cand["field_evidence"] = [
            ev for ev in bad_identity_cand["field_evidence"] if ev["field_path"] != "eligibility.identity"
        ]
        ver_bad = verify_candidate(bad_identity_cand, in_memory_blocks=gap_blocks)
        self.assertEqual(ver_bad["verification"]["status"], "failed_automated_checks")
        self.assertIn("missing_evidence:eligibility.identity", ver_bad["verification"]["errors"])

        self.assertEqual(evidence_digest("  測試  空白\n正規化 "), evidence_digest("測試 空白 正規化"))

    def test_dual_track_llm_extract_audit_merge_cache_and_injection_defense(self):
        # 1. Audit 模式：agree 標記 rule_and_model_agreed=True；disagree 寫入 conflicts 觸發 conflict_detected
        yx_blocks = make_yuanxue_blocks()
        audit_agree_resp = {
            "extracted_fields": [],
            "audit_findings": [
                {
                    "field_path": "benefit.items/0",
                    "verdict": "agree",
                    "llm_value": 525000,
                    "locator": yx_blocks[2]["locator"],
                    "quote": "伍拾貳萬伍仟元以上、玖拾萬元以下",
                    "note": "金額區間與原文一致",
                }
            ],
        }
        mock_audit_ok = MockModelAdapter({"*": audit_agree_resp}, mode="audit")
        cands_ok = extract_from_in_memory_blocks(
            CONFIG["sources"][2],
            yx_blocks,
            revision_id="a" * 64,
            observed_at="2026-10-29T09:17:00+08:00",
            model_adapter=mock_audit_ok,
        )
        ev_b0 = next(e for e in cands_ok[0]["field_evidence"] if e["field_path"] == "benefit.items/0")
        self.assertTrue(ev_b0.get("rule_and_model_agreed"))
        self.assertEqual(cands_ok[0]["source_metadata"]["adapter_used"], "rules_plus_llm_audit")

        audit_disagree_resp = {
            "extracted_fields": [],
            "audit_findings": [
                {
                    "field_path": "eligibility.candidate",
                    "verdict": "disagree",
                    "llm_value": "not_required",
                    "locator": yx_blocks[1]["locator"],
                    "quote": "通過博士學位候選人資格考核",
                    "note": "模型認為有例外條款",
                }
            ],
        }
        mock_audit_disagree = MockModelAdapter({"*": audit_disagree_resp}, mode="audit")
        cands_dis = extract_from_in_memory_blocks(
            CONFIG["sources"][2],
            yx_blocks,
            revision_id="b" * 64,
            observed_at="2026-10-29T09:17:00+08:00",
            model_adapter=mock_audit_disagree,
        )
        self.assertEqual(cands_dis[0]["verification"]["status"], "conflict_detected")
        self.assertFalse(cands_dis[0]["verification"]["checks"]["no_unresolved_conflicts"])
        # 規則原值 required 絕不被靜默覆蓋
        self.assertEqual(cands_dis[0]["eligibility"]["candidate"]["mode"], "required")

        # 2. Extract 補缺模式：攔截非原文子字串引文、攔截數值與引文二次解析不符、攔截上層期限誤填學生截止日
        bad_extract_resp = {
            "extracted_fields": [
                {
                    "field_path": "eligibility.nationality",
                    "value": "roc_only",
                    "unit": None,
                    "currency": None,
                    "actor": None,
                    "locator": yx_blocks[0]["locator"],
                    "quote": "原文完全不存在的引文字串",
                },
                {
                    "field_path": "schedule.student_deadline",
                    "value": "2026-01-30",
                    "unit": None,
                    "currency": None,
                    "actor": "student",
                    "locator": yx_blocks[3]["locator"],
                    "quote": "請學院於115年1月30日前彙整送達研究發展處",
                },
                {
                    "field_path": "policy_version.amended_on",
                    "value": "2099-12-31",
                    "unit": None,
                    "currency": None,
                    "actor": None,
                    "locator": yx_blocks[3]["locator"],
                    "quote": "115年1月30日",
                },
            ],
            "audit_findings": [],
        }
        mock_bad_ext = MockModelAdapter({"*": bad_extract_resp}, mode="extract")
        cands_bad_ext = extract_from_in_memory_blocks(
            CONFIG["sources"][2],
            yx_blocks,
            revision_id="c" * 64,
            observed_at="2026-10-29T09:17:00+08:00",
            model_adapter=mock_bad_ext,
        )
        self.assertEqual(mock_bad_ext.rejected_claims, 3)
        self.assertEqual(cands_bad_ext[0]["eligibility"]["nationality"], "unknown")
        self.assertIsNone(cands_bad_ext[0]["schedule"]["steps"][0]["deadline"]["value"])
        self.assertIsNone(cands_bad_ext[0]["policy_version"]["amended_on"])

        # 3. 合法的 Extract 補缺（引文存在於區塊且通過二次解析）與本地磁碟快取驗證
        blocks_with_nat = deepcopy(yx_blocks)
        blocks_with_nat[0]["text"] += "（申請人須具本國籍身分）。"
        good_extract_resp = {
            "extracted_fields": [
                {
                    "field_path": "eligibility.nationality",
                    "value": "roc_only",
                    "unit": None,
                    "currency": None,
                    "actor": None,
                    "locator": blocks_with_nat[0]["locator"],
                    "quote": "申請人須具本國籍身分",
                }
            ],
            "audit_findings": [],
        }
        # 移除規則直接觸發之關鍵字以測試純模型補缺
        blocks_with_nat[0]["text"] = blocks_with_nat[0]["text"].replace("本國籍", "臺灣地區戶籍")
        good_extract_resp["extracted_fields"][0]["quote"] = "申請人須具臺灣地區戶籍身分"
        mock_good_ext = MockModelAdapter({"*": good_extract_resp}, mode="both")
        cands_good_ext = extract_from_in_memory_blocks(
            CONFIG["sources"][2],
            blocks_with_nat,
            revision_id="d" * 64,
            observed_at="2026-10-29T09:17:00+08:00",
            model_adapter=mock_good_ext,
        )
        self.assertEqual(cands_good_ext[0]["eligibility"]["nationality"], "roc_only")
        self.assertEqual(cands_good_ext[0]["source_metadata"]["adapter_used"], "rules_plus_llm_both")
        self.assertIn("needs_human_review_for_model_supplement", cands_good_ext[0]["verification"]["warnings"])

    def test_provider_presets_and_nvidia_nim_adapter_configuration(self):
        from scripts.providers import PROVIDERS, provider_settings
        from scripts.extract_candidates import create_model_adapter_from_env
        self.assertNotIn("github", PROVIDERS)
        self.assertIn("gemini", PROVIDERS)
        base,model,key = provider_settings("mistral", {"OPENGSA_MODEL_BASE_URL":"https://api.groq.com/openai/v1", "OPENGSA_MODEL_NAME":"wrong-groq-model", "OPENGSA_MISTRAL_API_KEY":"synthetic"})
        self.assertEqual(base,"https://api.mistral.ai/v1")
        self.assertEqual(model,"mistral-small-latest")
        self.assertEqual(key,"OPENGSA_MISTRAL_API_KEY")
        with unittest.mock.patch.dict(os.environ,{"OPENGSA_MODEL_MODE":"audit","OPENGSA_MODEL_PROVIDER":"nvidia","OPENGSA_NVIDIA_API_KEY":"synthetic"},clear=True):
            self.assertIsInstance(create_model_adapter_from_env(),DisabledModelAdapter)
        with self.assertRaises(ValueError):
            provider_settings("siliconflow", {})



    def test_phase_2_deterministic_extractors_for_dragon_assistant_and_ta(self):
        src=next(s for s in CONFIG["sources"] if s["id"]=="nstc-abroad-dragon-rule")
        for year,amount in [(2025,900000),(2027,1200000)]:
            blocks=[{"locator":"id","text":"博士班在學學生，中華民國國籍，經學校推薦。"},
                    {"locator":"money","text":f"每年新臺幣{amount}元。"},
                    {"locator":"date","text":f"申請期間{year}-06-01至{year}-07-31由申請機構備函送達。"}]
            cand=extract_from_in_memory_blocks(src,blocks,revision_id="d"*64,observed_at="2026-10-30T09:17:00+08:00",as_of="2026-10-30")[0]
            self.assertEqual(cand["benefit"]["items"][0]["amount_min"],amount)
            self.assertEqual(cand["benefit"]["items"][0]["unit"],"per_year")
            self.assertEqual(cand["schedule"]["steps"][0]["deadline"]["value"],f"{year}-07-31")
            self.assertEqual(cand["schedule"]["steps"][0]["actor"],"institution")
            self.assertEqual(cand["application"]["state"],"closed" if year < 2026 else "unknown")
        # A recurring clause has no verified current-year window.
        blocks=[{"locator":"rule","text":"博士班學生每年六月一日至七月三十一日申請。"}]
        cand=extract_from_in_memory_blocks(src,blocks,revision_id="c"*64,observed_at="2026-10-30T09:17:00+08:00")[0]
        self.assertIsNone(cand["schedule"]["application_start"]["value"])
        self.assertEqual(cand["benefit"]["items"],[])



    def test_phase_2_candidates_end_to_end_review_and_diff_generation(self):
        # 1. 取得四大 Phase 2 來源
        dragon_src = next((s for s in CONFIG["sources"] if s["id"] == "nstc-abroad-dragon-rule"), None)
        asst_src = next((s for s in CONFIG["sources"] if s["id"] == "nstc-assistant-rule"), None)
        ta_src = next((s for s in CONFIG["sources"] if s["id"] == "ntu-ta-policy"), None)
        limit_src = next((s for s in CONFIG["sources"] if s["id"] == "ntu-ord-assistant-limit"), None)

        cands = []
        cands.extend(extract_from_in_memory_blocks(
            dragon_src,
            [{"locator": "FL039188-1", "text": "國家科學及技術委員會補助博士生赴國外研究作業要點。國內公立大學博士班在學一年以上經學校推薦。以一年研究費九十萬元為上限核給，補助七至十二個月。每年六月一日至七月三十一日完成線上申請並備函送會。"}],
            revision_id="d"*64, observed_at="2026-10-30T09:17:00+08:00", as_of="2026-10-28"
        ))
        cands.extend(extract_from_in_memory_blocks(
            asst_src,
            [{"locator": "FL028686-1", "text": "國科會補助專題研究計畫研究人力約用注意事項。專題計畫兼任助理碩士學生每月最高一萬六千元，博士級助理每月最高四萬元。受聘學生應簽訂書面約定。"}],
            revision_id="a"*64, observed_at="2026-10-30T09:17:00+08:00", as_of="2026-10-28"
        ))
        cands.extend(extract_from_in_memory_blocks(
            ta_src,
            [{"locator": "TA-1", "text": "臺大教務處教學助理制度獎勵金實施辦法。博士班一般課程教學助理每月八千至一萬元。碩士班一般中文教學助理每月六千至七千五百元。"}],
            revision_id="t"*64, observed_at="2026-10-30T09:17:00+08:00", as_of="2026-10-28"
        ))
        cands.extend(extract_from_in_memory_blocks(
            limit_src,
            [{"locator": "ORD-1", "text": "國立臺灣大學計畫兼任助理及研究獎助生每月支給上限標準表。碩士級每月支給上限兩萬元；博士生未取得候選人資格四萬兩千元；博士候選人五萬元。"}],
            revision_id="l"*64, observed_at="2026-10-30T09:17:00+08:00", as_of="2026-10-28"
        ))

        self.assertEqual(len(cands), 4)
        bundle = {
            "schema_version": "0.1.0-proposal",
            "as_of": "2026-10-28",
            "timezone": "Asia/Taipei",
            "model_enabled": False,
            "model_calls": 0,
            "official_data_modified": False,
            "candidates": cands,
        }
        verified_bundle, summary, md = build_review_report(bundle, PILOT)
        self.assertEqual(summary["total_candidates"], 4)
        self.assertEqual(summary["promotion_ready"], 0)  # 尚未人工獨立覆核，維持 pending
        self.assertEqual(summary["model_calls"], 0)
        self.assertEqual(summary["model_usage"]["hash_only_bytes_sent"], 0)
        self.assertFalse(summary["official_data_modified"])
        self.assertIn("nstc-abroad-dragon", md)
        self.assertIn("nstc-assistant-rule", md)
        self.assertIn("ntu-ta-policy", md)
        self.assertIn("ntu-ord-assistant-limit", md)




    def test_phase_3_deterministic_extractors_for_colleges_sinica_and_tsmc(self):
        for sid in ["sinica-phd-fellowship","tsmc-phd-fellowship","ntu-eecs-scholarship","ntu-coe-scholarship"]:
            src=next(s for s in CONFIG["sources"] if s["id"]==sid)
            blocks=[{"locator":"id","text":"博士候選人，非全時有給職，資格仍依完整辦法核定。"},
                    {"locator":"money","text":"每月新臺幣43000元。"},
                    {"locator":"date","text":"學生申請期間2025-03-01至2025-04-10截止。"}]
            cand=extract_from_in_memory_blocks(src,blocks,revision_id="e"*64,observed_at="2026-10-30T09:17:00+08:00")[0]
            self.assertEqual(cand["benefit"]["items"][0]["amount_min"],43000)
            self.assertEqual(cand["eligibility"]["employment_status"],"unemployed_or_no_fulltime_pay")
            self.assertEqual(cand["schedule"]["application_start"]["value"],"2025-03-01")
            self.assertEqual(cand["schedule"]["steps"][0]["deadline"]["value"],"2025-04-10")
            self.assertEqual(cand["verification"]["errors"],[])




    def test_review_ledger_promotion_ready_and_pr_draft_export(self):
        from scripts.review_candidates import candidate_fingerprint
        self.assertEqual(read_json(ROOT/"data/scan-reviews.json")["reviews"],[])
        src=CONFIG["sources"][3]
        blocks=make_nstc_conference_blocks()
        cand=extract_from_in_memory_blocks(src,blocks,revision_id="a"*64,observed_at="2026-10-28T09:17:00+08:00",as_of="2026-10-28")[0]
        bundle={"schema_version":"1.1.0-candidate","generated_at":"2026-10-28T09:17:00+08:00","as_of":"2026-10-28","timezone":"Asia/Taipei","model_enabled":False,"model_calls":0,"official_data_modified":False,"candidates":[cand]}
        entry={"revision_id":"a"*64,"source_id":src["id"],"candidate_id":cand["candidate_id"],"candidate_sha256":candidate_fingerprint(cand),"action":"applied","reviewer":"SYNTH-independent-reviewer","reviewed_on":"2026-10-28","reason":"Synthetic test disposition, not actual human approval"}
        ledger={"schema_version":"1.1.0","reviews":[entry]}
        verified,summary,_=build_review_report(bundle,PILOT,reviews_data=ledger,in_memory_blocks_by_source={src["url"]:blocks})
        self.assertEqual(summary["promotion_ready"],1)
        with tempfile.TemporaryDirectory() as temp:
            output=Path(temp)/"pr.json"
            ids=export_pr_candidate_draft(verified,PILOT,output,scan_sources_config=CONFIG)
            self.assertEqual(len(ids),1)
            self.assertEqual(validate_pilot(read_json(output)),[])
            tampered=deepcopy(verified)
            tampered["candidates"][0]["title"]="changed after approval"
            # Title is an approval-bound claim.
            tampered["candidates"][0]["benefit"]["summary"]="changed"
            self.assertEqual(export_pr_candidate_draft(tampered,PILOT,output,scan_sources_config=CONFIG),[])
        entry["reviewer"]=cand["review"]["editor"]
        _,summary,_=build_review_report(bundle,PILOT,reviews_data=ledger,in_memory_blocks_by_source={src["url"]:blocks})
        self.assertEqual(summary["promotion_ready"],0)
        with self.assertRaises(ValueError):
            export_pr_candidate_draft(verified,PILOT,ROOT/"data/pilot.json")



if __name__ == "__main__":
    unittest.main()
