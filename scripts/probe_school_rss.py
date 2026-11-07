"""盤點78校獎助專區是否宣告RSS／Atom；試跑只寫ignored的work/，不改候選、台帳，也不開Issue。

沿用scan_sources.Fetcher的robots、單次請求預算、同站間隔及403／429暫停。
只讀獎助專區頁本身及其宣告的feed：不猜常見路徑、不進公告內頁、不呼叫模型。
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import urljoin, urlsplit
import xml.etree.ElementTree as ET

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.scan_sources import Fetcher, ScanError

ROSTER = ROOT / "data/source-expansion/university-source-inventory.json"
CONFIG = ROOT / "data/scan-sources.json"
OUTPUT = ROOT / "work/discovery/rss-probe.json"
KEYWORDS = ("獎助", "獎學金", "助學", "急難", "補助")
BODY_LIMIT = 2_000_000
FEED_HREF = re.compile(r"(rss|atom|/feed)", re.I)
FEED_TYPE = re.compile(r"(rss|atom)\+xml", re.I)


def find_feed_links(html, base):
    """回傳頁面宣告的feed網址：先取<link rel=alternate>，再取連結路徑含rss／atom／feed者。"""
    soup = BeautifulSoup(html, "html.parser")
    found = []
    for link in soup.select('link[rel~="alternate"][href]'):
        if FEED_TYPE.search(link.get("type", "")):
            found.append(urljoin(base, link["href"]))
    for anchor in soup.select("a[href]"):
        parts = urlsplit(urljoin(base, anchor["href"]))
        if parts.scheme in ("http", "https") and FEED_HREF.search(parts.path + "?" + parts.query):
            found.append(parts.geturl())
    return list(dict.fromkeys(found))


def feed_titles(body):
    """解析RSS／Atom標題；不是feed或含DTD時回傳None。"""
    if re.search(rb"<!(DOCTYPE|ENTITY)", body[:4096], re.I):
        return None
    try:
        root = ET.fromstring(body)
    except ET.ParseError:
        return None
    tag = root.tag.rsplit("}", 1)[-1].lower()
    if tag not in ("rss", "feed", "rdf"):
        return None
    titles = []
    for node in root.iter():
        if node.tag.rsplit("}", 1)[-1].lower() in ("item", "entry"):
            for child in node:
                if child.tag.rsplit("}", 1)[-1].lower() == "title" and child.text:
                    titles.append(child.text.strip())
                    break
    return titles


def probe_school(fetcher, row):
    """回傳單校結果；預算用完的ScanError往外丟，讓該校留到下一輪。"""
    url = row["url"]
    host = urlsplit(url).hostname
    try:
        page = fetcher.get(url, {}, BODY_LIMIT)
        if page["status"] != 200:
            return {"status": "page_unavailable", "reason": f"http_{page['status']}"}
        links = find_feed_links(page["body"].decode("utf-8", errors="replace"), page["url"])
        same_host = [link for link in links if urlsplit(link).hostname == host]
        if not same_host:
            return {"status": "no_feed", "other_host_links": len(links)}
        for link in same_host[:2]:
            feed = fetcher.get(link, {}, BODY_LIMIT)
            titles = feed_titles(feed["body"]) if feed["status"] == 200 else None
            if titles is not None:
                matched = [title for title in titles if any(word in title for word in KEYWORDS)]
                return {"status": "feed_found", "feed_url": link, "items": len(titles),
                        "keyword_items": len(matched), "keyword_samples": [t[:60] for t in matched[:3]]}
        return {"status": "no_feed", "rejected_links": len(same_host[:2])}
    except ScanError as error:
        if str(error) == "run_budget_exhausted":
            raise
        return {"status": "skipped", "reason": str(error)}
    except subprocess.TimeoutExpired:
        return {"status": "skipped", "reason": "transport_timeout"}


def run(rows, config, previous, transport=None):
    """處理尚無結果的學校直到預算用完；回傳累積結果。"""
    hosts = [urlsplit(row["url"]).hostname for row in rows]
    settings = {**config, "allowed_hosts": hosts}
    fetcher = Fetcher(settings, transport) if transport else Fetcher(settings)
    results = dict(previous)
    for row in rows:
        if row["id"] in results:
            continue
        try:
            results[row["id"]] = {"name": row["name"], "url": row["url"], **probe_school(fetcher, row)}
        except ScanError:
            break
    return results, fetcher.count


def summary(results, total):
    counts = {}
    for result in results.values():
        counts[result["status"]] = counts.get(result["status"], 0) + 1
    return {"schools_total": total, "schools_done": len(results), "by_status": counts}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    rows = json.loads(ROSTER.read_text(encoding="utf-8"))["rows"]
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    previous = json.loads(args.output.read_text(encoding="utf-8"))["results"] if args.output.exists() else {}
    results, used = run(rows, config, previous)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    report = {"probed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "model_calls": 0,
              "http_requests_this_run": used, "summary": summary(results, len(rows)), "results": results}
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"http_requests_this_run": used, **report["summary"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
