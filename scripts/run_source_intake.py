"""處理一筆已核可的提交：只跑該來源，不等排程輪轉，也不佔待審佇列。

輸出只留在 --output（提案、預覽、留言）。不寫正式資料、不呼叫模型；資料 PR 由 open_data_pr.py 另外開，上架仍須人工合併。
"""
import argparse
from copy import deepcopy
import json
import os
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.expand_sources import INTAKE_OPTIONS, NOT_CARD_REASONS, export_report, initial_state, read, run_batch, save
from scripts.audit_sources import canonical_url
from scripts.propose_radar_update import HAND_BASELINE, write_proposal
from scripts.scan_sources import node_get

BATCH = "B1"
ACCEPTED = ("passed_automated_checks", "passed_with_gaps")
DISPOSITIONS = {"named_candidates_pending": "已產生候選", "source_document_or_discovery_only": "可讀取，但不像單一方案公告，未產生候選"}


def safe_text(value, limit=80):
    """網頁標題是外部內容，進 Issue 留言或 PR 前去掉提及、連結與表格語法。# 也換掉，「Fixes #5」合併時會關掉 Issue。"""
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    text = re.sub(r"[`|<>\[\]]", "", text).replace("@", "＠").replace("#", "＃")
    return text[:limit] or "（無標題）"


def hand_source_ids():
    known = set(read(ROOT / HAND_BASELINE)["candidate_ids"])
    return {card["source_metadata"]["source_id"] for path in (ROOT / "data/candidates").glob("*.json")
            for card in read(path)["candidates"] if card["candidate_id"] in known}


def process(request, output, transport=node_get, progress=print, options=INTAKE_OPTIONS, propose=True):
    output = Path(output)
    config = read(ROOT / "data/scan-sources.json")
    url = request["url"]
    # 手寫卡的 profile（標記字、選擇器）沒有驗證過，不拿來判斷真實頁面。
    # automation=not_enabled 是人工清單，只有手寫標題、沒有抽取設定；留著會把網站首頁命名成那個方案。
    config["sources"] = [source for source in config["sources"] if source["id"] not in hand_source_ids() and source.get("automation") != "not_enabled"]
    # 維護者已核可這個網址，即使舊 profile 是停用狀態也要跑；不影響排程設定。
    config["sources"] = [{**source, "enabled": True} if canonical_url(source["url"]) == url else deepcopy(source) for source in config["sources"]]
    inventory = {"as_of": None, "rows": [{"id": f"ISSUE-{request['issue']}", "url": url, "title": "", "batch": BATCH, "category": request["category"],
                                          "kind": "提交", "restrictions": [], "access_gate": "owner_approved_submission"}]}
    save(output / "inventory.json", inventory)
    state = initial_state(inventory)
    run_batch(inventory, state, BATCH, output / "state.json", config, transport=transport, progress=progress, options=options)
    report = output / "report"
    summary = export_report(inventory, state, report)
    bundle, profiles = read(report / "structured-candidates.json"), read(report / "source-profiles.json")
    result = {"schema_version": "source-intake-result-1", "issue": request["issue"], "url": url, "already_registered": bool(request.get("already_registered")), "http_requests": state["http_requests"], "model_calls": 0,
              "records": [{"url": r["url"], "status": r["status"], "disposition": r.get("disposition"), "not_card_reason": r.get("not_card_reason")}
                          for r in state["records"].values()],
              "links_skipped": sum(r.get("links_skipped", 0) for r in state["records"].values()),
              "candidates": [{"title": c["title"], "status": c["verification"]["status"], "program_key": c["program_key"]} for c in bundle["candidates"]],
              "proposal": None, "published": False, "official_data_modified": False, "expansion_summary": summary["statuses"]}
    if propose and any(c["verification"]["status"] in ACCEPTED for c in bundle["candidates"]):
        result["proposal"] = write_proposal(bundle, profiles, output / "proposal", replaced_urls=[url], temporal=read(report / "temporal-records.json"))
    save(output / "result.json", result)
    return result


def comment(result, run_url=None):
    lines = [f"來源處理完成：`{result['url']}`。沒有呼叫模型，也沒有改動網站資料。", ""]
    if result.get("already_registered"):
        lines.extend(["這個網址已登記過。", ""])
    lines.extend(["| 文件 | 結果 |", "|---|---|"])
    for record in result["records"]:
        why = NOT_CARD_REASONS.get(record.get("not_card_reason"))
        lines.append(f"| `{record['url']}` | {DISPOSITIONS.get(record['disposition'], '無法處理：' + safe_text(record['status']))}{'（' + why + '）' if why else ''} |")
    if result["candidates"]:
        lines.extend(["", "| 候選 | 自動檢核 |", "|---|---|"])
        lines.extend(f"| {safe_text(c['title'])} | {c['status']} |" for c in result["candidates"])
        programs = len({c.get("program_key") for c in result["candidates"]})
        lines.extend(["", f"共 {len(result['candidates'])} 份文件，歸成 {programs} 個方案。"])
    lines.append("")
    if result["links_skipped"]:
        lines.extend([f"**沒有處理完：** 還有 {result['links_skipped']} 個連結超過單次上限，沒有抓取。", ""])
    if result["proposal"]:
        lines.append(f"已產生待審提案（{result['proposal']['accepted_for_radar_proposal']} 筆）。**還沒上架**：接下來會開資料 PR，要人工看過並合併。")
        retired, manual = result["proposal"]["retired_hand_cards"], result["proposal"]["needs_manual_retire"]
        if retired:
            lines.extend(["", f"提案會取代 {len(retired)} 張手寫卡：" + "、".join(safe_text(row["title"], 40) for row in retired) + "。"])
        if manual:
            lines.extend(["", f"**要人工判斷：** 這個網址有 {len(manual)} 張手寫卡認不出是不是同一方案，提案沒有動它們：" + "、".join(safe_text(row["title"], 40) for row in manual) + "。"])
    else:
        lines.append("這次沒有可提案的候選，網站不會有變動。")
    if run_url:
        lines.append(f"\n提案與預覽：{run_url}（artifact 保留 14 天）")
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    request = read(args.request)
    if request["status"] != "accepted":
        print("skip: submission was rejected")
        return
    result = process(request, args.output)
    repository, run_id = os.environ.get("GITHUB_REPOSITORY"), os.environ.get("GITHUB_RUN_ID")
    run_url = f"https://github.com/{repository}/actions/runs/{run_id}" if repository and run_id else None
    (args.output / "comment.md").write_text(comment(result, run_url), encoding="utf-8")
    print(json.dumps({key: result[key] for key in ("http_requests", "model_calls", "published")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
