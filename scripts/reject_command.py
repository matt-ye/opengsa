"""資料 PR 上的單張卡駁回：維護者在 PR 留言 `/reject <卡片 id> [問題來源] <原因>`，寫進駁回台帳。

- 一則留言可以有多行 `/reject`，每行一張卡。問題來源是 dismiss_candidate.PROBLEMS 的代碼，可省略（記成 other）。
- 卡片留在候選檔，駁回原因留在台帳（data/scan-reviews.json）；網站和 RSS 建置時就不顯示這張卡。
- 這個 PR 新加的來源，如果它在 PR 裡的卡全被駁回，就停用，排程不再巡檢它。PR 之前就有的來源不動。
- 只改 PR 分支的工作目錄（--root），不推送、不留言；推送與留言由 workflow 做。留言內容從事件檔讀，不經過 shell。

每週一的資料 PR 會用新提案整個覆蓋分支，所以駁回後要在當週合併，否則下週一會被蓋掉。
"""
import argparse
import json
import os
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.dismiss_candidate import LEDGER, PROBLEMS, dismiss
from scripts.run_source_intake import safe_text

CONFIG = "data/scan-sources.json"
COMMAND = re.compile(r"^\s*/reject\s+(\S+)(?:\s+(.*))?$")
# 卡片代號只有英數、點、底線和連字號；其他字元的一律當成格式不對，不拿去比對。
CARD_ID = re.compile(r"[A-Za-z0-9._-]{1,200}")


def parse(body):
    """每行一個指令，回傳 (卡片 id, 問題來源, 原因)；格式不對的行回傳 (行文字, None, None)。"""
    commands = []
    for line in (body or "").splitlines():
        if not line.strip().startswith("/reject"):
            continue
        match = COMMAND.match(line)
        rest = (match.group(2) or "").strip() if match else ""
        if not match or not rest or not CARD_ID.fullmatch(match.group(1)):
            commands.append((line.strip(), None, None))
            continue
        head, *tail = re.split(r"\s+", rest, maxsplit=1)
        problem, reason = (head, (tail or [""])[0].strip()) if head in PROBLEMS else ("other", rest)
        commands.append((match.group(1), problem, reason) if reason else (line.strip(), None, None))
    return commands


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def disable_rejected_new_sources(root, base_root):
    """PR 新加的來源，卡全被駁回就停用；回傳停用的來源 id。"""
    base = {s["id"] for s in read(Path(base_root) / CONFIG)["sources"]}
    dismissed = already_dismissed(root)
    cards = {}
    for path in sorted((Path(root) / "data/candidates").glob("*.json")):
        for card in read(path)["candidates"]:
            cards.setdefault(card["source_metadata"]["source_id"], []).append(card["candidate_id"])
    path = Path(root) / CONFIG
    config = read(path)
    disabled = []
    for source in config["sources"]:
        ids = cards.get(source["id"], [])
        if source["id"] not in base and source.get("enabled", True) and ids and all(i in dismissed for i in ids):
            source["enabled"] = False
            disabled.append(source["id"])
    if disabled:
        path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return disabled


def already_dismissed(root):
    return {r["candidate_id"] for r in read(Path(root) / LEDGER)["reviews"] if r["action"] == "dismissed"}


def run(body, reviewer, root, base_root):
    results = []
    for candidate_id, problem, reason in parse(body):
        if problem is None:
            results.append({"line": candidate_id, "status": "bad_format"})
            continue
        if candidate_id in already_dismissed(root):
            results.append({"candidate_id": candidate_id, "status": "error", "error": "already_dismissed"})
            continue
        try:
            dismiss(candidate_id, reason, problem, reviewer, root=root)
            results.append({"candidate_id": candidate_id, "status": "dismissed", "problem": problem, "reason": reason})
        except ValueError as error:
            # 不認得的 id、重複駁回、原因空白：這行不動，其他行照做。
            results.append({"candidate_id": candidate_id, "status": "error", "error": str(error).split(":")[0]})
    disabled = disable_rejected_new_sources(root, base_root) if any(r["status"] == "dismissed" for r in results) else []
    return {"results": results, "disabled_sources": disabled}


def reply(outcome, pushed, failed_gate=None):
    done = [r for r in outcome["results"] if r["status"] == "dismissed"]
    lines = []
    if done:
        status = ("，並推到這個 PR。" if pushed else
                  f"，但沒有通過 `{safe_text(failed_gate, 40)}` 檢查，**沒有推送**，請看 Actions 紀錄。" if failed_gate else
                  "，但**推送失敗**，請看 Actions 紀錄。")
        lines.append(f"已駁回 {len(done)} 張，寫進 `{LEDGER}`" + status)
        lines.extend(f"- `{safe_text(r['candidate_id'], 80)}`：{safe_text(r['reason'], 120)}（{r['problem']}）" for r in done)
    if outcome["disabled_sources"]:
        lines.append("這個 PR 新加、卡全被駁回的來源已停用：" + "、".join(f"`{safe_text(s, 80)}`" for s in outcome["disabled_sources"]))
    for r in outcome["results"]:
        if r["status"] == "bad_format":
            lines.append(f"- 看不懂這行：`{safe_text(r['line'], 120)}`。格式是 `/reject <卡片 id> [問題來源] <原因>`。")
        elif r["status"] == "error":
            lines.append(f"- `{safe_text(r['candidate_id'], 80)}` 沒有駁回：`{safe_text(r['error'], 80)}`")
    if not outcome["results"]:
        lines.append("留言裡沒有 `/reject` 指令。")
    lines.extend(["", "問題來源代碼：" + "、".join(f"`{k}`" for k in PROBLEMS) + "。",
                  "每週一的資料 PR 會整個覆蓋這個分支，駁回後請在當週合併。"])
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--event", type=Path, default=os.environ.get("GITHUB_EVENT_PATH"))
    parser.add_argument("--root", type=Path, required=True, help="PR 分支的工作目錄")
    parser.add_argument("--base-root", type=Path, default=ROOT, help="main 的工作目錄，用來判斷哪些來源是 PR 新加的")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--reply", action="store_true", help="依 --output 的結果寫留言；--pushed 表示已推送")
    parser.add_argument("--pushed", action="store_true")
    parser.add_argument("--failed-gate", help="沒通過的檢查名稱（沒有推送）")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    if args.reply:
        if (args.output / "outcome.json").exists():
            text = reply(read(args.output / "outcome.json"), args.pushed, args.failed_gate)
        else:
            text = "處理 `/reject` 時出錯，PR 沒有任何變動，請看 Actions 紀錄。\n"
        (args.output / "comment.md").write_text(text, encoding="utf-8")
        return
    event = read(args.event)
    outcome = run(event["comment"]["body"], event["comment"]["user"]["login"], args.root, args.base_root)
    (args.output / "outcome.json").write_text(json.dumps(outcome, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"dismissed": sum(r["status"] == "dismissed" for r in outcome["results"]),
                      "disabled_sources": len(outcome["disabled_sources"])}))
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as handle:
            handle.write(f"changed={str(any(r['status'] == 'dismissed' for r in outcome['results'])).lower()}\n")


if __name__ == "__main__":
    main()
