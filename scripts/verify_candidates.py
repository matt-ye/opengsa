"""結構化獎助候選資料之獨立檢核器 (Independent Verifier)。

檢核六大面向：
1. Schema 驗證 (schema/candidate.schema.json)
2. 逐欄證據支持、hash_only 不洩漏原文、殘句／雜湊不猜測、防模型捏造 (Evidence & Anti-Hallucination)
3. 日期精度（Asia/Taipei、僅日期不自造 23:59、修正日不當生效日）與金額單位完整性
4. 年度／梯次／分支不混用（不將 114 與 115 學年度、教育部與國科會、一般與配合補助合成一筆）
5. 否定條件保留（非在職、不得兼領、未知兼領不當可兼領）與申請角色分流（機構／學院期限不當學生截止）
6. 來源衝突攔截與人工獨立覆核門檻（忽略 Agent 自信宣告，未經非原編輯者覆核維持 pending）
"""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.evaluate_deadlines import parse_iso_date, parse_taipei_datetime

VERIFIER_VERSION = "verifier-1.0.0"

CONTACT_RE = re.compile(r"@|電話|聯絡|承辦|傳真|住址|通訊地址|\b0\d{1,3}[- ]\d{6,}")
SKIP_RE = re.compile(r"名冊|名單|獲獎|得獎|姓名|學號|身分證|jsessionid|password|token=|login|登入", re.I)
TIME_EVIDENCE_RE = re.compile(r"(?:\d{1,2}\s*[時點:]\s*\d{0,2}|上午|下午|早上|中午|傍晚|午夜|17:00|08:00|12:00)")

CHINESE_AMOUNTS = {
    525000: ["525,000", "525000", "伍拾貳萬伍仟", "伍拾貳萬伍仟", "52.5萬", "五十二萬五千"],
    900000: ["900,000", "900000", "玖拾萬", "玖拾萬", "90萬", "九十萬"],
    100000: ["100,000", "100000", "壹拾萬", "拾萬", "10萬", "十萬"],
    40000: ["40,000", "40000", "肆萬", "4萬", "四萬"],
    8000: ["8,000", "8000", "捌仟", "八千"],
    10000: ["10,000", "10000", "壹萬", "1萬", "一萬"],
    16000: ["16,000", "16000", "1.6萬", "一萬六千"],
}


def digest_text(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def normalized(text):
    return re.sub(r"\s+", " ", text or "").strip()


def load_candidate_schema():
    return json.loads((ROOT / "schema/candidate.schema.json").read_text(encoding="utf-8"))


def _amount_tokens(val):
    if val is None:
        return []
    int_val = int(val)
    tokens = [str(int_val), f"{int_val:,}"]
    if int_val in CHINESE_AMOUNTS:
        tokens.extend(CHINESE_AMOUNTS[int_val])
    if int_val >= 10000 and int_val % 10000 == 0:
        wan = int_val // 10000
        tokens.append(f"{wan}萬")
    return tokens


def _date_tokens(iso_str):
    """將 YYYY-MM-DD 轉為原文可能出現的西元或民國年月日表達清單，供原文支持度核對。"""
    if not iso_str or len(iso_str) < 10:
        return []
    d = parse_iso_date(iso_str[:10])
    if d is None:
        return []
    roc_y = d.year - 1911
    m = d.month
    day = d.day
    return [
        f"{d.year}-{m:02d}-{day:02d}",
        f"{d.year}/{m:02d}/{day:02d}",
        f"{d.year}.{m:02d}.{day:02d}",
        f"{d.year}/{m}/{day}",
        f"{d.year}.{m}.{day}",
        f"{d.year}年{m}月{day}日",
        f"{roc_y}/{m:02d}/{day:02d}",
        f"{roc_y}/{m}/{day}",
        f"{roc_y}.{m:02d}.{day:02d}",
        f"{roc_y}.{m}.{day}",
        f"{roc_y}年{m}月{day}日",
        f"{roc_y}年{m:02d}月{day:02d}日",
        f"{m}月{day}日",
        f"{m}/{day}",
    ]


def verify_candidate(candidate, in_memory_blocks=None, now_iso=None):
    """獨立檢核單筆 candidate_record，回傳更新 verification 與 review 門檻後的副本。"""
    cand = deepcopy(candidate)
    now_iso = now_iso or datetime.now(timezone.utc).isoformat(timespec="seconds")

    # 移除任何模型自稱驗證欄位（Agent 自稱正確不能取代驗證）
    for forbidden_self_key in ("agent_confidence", "self_verified", "auto_approved", "model_approved"):
        cand.pop(forbidden_self_key, None)

    errors = []
    warnings = []

    schema = load_candidate_schema()
    record_schema = {
        "$schema": schema["$schema"],
        "$defs": schema["$defs"],
        "$ref": "#/$defs/candidate_record",
    }

    # 先給予預設 verification 結構以便執行 JSON Schema 驗證
    cand["verification"] = {
        "status": "failed_automated_checks",
        "verifier_version": VERIFIER_VERSION,
        "checked_at": now_iso,
        "model_self_claim_ignored": True,
        "checks": {
            "schema_valid": False,
            "evidence_supported": False,
            "date_and_amount_units_valid": False,
            "no_year_or_branch_mixing": False,
            "negation_and_roles_valid": False,
            "no_unresolved_conflicts": False,
        },
        "errors": [],
        "warnings": [],
    }

    # 1. Schema 檢查
    validator = Draft202012Validator(record_schema, format_checker=FormatChecker())
    schema_errors = [
        f"schema/{'/'.join(map(str, err.absolute_path))}: {err.message}"
        for err in validator.iter_errors(cand)
    ]
    schema_valid = len(schema_errors) == 0
    errors.extend(schema_errors)

    # 2. 證據支持與防捏造檢查 (Evidence Support & Anti-Hallucination)
    ev_errors = []
    meta = cand.get("source_metadata", {})
    ev_mode = meta.get("evidence_mode", "short_excerpt")
    ctx_suff = meta.get("context_sufficiency", "in_memory_full_blocks")
    field_ev = cand.get("field_evidence", [])
    ev_by_path = {}
    for entry in field_ev:
        ev_by_path.setdefault(entry.get("field_path", ""), []).append(entry)
        if entry.get("evidence_mode") != ev_mode:
            ev_errors.append(f"evidence_mode_mismatch:{entry.get('field_path')}")
        if ev_mode == "hash_only" and entry.get("excerpt") is not None:
            ev_errors.append(f"hash_only_excerpt_leak:{entry.get('field_path')}")
        if ev_mode == "short_excerpt":
            exc = entry.get("excerpt")
            if not exc:
                ev_errors.append(f"missing_short_excerpt:{entry.get('field_path')}")
            else:
                if digest_text(exc) != entry.get("excerpt_sha256"):
                    ev_errors.append(f"excerpt_sha256_mismatch:{entry.get('field_path')}")
                if CONTACT_RE.search(exc) or SKIP_RE.search(exc):
                    ev_errors.append(f"sensitive_or_contact_in_excerpt:{entry.get('field_path')}")

    block_map = {}
    if in_memory_blocks is not None:
        block_map = {b["locator"]: normalized(b["text"]) for b in in_memory_blocks}
        for entry in field_ev:
            loc = entry.get("locator")
            if loc not in block_map:
                ev_errors.append(f"evidence_locator_not_in_source:{entry.get('field_path')}:{loc}")
                continue
            block_text = block_map[loc]
            if ev_mode == "short_excerpt" and entry.get("excerpt"):
                if normalized(entry["excerpt"]) not in block_text:
                    ev_errors.append(f"hallucinated_excerpt_not_in_block:{entry.get('field_path')}")
            elif ev_mode == "hash_only":
                # 檢查雜湊是否來自該 block 的實際子字串或整段
                sha = entry.get("excerpt_sha256")
                if digest_text(block_text) != sha and not entry.get("_verified_in_memory_span"):
                    # 若無整段相等，檢查是否與 block 內任何行／句雜湊吻合
                    matched = any(
                        digest_text(part) == sha
                        for part in [block_text] + re.split(r"[。；！？\n]", block_text)
                        if part
                    )
                    if not matched:
                        ev_errors.append(f"hash_only_sha256_not_grounded_in_block:{entry.get('field_path')}")

    # 檢查無記憶體上下文（僅有雜湊或殘句）時不得猜測具體欄位值
    elig = cand.get("eligibility", {})
    benefit_items = cand.get("benefit", {}).get("items", [])
    steps = cand.get("schedule", {}).get("steps", [])
    has_concrete_claims = (
        elig.get("year_limit", {}).get("mode") not in (None, "unknown")
        or elig.get("candidate", {}).get("mode") not in (None, "unknown")
        or elig.get("nationality") not in (None, "unknown")
        or elig.get("employment_status") not in (None, "unknown")
        or len(benefit_items) > 0
        or cand.get("compatibility", {}).get("mode") not in (None, "unknown")
        or any(s.get("deadline", {}).get("kind") not in (None, "unknown") for s in steps)
    )
    if ctx_suff == "hash_only_without_memory" and has_concrete_claims:
        ev_errors.append("guessed_from_hash_without_in_memory_context")
    if ctx_suff == "robots_or_access_restricted" and has_concrete_claims:
        ev_errors.append("guessed_from_restricted_source")

    # 檢查必要欄位的 field_evidence 覆蓋率與原文數值支持
    if elig.get("year_limit", {}).get("mode") not in (None, "unknown"):
        if "eligibility.year_limit" not in ev_by_path or not elig["year_limit"].get("refs"):
            ev_errors.append("missing_evidence:eligibility.year_limit")
        elif in_memory_blocks is not None:
            locs = [e["locator"] for e in ev_by_path["eligibility.year_limit"]]
            combined = " ".join(block_map.get(l, "") for l in locs)
            ymode = elig["year_limit"]["mode"]
            if ymode == "unlimited" and "不限年級" not in combined:
                ev_errors.append("unsupported_year_limit_unlimited")
            if ymode == "range" and not any(k in combined for k in ("年級", "一至三", "1至3", "三年級以上")):
                ev_errors.append("unsupported_year_limit_range")

    if elig.get("candidate", {}).get("mode") not in (None, "unknown"):
        if "eligibility.candidate" not in ev_by_path or not elig["candidate"].get("refs"):
            ev_errors.append("missing_evidence:eligibility.candidate")
        elif in_memory_blocks is not None:
            locs = [e["locator"] for e in ev_by_path["eligibility.candidate"]]
            combined = " ".join(block_map.get(l, "") for l in locs)
            if "候選人" not in combined:
                ev_errors.append("unsupported_candidate_requirement")

    for idx, b_item in enumerate(benefit_items):
        path_key = f"benefit.items/{idx}"
        matching_ev = ev_by_path.get(path_key) or ev_by_path.get("benefit.items") or []
        if not matching_ev or not b_item.get("refs"):
            ev_errors.append(f"missing_evidence:{path_key}")
        elif in_memory_blocks is not None:
            locs = [e["locator"] for e in matching_ev]
            combined = " ".join(block_map.get(l, "") for l in locs)
            for amt_field in ("amount_min", "amount_max"):
                amt = b_item.get(amt_field)
                if amt is not None:
                    tokens = _amount_tokens(amt)
                    if not any(tok in combined for tok in tokens):
                        ev_errors.append(f"hallucinated_amount_not_in_source:{path_key}:{amt}")

    if cand.get("compatibility", {}).get("mode") not in (None, "unknown"):
        if "compatibility" not in ev_by_path or not cand["compatibility"].get("refs"):
            ev_errors.append("missing_evidence:compatibility")

    for idx, step in enumerate(steps):
        dl = step.get("deadline", {})
        if dl.get("kind") in ("date", "datetime", "relative"):
            path_key = f"schedule.steps/{idx}/deadline"
            matching_ev = ev_by_path.get(path_key) or ev_by_path.get("schedule.steps") or []
            if not matching_ev or not step.get("refs"):
                ev_errors.append(f"missing_evidence:{path_key}")
            elif in_memory_blocks is not None and dl.get("kind") in ("date", "datetime") and dl.get("value"):
                locs = [e["locator"] for e in matching_ev]
                combined = " ".join(block_map.get(l, "") for l in locs)
                dtokens = _date_tokens(dl["value"])
                if not any(tok in combined.replace(" ", "") for tok in dtokens):
                    ev_errors.append(f"hallucinated_date_not_in_source:{path_key}:{dl['value']}")
                if dl.get("kind") == "datetime" and not TIME_EVIDENCE_RE.search(combined):
                    ev_errors.append(f"invented_time_for_date_only_source:{path_key}:{dl['value']}")

    evidence_supported = len(ev_errors) == 0
    errors.extend(ev_errors)

    # 3. 日期與金額單位檢查 (Date & Amount Units)
    da_errors = []
    app_start = cand.get("schedule", {}).get("application_start", {})
    if app_start.get("kind") == "date":
        if parse_iso_date(app_start.get("value")) is None:
            da_errors.append("invalid_application_start_date")
    elif app_start.get("kind") == "datetime":
        if parse_taipei_datetime(app_start.get("value")) is None:
            da_errors.append("invalid_application_start_datetime")

    student_dates = []
    upper_dates = []
    for idx, step in enumerate(steps):
        dl = step.get("deadline", {})
        kind = dl.get("kind")
        val = dl.get("value")
        if kind == "date":
            d = parse_iso_date(val)
            if d is None:
                da_errors.append(f"invalid_step_date:{idx}:{val}")
            else:
                if step.get("actor") in ("student", "student_or_representative"):
                    student_dates.append(d)
                elif step.get("actor") in ("department", "college", "unit", "university", "institution"):
                    upper_dates.append(d)
        elif kind == "datetime":
            dt = parse_taipei_datetime(val)
            if dt is None:
                da_errors.append(f"invalid_step_datetime:{idx}:{val}")
            else:
                if "T23:59" in val and ("僅公告日期" in dl.get("note", "") or "未載時間" in dl.get("note", "")):
                    da_errors.append(f"invented_midnight_deadline:{idx}:{val}")
                if step.get("actor") in ("student", "student_or_representative"):
                    student_dates.append(dt.date())
                elif step.get("actor") in ("department", "college", "unit", "university", "institution"):
                    upper_dates.append(dt.date())

    if app_start.get("value") and student_dates:
        start_d = parse_iso_date(app_start["value"][:10])
        if start_d and any(sd < start_d for sd in student_dates):
            da_errors.append("application_start_after_student_deadline")

    if student_dates and upper_dates:
        if min(student_dates) > max(upper_dates):
            da_errors.append("student_deadline_after_institution_or_college_deadline")

    # 檢查法規修正日不得自動當作生效日
    pver = cand.get("policy_version", {})
    if pver.get("effective_from"):
        if pver.get("effective_from") in (pver.get("amended_on"), pver.get("promulgated_on")):
            if in_memory_blocks is not None:
                p_evs = ev_by_path.get("policy_version", [])
                p_text = " ".join(block_map.get(e["locator"], "") for e in p_evs)
                if not any(k in p_text for k in ("生效", "施行", "實施")):
                    da_errors.append("amended_or_promulgated_date_copied_as_effective_date")
            elif "自動當生效日" in pver.get("note", "") or "未核" in pver.get("note", ""):
                da_errors.append("amended_or_promulgated_date_copied_as_effective_date")

    # 檢查金額單位完整性
    for idx, b_item in enumerate(benefit_items):
        has_num = b_item.get("amount_min") is not None or b_item.get("amount_max") is not None
        if has_num:
            if b_item.get("currency") in (None, "unknown"):
                da_errors.append(f"benefit_missing_currency:benefit.items/{idx}")
            if b_item.get("unit") in (None, "unknown"):
                da_errors.append(f"benefit_missing_unit:benefit.items/{idx}")
            if b_item.get("basis") in (None, "unknown"):
                da_errors.append(f"benefit_missing_basis:benefit.items/{idx}")
        if b_item.get("amount_min") is not None and b_item.get("amount_max") is not None:
            if b_item["amount_min"] > b_item["amount_max"]:
                da_errors.append(f"benefit_inverted_amount_range:benefit.items/{idx}")
        if b_item.get("duration_months_min") is not None and b_item.get("duration_months_max") is not None:
            if b_item["duration_months_min"] > b_item["duration_months_max"]:
                da_errors.append(f"benefit_inverted_duration_range:benefit.items/{idx}")

    date_and_amount_units_valid = len(da_errors) == 0
    errors.extend(da_errors)

    # 4. 年度／梯次／分支不混用檢查 (No Year or Branch Mixing)
    mix_errors = []
    cycle = cand.get("cycle", {})
    cycle_label = cycle.get("label", "")
    title = cand.get("title", "")
    combined_header = f"{title} {cycle_label}"

    # 檢查同一筆是否混入兩個不同學年度（排除明示「115年申請116年度」的跨年申請標籤）
    acad_years = set(re.findall(r"(1\d{2})\s*學年度", combined_header))
    if len(acad_years) > 1:
        mix_errors.append(f"mixed_academic_years_in_single_record:{sorted(acad_years)}")

    # 檢查是否把教育部與國科會博士獎學金混為同一筆
    if "教育部" in combined_header and "國科會" in combined_header and cand.get("category") == "phd_research":
        mix_errors.append("mixed_moe_and_nstc_phd_branches_in_single_record")

    # 檢查遠學是否把一般補助與配合補助混為同一筆
    if "一般補助" in combined_header and "配合補助" in combined_header:
        mix_errors.append("mixed_ordinary_and_matching_branches_in_single_record")
    if len(benefit_items) > 1:
        branches = {b.get("branch_or_tier") for b in benefit_items if b.get("branch_or_tier")}
        if len(branches) > 1 and ("一般補助" in branches or "配合補助" in branches or "教育部" in branches or "國科會" in branches):
            mix_errors.append(f"mixed_mutually_exclusive_benefit_branches:{sorted(branches)}")

    no_year_or_branch_mixing = len(mix_errors) == 0
    errors.extend(mix_errors)

    # 5. 否定條件與申請角色檢查 (Negated Conditions & Participant Roles)
    nr_errors = []
    id_text = elig.get("identity", {}).get("text", "")
    neg_conds = elig.get("negated_conditions", [])
    all_ev_text = " ".join(
        (e.get("excerpt") or "") + " " + (block_map.get(e.get("locator", ""), "") if in_memory_blocks else "")
        for e in field_ev
        if not str(e.get("field_path", "")).startswith("raw_clue.")
    )
    combined_elig_text = f"{id_text} {all_ev_text}"

    if any(k in combined_elig_text for k in ("非在職", "不含在職")):
        if elig.get("employment_status") == "allowed":
            nr_errors.append("negated_in_service_condition_turned_into_allowed")
        if not any(nc.get("field") == "employment_status" for nc in neg_conds):
            nr_errors.append("missing_negated_condition_entry_for_in_service")

    comp = cand.get("compatibility", {})
    comp_text = f"{comp.get('note', '')} {all_ev_text}"
    if any(k in comp_text for k in ("不得重複", "不得兼領", "重複請領", "不得向本會申請", "擇一")):
        if comp.get("mode") == "allowed":
            nr_errors.append("negated_compatibility_turned_into_allowed")

    # 申請角色與步驟行為主體檢查
    participants = cand.get("participants", {})
    if cand.get("resource_kind") == "employment_support" and participants.get("applicant") == "student":
        nr_errors.append("employment_support_applicant_cannot_be_student")
    if cand.get("program_key") in ("nstc-grad-conference-policy", "nstc-abroad", "faos-student-conference"):
        if participants.get("applicant") == "student":
            nr_errors.append(f"institution_applied_program_misassigned_applicant:{cand.get('program_key')}")

    for idx, step in enumerate(steps):
        actor = step.get("actor")
        action_and_note = f"{step.get('action', '')} {step.get('deadline', {}).get('note', '')}"
        if actor in ("student", "student_or_representative"):
            # 若動作明示為學院遞送推薦名單、學校負責人於會前兩個月向基金會提出、機關彙送或備函，不可掛在 student 名下！
            if any(
                phrase in action_and_note
                for phrase in ("學院送件", "遞送推薦名單至研究生教務組", "學校負責人提出", "向國科會彙送", "備函檢送名冊", "會議開始日前兩個月")
            ) and "之前一日17:00" not in action_and_note:
                nr_errors.append(f"institution_or_college_deadline_misassigned_to_student:steps/{idx}")

    negation_and_roles_valid = len(nr_errors) == 0
    errors.extend(nr_errors)

    # 6. 缺漏／衝突檢查與覆核狀態門檻 (Conflicts & Review Gate)
    conflicts = cand.get("gaps_and_conflicts", {}).get("conflicts", [])
    no_unresolved_conflicts = len(conflicts) == 0
    if not no_unresolved_conflicts:
        warnings.append(f"unresolved_conflicts_count:{len(conflicts)}")

    cand["verification"]["checks"] = {
        "schema_valid": schema_valid,
        "evidence_supported": evidence_supported,
        "date_and_amount_units_valid": date_and_amount_units_valid,
        "no_year_or_branch_mixing": no_year_or_branch_mixing,
        "negation_and_roles_valid": negation_and_roles_valid,
        "no_unresolved_conflicts": no_unresolved_conflicts,
    }
    cand["verification"]["errors"] = errors
    cand["verification"]["warnings"] = warnings

    if ctx_suff in ("hash_only_without_memory", "short_excerpt_only", "robots_or_access_restricted") and not errors:
        cand["verification"]["status"] = "needs_context"
    elif errors:
        cand["verification"]["status"] = "failed_automated_checks"
    elif not no_unresolved_conflicts:
        cand["verification"]["status"] = "conflict_detected"
    else:
        cand["verification"]["status"] = "passed_automated_checks"

    # 強制執行獨立覆核門檻：未通過檢核或無非原編輯者覆核，一律維持 pending 且 promotion_ready = False
    rev = cand.get("review", {})
    editor = rev.get("editor", "extractor")
    ind_rev = rev.get("independent_reviewer")
    rev_on = rev.get("reviewed_on")
    if (
        cand["verification"]["status"] == "passed_automated_checks"
        and rev.get("status") == "reviewed"
        and ind_rev
        and ind_rev != editor
        and parse_iso_date(rev_on) is not None
    ):
        rev["promotion_ready"] = True
    else:
        if rev.get("status") == "reviewed":
            if not ind_rev or ind_rev == editor:
                cand["verification"]["errors"].append("independent_reviewer_required_and_must_differ_from_editor")
                cand["verification"]["status"] = "failed_automated_checks"
            rev["status"] = "pending"
        rev["promotion_ready"] = False

    return cand


def verify_bundle(bundle, in_memory_blocks_by_source=None):
    """檢核整份 candidate bundle 並檢查根層 Schema。"""
    result = deepcopy(bundle)
    in_memory_blocks_by_source = in_memory_blocks_by_source or {}
    verified_list = []
    for cand in result.get("candidates", []):
        sid = cand.get("source_metadata", {}).get("source_id")
        url = cand.get("source_metadata", {}).get("url")
        blocks = in_memory_blocks_by_source.get(url) or in_memory_blocks_by_source.get(sid)
        verified_list.append(verify_candidate(cand, in_memory_blocks=blocks))
    result["candidates"] = verified_list

    schema = load_candidate_schema()
    bundle_errors = [
        f"bundle/{'/'.join(map(str, err.absolute_path))}: {err.message}"
        for err in Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(result)
    ]
    return result, bundle_errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path, help="Path to structured-candidates.json")
    args = parser.parse_args()
    bundle = json.loads(args.path.read_text(encoding="utf-8"))
    verified, bundle_errors = verify_bundle(bundle)
    if bundle_errors:
        for err in bundle_errors:
            print(err)
        raise SystemExit(1)
    statuses = [c["verification"]["status"] for c in verified["candidates"]]
    print(json.dumps({"total": len(statuses), "statuses": statuses}, ensure_ascii=False))
    if any(s == "failed_automated_checks" for s in statuses):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
