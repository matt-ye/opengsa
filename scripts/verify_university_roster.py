"""逐校驗證78校名冊網址；失效時從名冊內其他入口沿頁面連結往下找獎助頁。

沿用scan_sources.Fetcher的robots、單次請求預算、同站間隔及403／429暫停。
只跟隨同校網域（xxx.edu.tw）的連結；只保存網址、狀態與連結文字，不保存頁面內文。
結果寫入ignored的work/，由apply步驟另行套用；這支程式不改資料。
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.scan_sources import Fetcher, ScanError

ROSTER = ROOT / "data/source-expansion/university-source-inventory.json"
CONFIG = ROOT / "data/scan-sources.json"
OUTPUT = ROOT / "work/discovery/roster-verification.json"
BODY_LIMIT = 2_000_000
MAX_PAGES_PER_SCHOOL = 6
PORTAL = re.compile(r"獎助|獎學金|助學|獎補助|急難")
ASSISTANCE = re.compile(r"生活輔導|生輔|學輔|生活助學|僑生|住宿服務")
AFFAIRS = re.compile(r"學務|學生事務|student\s*affairs", re.I)
SEEDS = (("portal", "scholarship_portal_url"), ("assistance", "assistance_office_url"),
         ("student_affairs", "student_affairs_url"), ("official_website", "official_website"))
RANK = {"portal": 3, "assistance": 2, "student_affairs": 1, "official_website": 0}
# 導覽項目的文字很短；長文字多半是單篇公告，不能當成專區入口。
MAX_NAV_LABEL = 12
FILE_PATH = re.compile(r"\.(pdf|docx?|xlsx?|pptx?|odt|ods|zip|rar|jpe?g|png)$", re.I)
NON_PORTAL_PATH = re.compile(r"/(course|eclass|news|post)", re.I)


def school_domain(url):
    """xxx.edu.tw或其他網域的末三段，作為同校範圍。"""
    host = urlsplit(url).hostname or ""
    return ".".join(host.split(".")[-3:])


def classify(text):
    if PORTAL.search(text):
        return "portal"
    if ASSISTANCE.search(text):
        return "assistance"
    if AFFAIRS.search(text):
        return "student_affairs"
    return None


def page_signals(body):
    """回傳(標題與標題列文字, [(連結網址, 連結文字)])。"""
    soup = BeautifulSoup(body, "html.parser")
    heading = " ".join(node.get_text(" ", strip=True) for node in soup.select("title,h1"))
    links = [(anchor["href"], anchor.get_text(" ", strip=True)) for anchor in soup.select("a[href]")]
    return heading[:200], links


def next_links(links, base, domain, seen):
    """依層級由深到淺排序同校連結；只看連結文字，不猜路徑。"""
    ranked = []
    for href, label in links:
        level = classify(label)
        if not level or len(label) > MAX_NAV_LABEL:
            continue
        target = urljoin(base, href).split("#", 1)[0]
        parts = urlsplit(target)
        if FILE_PATH.search(parts.path) or NON_PORTAL_PATH.search(parts.path):
            continue
        if parts.scheme == "http":
            target = "https" + target[4:]
            parts = urlsplit(target)
        if parts.scheme != "https" or school_domain(target) != domain or target in seen:
            continue
        ranked.append((RANK[level], target, label[:40]))
    ranked.sort(key=lambda item: -item[0])
    return list(dict.fromkeys(ranked))


def fetch_page(fetcher, url, dead_hosts):
    """回傳(status, final_url, body)；連不上的網域記入dead_hosts並回傳失敗原因。"""
    host = urlsplit(url).hostname
    if host in dead_hosts:
        return dead_hosts[host], url, None
    fetcher.config["allowed_hosts"].append(host)
    try:
        response = fetcher.get(url, {}, BODY_LIMIT)
    except ScanError as error:
        if str(error) == "run_budget_exhausted":
            raise
        if str(error) == "transport_error":
            dead_hosts[host] = "transport_error"
        return str(error), url, None
    except subprocess.TimeoutExpired:
        dead_hosts[host] = "transport_timeout"
        return "transport_timeout", url, None
    return response["status"], response.get("url", url), response["body"]


def verify_school(fetcher, row, dead_hosts):
    """回傳最深一層可驗證頁面；預算用完往外丟，該校留到下一輪。"""
    checks, best, seen = {}, None, set()
    queue = []
    for level, field in SEEDS:
        url = row[field]
        if url and url not in seen:
            seen.add(url)
            queue.append((RANK[level], url, f"roster:{field}"))
    pages = 0
    while queue and pages < MAX_PAGES_PER_SCHOOL:
        queue.sort(key=lambda item: -item[0])
        rank, url, via = queue.pop(0)
        pages += 1
        status, final, body = fetch_page(fetcher, url, dead_hosts)
        checks[url] = status
        if status != 200 or body is None:
            continue
        heading, links = page_signals(body)
        level = classify(heading)
        confirmed = RANK[level] if level else 0
        # 名冊自稱的層級要由頁面標題佐證；學校頁面上的連結文字本身就是校方的標示，頁面可開即採信。
        found = min(rank, confirmed) if via.startswith("roster:") else rank
        if best is None or found > best["rank"]:
            best = {"rank": found, "url": final, "via": via, "heading": heading[:80]}
        if best["rank"] == RANK["portal"]:
            break
        for item in next_links(links, final, school_domain(final), seen)[:3]:
            seen.add(item[1])
            queue.append(item)
    level = next((name for name, value in RANK.items() if best and value == best["rank"]), None)
    return {"level": level, "url": best["url"] if best else None, "via": best["via"] if best else None,
            "heading": best["heading"] if best else None, "checks": checks}


def run(rows, config, previous, transport=None, on_progress=None):
    settings = {**config, "allowed_hosts": []}
    fetcher = Fetcher(settings, transport) if transport else Fetcher(settings)
    results, dead_hosts = dict(previous.get("results", {})), dict(previous.get("dead_hosts", {}))
    for row in rows:
        if row["id"] in results:
            continue
        try:
            results[row["id"]] = {"name": row["name"], "roster_url": row["url"],
                                  **verify_school(fetcher, row, dead_hosts)}
        except ScanError:
            break
        if on_progress:
            on_progress(results, dead_hosts, fetcher.count)
    return results, dead_hosts, fetcher.count


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    rows = json.loads(ROSTER.read_text(encoding="utf-8"))["rows"]
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    previous = json.loads(args.output.read_text(encoding="utf-8")) if args.output.exists() else {}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    base = previous.get("http_requests_total", 0)

    def save(results, dead_hosts, used):
        counts = {}
        for result in results.values():
            counts[str(result["level"])] = counts.get(str(result["level"]), 0) + 1
        report = {"checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "model_calls": 0,
                  "http_requests_total": base + used, "schools_done": len(results), "by_level": counts,
                  "dead_hosts": dead_hosts, "results": results}
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return report

    results, dead_hosts, used = run(rows, config, previous, on_progress=save)
    report = save(results, dead_hosts, used)
    print(json.dumps({k: report[k] for k in ("http_requests_total", "schools_done", "by_level")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
