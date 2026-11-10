"""每週一重跑使用者核可過的獎助入口頁（data/entry-pages.json），找出還不是來源的新方案頁，併進週一的資料 PR。

- 每日掃描只重抓來源頁本身、不跟連結，所以入口頁上新出現的方案要靠這支找。
- 入口頁上已經是來源的連結不再跟（每日掃描會處理），只對新連結跑提交流程。
- 有排程掃描的提案（--base-proposal）時，先把它套到工作目錄再產生新提案，最後把兩份的檔案合併：
  入口頁提案的檔案是在掃描結果之上產生的，以它為準；只有掃描改到的檔案從掃描提案補進來。
- 只連公開網址、遵守 robots、同站間隔 3 秒、不呼叫模型。輸出留在 --output，不寫正式資料；上架仍須人工合併 PR。

輸出：<output>/proposal（給 open_data_pr.py），並在 GITHUB_OUTPUT 寫 has_proposal。
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.expand_sources import read
from scripts.open_data_pr import apply_proposal
from scripts.run_hand_replacement import BATCH_OPTIONS, build_proposal, run

REGISTRY = "data/entry-pages.json"
WATCH_OPTIONS = {**BATCH_OPTIONS, "skip_known_children": True}
COUNTS = ("accepted_for_radar_proposal", "withheld_failed_checks", "temporal_records")
LISTS = ("dropped_not_distinct", "withheld_site_contract", "retired_hand_cards", "needs_manual_retire")


def merge_summaries(base, entry):
    """PR 說明要涵蓋兩份提案：數字相加、清單相接，另記入口頁那份接受了幾筆。"""
    merged = dict(base or {})
    for key in COUNTS:
        merged[key] = (base or {}).get(key, 0) + entry.get(key, 0)
    for key in LISTS:
        merged[key] = (base or {}).get(key, []) + entry.get(key, [])
    merged["entry_pages_accepted"] = entry.get("accepted_for_radar_proposal", 0)
    return merged


def combine(base, entry, final):
    """入口頁提案為主；掃描提案改到、入口頁提案沒有的檔案補進來。"""
    if final.exists():
        shutil.rmtree(final)
    shutil.copytree(entry, final)
    if base:
        for path in (base / "repo").rglob("*"):
            target = final / "repo" / path.relative_to(base / "repo")
            if path.is_file() and not target.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(path, target)
    summary = merge_summaries(read(base / "summary.json") if base else None, read(entry / "summary.json"))
    (final / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary


def watch(output, base=None, root=ROOT, max_requests=300, runner=run, proposer=build_proposal):
    output = Path(output)
    registry = Path(root) / REGISTRY
    pages = read(registry)["pages"] if registry.exists() else []
    base = Path(base) if base and (Path(base) / "summary.json").exists() else None
    base_accepted = read(base / "summary.json")["accepted_for_radar_proposal"] if base else 0
    final = output / "proposal"
    entry_summary = None
    if pages:
        if base and base_accepted:
            apply_proposal(base, root)
        targets = [{"url": p["url"], "category": p["category"], "cards": []} for p in pages]
        runner(output / "intake", targets, max_requests=max_requests, options=WATCH_OPTIONS)
        try:
            entry_summary = proposer(output / "intake", targets, preview=False)
        except ValueError:  # 這週入口頁上沒有新方案
            entry_summary = None
    if entry_summary and entry_summary["accepted_for_radar_proposal"]:
        summary = combine(base if base_accepted else None, output / "intake/proposal", final)
    elif base:
        if final.exists():
            shutil.rmtree(final)
        shutil.copytree(base, final)
        summary = read(final / "summary.json")
    else:
        summary = {"accepted_for_radar_proposal": 0}
    return {"entry_pages": len(pages), "entry_pages_accepted": (entry_summary or {}).get("accepted_for_radar_proposal", 0),
            "has_proposal": summary["accepted_for_radar_proposal"] > 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "work/entry-watch")
    parser.add_argument("--base-proposal", type=Path, help="同一輪排程掃描的提案目錄（可省略）")
    parser.add_argument("--max-requests", type=int, default=300)
    args = parser.parse_args()
    if args.output.resolve().is_relative_to(ROOT / "data"):
        parser.error("write review artifacts outside data")
    result = watch(args.output, args.base_proposal, max_requests=args.max_requests)
    print(json.dumps(result, ensure_ascii=False))
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as handle:
            handle.write(f"has_proposal={str(result['has_proposal']).lower()}\n")


if __name__ == "__main__":
    main()
