"""把手寫卡的來源逐一送進提交流程，彙整成一份待審提案。可中斷、可續跑。

只連公開網址、遵守 robots、不呼叫模型。輸出留在 --output，不寫正式資料；上架仍須人工套用提案並合併 PR。
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import re
import sys
import time
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.audit_sources import canonical_url
from scripts.expand_sources import DENIED, INTAKE_OPTIONS, read, save
from scripts.intake_source import IntakeRejected, validated_url
from scripts.propose_radar_update import ACCEPT, HAND_BASELINE, write_proposal
from scripts.run_source_intake import process
from scripts.scan_sources import digest, node_get

# 首頁連結很多，一次全跟太久；超過的會記在 links_skipped。
BATCH_OPTIONS = {**INTAKE_OPTIONS, "max_children": 20}
CATEGORIES = {"student-perks": "ai", "emergency-relief-aid": "living", "k12-scholarships": "living"}
TARGET_SPACING_SECONDS = 3


def hand_targets(root=ROOT):
    """回傳手寫卡的來源（去重），含它們所在的候選檔與標題，方便事後對照。"""
    known = set(read(root / HAND_BASELINE)["candidate_ids"])
    targets = {}
    for path in sorted((root / "data/candidates").glob("*.json")):
        for card in read(path)["candidates"]:
            if card["candidate_id"] in known:
                url = canonical_url(card["source_metadata"]["url"])
                row = targets.setdefault(url, {"url": url, "category": CATEGORIES.get(path.stem, "scholarship"), "cards": []})
                row["cards"].append({"candidate_id": card["candidate_id"], "title": card["title"], "program_key": card["program_key"], "bundle": path.stem})
    return list(targets.values())


def load_targets(path, include_hand_urls=False):
    """研究查到的網址：[{url, category}]。重複的只跑一次，手寫卡已跑過的網址預設不用再跑。"""
    seen = set() if include_hand_urls else {row["url"] for row in hand_targets()}
    targets = []
    for row in read(path):
        url = canonical_url(row["url"])
        if url not in seen:
            seen.add(url)
            targets.append({"url": url, "category": row["category"], "cards": []})
    return targets


def spread(rows, count):
    """抽樣時平均取，才會涵蓋不同候選檔。"""
    if not count or count >= len(rows):
        return rows
    return [rows[index * len(rows) // count] for index in range(count)]


def source_dir(output, url):
    return Path(output) / "sources" / digest(url)[:16]


def run(output, targets, transport=node_get, max_requests=3000, spacing=TARGET_SPACING_SECONDS, progress=print, options=BATCH_OPTIONS):
    output = Path(output)
    used, paused = 0, {}
    for row in targets:
        directory, url = source_dir(output, row["url"]), row["url"]
        done = directory / "outcome.json"
        if done.exists():
            used += read(done).get("http_requests", 0)
            continue
        if used >= max_requests:
            progress(f"stop: reached {max_requests} requests; rerun to continue")
            break
        host = urlsplit(url).hostname
        outcome = {"url": url, "cards": row["cards"], "http_requests": 0, "candidates": [], "statuses": [], "links_skipped": 0}
        try:
            if host in paused:
                raise IntakeRejected("host_paused:" + paused[host])
            valid = validated_url(url)
            result = process({"issue": digest(url)[:12], "url": valid, "category": row["category"]}, directory, transport=transport,
                             progress=lambda *a, **k: None, options=options, propose=False)
            outcome.update(http_requests=result["http_requests"], candidates=result["candidates"], links_skipped=result["links_skipped"],
                           statuses=[r["status"] for r in result["records"]],
                           not_card_reasons=[r["not_card_reason"] for r in result["records"] if r.get("not_card_reason")])
            first = result["records"][0]["status"] if result["records"] else ""
            if DENIED.search(first) and first != "robots_denied":
                paused[host] = first
        except IntakeRejected as error:
            outcome["statuses"] = [str(error)]
        except Exception as error:  # 單一來源失敗不能中斷整批；原因記下來。
            outcome["statuses"] = ["unexpected_" + type(error).__name__]
        save(done, outcome)
        used += outcome["http_requests"]
        progress(json.dumps({"url": url, "requests": used, "statuses": Counter(outcome["statuses"]), "candidates": len(outcome["candidates"])}, ensure_ascii=False), flush=True)
        time.sleep(spacing)
    return summarize(output, targets)


def outcomes(output, targets):
    return [read(source_dir(output, row["url"]) / "outcome.json") for row in targets if (source_dir(output, row["url"]) / "outcome.json").exists()]


def summarize(output, targets):
    rows = outcomes(output, targets)
    accepted = [r for r in rows if any(c["status"] in ACCEPT for c in r["candidates"])]
    summary = {"targets": len(targets), "finished": len(rows), "with_accepted_candidates": len(accepted), "no_candidate": len(rows) - len(accepted),
               "hand_cards_on_finished": sum(len(r["cards"]) for r in rows), "hand_cards_with_accepted_source": sum(len(r["cards"]) for r in accepted),
               "candidates": sum(len(r["candidates"]) for r in rows), "http_requests": sum(r["http_requests"] for r in rows),
               "links_skipped": sum(r["links_skipped"] for r in rows), "model_calls": 0,
               "statuses": dict(Counter(re.sub(r":.*", "", s) for r in rows for s in r["statuses"]).most_common()),
               # 讀到了卻沒成卡的頁面卡在哪一關。
               "not_card_reasons": dict(Counter(x for r in rows for x in r.get("not_card_reasons", [])).most_common())}
    save(Path(output) / "summary.json", summary)
    return summary


def build_proposal(output, targets, preview=True):
    """彙整候選成一份提案。只有真的抽到候選的來源，才會取代它的手寫卡。"""
    output = Path(output)
    candidates, profiles, config = {}, {}, read(ROOT / "data/scan-sources.json")
    replaced, base, temporal = [], None, {}
    for row in outcomes(output, targets):
        report = source_dir(output, row["url"]) / "report"
        if not (report / "structured-candidates.json").exists():
            continue
        bundle = read(report / "structured-candidates.json")
        base = base or bundle
        accepted = [c for c in bundle["candidates"] if c["verification"]["status"] in ACCEPT]
        if accepted:
            replaced.append(row["url"])
        candidates.update({c["candidate_id"]: c for c in bundle["candidates"]})
        if (report / "temporal-records.json").exists():
            temporal.update(read(report / "temporal-records.json"))
        state = read(source_dir(output, row["url"]) / "state.json")
        profiles.update(state["profiles"])
        config["allowed_hosts"] = sorted(set(config["allowed_hosts"]) | {urlsplit(p["url"]).hostname for p in state["profiles"].values()})
    if not base:
        raise ValueError("no_candidates_to_propose")
    known = {source["id"] for source in config["sources"]}
    config["sources"] = config["sources"] + [p for key, p in profiles.items() if key not in known]
    return write_proposal({**base, "candidates": list(candidates.values())}, config, output / "proposal", preview=preview, replaced_urls=replaced, temporal=temporal)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--sample", type=int, help="只跑平均抽出的 N 個來源")
    parser.add_argument("--targets", type=Path, help="改跑這份網址清單，不跑手寫卡的來源")
    parser.add_argument("--include-hand-urls", action="store_true", help="清單裡手寫卡用過的網址也要跑")
    parser.add_argument("--max-requests", type=int, default=3000)
    parser.add_argument("--propose", action="store_true", help="不抓取，只把已跑完的結果彙整成提案")
    args = parser.parse_args()
    if args.output.resolve().is_relative_to(ROOT / "data"):
        parser.error("write review artifacts outside data")
    targets = spread(load_targets(args.targets, args.include_hand_urls) if args.targets else hand_targets(), args.sample)
    if args.propose:
        print(json.dumps(build_proposal(args.output, targets), ensure_ascii=False))
    else:
        print(json.dumps(run(args.output, targets, max_requests=args.max_requests), ensure_ascii=False))


if __name__ == "__main__":
    main()
