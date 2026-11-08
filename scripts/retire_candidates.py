"""把指定的候選卡從資料中撤下：卡片本身、手寫基準、時程觀察、來源鏈。

卡片內容留在 git 歷史，撤下的理由記在 --reason 指定的檔案（通常是 docs/audits 底下的查核紀錄）。
"""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.expand_sources import read, save
from scripts.propose_radar_update import HAND_BASELINE


def retire_from_batch(batch, ids, programs):
    """來源鏈文件可能被多張卡共用，只有所有卡都撤下才刪文件。"""
    documents = []
    for document in batch["documents"]:
        remaining = [i for i in document.get("candidate_ids", []) if i not in ids]
        if remaining or not document.get("candidate_ids"):
            documents.append({**document, "candidate_ids": remaining} if document.get("candidate_ids") else document)
    alive = {document["id"] for document in documents}
    edges = [e for e in batch["edges"] if e.get("program_key") not in programs and e["from"] in alive and e["to"] in alive]
    scopes = [s for s in batch.get("scopes", []) if (s["id"] if isinstance(s, dict) else s) not in programs]
    bindings = [b for b in batch.get("candidate_bindings", []) if b["candidate_id"] not in ids]
    updated = {**batch, "documents": documents, "edges": edges, "scopes": scopes, "candidate_bindings": bindings,
               "total_documents": len(documents), "total_edges": len(edges)}
    for report in updated.get("reports", []):
        if "verified_schemes" in report:
            report["verified_schemes"] = len(bindings)
    return updated


def retire(ids, root=ROOT):
    """回傳實際撤下的卡；不存在的 id 直接報錯，避免以為撤了其實沒有。"""
    ids, found, programs = set(ids), [], set()
    bundles = {}
    for path in sorted((root / "data/candidates").glob("*.json")):
        bundle = read(path)
        gone = [c for c in bundle["candidates"] if c["candidate_id"] in ids]
        if gone:
            found.extend(gone)
            programs |= {c["program_key"] for c in gone}
            bundles[path] = {**bundle, "candidates": [c for c in bundle["candidates"] if c["candidate_id"] not in ids]}
    missing = ids - {c["candidate_id"] for c in found}
    if missing:
        raise ValueError("unknown_candidate_ids: " + ", ".join(sorted(missing)[:5]))
    # 還有其他卡在用的方案，來源鏈要留著。
    still_used = {c["program_key"] for bundle in bundles.values() for c in bundle["candidates"]}
    for path in sorted((root / "data/candidates").glob("*.json")):
        if path not in bundles:
            still_used |= {c["program_key"] for c in read(path)["candidates"]}
    programs -= still_used
    for path, bundle in bundles.items():
        save(path, bundle)
    baseline = read(root / HAND_BASELINE)
    hand_sources = {c["source_metadata"]["source_id"] for c in found if c["candidate_id"] in set(baseline["candidate_ids"])}
    save(root / HAND_BASELINE, {**baseline, "candidate_ids": [i for i in baseline["candidate_ids"] if i not in ids]})
    for path in sorted((root / "data").glob("*temporal-observations.json")):
        data = read(path)
        if any(i in data["records"] for i in ids):
            save(path, {**data, "records": {k: v for k, v in data["records"].items() if k not in ids}})
    registry_path = root / "data/source-chain-batches/batch-registry.json"
    registry = read(registry_path)
    for entry in registry["batches"]:
        path = root / entry["file"]
        batch = read(path)
        if "candidate_bindings" in batch and any(b["candidate_id"] in ids for b in batch["candidate_bindings"]):
            batch = retire_from_batch(batch, ids, programs)
            save(path, batch)
            entry.update(documents=batch["total_documents"], edges=batch["total_edges"], candidates=len(batch["candidate_bindings"]))
    # 沒有卡片在用的來源不再排程掃描，否則連不上的網址會一直吃掉每輪的請求額度。
    config_path = root / "data/scan-sources.json"
    config = read(config_path)
    used = {c["source_metadata"]["source_id"] for path in (root / "data/candidates").glob("*.json") for c in read(path)["candidates"]}
    orphaned = {c["source_metadata"]["source_id"] for c in found} - used
    # 手寫卡的 profile（標題、選擇器）沒驗證過。卡撤掉後它就不再被當成手寫來源排除，
    # 提交流程遇到同網址會拿它把首頁命名成那個方案，所以標成人工清單，流程不再採用。
    def retired(source):
        if source["id"] not in orphaned:
            return source
        return {**source, "enabled": False, **({"automation": "not_enabled"} if source["id"] in hand_sources else {})}
    save(config_path, {**config, "sources": [retired(s) for s in config["sources"]]})
    save(registry_path, {**registry, "total_documents": sum(e["documents"] for e in registry["batches"]), "total_edges": sum(e["edges"] for e in registry["batches"]),
                         "total_schemes_covered": sum(e["candidates"] for e in registry["batches"])})
    return found


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ids", type=Path, required=True, help="JSON 陣列：要撤下的 candidate_id")
    args = parser.parse_args()
    found = retire(json.loads(args.ids.read_text(encoding="utf-8")))
    print(json.dumps({"retired": len(found)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
