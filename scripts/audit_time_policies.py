"""Offline per-item temporal audit with 3-track and incremental diff status; does not fetch sources or assert approval."""
from collections import Counter
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.radar_metadata import radar_metadata
from scripts.source_chains import timeline_metadata
from scripts.time_policy import validate_temporal_snapshot
from scripts.review_candidates import candidate_fingerprint
from scripts.temporal_tracks import classify_source_track, evaluate_incremental_diff, parser_fingerprint


def audit():
    read = lambda path: json.loads((ROOT / path).read_text(encoding="utf-8"))
    bundle = read("data/candidates/source-review.json")
    observations = read("data/temporal-observations.json")
    errors = validate_temporal_snapshot(bundle, observations)
    if errors:
        raise ValueError(errors)
    radar = radar_metadata(bundle, observations)["records"]
    chain = timeline_metadata(read("data/source-chains.json"), bundle)
    rows = []
    current_parser = parser_fingerprint()
    for candidate in bundle["candidates"]:
        cid = candidate["candidate_id"]
        record = observations["records"].get(cid, {})
        if record.get("candidate_sha256") != candidate_fingerprint(candidate):
            record = {"url": candidate["source_metadata"]["url"], "status": "not_replayed", "reason": "new_or_changed_candidate"}
        meta = radar[cid]
        policy = meta["time_policy"]
        contexts = chain["records"].get(cid, {}).get("contexts", [])
        dated = meta.get("time_dates", {})
        examples = sorted({c["scope_label"] for c in contexts if c["scope"] != "general"})
        absolute = [{"actor": r["actor"], "stage": r["stage"], "value": r["value"]} for r in policy["rules"] if r["kind"] == "absolute"]
        ambiguous = "multiple_cycles_need_split" in policy["gaps"]
        form = (
            "跨年度規則卡；分年核對後才畫座標"
            if ambiguous
            else "年度上限／個人條件標記"
            if policy["submission_mode"] == "conditional_deadline"
            else "學生固定申請長條"
            if all(k in dated for k in ("start", "end"))
            else "單一學生截止標記＋準備建議（非起日）"
            if "end" in dated
            else "單位／行政時點標記；不代填學生期限"
            if absolute
            else "制度參考卡，不畫申請長條"
            if policy["submission_mode"] == "reference"
            else "時間規則卡，不虛構日曆座標"
            if policy["rules"]
            else "待補原因與來源入口，不畫假區間"
        )
        if examples:
            form += "；另有具名單位範例／參考層"
        track = classify_source_track(candidate)
        diff_info = evaluate_incremental_diff(candidate, observations=observations, current_parser_sha256=current_parser)
        rows.append({
            "candidate_id": cid,
            "title": candidate["title"],
            "source_id": candidate["source_metadata"]["source_id"],
            "schedule_track": track,
            "incremental_decision": diff_info["decision"],
            "url": record["url"],
            "latest_replay_status": record["status"],
            "reason": record.get("reason"),
            "submission_mode": policy["submission_mode"],
            "gantt_form": form,
            "dates": dated,
            "absolute_rules": absolute,
            "gaps": policy["gaps"],
            "example_scopes": examples,
            "attachment_urls": [d["url"] for d in record.get("documents", [])],
            "next_step": (
                "保留當期來源連結；按規則及個人條件核對"
                if policy["submission_mode"] not in ("undetermined", "mixed")
                else "先分年度／梯次並核對收件角色"
                if ambiguous
                else "續查附件／當期公告／適用單位；不補猜日期"
            ),
        })
    return {
        "version": "temporal-item-audit-1",
        "as_of": max(r["observed_at"][:10] for r in observations["records"].values()),
        "candidate_as_of": bundle["as_of"],
        "items": len(rows),
        "http_requests": observations["http_requests"],
        "model_calls": 0,
        "human_approvals": 0,
        "published": False,
        "tracks": dict(Counter(r["schedule_track"] for r in rows)),
        "incremental_decisions": dict(Counter(r["incremental_decision"] for r in rows)),
        "modes": dict(Counter(r["submission_mode"] for r in rows)),
        "latest_statuses": dict(Counter(r["latest_replay_status"] for r in rows)),
        "records": rows,
    }


if __name__ == "__main__":
    report = audit()
    target = ROOT / "docs/audits/temporal-reextraction-2026-11-03.json"
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# 時間重萃逐項檢核（含增量比對決策）",
        "",
        "離線投影檢查，不代表獨立人工核准；原文未存檔，模型0。",
        "既有單位範例仍有自己的年度／版本／適用範圍，不因本輪主頁觀察而回填學生資格或受理狀態。",
        "",
        "| # | 軌道 | 增量狀態 | 來源／項目 | 時間類別 | 甘特形式 | 後續 |",
        "|---|---|---|---|---|---|---|",
    ]
    for i, r in enumerate(report["records"], 1):
        reason = "；" + r["reason"] if r["reason"] else ""
        lines.append(
            f"| {i} | `{r['schedule_track']}` | `{r['incremental_decision']}` | [{r['source_id']}：{r['title']}]({r['url']}) | {r['submission_mode']} | {r['gantt_form']} | {r['next_step']}{reason} |"
        )
    (target.with_suffix(".md")).write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "records"}, ensure_ascii=False))
