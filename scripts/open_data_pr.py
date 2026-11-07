"""把待審提案變成資料 PR：套用、跑檢查、推分支、開 PR。不會合併；合併才是人工審核與上架。

分兩步跑，寫入權限只在第二步：
- 預設：套用提案、跑和 CI 相同的檢查、在本機提交。提案內容來自公開網站，這一步碰不到權杖。
- --publish：推分支並開 PR。沒有權限開 PR 時，改給比較連結讓維護者自己開。

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
    if summary.get("withheld_site_contract"):
        lines.append(f"- 不符合網站資料規格而扣下 {len(summary['withheld_site_contract'])} 筆：" + "、".join(safe_text(row["title"], 40) for row in summary["withheld_site_contract"][:20]))
    if retired:
        lines.append(f"- 取代手寫卡 {len(retired)} 張：" + "、".join(safe_text(row["title"], 40) for row in retired[:20]))
    if manual:
        lines.append(f"- **要人工判斷**：{len(manual)} 張手寫卡認不出是不是同一方案，沒有動：" + "、".join(safe_text(row["title"], 40) for row in manual[:20]))
    if new_hosts:
        lines.extend(["", "**新網域沒有加進 `allowed_hosts`：** " + "、".join(f"`{safe_text(host, 80)}`" for host in new_hosts),
                      "", "這些來源的 profile 是停用狀態，卡片可以上架，但不會被排程巡檢。確認網域可信後再手動加。"])
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
        if git("status", "--porcelain", "--", "data", "docs/source-chains").strip():
            failed = run_gates(root, runner)
            result = {"status": "gates_failed", "failed_gate": failed} if failed else {"status": "ready", "new_hosts": new_hosts}
            if not failed:
                (output / "pr-body.md").write_text(pr_body(summary, new_hosts, source_label), encoding="utf-8")
                git("add", "--", "data", "docs/source-chains")
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
    runner(["git", "push", "--force", remote, f"HEAD:refs/heads/{branch}"], cwd=ROOT, check=True, capture_output=True)
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
            # repo 設定不允許 Actions 開 PR 時走這裡。維護者開的 PR 會正常跑 CI。
            result["compare_url"] = f"https://github.com/{repository}/compare/main...{branch}?expand=1"
    (output / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def comment(result):
    if result["status"] == "gates_failed":
        return f"提案沒有通過 `{safe_text(result['failed_gate'])}`，沒有開 PR，網站不會變動。\n"
    if result["status"] != "ready":
        return "沒有需要更新的資料，沒有開 PR。\n"
    if result.get("pr_url"):
        return f"已開資料 PR：{result['pr_url']}。**還沒上架**，要人工看過並合併。\n"
    return f"分支已推送，但 Actions 沒有權限開 PR。請從這裡開：{result['compare_url']}\n**還沒上架**，要人工看過並合併。\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--proposal", type=Path)
    parser.add_argument("--output", type=Path, default=ROOT / "work/data-pr")
    parser.add_argument("--label", default="排程掃描", help="PR 內文的來源說明")
    parser.add_argument("--apply-only", action="store_true", help="只套用提案，不跑檢查也不提交")
    parser.add_argument("--publish", action="store_true")
    parser.add_argument("--branch")
    parser.add_argument("--title", default="data: 待審提案")
    args = parser.parse_args()
    if args.publish:
        result = publish(args.output, args.branch, args.title, os.environ["GITHUB_REPOSITORY"], os.environ["GH_TOKEN"])
        (args.output / "comment.md").write_text(comment(result), encoding="utf-8")
    elif args.apply_only:
        result = {"new_hosts": apply_proposal(args.proposal)}
    else:
        result = prepare(args.proposal, args.output, args.label)
    print(json.dumps(result, ensure_ascii=False))
    if result.get("status") == "gates_failed":
        sys.exit(1)


if __name__ == "__main__":
    main()
