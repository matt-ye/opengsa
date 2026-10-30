"""結構化獎助候選資料之獨立檢核器 (Independent Verifier v1.1)。

檢核七大面向：
1. Schema 驗證 (schema/candidate.schema.json, 支援 1.0.0-candidate 與 1.1.0-candidate)
2. 逐欄證據支持、共用 evidence_digest 嚴格雜湊比對、hash_only 零原文外洩、殘句／雜湊不猜測、防模型捏造 (Evidence & Anti-Hallucination)
3. 日期精度（Asia/Taipei、僅日期不自造 23:59、修正日不當生效日）與金額單位完整性
4. 年度／梯次／分支不混用（不將 114 與 115 學年度、教育部與國科會、一般與配合補助合成一筆）
5. 否定條件保留（非在職、不得兼領、未知兼領不當可兼領）與申請角色分流（機構／學院期限不當學生截止）
6. 來源衝突與規則／模型盤查異議攔截（conflict_detected）
7. 欄位涵蓋率與對照草稿退步檢查（coverage_ok；若正確但缺關鍵欄位或較 pilot.json 退步則標為 passed_with_gaps）
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

VERIFIER_VERSION = "verifier-1.1.0"

CONTACT_RE = re.compile(r"@|電話|聯絡|承辦|傳真|住址|通訊地址|\b0\d{1,3}[- ]\d{6,}")
SKIP_RE = re.compile(r"名冊|名單|獲獎|得獎|姓名|學號|身分證|jsessionid|password|token=|login|登入", re.I)
TIME_EVIDENCE_RE = re.compile(r"(?:\d{1,2}\s*[時點:]\s*\d{0,2}|上午|下午|早上|中午|傍晚|午夜|17:00|08:00|12:00)")

CHINESE_AMOUNTS = {
    20000: ["20,000", "20000", "2萬", "貳萬", "二萬"],
    40000: ["40,000", "40000", "4萬", "肆萬", "四萬"],
    100000: ["100,000", "100000", "10萬", "壹拾萬", "拾萬", "十萬"],
    525000: ["525,000", "525000", "伍拾貳萬伍仟", "伍拾貳萬伍仟", "五十二萬五千", "52.5萬"],
    900000: ["900,000", "900000", "玖拾萬", "玖拾萬", "九十萬", "90萬"],
}

def _to_chinese_num(n):
    digits = ['', '一', '二', '三', '四', '五', '六', '七', '八', '九']
    if n < 10:
        return digits[n]
    elif n == 10:
        return '十'
    elif n < 20:
        return '十' + digits[n % 10]
    elif n % 10 == 0:
        return digits[n // 10] + '十'
    elif n < 100:
        return digits[n // 10] + '十' + digits[n % 10]
    return str(n)


ROC_CHINESE_YEARS = {
    111: "一一一",
    112: "一一二",
    113: "一一三",
    114: "一一四",
    115: "一一五",
    116: "一一六",
    117: "一一七",
}


def normalized(text):
    """與 scan_sources.py 一致之空白與隱藏字元正規化。"""
    cleaned = re.sub(r"[\u200b-\u200d\ufeff]", "", str(text or "")).replace("\u00a0", " ").replace("\u3000", " ")
    return re.sub(r"\s+", " ", cleaned).strip()


def evidence_digest(text):
    """共用之正規化文字 SHA-256 計算函式（R6：統一 scan_sources / extract / verify 雜湊基準）。"""
    return hashlib.sha256(normalized(text).encode("utf-8")).hexdigest()


def digest_text(text):
    """向後相容別名，統一走 evidence_digest。"""
    return evidence_digest(text)


def load_candidate_schema():
    return json.loads((ROOT / "schema/candidate.schema.json").read_text(encoding="utf-8"))


def _date_tokens(iso_date_str):
    """產生某個西元日期可能出現在中文／民國／西元原文中的字元片段，用於驗證日期非憑空捏造。"""
    d = parse_iso_date(iso_date_str[:10])
    if d is None:
        return []
    roc_year = d.year - 1911
    tokens = [
        f"{d.year}-{d.month:02d}-{d.day:02d}",
        f"{d.year}/{d.month:02d}/{d.day:02d}",
        f"{d.year}/{d.month}/{d.day}",
        f"{d.year}.{d.month}.{d.day}",
        f"{d.year}年{d.month}月{d.day}日",
        f"{roc_year}年{d.month}月{d.day}日",
        f"{roc_year}/{d.month:02d}/{d.day:02d}",
        f"{roc_year}/{d.month}/{d.day}",
        f"{roc_year}.{d.month:02d}.{d.day:02d}",
        f"{roc_year}.{d.month}.{d.day}",
        f"{d.month}月{d.day}日",
        f"{d.month}/{d.day}",
    ]
    cm = _to_chinese_num(d.month)
    cd = _to_chinese_num(d.day)
    tokens.extend([
        f"{cm}月{cd}日",
        f"{cm}月{cd}號",
        f"{d.month}月{cd}日",
        f"{cm}月{d.day}日",
    ])
    if roc_year in ROC_CHINESE_YEARS:
        cy = ROC_CHINESE_YEARS[roc_year]
        tokens.append(f"{cy}年")
        tokens.append(f"{cy}年{cm}月{cd}日")
        tokens.append(f"{cy}年{d.month}月{d.day}日")
    return list(dict.fromkeys(tokens))


def _amount_tokens(amount):
    if amount is None:
        return []
    amt_int = int(amount)
    tokens = [str(amt_int), f"{amt_int:,}"]
    if amt_int in CHINESE_AMOUNTS:
        tokens.extend(CHINESE_AMOUNTS[amt_int])
    if amt_int % 10000 == 0:
        wan = amt_int // 10000
        tokens.append(f"{wan}萬")
        c_wan = _to_chinese_num(wan)
        tokens.append(f"{c_wan}萬")
        if wan == 2:
            tokens.append("兩萬")
    return list(dict.fromkeys(tokens))


def strip_model_self_claims(candidate):
    """移除並忽略模型或 Agent 自行附加的自信分數或自稱通過檢核欄位。"""
    cleaned = deepcopy(candidate)
    for forbidden_key in ("self_verified", "agent_confidence", "model_approved", "auto_approve", "verified_by_llm"):
        cleaned.pop(forbidden_key, None)
        if isinstance(cleaned.get("verification"), dict):
            cleaned["verification"].pop(forbidden_key, None)
        if isinstance(cleaned.get("review"), dict):
            cleaned["review"].pop(forbidden_key, None)
    return cleaned


def verify_candidate(candidate, in_memory_blocks=None, now_iso=None, schema=None, pilot_by_id=None):
    """對單筆結構化候選執行七大獨立檢核，回傳更新 verification 與 review 狀態後的候選複本。"""
    cand = strip_model_self_claims(candidate)
    schema = schema or load_candidate_schema()
    now_iso = now_iso or datetime.now(timezone.utc).isoformat(timespec="seconds")
    errors = []
    warnings = []

    if "verification" not in cand or not isinstance(cand["verification"], dict):
        cand["verification"] = {}
    prior_warnings = [
        w for w in cand["verification"].get("warnings", [])
        if isinstance(w, str) and not w.startswith("unresolved_conflicts_count:") and not w.startswith("coverage_")
    ]
    warnings = list(prior_warnings)
    cand["verification"].setdefault("audit_findings", [])
    cand["verification"]["verifier_version"] = VERIFIER_VERSION
    cand["verification"]["checked_at"] = now_iso
    cand["verification"]["model_self_claim_ignored"] = True
    cand["verification"]["checks"] = {
        "schema_valid": True,
        "evidence_supported": True,
        "date_and_amount_units_valid": True,
        "no_year_or_branch_mixing": True,
        "negation_and_roles_valid": True,
        "no_unresolved_conflicts": True,
        "coverage_ok": True,
    }
    cand["verification"]["errors"] = []
    cand["verification"]["warnings"] = []

    # 1. Schema 驗證 (對單筆 candidate_record 子 Schema 驗證)
    record_schema = {
        "$schema": schema["$schema"],
        "$defs": schema["$defs"],
        "$ref": "#/$defs/candidate_record",
    }
    validator = Draft202012Validator(record_schema, format_checker=FormatChecker())
    schema_errors = [
        f"schema/{'/'.join(map(str, err.absolute_path)) or '<root>'}: {err.message}"
        for err in validator.iter_errors(cand)
    ]
    schema_valid = len(schema_errors) == 0
    errors.extend(schema_errors)

    # 2. 證據支持與防捏造檢查 (Evidence Support & Anti-Hallucination)
    ev_errors = []
    meta = cand.get("source_metadata", {})
    ev_mode = meta.get("evidence_mode", "short_excerpt")
    ctx_suff = meta.get("context_sufficiency", "in_memory_full_blocks")
    is_stub = ctx_suff in ("hash_only_without_memory", "short_excerpt_only", "robots_or_access_restricted")
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
                if evidence_digest(exc) != entry.get("excerpt_sha256"):
                    ev_errors.append(f"excerpt_sha256_mismatch:{entry.get('field_path')}")
                if CONTACT_RE.search(exc) or SKIP_RE.search(exc):
                    ev_errors.append(f"sensitive_or_contact_in_excerpt:{entry.get('field_path')}")

    block_map = {}
    block_hashes_by_loc = {}
    if in_memory_blocks is not None:
        for b in in_memory_blocks:
            loc = b["locator"]
            norm_t = normalized(b["text"])
            block_map[loc] = (block_map[loc] + " " + norm_t) if loc in block_map else norm_t
            block_hashes_by_loc.setdefault(loc, set()).add(evidence_digest(norm_t))
        for entry in field_ev:
            loc = entry.get("locator")
            if loc not in block_map:
                ev_errors.append(f"evidence_locator_not_in_source:{entry.get('field_path')}:{loc}")
                continue
            block_text = block_map[loc]
            valid_hashes = block_hashes_by_loc.get(loc, set())
            blk_sha = entry.get("source_block_sha256")
            if blk_sha and blk_sha not in valid_hashes and evidence_digest(block_text) != blk_sha:
                ev_errors.append(f"source_block_sha256_mismatch:{entry.get('field_path')}")
            if ev_mode == "short_excerpt" and entry.get("excerpt"):
                if normalized(entry["excerpt"]) not in block_text:
                    ev_errors.append(f"hallucinated_excerpt_not_in_block:{entry.get('field_path')}")
            elif ev_mode == "hash_only":
                sha = entry.get("excerpt_sha256")
                if sha not in valid_hashes and evidence_digest(block_text) != sha and not entry.get("_verified_in_memory_span"):
                    matched = any(
                        evidence_digest(part) == sha
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

    # R7：檢查所有非 unknown 欄位的 field_evidence 覆蓋率與原文數值支持
    if not is_stub:
        id_refs = elig.get("identity", {}).get("refs", [])
        is_extracted_identity = bool(id_refs and id_refs[0].get("locator") not in (None, "top"))
        if not ev_by_path.get("eligibility.identity"):
            if is_extracted_identity or not any(not k.startswith("raw_clue.") for k in ev_by_path):
                ev_errors.append("missing_evidence:eligibility.identity")

    if elig.get("nationality") not in (None, "unknown"):
        if "eligibility.nationality" not in ev_by_path:
            ev_errors.append("missing_evidence:eligibility.nationality")

    if elig.get("employment_status") not in (None, "unknown"):
        if "eligibility.employment_status" not in ev_by_path:
            ev_errors.append("missing_evidence:eligibility.employment_status")

    if elig.get("year_limit", {}).get("mode") not in (None, "unknown"):
        if "eligibility.year_limit" not in ev_by_path or not elig["year_limit"].get("refs"):
            ev_errors.append("missing_evidence:eligibility.year_limit")
        elif in_memory_blocks is not None:
            locs = [e["locator"] for e in ev_by_path["eligibility.year_limit"]]
            combined = " ".join(block_map.get(l, "") for l in locs)
            ymode = elig["year_limit"]["mode"]
            if ymode == "unlimited" and not any(k in combined for k in ("不限年級", "不分年級", "各年級")):
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
        if in_memory_blocks is not None:
            locs = [e["locator"] for e in matching_ev] if matching_ev else [r.get("locator") for r in b_item.get("refs", []) if r.get("locator")]
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

    app_start_field = cand.get("schedule", {}).get("application_start", {})
    if app_start_field.get("kind") in ("date", "datetime") and app_start_field.get("value"):
        matching_app_ev = ev_by_path.get("schedule.application_start") or []
        if matching_app_ev and in_memory_blocks is not None:
            locs = [e["locator"] for e in matching_app_ev]
            combined = " ".join(block_map.get(loc, "") for loc in locs)
            dtokens = _date_tokens(app_start_field["value"])
            if not any(tok in combined.replace(" ", "") for tok in dtokens):
                ev_errors.append(f"hallucinated_date_not_in_source:schedule.application_start:{app_start_field['value']}")

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

    pver = cand.get("policy_version", {})
    if any(pver.get(k) for k in ("promulgated_on", "amended_on", "effective_from")):
        if "policy_version" not in ev_by_path or not pver.get("refs"):
            ev_errors.append("missing_evidence:policy_version")

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

    acad_years = set(re.findall(r"(1\d{2})\s*學年度", combined_header))
    if len(acad_years) > 1:
        mix_errors.append(f"mixed_academic_years_in_single_record:{sorted(acad_years)}")

    if "教育部" in combined_header and "國科會" in combined_header and cand.get("category") == "phd_research":
        mix_errors.append("mixed_moe_and_nstc_phd_branches_in_single_record")

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
            if any(
                phrase in action_and_note
                for phrase in ("學院送件", "遞送推薦名單至研究生教務組", "學校負責人提出", "向國科會彙送", "備函檢送名冊", "會議開始日前兩個月")
            ) and "之前一日17:00" not in action_and_note:
                nr_errors.append(f"institution_or_college_deadline_misassigned_to_student:steps/{idx}")

    negation_and_roles_valid = len(nr_errors) == 0
    errors.extend(nr_errors)

    # 6. 缺漏／衝突檢查 (Conflicts)
    conflicts = cand.get("gaps_and_conflicts", {}).get("conflicts", [])
    no_unresolved_conflicts = len(conflicts) == 0
    if not no_unresolved_conflicts:
        warnings.append(f"unresolved_conflicts_count:{len(conflicts)}")

    # 7. R5：欄位涵蓋率與對照 pilot.json 退步檢查 (Coverage & Regression Check)
    coverage_warnings = []
    if not is_stub:
        if len(field_ev) < 2:
            coverage_warnings.append("coverage_gap:fewer_than_2_field_evidence_entries")
        if cand.get("resource_kind") in ("scholarship", "award") and len(benefit_items) == 0:
            coverage_warnings.append("coverage_gap:missing_structured_benefit_items")
        for mf in cand.get("gaps_and_conflicts", {}).get("missing_fields", []):
            if "unfetched_attachment" in mf:
                coverage_warnings.append(f"coverage_gap:{mf}")

        if pilot_by_id and cycle.get("kind") != "policy_snapshot":
            opp_id = cand.get("opportunity_id")
            pilot_opp = pilot_by_id.get(opp_id) if opp_id else None
            if pilot_opp:
                p_ymode = pilot_opp.get("eligibility", {}).get("year_limit", {}).get("mode", "unknown")
                c_ymode = elig.get("year_limit", {}).get("mode", "unknown")
                if p_ymode != "unknown" and c_ymode == "unknown":
                    coverage_warnings.append(f"coverage_regression:eligibility.year_limit.mode({p_ymode}->unknown)")

                p_cmode = pilot_opp.get("compatibility", {}).get("mode", "unknown")
                c_cmode = comp.get("mode", "unknown")
                if p_cmode != "unknown" and c_cmode == "unknown":
                    coverage_warnings.append(f"coverage_regression:compatibility.mode({p_cmode}->unknown)")

                p_dated_steps = [
                    (s.get("actor"), s.get("deadline", {}).get("value"))
                    for s in pilot_opp.get("steps", [])
                    if s.get("deadline", {}).get("value")
                ]
                c_dated_steps = [
                    (s.get("actor"), s.get("deadline", {}).get("value"))
                    for s in steps
                    if s.get("deadline", {}).get("value")
                ]
                if p_dated_steps and not c_dated_steps:
                    coverage_warnings.append(f"coverage_regression:schedule.steps_missing_dated_step({p_dated_steps})")

    coverage_ok = len(coverage_warnings) == 0
    warnings.extend(coverage_warnings)

    cand["verification"]["checks"] = {
        "schema_valid": schema_valid,
        "evidence_supported": evidence_supported,
        "date_and_amount_units_valid": date_and_amount_units_valid,
        "no_year_or_branch_mixing": no_year_or_branch_mixing,
        "negation_and_roles_valid": negation_and_roles_valid,
        "no_unresolved_conflicts": no_unresolved_conflicts,
        "coverage_ok": coverage_ok,
    }
    cand["verification"]["errors"] = errors
    cand["verification"]["warnings"] = warnings

    if is_stub and not errors:
        cand["verification"]["status"] = "needs_context"
    elif errors:
        cand["verification"]["status"] = "failed_automated_checks"
    elif not no_unresolved_conflicts:
        cand["verification"]["status"] = "conflict_detected"
    elif not coverage_ok:
        cand["verification"]["status"] = "passed_with_gaps"
    else:
        cand["verification"]["status"] = "passed_automated_checks"

    # 強制執行獨立覆核門檻：未通過檢核或無非原編輯者覆核，一律維持 pending 且 promotion_ready = False
    rev = cand.get("review", {})
    editor = rev.get("editor", "extractor")
    ind_rev = rev.get("independent_reviewer")
    rev_on = rev.get("reviewed_on")
    if (
        cand["verification"]["status"] in ("passed_automated_checks", "passed_with_gaps")
        and rev.get("status") == "reviewed"
        and ind_rev
        and ind_rev != editor
        and parse_iso_date(rev_on) is not None
    ):
        rev["promotion_ready"] = cand["verification"]["status"] == "passed_automated_checks"
    else:
        if rev.get("status") == "reviewed":
            if not ind_rev or ind_rev == editor:
                cand["verification"]["errors"].append("independent_reviewer_required_and_must_differ_from_editor")
                cand["verification"]["status"] = "failed_automated_checks"
            rev["status"] = "pending"
        rev["promotion_ready"] = False

    return cand


def verify_bundle(bundle, in_memory_blocks_by_source=None, pilot_data=None):
    """檢核整份 candidate bundle 並檢查根層 Schema。"""
    result = deepcopy(bundle)
    in_memory_blocks_by_source = in_memory_blocks_by_source or {}
    pilot_by_id = {}
    if pilot_data and isinstance(pilot_data.get("opportunities"), list):
        pilot_by_id = {opp["id"]: opp for opp in pilot_data["opportunities"]}

    verified_list = []
    for cand in result.get("candidates", []):
        sid = cand.get("source_metadata", {}).get("source_id")
        url = cand.get("source_metadata", {}).get("url")
        blocks = in_memory_blocks_by_source.get(url) or in_memory_blocks_by_source.get(sid)
        verified_list.append(verify_candidate(cand, in_memory_blocks=blocks, pilot_by_id=pilot_by_id))
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
    parser.add_argument("--pilot", type=Path, default=ROOT / "data/pilot.json")
    args = parser.parse_args()
    bundle = json.loads(args.path.read_text(encoding="utf-8"))
    pilot_data = json.loads(args.pilot.read_text(encoding="utf-8")) if args.pilot.exists() else None
    verified, bundle_errors = verify_bundle(bundle, pilot_data=pilot_data)
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
