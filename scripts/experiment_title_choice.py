"""實驗：標題去雜訊的「受限選擇」模型節點（第 1 階段，離線，不接排程）。

做法：把頁面上現成的標題字串（h1、og:title、<title>、h2/h3、名稱欄位，以及規則選的標題）列成選項，
請模型只回答選項編號，也可以回答 0（都不是方案名稱）。模型的輸出因此一定是原文裡的字串，不會編造。
只送標題字串，不送內文；依「模型＋選項」的雜湊快取，重跑不再呼叫。

頁面來自 data/eval/page-expectations.json，原始回應讀 work/eval/page-cache（先跑 scripts/evaluate_pages.py）。
輸出 work/experiments/title-choice/report.json：每頁的規則標題、模型標題與選項，交給人或代理盲評。
"""
import argparse
import base64
import json
import os
from pathlib import Path
import sys
import time
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from bs4 import BeautifulSoup

from scripts.expand_sources import clean_title, labelled_name, prepare_response, read, save
from scripts.providers import PROVIDERS, provider_settings
from scripts.scan_sources import digest

GOLD = ROOT / "data/eval/page-expectations.json"
PROMPT = ("你在整理台灣的獎助學金、急難救助與學生優惠資料。下面是同一個網頁上出現的標題字串。"
          "請選出最適合當作「這個方案名稱」的一個：要看得出是哪個單位的什麼方案，不要網站名稱、公告字樣或行銷標語。"
          "只回答選項編號；如果沒有一個是方案名稱，回答 0。")


def options(body, url, category):
    """頁面上現成的標題字串，去重後最多 12 個；規則選的標題排第一。"""
    soup = BeautifulSoup(body, "html.parser")
    response = {"body": body, "headers": {"content-type": "text/html"}, "url": url}
    rule = clean_title(prepare_response(response, {}, {urllib.parse.urlsplit(url).hostname}, link_limit=None,
                                        broad_links=True, category=category)["title"])
    found = [rule]
    meta = soup.select_one('meta[property="og:title"]')
    found += [meta.get("content", "")] if meta else []
    found += [soup.title.get_text(" ", strip=True)] if soup.title else []
    found += [n.get_text(" ", strip=True) for n in soup.select("h1,h2,h3")]
    found.append(labelled_name(soup, category))
    unique = []
    for text in found:
        text = " ".join(text.split())
        if 2 <= len(text) <= 120 and text not in unique:
            unique.append(text)
    return rule, unique[:12]


def ask(provider, choices, cache):
    base, model, key_env = provider_settings(provider, os.environ)
    listing = "\n".join(f"{i}. {text}" for i, text in enumerate(choices, 1))
    key = digest([model, PROMPT, listing])[:24]
    path = cache / f"{key}.json"
    if path.exists():
        return read(path), True
    payload = {"model": model, "temperature": 0, "max_tokens": 8,
               "messages": [{"role": "system", "content": PROMPT}, {"role": "user", "content": listing}]}
    request = urllib.request.Request(base + "/chat/completions", data=json.dumps(payload).encode(),
                                     headers={"Authorization": "Bearer " + os.environ[key_env], "Content-Type": "application/json",
                                              "User-Agent": "OpenGSA/0.2 (+https://github.com/matt-ye/opengsa)"})
    with urllib.request.urlopen(request, timeout=60) as response:
        data = json.loads(response.read())
    text = data["choices"][0]["message"]["content"].strip()
    digits = "".join(ch for ch in text if ch.isdigit())
    result = {"model": model, "raw": text[:40], "choice": int(digits) if digits else None, "usage": data.get("usage", {})}
    cache.mkdir(parents=True, exist_ok=True)
    save(path, result)
    return result, False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", default="groq")
    parser.add_argument("--cache", type=Path, default=ROOT / "work/eval/page-cache")
    parser.add_argument("--output", type=Path, default=ROOT / "work/experiments/title-choice")
    args = parser.parse_args()
    if PROVIDERS[args.provider]["inference_policy"] not in ("user_reported_free", "zero_price_free_only"):
        sys.exit("只用確認免費的模型")
    rows, calls = [], 0
    for entry in read(GOLD)["pages"]:
        path = args.cache / (digest(entry["url"])[:24] + ".json")
        if not path.exists():
            continue
        saved = read(path)
        body = base64.b64decode(saved["body"])
        if not body.lstrip()[:200].lower().startswith((b"<!doctype", b"<html", b"<?xml")) and b"<html" not in body[:2000].lower():
            continue
        rule, choices = options(body, entry["url"], entry["category"])
        result, cached = ask(args.provider, choices, args.output / "model-cache")
        calls += 0 if cached else 1
        if not cached:
            time.sleep(2)
        picked = choices[result["choice"] - 1] if result["choice"] and 0 < result["choice"] <= len(choices) else None
        rows.append({"url": entry["url"], "expected_contains": entry["expect"].get("title_contains"), "rule": rule,
                     "model": picked, "model_said": result["raw"], "options": choices})
        print(json.dumps({"url": entry["url"][:60], "rule": rule[:40], "model": (picked or "")[:40]}, ensure_ascii=False), flush=True)
    args.output.mkdir(parents=True, exist_ok=True)
    save(args.output / "report.json", {"provider": args.provider, "calls": calls, "rows": rows})
    print(json.dumps({"pages": len(rows), "calls": calls, "same": sum(r["rule"] == r["model"] for r in rows)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
