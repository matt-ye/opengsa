"""候選覆核與差異比對流程 (Candidate Review & Diff Workflow v1.1)。

功能：
1. 串接「來源變更 → 結構化萃取（規則 + 可選模型）→ 獨立檢核（7項指標含 coverage_ok）→ 申請時間與 P1 資格試算 → 與 data/pilot.json 差異比對 → 人工處置狀態」。
2. 區分「法規快照 (policy_snapshot)」與「年度／梯次申請公告 (academic_year / calendar_year / event_relative)」，避免將設置辦法 PDF 誤與當期申請步驟比對產生假差異 (R3)。
3. 輸出易讀之 Markdown 覆核報告、JSON 差異表與 model-usage.json。
4. 嚴格保護正式資料：禁止爬蟲或模型直接覆寫 data/pilot.json，未完成非原編輯者獨立覆核與檢核通過者一律維持 pending。
"""
import argparse
from copy import deepcopy
import html
import json
import hashlib
from datetime import datetime, timezone, timedelta
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.check_data import validate as validate_pilot_data
from scripts.evaluate_deadlines import evaluate_application_window, evaluate_eligibility, make_p1_profile, taipei_today, parse_iso_date
from scripts.extract_candidates import refetch_and_extract_candidates
from scripts.verify_candidates import verify_bundle
from jsonschema import Draft202012Validator, FormatChecker


def validate_review_ledger(payload):
    schema = json.loads((ROOT / "schema/scan-reviews.schema.json").read_text(encoding="utf-8"))
    errors = list(Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(payload))
    keys = [(r.get("revision_id"), r.get("candidate_id")) for r in payload.get("reviews", [])]
    if errors or len(keys) != len(set(keys)):
        raise ValueError("Invalid review ledger: " + (errors[0].message if errors else "duplicate disposition"))
    if any(r["reviewed_on"] > taipei_today() for r in payload["reviews"]):
        raise ValueError("Review date cannot be in the future")
    if any(not r["reviewer"].strip() or not r["reason"].strip() for r in payload["reviews"]):
        raise ValueError("Reviewer and reason cannot be blank")


def candidate_fingerprint(candidate):
    """Bind approval to the actual claims; exclude changing evaluation timestamps."""
    fields = {k: candidate.get(k) for k in ("candidate_id", "title", "category", "resource_kind", "scope", "institution_scope", "evidence_status", "program_key", "cycle", "source_metadata", "participants", "organizations", "eligibility", "benefit", "compatibility", "hardship", "schedule", "policy_version", "field_evidence", "application_method", "field_applicability", "expense_period", "gaps_and_conflicts")}
    fields["editor"] = candidate.get("review", {}).get("editor")
    fields["opportunity_id"] = candidate.get("opportunity_id")
    return hashlib.sha256(json.dumps(fields, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def _escape_md(value):
    return (
        html.escape(str(value if value is not None else "—"))
        .replace("|", "&#124;")
        .replace("`", "&#96;")
        .replace("[", "&#91;")
        .replace("]", "&#93;")
        .replace("\n", " ")
    )


def compute_candidate_diff(candidate, pilot_data):
    """比對單筆結構化候選與 data/pilot.json 現有機會或法規版本之差異，絕不修改 pilot_data。
    若 cycle.kind == 'policy_snapshot'（如設置辦法 PDF），與法規基準比對，不與當期申請機會比對 steps / application.state (R3)。
    """
    cycle_kind = candidate.get("cycle", {}).get("kind")
    prog_key = candidate.get("program_key")

    if cycle_kind == "policy_snapshot":
        # 尋找對應 program_key 之既有學習／法規設定做條文層級比對，不比對當期申請狀態與梯次截止日
        matching_opps = [o for o in pilot_data.get("opportunities", []) if o.get("program_key") == prog_key]
        diffs = []
        if matching_opps:
            ref_opp = matching_opps[0]
            for field in ("application_method","field_applicability","expense_period"):
                if candidate.get(field) and candidate[field] != ref_opp.get(field):
                    diffs.append({"field":field,"pilot_value":ref_opp.get(field),"candidate_value":candidate[field]})
            for field_path, old_val, new_val in [
                ("compatibility.mode", ref_opp.get("compatibility", {}).get("mode"), candidate.get("compatibility", {}).get("mode")),
            ]:
                if old_val != new_val and new_val not in (None, "unknown"):
                    diffs.append({"field": field_path, "pilot_value": old_val, "candidate_value": new_val})
        return {
            "diff_status": "policy_regulation_snapshot",
            "matched_opportunity_id": f"policy:{prog_key}",
            "field_diffs": diffs,
        }

    opp_by_id = {item["id"]: item for item in pilot_data.get("opportunities", [])}
    opp_by_prog_cycle = {
        (item["program_key"], item["cycle"]["label"]): item
        for item in pilot_data.get("opportunities", [])
    }

    opp_id = candidate.get("opportunity_id")
    matched = opp_by_id.get(opp_id) if opp_id else None
    if matched is None:
        matched = opp_by_prog_cycle.get((prog_key, candidate.get("cycle", {}).get("label")))

    if matched is None:
        return {
            "diff_status": "new_candidate_not_in_pilot",
            "matched_opportunity_id": None,
            "field_diffs": [],
        }

    diffs = []
    comparisons = [
        ("title", matched.get("title"), candidate.get("title")),
        ("cycle.label", matched.get("cycle", {}).get("label"), candidate.get("cycle", {}).get("label")),
        ("participants.applicant", matched.get("participants", {}).get("applicant"), candidate.get("participants", {}).get("applicant")),
        (
            "eligibility.year_limit.mode",
            matched.get("eligibility", {}).get("year_limit", {}).get("mode"),
            candidate.get("eligibility", {}).get("year_limit", {}).get("mode"),
        ),
        (
            "eligibility.candidate.mode",
            matched.get("eligibility", {}).get("candidate", {}).get("mode"),
            candidate.get("eligibility", {}).get("candidate", {}).get("mode"),
        ),
        ("compatibility.mode", matched.get("compatibility", {}).get("mode"), candidate.get("compatibility", {}).get("mode")),
        ("hardship.mode", matched.get("hardship", {}).get("mode"), candidate.get("hardship", {}).get("mode")),
        ("application.state", matched.get("application", {}).get("state"), candidate.get("application", {}).get("state")),
    ]
    for field_path, old_val, new_val in comparisons:
        if old_val != new_val:
            diffs.append({"field": field_path, "pilot_value": old_val, "candidate_value": new_val})
    for field in ("application_method","field_applicability","expense_period"):
        if matched.get(field) != candidate.get(field):
            diffs.append({"field":field,"pilot_value":matched.get(field),"candidate_value":candidate.get(field)})

    old_steps = [
        (s["actor"], s["deadline"]["kind"], s["deadline"]["value"])
        for s in matched.get("steps", [])
    ]
    new_steps = [
        (s["actor"], s["deadline"]["kind"], s["deadline"]["value"])
        for s in candidate.get("schedule", {}).get("steps", [])
        if s["actor"] != "supplement"
    ]
    if old_steps != new_steps:
        diffs.append({"field": "schedule.steps", "pilot_value": old_steps, "candidate_value": new_steps})

    return {
        "diff_status": "modified_fields" if diffs else "aligned_with_pilot",
        "matched_opportunity_id": matched["id"],
        "field_diffs": diffs,
    }


def apply_review_ledger(candidate, reviews_by_revision):
    """套用 data/scan-reviews.json 人工處置紀錄與獨立覆核檢查，回傳更新後之候選副本。"""
    cand = deepcopy(candidate)
    # A candidate file cannot confer its own human approval; the ledger is authoritative.
    cand["review"].update(status="pending",promotion_ready=False,independent_reviewer=None,reviewed_on=None,ledger_action="unreviewed")
    cand["review"].pop("approved_candidate_sha256",None)
    rev_id = cand.get("source_metadata", {}).get("revision_id")
    entries = reviews_by_revision.get(rev_id, [])
    if isinstance(entries, dict):
        entries = [entries]
    ledger_entry = next((r for r in entries if r.get("source_id") == cand.get("source_metadata", {}).get("source_id") and r.get("candidate_id") in (None, cand.get("candidate_id"))), None)
    if not ledger_entry:
        return cand

    action = ledger_entry.get("action", "unreviewed")
    reviewer = ledger_entry.get("reviewer")
    reviewed_on = ledger_entry.get("reviewed_on")
    cand["review"]["ledger_action"] = action

    if action == "dismissed":
        cand["review"]["status"] = "dismissed"
        cand["review"]["independent_reviewer"] = reviewer
        cand["review"]["reviewed_on"] = reviewed_on
        cand["review"]["promotion_ready"] = False
    elif action == "applied":
        editor = cand["review"].get("editor", "extractor")
        ver_status = cand.get("verification", {}).get("status")
        if (
            reviewer
            and reviewer.strip().casefold() != editor.strip().casefold()
            and ver_status == "passed_automated_checks"
            and parse_iso_date(reviewed_on) is not None and reviewed_on <= taipei_today()
            and ledger_entry.get("candidate_id") == cand.get("candidate_id")
            and ledger_entry.get("candidate_sha256") == candidate_fingerprint(cand)
        ):
            cand["review"]["status"] = "reviewed"
            cand["review"]["independent_reviewer"] = reviewer
            cand["review"]["reviewed_on"] = reviewed_on
            cand["review"]["promotion_ready"] = True
            cand["review"]["approved_candidate_sha256"] = ledger_entry["candidate_sha256"]
        else:
            cand["review"]["status"] = "pending"
            cand["review"]["independent_reviewer"] = reviewer
            cand["review"]["reviewed_on"] = reviewed_on
            cand["review"]["promotion_ready"] = False
    elif action == "noted":
        cand["review"]["status"] = "pending"
        cand["review"]["independent_reviewer"] = reviewer
        cand["review"]["reviewed_on"] = reviewed_on
        cand["review"]["promotion_ready"] = False

    return cand


def build_review_report(
    candidate_bundle,
    pilot_data,
    scan_report=None,
    reviews_data=None,
    refetch_statuses=None,
    in_memory_blocks_by_source=None,
):
    """整合來源變更、萃取、檢核、申請時間與人工覆核差異，產生結構化報告與 Markdown。"""
    reviews_list = (reviews_data or {}).get("reviews", [])
    if reviews_data is not None:
        validate_review_ledger(reviews_data)
    reviews_by_rev = {}
    for entry in reviews_list:
        reviews_by_rev.setdefault(entry["revision_id"], []).append(entry)
    refetch_statuses = refetch_statuses or {}
    as_of = candidate_bundle.get("as_of", "2026-10-29")
    p1_profile = make_p1_profile()

    verified_bundle, bundle_errors = verify_bundle(candidate_bundle, in_memory_blocks_by_source=in_memory_blocks_by_source, pilot_data=pilot_data)
    enriched_candidates = []
    review_rows = []

    for cand in verified_bundle.get("candidates", []):
        cand = apply_review_ledger(cand, reviews_by_rev)
        if bundle_errors:
            cand["review"].update(status="pending",promotion_ready=False)
        window = evaluate_application_window(cand, as_of)
        p1_eval = evaluate_eligibility(cand, p1_profile, as_of=as_of)
        diff = compute_candidate_diff(cand, pilot_data)

        enriched_candidates.append(cand)
        review_rows.append(
            {
                "candidate_id": cand["candidate_id"],
                "opportunity_id": cand.get("opportunity_id"),
                "program_key": cand["program_key"],
                "title": cand["title"],
                "cycle": cand["cycle"],
                "source_metadata": cand["source_metadata"],
                "refetch_status": refetch_statuses.get(cand["source_metadata"]["url"], "in_memory"),
                "verification": cand["verification"],
                "application_window": {
                    "state": window["state"],
                    "reason_code": window["reason_code"],
                    "student_deadline": window["student_deadline"],
                    "upper_layer_deadlines": window["upper_layer_deadlines"],
                },
                "p1_eligibility": {
                    "criteria": p1_eval["criteria"],
                    "missing_information": p1_eval["missing_information"],
                    "official_qualification_approved": False,
                },
                "diff_against_pilot": diff,
                "review": cand["review"],
            }
        )

    verified_bundle["candidates"] = enriched_candidates
    model_usage = verified_bundle.get(
        "model_usage",
        {
            "adapter_kind": "deterministic_rule",
            "mode": "off",
            "enabled": bool(verified_bundle.get("model_enabled", False)),
            "calls": verified_bundle.get("model_calls", 0),
            "hash_only_bytes_sent": 0,
        },
    )
    summary = {
        "as_of": as_of,
        "total_candidates": len(enriched_candidates),
        "passed_automated_checks": sum(1 for c in enriched_candidates if c["verification"]["status"] == "passed_automated_checks"),
        "passed_with_gaps": sum(1 for c in enriched_candidates if c["verification"]["status"] == "passed_with_gaps"),
        "failed_automated_checks": sum(1 for c in enriched_candidates if c["verification"]["status"] == "failed_automated_checks"),
        "needs_context": sum(1 for c in enriched_candidates if c["verification"]["status"] == "needs_context"),
        "conflict_detected": sum(1 for c in enriched_candidates if c["verification"]["status"] == "conflict_detected"),
        "promotion_ready": sum(1 for c in enriched_candidates if c["review"]["promotion_ready"]),
        "model_calls": verified_bundle.get("model_calls", 0),
        "model_usage": model_usage,
        "official_data_modified": False,
        "bundle_schema_errors": bundle_errors,
        "rows": review_rows,
    }
    md = render_review_markdown(summary, verified_bundle, scan_report)
    return verified_bundle, summary, md


def render_review_markdown(summary, verified_bundle, scan_report=None):
    """產生區分『來源變更、萃取結果、檢核與時間判斷、與正式資料差異及人工處置』四層之 Markdown 覆核報告。"""
    m_usage = summary.get("model_usage") or {}
    lines = [
        "# OpenGSA 候選結構化萃取、獨立檢核與差異覆核報告",
        "",
        "> **重要聲明**：本報告為自動化萃取與獨立檢核之待覆核候選結果，**不會自動覆寫 `data/pilot.json`，亦不代表官方資格已核定**。",
        "> 教務處等 `hash_only` 來源僅輸出雜湊與區塊定位，零原文摘錄外流，且未將受限原文送往任何外部模型 (`hash_only_bytes_sent = 0`)。",
        "",
        (
            f"- 評估基準日 (`Asia/Taipei`)：`{summary['as_of']}`｜"
            f"候選筆數：`{summary['total_candidates']}`｜"
            f"完整通過 (`passed_automated_checks`)：`{summary['passed_automated_checks']}`｜"
            f"結構通過但待補欄位 (`passed_with_gaps`)：`{summary.get('passed_with_gaps', 0)}`｜"
            f"待補上下文：`{summary['needs_context']}`｜"
            f"檢核攔截／衝突：`{summary['failed_automated_checks'] + summary['conflict_detected']}`｜"
            f"可轉資料 PR (`promotion_ready`)：`{summary['promotion_ready']}`｜"
            f"模型模式：`{m_usage.get('mode', 'off')}`（呼叫 `{summary['model_calls']}` 次，`hash_only` 外送 `{m_usage.get('hash_only_bytes_sent', 0)}` bytes）｜"
            f"正式資料已修改：`{summary['official_data_modified']}`"
        ),
        "",
        "## 一、來源變更與記憶體上下文狀態（Source Changes）",
        "",
        "| 來源 ID | 類型／URL | 掃描狀態 | 證據模式 | 上下文取得方式 | 語義雜湊前12碼 |",
        "|---|---|---|---|---|---|",
    ]
    seen_urls = set()
    docs_by_url = {d.get("url"): d for d in (scan_report or {}).get("documents", [])}
    for row in summary["rows"]:
        meta = row["source_metadata"]
        url = meta["url"]
        if url in seen_urls:
            continue
        seen_urls.add(url)
        doc_info = docs_by_url.get(url, {})
        scan_st = doc_info.get("status", "observed")
        lines.append(
            f"| {_escape_md(meta['source_id'])} | {_escape_md(url)} | {_escape_md(scan_st)} | "
            f"`{_escape_md(meta['evidence_mode'])}` | `{_escape_md(meta['context_sufficiency'])}` | "
            f"`{_escape_md(meta['revision_id'][:12])}` |"
        )

    lines.extend(
        [
            "",
            "## 二、結構化萃取結果（Structured Extraction）",
            "",
            "| 候選 ID | 制度／分支／年度 | 申請／受益角色 | 年級／候選人／否定條件 | 金額與單位 | 證據筆數（摘錄合規） |",
            "|---|---|---|---|---|---|",
        ]
    )
    cand_by_id = {c["candidate_id"]: c for c in verified_bundle.get("candidates", [])}
    for row in summary["rows"]:
        cand = cand_by_id[row["candidate_id"]]
        cyc = cand["cycle"]
        branch_str = f"{cand['program_key']} / {cyc.get('label')} ({cyc.get('branch') or '主分支'})"
        part = cand["participants"]
        role_str = f"申請:{part['applicant']} → 受益:{part['beneficiary']}"
        elig = cand["eligibility"]
        ymode = elig["year_limit"]["mode"]
        if ymode == "range":
            ymode = f"range({elig['year_limit']['min']}-{elig['year_limit']['max']})"
        cmode = elig["candidate"]["mode"]
        neg_cnt = len(elig["negated_conditions"])
        cond_str = f"年級:{ymode} / 候選人:{cmode} / 否定條件:{neg_cnt}項"
        b_items = cand["benefit"]["items"]
        if b_items:
            b0 = b_items[0]
            amt_str = f"{b0['amount_min']}~{b0['amount_max']} {b0['currency']} ({b0['unit']})"
        else:
            amt_str = cand["benefit"]["summary"][:28]
        ev_cnt = len(cand["field_evidence"])
        agreed_cnt = sum(1 for e in cand["field_evidence"] if e.get("rule_and_model_agreed") is True)
        has_non_null_excerpt = any(e.get("excerpt") is not None for e in cand["field_evidence"])
        ev_note = f"{ev_cnt} 筆（hash_only 零原文）" if cand["source_metadata"]["evidence_mode"] == "hash_only" and not has_non_null_excerpt else f"{ev_cnt} 筆（短摘錄，雙軌一致:{agreed_cnt}）"
        lines.append(
            f"| `{_escape_md(cand['candidate_id'])}` | {_escape_md(branch_str)} | {_escape_md(role_str)} | "
            f"{_escape_md(cond_str)} | {_escape_md(amt_str)} | {_escape_md(ev_note)} |"
        )

    lines.extend(["", "### 申辦途徑與欄位適用性", "", "| 候選 | 方式／紙本／親簽 | 截止判準 | N/A欄位與理由 |", "|---|---|---|---|"])
    for cand in verified_bundle.get("candidates",[]):
        method=cand.get("application_method",{})
        na="；".join(k+":"+v["reason"] for k,v in cand.get("field_applicability",{}).items() if v["status"]=="not_applicable") or "未記錄不適用；未知不自動轉N/A"
        text=" / ".join(method.get(k,"unknown") for k in ("mode","paper_delivery","handwritten_signature"))
        lines.append(f"| {_escape_md(cand['candidate_id'])} | {_escape_md(text)} | {_escape_md(method.get('deadline_basis','unknown'))} | {_escape_md(na)} |")
    lines.extend(
        [
            "",
            "## 三、獨立檢核與申請時間／P1資格判斷（Verification & Window）",
            "",
            "| 候選 ID | 自動檢核狀態 | 檢核錯誤／警告 | 學生受理狀態 | 學生截止 vs 院校／機關期限 | P1（博五候選人）比對 |",
            "|---|---|---|---|---|---|",
        ]
    )
    for row in summary["rows"]:
        ver = row["verification"]
        win = row["application_window"]
        p1 = row["p1_eligibility"]
        err_str = "; ".join(ver["errors"] + ver["warnings"]) or "無"
        upper_str = ", ".join(f"{u['actor']}:{u['value'] or u['kind']}" for u in win["upper_layer_deadlines"]) or "無"
        dl_compare = f"學生:{win['student_deadline'] or 'unknown'} ｜ 上層:{upper_str}"
        lines.append(
            f"| `{_escape_md(row['candidate_id'])}` | `{_escape_md(ver['status'])}` | {_escape_md(err_str)} | "
            f"`{_escape_md(win['state'])}` (`{_escape_md(win['reason_code'])}`) | {_escape_md(dl_compare)} | "
            f"`{_escape_md(p1['criteria'])}` |"
        )

    lines.extend(
        [
            "",
            "## 四、與 `data/pilot.json` 差異及人工覆核處置（Diff & Review Ledger）",
            "",
            "| 候選 ID | 對應正式草稿 ID | 差異狀態 | 變更欄位摘要 | 人工處置 (`scan-reviews.json`) | 覆核狀態 (`promotion_ready`) |",
            "|---|---|---|---|---|---|",
        ]
    )
    for row in summary["rows"]:
        diff = row["diff_against_pilot"]
        rev = row["review"]
        f_diffs = ", ".join(f"{d['field']}: {d['pilot_value']} -> {d['candidate_value']}" for d in diff["field_diffs"]) or "無欄位差異"
        lines.append(
            f"| `{_escape_md(row['candidate_id'])}` | `{_escape_md(diff['matched_opportunity_id'] or '新增候選')}` | "
            f"`{_escape_md(diff['diff_status'])}` | {_escape_md(f_diffs)} | "
            f"`{_escape_md(rev['ledger_action'])}` | `{_escape_md(rev['status'])}` (`{rev['promotion_ready']}`) |"
        )

    return "\n".join(lines) + "\n"


def candidate_to_pilot_opportunity(cand):
    """將已通過檢核與獨立覆核之候選轉換為 schema/pilot.schema.json 相容之 opportunity 結構。"""
    elig = cand["eligibility"]
    steps = [
        {
            "actor": s["actor"],
            "action": s["action"],
            "deadline": deepcopy(s["deadline"]),
            "refs": deepcopy(s["refs"]),
            **({"application_method":deepcopy(s["application_method"])} if "application_method" in s else {}),
        }
        for s in cand["schedule"]["steps"]
    ]
    opp = {
        "id": cand["opportunity_id"] or cand["candidate_id"],
        "program_key": cand["program_key"],
        "title": cand["title"],
        "category": cand["category"],
        "resource_kind": cand["resource_kind"],
        "scope": cand["scope"],
        "institution_scope": deepcopy(cand.get("institution_scope", {})),
        "cycle": {
            "kind": cand["cycle"]["kind"],
            "label": cand["cycle"]["label"],
        },
        "participants": deepcopy(cand["participants"]),
        "organizations": deepcopy(cand["organizations"]),
        "eligibility": {
            "degrees": deepcopy(elig["degrees"]),
            "institution": elig["institution"],
            "identity": deepcopy(elig["identity"]),
            "year_limit": deepcopy(elig["year_limit"]),
            "candidate": deepcopy(elig["candidate"]),
            **{key: deepcopy(elig[key]) for key in ("nationality", "employment_status", "negated_conditions", "graduation_requirement", "prior_funding_rule")},
            "other_conditions": deepcopy(elig["other_conditions"]),
        },
        "compatibility": deepcopy(cand["compatibility"]),
        "hardship": deepcopy(cand["hardship"]),
        "benefit": {
            "text": cand["benefit"]["summary"],
            "items": deepcopy(cand["benefit"]["items"]),
            "refs": deepcopy(cand["benefit"]["refs"]),
        },
        **{k:deepcopy(cand[k]) for k in ("application_method","field_applicability","expense_period") if k in cand},
        "start": deepcopy(cand["schedule"]["application_start"]) if cand.get("schedule", {}).get("application_start") else None,
        "result": deepcopy(cand["schedule"]["result_date"]) if cand.get("schedule", {}).get("result_date") else None,
        "steps": steps,
        "application": deepcopy(cand["application"]),
        "evidence_status": cand["evidence_status"],
        "review": {
            "status": "reviewed" if cand["review"]["status"] == "reviewed" else "draft",
            "editor": cand["review"]["editor"],
            "independent_reviewer": cand["review"]["independent_reviewer"],
            "reviewed_on": cand["review"]["reviewed_on"],
        },
        "open_questions": deepcopy(cand["gaps_and_conflicts"]["open_questions"]),
        "policy_version": deepcopy(cand["policy_version"]),
        "field_evidence": deepcopy(cand["field_evidence"]),
    }
    if opp.get("start") is None or opp["start"].get("kind") == "unknown" and not opp["start"].get("value"):
        opp.pop("start", None)
    elif opp.get("start"):
        opp["start"]["refs"] = [{"source":e["source"],"locator":e["locator"]} for e in cand["field_evidence"] if e["field_path"] == "schedule.application_start"]
    if opp.get("result") is None or opp["result"].get("kind") == "unknown" and not opp["result"].get("value"):
        opp.pop("result", None)
    return opp


def export_pr_candidate_draft(verified_bundle, pilot_data, output_path, scan_sources_config=None):
    """僅將 promotion_ready == True（通過獨立檢核且經非編輯者人工覆核）之候選項目匯出至 PR 暫存檔。
    嚴禁覆寫 data/pilot.json！
    """
    output_path = Path(output_path)
    official_pilot_path = (ROOT / "data/pilot.json").resolve()
    if output_path.resolve() == official_pilot_path:
        raise ValueError("Refusing to overwrite official data/pilot.json directly; export to a PR staging path instead.")

    draft_pilot = deepcopy(pilot_data)
    opp_index = {item["id"]: idx for idx, item in enumerate(draft_pilot["opportunities"])}
    scan_by_id = {}
    if scan_sources_config and "sources" in scan_sources_config:
        scan_by_id = {s["id"]: s for s in scan_sources_config["sources"]}
    elif (ROOT / "data/scan-sources.json").exists():
        try:
            cfg = json.loads((ROOT / "data/scan-sources.json").read_text(encoding="utf-8"))
            scan_by_id = {s["id"]: s for s in cfg.get("sources", [])}
        except Exception:
            pass

    ready = [c for c in verified_bundle.get("candidates", []) if c.get("review", {}).get("promotion_ready")]
    targets = [c.get("opportunity_id") or c["candidate_id"] for c in ready]
    if len(targets) != len(set(targets)):
        raise ValueError("Same opportunity has multiple document candidates; reconcile evidence before export")
    promoted_ids = []

    for cand in verified_bundle.get("candidates", []):
        if not cand.get("review", {}).get("promotion_ready"):
            continue
        if cand.get("verification", {}).get("status") != "passed_automated_checks":
            continue
        if cand.get("review", {}).get("status") != "reviewed":
            continue
        if not cand["review"].get("independent_reviewer") or cand["review"]["independent_reviewer"] == cand["review"]["editor"]:
            continue
        if cand["review"].get("approved_candidate_sha256") != candidate_fingerprint(cand):
            continue

        opp = candidate_to_pilot_opportunity(cand)
        if opp["application"]["as_of"] != draft_pilot["as_of"]:
            raise ValueError("Snapshot dates differ; explicitly refresh the dataset and application states before export")

        # 同步登錄來源台帳至草稿 sources，維持 pilot.schema.json 與 check_data 資料契約完整性
        src_id = cand.get("source_metadata", {}).get("source_id")
        if src_id and not any(s["id"] == src_id for s in draft_pilot.get("sources", [])):
            scan_src = scan_by_id.get(src_id, {})
            draft_pilot["sources"].append({
                "id": src_id,
                "title": scan_src.get("title", cand.get("title")),
                "url": cand.get("source_metadata", {}).get("url"),
                "authority": "official_page",
                "access": "public",
                "checked_on": datetime.fromisoformat(cand["source_metadata"]["observed_at"]).astimezone(timezone(timedelta(hours=8))).date().isoformat(),
                "locator": "候選來源觀察記錄",
                "owner": None,
                "ownership_status": "unassigned",
                "proposed_review_frequency": "每週二/五低頻掃描；人工獨立覆核",
                "automation": "not_enabled",
                "crawl_permission": "not_reviewed",
                "next_action": "獨立覆核後納入公開候選台帳",
                "redistribution": "link_and_original_summary_only",
            })

        if opp["id"] in opp_index:
            draft_pilot["opportunities"][opp_index[opp["id"]]] = opp
        else:
            draft_pilot["opportunities"].append(opp)
        promoted_ids.append(opp["id"])

    validation_errors = validate_pilot_data(draft_pilot)
    if validation_errors:
        raise ValueError(f"Promoted PR draft failed pilot.schema.json validation: {validation_errors}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(draft_pilot, ensure_ascii=False, indent=2), encoding="utf-8")
    return promoted_ids


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "data/scan-sources.json")
    parser.add_argument("--candidates", type=Path, default=ROOT / "work/scanner/report/candidates.json")
    parser.add_argument("--pilot", type=Path, default=ROOT / "data/pilot.json")
    parser.add_argument("--reviews", type=Path, default=ROOT / "data/scan-reviews.json")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "work/scanner/report")
    parser.add_argument("--as-of", default=taipei_today())
    parser.add_argument("--no-refetch", action="store_true")
    parser.add_argument("--export-pr-draft", type=Path, default=None, help="Path to export promoted PR draft")
    args = parser.parse_args()

    config = json.loads(args.config.read_text(encoding="utf-8"))
    pilot_data = json.loads(args.pilot.read_text(encoding="utf-8"))
    reviews_data = json.loads(args.reviews.read_text(encoding="utf-8")) if args.reviews.exists() else {"reviews": []}
    raw_input = json.loads(args.candidates.read_text(encoding="utf-8")) if args.candidates.exists() else []

    from scripts.scan_sources import Fetcher
    fetcher = Fetcher(config)
    if isinstance(raw_input, dict) and "candidates" in raw_input and (not raw_input["candidates"] or "candidate_id" in raw_input["candidates"][0]):
        bundle = raw_input
        refetch_statuses = {c.get("source_metadata", {}).get("url"): "in_memory" for c in bundle.get("candidates", [])}
    else:
        pending = raw_input if isinstance(raw_input, list) else (raw_input.get("pending") or [])
        bundle, refetch_statuses = refetch_and_extract_candidates(
            pending,
            config,
            fetcher=fetcher,
            as_of=args.as_of,
            allow_network_refetch=not args.no_refetch,
        )
    verified_bundle, summary, md = build_review_report(
        bundle,
        pilot_data,
        reviews_data=reviews_data,
        refetch_statuses=refetch_statuses,
        in_memory_blocks_by_source=fetcher.in_memory_blocks,
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "structured-candidates.json").write_text(
        json.dumps(verified_bundle, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (args.output_dir / "review-diff.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (args.output_dir / "model-usage.json").write_text(
        json.dumps(summary.get("model_usage", {}), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (args.output_dir / "review-summary.md").write_text(md, encoding="utf-8")
    if args.export_pr_draft and summary["promotion_ready"] > 0:
        promoted = export_pr_candidate_draft(
            verified_bundle,
            pilot_data,
            args.export_pr_draft,
            scan_sources_config=config,
        )
        print(f"Exported {len(promoted)} promoted opportunities to {args.export_pr_draft}: {promoted}")

    print(
        json.dumps(
            {
                "total_candidates": summary["total_candidates"],
                "passed_automated_checks": summary["passed_automated_checks"],
                "passed_with_gaps": summary["passed_with_gaps"],
                "needs_context": summary["needs_context"],
                "promotion_ready": summary["promotion_ready"],
                "model_calls": summary["model_calls"],
                "official_data_modified": summary["official_data_modified"],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
