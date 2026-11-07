"""逐一連線檢查候選來源網址；只記狀態與頁面標題，不存內文、不改資料。

沿用scan_sources.Fetcher的robots、單次請求預算、同站間隔及403／429暫停；分批執行，結果累積在ignored的work/。
"""
import argparse
import glob
import json
from pathlib import Path
import subprocess
import sys
from urllib.parse import urlsplit

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.scan_sources import Fetcher, ScanError

OUTPUT = ROOT / "work/discovery/candidate-sources.json"
BODY_LIMIT = 2_000_000


def collect(root=ROOT):
    """回傳{url: [{bundle, candidate_id}]}。"""
    urls = {}
    for path in sorted(glob.glob(str(Path(root) / "data/candidates/*.json"))):
        bundle = Path(path).stem
        for candidate in json.loads(Path(path).read_text(encoding="utf-8"))["candidates"]:
            url = candidate["source_metadata"]["url"]
            urls.setdefault(url, []).append({"bundle": bundle, "candidate_id": candidate["candidate_id"]})
    return urls


def check(fetcher, url, dead_hosts):
    """回傳單一網址結果；預算用完往外丟，留到下一輪。"""
    host = urlsplit(url).hostname
    if host in dead_hosts:
        return {"status": dead_hosts[host]}
    fetcher.config["allowed_hosts"].append(host)
    try:
        response = fetcher.get(url, {}, BODY_LIMIT)
    except ScanError as error:
        if str(error) == "run_budget_exhausted":
            raise
        if str(error) in ("transport_error", "robots_unavailable"):
            dead_hosts[host] = str(error)
        return {"status": str(error)}
    except subprocess.TimeoutExpired:
        dead_hosts[host] = "transport_timeout"
        return {"status": "transport_timeout"}
    result = {"status": response["status"], "final_url": response.get("url", url)}
    if response["status"] == 200 and b"<" in response["body"][:2048]:
        title = BeautifulSoup(response["body"], "html.parser").title
        result["title"] = title.get_text(" ", strip=True)[:100] if title else ""
    return result


def run(urls, config, previous, transport=None, on_progress=None):
    settings = {**config, "allowed_hosts": []}
    fetcher = Fetcher(settings, transport) if transport else Fetcher(settings)
    results, dead_hosts = dict(previous.get("results", {})), dict(previous.get("dead_hosts", {}))
    for url in urls:
        if url in results:
            continue
        try:
            results[url] = check(fetcher, url, dead_hosts)
        except ScanError:
            break
        if on_progress:
            on_progress(results, dead_hosts, fetcher.count)
    return results, dead_hosts, fetcher.count


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    urls = collect()
    config = json.loads((ROOT / "data/scan-sources.json").read_text(encoding="utf-8"))
    previous = json.loads(args.output.read_text(encoding="utf-8")) if args.output.exists() else {}
    base = previous.get("http_requests_total", 0)
    args.output.parent.mkdir(parents=True, exist_ok=True)

    def save(results, dead_hosts, used):
        report = {"http_requests_total": base + used, "model_calls": 0, "urls_total": len(urls),
                  "urls_done": len(results), "dead_hosts": dead_hosts, "results": results}
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return report

    results, dead_hosts, used = run(urls, config, previous, on_progress=save)
    report = save(results, dead_hosts, used)
    print(json.dumps({k: report[k] for k in ("http_requests_total", "urls_total", "urls_done")}))


if __name__ == "__main__":
    main()
