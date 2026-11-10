"""第 2 階段：大專校院獎助入口探索（設計見 docs/UNIVERSITY-DISCOVERY-DESIGN.md）。

- 對象：名冊（docs/audits/university-roster-verification-2026-11-07.json）中目前沒有任何卡片的學校。
- 每校兩條路都跑，抓過的頁面在同一輪共用：
  - 模型版本（ReAct D）：模型看目前頁面的標題與編號連結，回答「打開第 n 個」或「入口頁是第 n 個」。
    只送連結文字、網址與頁面標題，不送內文；每校最多 MAX_STEPS 步。
  - 規則版本：連結文字或網址含獎助關鍵字的，加上學務處頁面上的同類連結。
- 最終採用：模型找到並通過確認的入口頁優先；模型沒找到或失敗時改用規則的。兩條路的結果都記成案例。
- 確認：入口頁要能讀到，而且是「索引頁」（列出多個獎助連結）或可以直接成卡（not_card_reason 為空）。
- 抓取沿用 scan_sources.Fetcher：robots、同站間隔 3 秒、403／429 暫停該站；每輪請求上限另計（預設 100）。
- 可續跑：已完成的學校記在 state，下一輪接著做。

輸出（work/discovery/）：report.json（每校結果與案例）、issue.md（給使用者勾選網域的清單）。
"""
import argparse
import json
import os
from pathlib import Path
import re
import sys
import time
import urllib.request
from urllib.parse import urljoin, urlsplit

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from bs4 import BeautifulSoup

from scripts.expand_sources import not_card_reason, prepare_response, read, save
from scripts.providers import PROVIDERS, provider_settings
from scripts.run_source_intake import safe_text
from scripts.scan_sources import AGENT, Fetcher, ScanError, digest, node_get

ROSTER = ROOT / "docs/audits/university-roster-verification-2026-11-07.json"
KEYWORDS = re.compile(r"獎學金|獎助|助學|急難|弱勢|學雜費減免|工讀|scholarship|financial\s*aid", re.I)
EXCLUDE = re.compile(r"名單|榜單|得獎|獲獎|成果|新聞稿|花絮|頒獎|表格下載|申請表")
OFFICE = re.compile(r"學務處|學生事務|生活輔導|生輔|student\s*affairs", re.I)
CATEGORY = "living_tuition"  # 學校獎助頁大多是學雜費與生活助學類
INDEX_LINKS = 3
MAX_STEPS = 6
MAX_LINKS = 60
PROMPT = ("你在幫一個台灣獎助學金資料網站，找某所大學的「獎助學金入口頁」：列出多個獎學金、助學金、急難救助或弱勢助學方案的頁面，"
          "通常在學務處或生活輔導組。每一步你會看到目前頁面的標題和編號連結。只回答一個 JSON："
          '{"action":"open","n":編號} 打開一個連結看看；{"action":"answer","n":[編號,...]} 這些就是入口頁（最多 3 個）；'
          '{"action":"none"} 找不到。不要回答其他文字。')


def base_domain(host):
    parts = (host or "").split(".")
    return ".".join(parts[-3:]) if host and host.endswith((".edu.tw", ".gov.tw", ".org.tw")) else ".".join(parts[-2:])


def schools_without_cards(root=ROOT):
    rows = read(ROSTER)["rows"]
    covered = {base_domain(urlsplit(c["source_metadata"]["url"]).hostname)
               for path in (root / "data/candidates").glob("*.json") for c in read(path)["candidates"]}
    return [r for r in rows if base_domain(urlsplit(r["url"]).hostname) not in covered]


class SameSite(set):
    """allowed_hosts 的替身：同一所學校網域下的任何子網域都算（學務處常在 osa.、sa. 等子網域，轉址也常跨子網域）。"""

    def __init__(self, base):
        super().__init__()
        self.base = base

    def __contains__(self, host):
        return bool(host) and (host == self.base or host.endswith("." + self.base))


class Browser:
    """同一輪共用的抓取器：只抓同一所學校網域下的 https 網址，頁面在記憶體快取。"""

    def __init__(self, max_requests, transport=node_get, sleeper=time.sleep):
        self.fetcher = Fetcher({"allowed_hosts": SameSite(""), "max_requests": max_requests, "minimum_host_interval_seconds": 3,
                                "max_run_seconds": 3600}, transport=transport, sleeper=sleeper)
        self.pages = {}

    @property
    def used(self):
        return self.fetcher.count

    def open(self, url, base):
        if url in self.pages:
            return self.pages[url]
        hosts = self.fetcher.config["allowed_hosts"] = SameSite(base)
        if urlsplit(url).hostname not in hosts:
            raise ScanError("off_site")
        response = self.fetcher.get(url, {}, 2 * 1024 * 1024)
        final = response["url"]
        if response["status"] != 200 or "html" not in response["headers"].get("content-type", "").lower():
            page = {"url": final, "status": response["status"], "title": "", "links": [], "prepared": None}
        else:
            soup = BeautifulSoup(response["body"], "html.parser")
            links, seen = [], set()
            for a in soup.select("a[href]"):
                label = " ".join(a.get_text(" ", strip=True).split())[:60]
                target = urljoin(final, a["href"]).split("#")[0]
                if label and target.startswith("https://") and urlsplit(target).hostname in hosts and target not in seen:
                    seen.add(target)
                    # 導覽、頁首、頁尾的連結每頁都一樣，判斷索引頁時不算。
                    menu = bool(a.find_parent(["nav", "header", "footer"]) or a.find_parent(attrs={"role": "navigation"}))
                    links.append({"label": label, "url": target, "menu": menu})
            try:
                prepared = prepare_response({**response, "url": final}, {}, hosts, link_limit=None, broad_links=True,
                                            category=CATEGORY)
            except (ScanError, ValueError):
                prepared = None
            page = {"url": final, "status": 200, "title": (soup.title.get_text(" ", strip=True) if soup.title else "")[:80],
                    "links": links, "prepared": prepared}
        self.pages[url] = self.pages[final] = page
        return page


def keyword_links(page):
    return [l for l in page["links"] if (KEYWORDS.search(l["label"]) or KEYWORDS.search(l["url"])) and not EXCLUDE.search(l["label"])]


def verify(browser, url, base):
    """入口頁要讀得到，而且是索引頁或可以直接成卡。回傳 (是否通過, 依據)。"""
    try:
        page = browser.open(url, base)
    except ScanError as error:
        return False, str(error)
    if page["status"] != 200:
        return False, f"http_{page['status']}"
    # 只數內文區的連結：導覽選單每頁都一樣，數進去的話整個網站每頁都像索引頁。
    count = len(keyword_links({"links": [l for l in page["links"] if not l["menu"]]}))
    if count >= INDEX_LINKS:
        return True, f"索引頁（{count} 個獎助連結）"
    reason = not_card_reason({"url": page["url"], "category": CATEGORY}, page["prepared"], None) if page["prepared"] else "unreadable"
    return (reason is None), ("可直接成卡" if reason is None else f"不是入口頁（{reason}，{count} 個獎助連結）")


def rule_find(browser, home, base):
    """規則版本：首頁的獎助連結，加上學務處頁面上的獎助連結。"""
    page = browser.open(home, base)
    found = keyword_links(page)
    for office in [l for l in page["links"] if OFFICE.search(l["label"])][:2]:
        try:
            found += keyword_links(browser.open(office["url"], base))
        except ScanError:
            continue
    ranked, seen = [], set()
    for link in sorted(found, key=lambda l: (not KEYWORDS.search(l["label"]), len(l["url"]))):
        if link["url"] not in seen:
            seen.add(link["url"])
            ranked.append(link)
    return ranked[:5]


def ask_model(provider, messages, cache):
    base, model, key_env = provider_settings(provider, os.environ)
    key = digest([model, messages])[:24]
    path = cache / f"{key}.json"
    if path.exists():
        return read(path), True
    payload = {"model": model, "temperature": 0, "max_tokens": 60, "messages": messages}
    if provider == "groq":
        payload["reasoning_effort"] = "none"
    request = urllib.request.Request(base + "/chat/completions", data=json.dumps(payload).encode(), headers={
        "Authorization": "Bearer " + os.environ[key_env], "Content-Type": "application/json", "User-Agent": AGENT})
    with urllib.request.urlopen(request, timeout=60) as response:
        text = json.loads(response.read())["choices"][0]["message"]["content"].strip()
    match = re.search(r"\{.*\}", text, re.S)
    result = {"model": model, "raw": text[:200], "action": json.loads(match.group(0)) if match else None}
    cache.mkdir(parents=True, exist_ok=True)
    save(path, result)
    return result, False


def listing(page):
    """給模型看的連結：獎助與學務處連結排前面，最多 MAX_LINKS 個。只有連結文字與網址。"""
    links = sorted(page["links"], key=lambda l: (not KEYWORDS.search(l["label"]), not OFFICE.search(l["label"])))[:MAX_LINKS]
    return links, f"頁面標題：{page['title']}\n" + "\n".join(f"{i}. {l['label']} | {l['url']}" for i, l in enumerate(links, 1))


def model_find(browser, home, base, school, provider, cache, budget):
    """ReAct D：模型一步一步選要打開的連結，最後回答入口頁。回傳 (入口頁連結, 步驟紀錄)。"""
    page = browser.open(home, base)
    messages = [{"role": "system", "content": PROMPT}]
    steps = []
    for _ in range(MAX_STEPS):
        if budget["model_calls"] <= 0:
            steps.append({"stop": "model_budget"})
            return [], steps
        links, text = listing(page)
        messages.append({"role": "user", "content": f"學校：{school}\n{text}"})
        result, cached = ask_model(provider, messages, cache)
        budget["model_calls"] -= 0 if cached else 1
        if not cached:
            time.sleep(2)
        action = result["action"] or {}
        steps.append({"page": page["url"], "action": action, "raw": result["raw"][:80]})
        messages.append({"role": "assistant", "content": result["raw"]})
        if action.get("action") == "open" and isinstance(action.get("n"), int) and 0 < action["n"] <= len(links):
            try:
                page = browser.open(links[action["n"] - 1]["url"], base)
            except ScanError as error:
                messages.append({"role": "user", "content": f"打不開（{error}），請選別的。"})
            continue
        if action.get("action") == "answer":
            picks = action.get("n") if isinstance(action.get("n"), list) else [action.get("n")]
            return [links[n - 1] for n in picks if isinstance(n, int) and 0 < n <= len(links)][:3], steps
        return [], steps
    steps.append({"stop": "max_steps"})
    return [], steps


def discover(school, browser, provider, cache, budget):
    home = school.get("url")
    base = base_domain(urlsplit(home).hostname)
    case = {"id": school["id"], "name": school["name"], "home": home, "base": base}
    try:
        browser.open(home, base)
    except ScanError as error:
        return {**case, "status": f"home_unreachable:{error}", "entries": []}
    model_links, steps = ([], [{"stop": "model_disabled"}])
    if provider:
        try:
            model_links, steps = model_find(browser, home, base, school["name"], provider, cache, budget)
        except Exception as error:  # 模型呼叫失敗就改用規則，原因記下來。
            steps = [{"stop": "model_error:" + type(error).__name__}]
    rule_links = rule_find(browser, home, base)
    checked = {}
    for link in model_links + rule_links:
        if link["url"] not in checked and browser.used < browser.fetcher.config["max_requests"]:
            checked[link["url"]] = verify(browser, link["url"], base)
    model_ok = [{**l, "basis": checked[l["url"]][1]} for l in model_links if checked.get(l["url"], (False,))[0]]
    rule_ok = [{**l, "basis": checked[l["url"]][1]} for l in rule_links if checked.get(l["url"], (False,))[0]]
    entries, source = (model_ok, "model") if model_ok else (rule_ok[:3], "rule") if rule_ok else ([], "none")
    return {**case, "status": "found" if entries else "not_found", "source": source, "entries": entries,
            "model": {"links": model_links, "accepted": len(model_ok), "steps": steps},
            "rule": {"links": rule_links, "accepted": len(rule_ok)}}


def issue_markdown(results):
    lines = ["# 大專校院獎助入口探索結果", "",
             "勾選要加入巡檢的學校後，請 agent 開 PR 把網域加入 `allowed_hosts`、入口頁設為來源（見 docs/UNIVERSITY-DISCOVERY-DESIGN.md）。", "",
             "| 來源 | 意思 |", "|---|---|", "| model | 模型一步步找到，並通過確認 |", "| rule | 模型沒找到，關鍵字規則找到並通過確認 |", ""]
    for r in results:
        if r["status"] != "found":
            continue
        hosts = sorted({urlsplit(e["url"]).hostname for e in r["entries"]})
        lines.append(f"- [ ] {r['id']} {r['name']}（{r['source']}）網域：{'、'.join(hosts)}")
        # 連結文字是外部內容：進 Issue 前去掉提及與 Markdown 語法。
        lines.extend(f"  - {safe_text(e['label'], 40)}：{e['url']}（{e['basis']}）" for e in r["entries"])
    missing = [f"{r['id']} {r['name']}（{r['status']}）" for r in results if r["status"] != "found"]
    if missing:
        lines += ["", "## 沒找到入口頁", ""] + [f"- {m}" for m in missing]
    return "\n".join(lines) + "\n"


def approved_targets(issue_body, results):
    """Issue 裡勾選的學校，換成 run_hand_replacement.py --targets 吃的網址清單 [{url, category}]。"""
    ticked = set(re.findall(r"^- \[[xX]\] ([A-Z]\d+) ", issue_body, re.M))
    return [{"url": e["url"], "category": CATEGORY} for r in results if r["id"] in ticked and r["status"] == "found" for e in r["entries"]]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "work/discovery")
    parser.add_argument("--max-requests", type=int, default=100)
    parser.add_argument("--max-model-calls", type=int, default=150)
    parser.add_argument("--provider", default="groq", help="模型供應商；空字串只跑規則")
    parser.add_argument("--limit", type=int, help="本輪最多處理幾校")
    parser.add_argument("--approved", type=Path, help="Issue 內文檔：只把勾選的學校寫成 approved-targets.json，不抓取")
    args = parser.parse_args()
    if args.approved:
        targets = approved_targets(args.approved.read_text(encoding="utf-8"), read(args.output / "report.json")["schools"])
        save(args.output / "approved-targets.json", targets)
        print(json.dumps({"approved_entries": len(targets)}, ensure_ascii=False))
        return
    provider = args.provider or None
    if provider and PROVIDERS[provider]["inference_policy"] not in ("user_reported_free", "zero_price_free_only"):
        sys.exit("只用確認免費的模型")
    if provider and not any(os.environ.get(k, "").strip() for k in PROVIDERS[provider]["key_envs"]):
        provider = None  # 沒有金鑰就只跑規則
    state_path = args.output / "state.json"
    state = read(state_path) if state_path.exists() else {"done": {}}
    browser = Browser(args.max_requests)
    budget = {"model_calls": args.max_model_calls}
    todo = [s for s in schools_without_cards() if s["id"] not in state["done"]][: args.limit]
    for school in todo:
        if browser.used >= args.max_requests - 6:
            break
        result = discover(school, browser, provider, args.output / "model-cache", budget)
        state["done"][school["id"]] = result
        save(state_path, state)
        print(json.dumps({"id": school["id"], "status": result["status"], "source": result.get("source"),
                          "requests": browser.used}, ensure_ascii=False), flush=True)
    results = list(state["done"].values())
    save(args.output / "report.json", {"schools": results, "requests_this_run": browser.used,
                                        "model_calls_this_run": args.max_model_calls - budget["model_calls"]})
    (args.output / "issue.md").write_text(issue_markdown(results), encoding="utf-8")
    found = sum(r["status"] == "found" for r in results)
    print(json.dumps({"schools_done": len(results), "found": found, "by_source": {
        s: sum(r.get("source") == s for r in results) for s in ("model", "rule")}, "remaining": len(schools_without_cards()) - len(results)},
        ensure_ascii=False))


if __name__ == "__main__":
    main()
