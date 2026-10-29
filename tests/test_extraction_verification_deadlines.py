"""測試結構化候選 Schema、規則與模型 Adapter 萃取、獨立檢核、申請時間判斷、P1 資格比對與覆核流程。
所有測試皆使用離線合成樣本與記憶體 fixture，不發送外部網路請求，亦不呼叫真實外部模型。
"""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest

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
        self.assertEqual(schema["properties"]["schema_version"]["const"], "1.0.0-candidate")

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
        self.assertEqual(yx["verification"]["status"], "passed_automated_checks")
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
        verified_bundle, summary, md = build_review_report(good_bundle, PILOT)
        self.assertEqual(summary["passed_automated_checks"], 1)
        self.assertEqual(summary["promotion_ready"], 0)  # 尚未經人工獨立覆核
        self.assertIn("一、來源變更", md)
        self.assertIn("二、結構化萃取結果", md)
        self.assertIn("三、獨立檢核與申請時間", md)
        self.assertIn("四、與 `data/pilot.json` 差異及人工覆核處置", md)

        # 嚴格禁止直接覆寫 data/pilot.json
        with self.assertRaises(ValueError):
            export_pr_candidate_draft(verified_bundle, PILOT, ROOT / "data/pilot.json")

        # 自審 (independent_reviewer == editor) 不得升級為 promotion_ready
        self_reviews = {
            "reviews": [
                {
                    "revision_id": "7" * 64,
                    "action": "applied",
                    "reviewer": verified_bundle["candidates"][0]["review"]["editor"],
                    "reason": "自審測試",
                    "reviewed_on": "2026-10-28",
                }
            ]
        }
        vb_self, sum_self, _ = build_review_report(good_bundle, PILOT, reviews_data=self_reviews)
        self.assertEqual(sum_self["promotion_ready"], 0)

        # 經非原編輯者獨立覆核通過後，可匯出至 PR 暫存檔且通過 check_data.validate
        ind_reviews = {
            "reviews": [
                {
                    "revision_id": "7" * 64,
                    "action": "applied",
                    "reviewer": "independent-maintainer-2",
                    "reason": "已逐欄核對研發處原文與金額期間",
                    "reviewed_on": "2026-10-28",
                }
            ]
        }
        vb_ind, sum_ind, _ = build_review_report(good_bundle, PILOT, reviews_data=ind_reviews)
        self.assertEqual(sum_ind["promotion_ready"], 1)
        with tempfile.TemporaryDirectory() as tmpdir:
            staging_path = Path(tmpdir) / "pilot-pr-candidate.json"
            promoted = export_pr_candidate_draft(vb_ind, PILOT, staging_path)
            self.assertEqual(promoted, ["ntu-yuanxue-115-ordinary"])
            staged_data = read_json(staging_path)
            self.assertEqual(validate_pilot(staged_data), [])

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


if __name__ == "__main__":
    unittest.main()
