"""把待審提案變成資料 PR：套用、跑檢查、推分支、開 PR。不會合併；合併才是人工審核與上架。

分兩步跑，寫入權限只在第二步：
- 預設：套用提案、跑和 CI 相同的檢查、在本機提交。提案內容來自公開網站，這一步碰不到權杖。
- --publish：推分支並開 PR。沒有權限開 PR 時，改給比較連結讓維護者自己開。
- --notify：在固定的收件匣 Issue 留言，維護者在手機上收到推播，點連結就能開 PR。

用 GITHUB_TOKEN 開的 PR 不會觸發 pull_request CI，所以檢查一定要在這裡跑過才推。
"""
import argparse
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.run_source_intake import safe_text
CARD_ID = re.compile(r"[A-Za-z0-9._-]{1,200}")

ALLOWED_PREFIXES = ("data/", "docs/source-chains/")
BRANCH = re.compile(r"data/[a-z0-9-]+")
CONFIG = "data/scan-sources.json"
BOT = ("github-actions[bot]", "41898282+github-actions[bot]@users.noreply.github.com")
GATES = (("check_data", [sys.executable, "scripts/check_data.py"]),
         ("check_provenance", [sys.executable, "scripts/check_provenance.py"]),
         ("check_config", [sys.executable, "scripts/scan_sources.py", "--check-config"]),
         ("unittest", [sys.executable, "-m", "unittest", "discover", "-s", "tests"]),
         ("node_test", ["node", "--test", "tests/prototype.test.cjs"]))


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def proposal_files(proposal):
    """提案只能改資料和資訊鏈圖；其他路徑一律拒絕，避免網頁內容影響到程式或 workflow。"""
    repo = Path(proposal) / "repo"
    files = sorted(path.relative_to(repo).as_posix() for path in repo.rglob("*") if path.is_file())
    for name in files:
        if not name.startswith(ALLOWED_PREFIXES) or ".." in PurePosixPath(name).parts:
            raise ValueError("proposal_path_not_allowed: " + name[:120])
    return files


def apply_proposal(proposal, root=ROOT):
    """蓋到工作目錄並回傳新網域。公開提交的網域不進 allowed_hosts，要排程巡檢由維護者另外加。"""
    files = proposal_files(proposal)
    before = read(Path(root) / CONFIG)["allowed_hosts"]
    for name in files:
        target = Path(root) / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(Path(proposal) / "repo" / name, target)
    # 提案自動取代的手寫卡已從卡片檔移除；它在時程紀錄和來源鏈留下的參照也要一起清。
    summary_path = Path(proposal) / "summary.json"
    if summary_path.exists():
        from scripts.retire_candidates import scrub
        scrub([row["candidate_id"] for row in read(summary_path).get("retired_hand_cards", [])], Path(root))
    # README 的資料規模區塊跟著資料走，和提案一起提交。
    from scripts.readme_counts import refresh
    refresh(Path(root))
    config = read(Path(root) / CONFIG)
    new_hosts = sorted(set(config["allowed_hosts"]) - set(before))
    if new_hosts:
        config["allowed_hosts"] = before
        (Path(root) / CONFIG).write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    enabled = [s["id"] for s in config["sources"] if s.get("enabled", True) and urlhost(s["url"]) in new_hosts]
    if enabled:
        raise ValueError("new_host_source_enabled: " + enabled[0][:80])
    return new_hosts


def urlhost(url):
    from urllib.parse import urlsplit
    return urlsplit(url).hostname


def run_gates(root=ROOT, runner=subprocess.run):
    """回傳第一個沒過的檢查；全過回傳 None。建置放暫存目錄，不留在工作目錄。"""
    env = {**os.environ, "OPENGSA_MODEL_MODE": "off", "PYTHONUTF8": "1"}
    with tempfile.TemporaryDirectory() as site:
        for name, command in (*GATES, ("build_site", [sys.executable, "scripts/build_site.py", site])):
            if runner(command, cwd=root, env=env).returncode:
                return name
    return None


def pr_body(summary, new_hosts, source_label):
    lines = [f"來源：{source_label}。這是自動產生的待審提案，**合併後會直接上架**，請先看過內容。", "",
             f"- 提案接受 {summary['accepted_for_radar_proposal']} 筆，檢核未過而扣下 {summary['withheld_failed_checks']} 筆",
             f"- 帶時間紀錄 {summary.get('temporal_records', 0)} 筆"]
    retired, manual = summary.get("retired_hand_cards", []), summary.get("needs_manual_retire", [])
    if summary.get("dropped_not_distinct"):
        lines.append(f"- 重複或標題看不出方案而不成卡 {len(summary['dropped_not_distinct'])} 筆")
    if summary.get("withheld_site_contract"):
        lines.append(f"- 不符合網站資料規格而扣下 {len(summary['withheld_site_contract'])} 筆：" + "、".join(safe_text(row["title"], 40) for row in summary["withheld_site_contract"][:20]))
    if retired:
        lines.append(f"- 取代手寫卡 {len(retired)} 張：" + "、".join(safe_text(row["title"], 40) for row in retired[:20]))
    if manual:
        lines.append(f"- **要人工判斷**：{len(manual)} 張手寫卡認不出是不是同一方案，沒有動：" + "、".join(safe_text(row["title"], 40) for row in manual[:20]))
    if new_hosts:
        lines.extend(["", "**新網域沒有加進 `allowed_hosts`：** " + "、".join(f"`{safe_text(host, 80)}`" for host in new_hosts),
                      "", "這些來源的 profile 是停用狀態，卡片可以上架，但不會被排程巡檢。確認網域可信後再手動加。"])
    cards = summary.get("accepted_cards", [])
    if cards:
        lines.extend(["", "**卡片清單**：要拿掉某張卡，在這個 PR 留言 `/reject <卡片 id> [問題來源] <原因>`，一行一張；"
                      "問題來源可省略，代碼見 `scripts/dismiss_candidate.py`。駁回後請在當週合併，下週一的提案會覆蓋這個分支。", "",
                      "| 卡片 id | 標題 | 網站 |", "|---|---|---|"])
        # 代號原樣列出（/reject 要用原樣）；不符合代號格式的才經過 safe_text。
        lines.extend(f"| `{c['candidate_id'] if CARD_ID.fullmatch(c['candidate_id']) else safe_text(c['candidate_id'], 80)}` | {safe_text(c['title'], 60)} | {safe_text(urlhost(c['url']), 80)} |" for c in cards[:100])
        if len(cards) > 100:
            lines.append(f"| … | 另有 {len(cards) - 100} 張，見 `data/candidates/source-review.json` |")
    lines.extend(["", "推送前已跑過：`check_data`、`check_provenance`、`--check-config`、`unittest`、`node --test`、`build_site`。",
                  "這個 PR 由 Actions 開立時不會觸發 CI，所以上面這些是在開 PR 的 job 裡跑的。",
                  "", "人工核准數 0。沒有呼叫模型。"])
    return "\n".join(lines) + "\n"


def prepare(proposal, output, source_label, root=ROOT, runner=subprocess.run, git=None):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    git = git or (lambda *args: subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True).stdout)
    summary = read(Path(proposal) / "summary.json")
    result = {"status": "no_changes", "pr_url": None}
    if summary["accepted_for_radar_proposal"]:
        new_hosts = apply_proposal(proposal, root)
        if git("status", "--porcelain", "--", "data", "docs/source-chains", "README.md").strip():
            failed = run_gates(root, runner)
            result = {"status": "gates_failed", "failed_gate": failed} if failed else {"status": "ready", "new_hosts": new_hosts}
            if not failed:
                (output / "pr-body.md").write_text(pr_body(summary, new_hosts, source_label), encoding="utf-8")
                git("add", "--", "data", "docs/source-chains", "README.md")
                git("-c", f"user.name={BOT[0]}", "-c", f"user.email={BOT[1]}", "commit", "-m", f"data: 待審提案（{source_label}）")
    (output / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def publish(output, branch, title, repository, token, runner=subprocess.run):
    """固定分支名：同一來源只有一個 PR，新提案覆蓋舊提案。分支名限定 data/，不會蓋到別的分支。"""
    if not BRANCH.fullmatch(branch):
        raise ValueError("branch_not_allowed")
    output = Path(output)
    result = read(output / "result.json")
    if result["status"] != "ready":
        return result
    remote = f"https://x-access-token:{token}@github.com/{repository}.git"
    # 指令裡有權杖：不用 check=True，例外訊息會印出整行指令。
    if runner(["git", "push", "--force", remote, f"HEAD:refs/heads/{branch}"], cwd=ROOT, capture_output=True).returncode:
        raise RuntimeError("git_push_failed")
    env = {**os.environ, "GH_TOKEN": token}
    body = str(output / "pr-body.md")
    listed = runner(["gh", "pr", "list", "--repo", repository, "--head", branch, "--state", "open", "--json", "url"], env=env, capture_output=True, text=True)
    existing = json.loads(listed.stdout or "[]") if listed.returncode == 0 else []
    if existing:
        runner(["gh", "pr", "edit", existing[0]["url"], "--repo", repository, "--body-file", body], env=env, capture_output=True)
        result["pr_url"] = existing[0]["url"]
    else:
        created = runner(["gh", "pr", "create", "--repo", repository, "--base", "main", "--head", branch, "--title", title, "--body-file", body], env=env, capture_output=True, text=True)
        if created.returncode == 0:
            result["pr_url"] = created.stdout.strip()
        else:
            # 通常是 repo 設定不允許 Actions 開 PR。維護者開的 PR 會正常跑 CI。
            result["compare_url"] = f"https://github.com/{repository}/compare/main...{branch}?expand=1"
    (output / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


INBOX_TITLE = "待審資料收件匣"


def inbox_body(owner):
    return "\n".join([
        "這張 Issue 是排程掃描的待審資料收件匣，由 Actions 維護，請不要關閉；關閉後下一次有提案時會再開一張。", "",
        "每輪掃描產生新的待審提案時，bot 會在這裡留言：新卡數量、扣下的原因，以及開資料 PR 的連結。"
        "留言才會推播，改 Issue 內文不會，所以每次都是新留言。", "",
        "處理方式：點留言裡的連結開 PR，等 CI 跑完，看過後合併。合併就是上架；不想上架就不要合併，下一輪的新提案會覆蓋同一個分支。", "",
        f"@{owner} 開立時提及你，你會自動訂閱這張 Issue。", ""])


def notify(output, repository, token, owner, runner=subprocess.run):
    """有新提案或提案沒過檢查時，在收件匣 Issue 留言；沒有變動就不吵人。回傳留言的 Issue 編號。"""
    output = Path(output)
    if not (output / "comment.md").exists() or not (output / "result.json").exists():
        return None
    result = read(output / "result.json")
    if result["status"] not in ("ready", "gates_failed"):
        return None
    text = (output / "comment.md").read_text(encoding="utf-8")
    if result["status"] == "ready" and (output / "pr-body.md").exists():
        text += "\n" + (output / "pr-body.md").read_text(encoding="utf-8")
    (output / "inbox-comment.md").write_text(text, encoding="utf-8")
    env = {**os.environ, "GH_TOKEN": token}
    # 用作者篩選再比對完整標題，不用全文搜尋：搜尋索引有延遲，剛開的 Issue 會找不到而重複開。
    listed = runner(["gh", "issue", "list", "--repo", repository, "--state", "open", "--author", "app/github-actions",
                     "--limit", "200", "--json", "number,title"], env=env, capture_output=True, text=True)
    if listed.returncode:
        raise RuntimeError("inbox_list_failed")
    found = [row["number"] for row in json.loads(listed.stdout or "[]") if row["title"] == INBOX_TITLE]
    if found:
        number = str(min(found))
    else:
        (output / "inbox-body.md").write_text(inbox_body(owner), encoding="utf-8")
        created = runner(["gh", "issue", "create", "--repo", repository, "--title", INBOX_TITLE, "--body-file", str(output / "inbox-body.md")],
                         env=env, capture_output=True, text=True)
        if created.returncode:
            raise RuntimeError("inbox_create_failed")
        number = created.stdout.strip().rsplit("/", 1)[-1]
    if runner(["gh", "issue", "comment", number, "--repo", repository, "--body-file", str(output / "inbox-comment.md")],
              env=env, capture_output=True, text=True).returncode:
        raise RuntimeError("inbox_comment_failed")
    return number


def comment(result):
    if result["status"] == "gates_failed":
        return f"提案沒有通過 `{safe_text(result['failed_gate'])}`，沒有開 PR，網站不會變動。\n"
    if result["status"] != "ready":
        return "沒有需要更新的資料，沒有開 PR。\n"
    if result.get("pr_url"):
        return f"已開資料 PR：{result['pr_url']}。**還沒上架**，要人工看過並合併。\n"
    return f"分支已推送，但 Actions 沒有開成 PR（通常是 repo 設定不允許）。請從這裡開：{result['compare_url']}\n**還沒上架**，要人工看過並合併。\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--proposal", type=Path)
    parser.add_argument("--output", type=Path, default=ROOT / "work/data-pr")
    parser.add_argument("--label", default="排程掃描", help="PR 內文的來源說明")
    parser.add_argument("--apply-only", action="store_true", help="只套用提案，不跑檢查也不提交")
    parser.add_argument("--publish", action="store_true")
    parser.add_argument("--notify", action="store_true", help="在收件匣 Issue 留言")
    parser.add_argument("--branch")
    parser.add_argument("--title", default="data: 待審提案")
    args = parser.parse_args()
    if args.notify:
        number = notify(args.output, os.environ["GITHUB_REPOSITORY"], os.environ["GH_TOKEN"], os.environ["OWNER"])
        print(json.dumps({"inbox_issue": number}, ensure_ascii=False))
        return
    if args.publish:
        result = publish(args.output, args.branch, args.title, os.environ["GITHUB_REPOSITORY"], os.environ["GH_TOKEN"])
        (args.output / "comment.md").write_text(comment(result), encoding="utf-8")
    elif args.apply_only:
        result = {"new_hosts": apply_proposal(args.proposal)}
    else:
        result = prepare(args.proposal, args.output, args.label)
        # 檢查沒過時不會走到 --publish，留言要在這裡寫好。
        if result["status"] != "ready":
            (args.output / "comment.md").write_text(comment(result), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    if result.get("status") == "gates_failed":
        sys.exit(1)


if __name__ == "__main__":
    main()
