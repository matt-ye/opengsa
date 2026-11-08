"""駁回一張卡：寫進人工台帳，網站和 RSS 下一次建置就不再顯示。

卡片本身留在候選檔，駁回原因和問題來源留在台帳，之後可以回頭改進萃取腳本。
目前只有 repo owner 核准與駁回。
"""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.evaluate_deadlines import taipei_today
from scripts.review_candidates import validate_review_ledger

LEDGER = "data/scan-reviews.json"
PROBLEMS = {"source_page": "來源頁本身有問題（過期、內容錯誤、不是官方）", "extraction": "萃取抽錯或漏抽", "wrong_url": "網址錯誤或指到別的方案",
            "not_a_program": "不是獎助方案（索引頁、新聞、名單）", "other": "其他，寫在原因裡"}


def find_card(candidate_id, root=ROOT):
    for path in sorted((Path(root) / "data/candidates").glob("*.json")):
        for card in json.loads(path.read_text(encoding="utf-8"))["candidates"]:
            if card["candidate_id"] == candidate_id:
                return card
    raise ValueError("unknown_candidate_id: " + candidate_id[:80])


def dismiss(candidate_id, reason, problem_source, reviewer, root=ROOT, today=None):
    if problem_source not in PROBLEMS:
        raise ValueError("unknown_problem_source")
    card = find_card(candidate_id, root)
    path = Path(root) / LEDGER
    ledger = json.loads(path.read_text(encoding="utf-8"))
    entry = {"revision_id": card["source_metadata"]["revision_id"], "source_id": card["source_metadata"]["source_id"], "candidate_id": candidate_id,
             "action": "dismissed", "reviewer": reviewer, "reason": reason, "problem_source": problem_source, "reviewed_on": today or taipei_today()}
    ledger["reviews"].append(entry)
    validate_review_ledger(ledger)
    path.write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return entry


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-id", required=True)
    parser.add_argument("--reason", required=True)
    parser.add_argument("--problem-source", required=True, choices=sorted(PROBLEMS), help="; ".join(f"{k}: {v}" for k, v in PROBLEMS.items()))
    parser.add_argument("--reviewer", default="matt-ye")
    args = parser.parse_args()
    print(json.dumps(dismiss(args.candidate_id, args.reason, args.problem_source, args.reviewer), ensure_ascii=False))


if __name__ == "__main__":
    main()
