"""真實頁面評測集：改萃取規則後，用 data/eval/page-expectations.json 的預期檢查有沒有退步。

- 每個網址照提交流程抓取、萃取（模型關閉），再經提案時同樣的不成卡過濾（distinct_named_cards）。
- 正例：要有標題含指定字的卡，類別、截止日符合；禁止的標題不能出現。
- 反例（no_card）：不能成卡，且卡在指定的那一關。改善後成卡會標成「變動」，請人確認後更新預期，不算退步。
- 原始回應快取在 work/eval/page-cache（不進 repo：來源原文不存檔）。--offline 只用快取，不連外。

有退步時結束碼為 1。
"""
import argparse
import base64
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.expand_sources import NOT_CARD_REASONS, read, save
from scripts.intake_source import IntakeRejected, validated_url
from scripts.propose_radar_update import ACCEPT, distinct_named_cards
from scripts.run_hand_replacement import BATCH_OPTIONS
from scripts.run_source_intake import process
from scripts.scan_sources import ScanError, digest, node_get

GOLD = ROOT / "data/eval/page-expectations.json"


def cached(cache, offline):
    """把抓取結果存在本機，重跑時不再連外；--offline 時沒快取就當成抓不到。"""
    cache.mkdir(parents=True, exist_ok=True)

    def transport(url, headers, limit):
        path = cache / (digest(url)[:24] + ".json")
        if path.exists():
            saved = read(path)
            return {**saved, "body": base64.b64decode(saved["body"])}
        if offline:
            raise ScanError("not_cached")
        response = node_get(url, headers, limit)
        save(path, {**response, "body": base64.b64encode(response["body"]).decode()})
        return response
    return transport


def check(entry, cards, reason):
    """回傳 (狀態, 說明)。狀態：pass、regression、changed。"""
    expect = entry["expect"]
    titles = [c["title"] for c in cards]
    if expect.get("no_card"):
        if cards:
            return "changed", "預期不成卡，現在成卡：" + "、".join(titles[:3])
        if reason != expect.get("reason"):
            return "changed", f"仍不成卡，但卡在 {reason}（預期 {expect.get('reason')}）"
        return "pass", NOT_CARD_REASONS.get(reason, reason or "")
    problems = []
    hit = [c for c in cards if expect["title_contains"] in c["title"]]
    if not hit:
        problems.append(f"沒有標題含「{expect['title_contains']}」的卡（有：{'、'.join(titles[:4]) or '無'}；卡在 {reason}）")
    if hit and expect.get("card_category") and not any(c["category"] == expect["card_category"] for c in hit):
        problems.append(f"類別不是 {expect['card_category']}（是 {hit[0]['category']}）")
    if hit and expect.get("deadline_prefix"):
        deadlines = [s["deadline"].get("value") or "" for c in hit for s in c["schedule"]["steps"]]
        if not any(d.startswith(expect["deadline_prefix"]) for d in deadlines):
            problems.append(f"截止日不是 {expect['deadline_prefix']}（是 {[d for d in deadlines if d] or '無'}）")
    for word in entry.get("forbid_titles_containing", []):
        problems.extend(f"不該成卡的「{t}」成卡了" for t in titles if word in t)
    for title in entry.get("forbid_titles_equal", []):
        problems.extend(f"不該成卡的「{t}」成卡了" for t in titles if t.strip() == title)
    return ("regression", "；".join(problems)) if problems else ("pass", "")


def evaluate(entry, output, transport):
    url = entry["url"]
    try:
        result = process({"issue": digest(url)[:12], "url": validated_url(url), "category": entry["category"]}, output,
                         transport=transport, progress=lambda *a, **k: None, options=BATCH_OPTIONS, propose=False)
    except (IntakeRejected, ScanError) as error:
        return [], str(error)
    bundle_path = Path(output) / "report/structured-candidates.json"
    cards = [c for c in read(bundle_path)["candidates"] if c["verification"]["status"] in ACCEPT] if bundle_path.exists() else []
    kept, _ = distinct_named_cards(cards)
    root = next((r for r in result["records"] if r["url"] == url), result["records"][0] if result["records"] else {})
    return kept, root.get("not_card_reason") or root.get("status")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "work/eval/pages")
    parser.add_argument("--cache", type=Path, default=ROOT / "work/eval/page-cache")
    parser.add_argument("--offline", action="store_true", help="只用快取，不連外")
    args = parser.parse_args()
    transport = cached(args.cache, args.offline)
    if args.offline:
        # 只讀快取時沒有連外，不需要對網站保持請求間隔。
        import scripts.expand_sources as expand
        from scripts.scan_sources import Fetcher

        class NoWait(Fetcher):
            def __init__(self, config, transport=node_get, **_):
                super().__init__(config, transport=transport, sleeper=lambda _: None)
        expand.Fetcher = NoWait
    rows = []
    for entry in read(GOLD)["pages"]:
        cards, reason = evaluate(entry, args.output / digest(entry["url"])[:16], transport)
        status, detail = check(entry, cards, reason)
        rows.append({"url": entry["url"], "status": status, "detail": detail})
        print(json.dumps(rows[-1], ensure_ascii=False), flush=True)
    counts = {s: sum(r["status"] == s for r in rows) for s in ("pass", "regression", "changed")}
    lines = [f"# 真實頁面評測\n\n通過 {counts['pass']}，退步 {counts['regression']}，變動 {counts['changed']}。\n", "| 狀態 | 網址 | 說明 |", "|---|---|---|"]
    lines.extend(f"| {r['status']} | {r['url'][:80]} | {r['detail'][:200]} |" for r in rows if r["status"] != "pass")
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    save(args.output / "report.json", {"counts": counts, "rows": rows})
    print(json.dumps(counts, ensure_ascii=False))
    sys.exit(1 if counts["regression"] else 0)


if __name__ == "__main__":
    main()
