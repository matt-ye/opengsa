"""每輪掃描後，把每個來源的狀態寫成 status/pipeline.csv 與 status/pipeline.json。

兩份檔案來自同一份資料，只是格式不同，用來比較哪種比較好讀：
- CSV 一列一個來源，只放短欄位。GitHub 只把 512 KB 以下的 CSV 顯示成表格，1000 個來源大約每列要在 500 bytes 以內。
- JSON 多放資訊鏈：每個來源連到的附件各自的狀態。

檔案裡不放執行時間，只放內容雜湊的前 12 碼。來源沒變，檔案就不變，workflow 也就不會提交。
只由排程掃描的 bot 寫入；人工不要改，改了下一輪也會被蓋掉。
"""
import argparse
import csv
import io
import json
from pathlib import Path
import sys
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
FIELDS = ("source_id", "host", "enabled", "status", "failures", "pending", "attachments", "revision")


def document_status(url, state):
    """ok：上次讀到了；not_checked：還沒輪到；其他是上次失敗的原因。"""
    failure = state.get("failures", {}).get(url)
    if failure:
        return failure["status"], failure["count"]
    return ("ok" if url in state.get("documents", {}) else "not_checked"), 0


def rows(config, state):
    pending = {}
    for item in state.get("pending", {}).values():
        pending[item["source_id"]] = pending.get(item["source_id"], 0) + 1
    out = []
    for source in config["sources"]:
        url = source["url"]
        document = state.get("documents", {}).get(url, {})
        enabled = source.get("enabled", True)
        status, failures = document_status(url, state) if enabled else ("disabled", 0)
        chain = []
        for item in document.get("attachments", []):
            child_status, child_failures = document_status(item["url"], state)
            chain.append({"url": item["url"], "status": child_status, "failures": child_failures,
                          "revision": (state.get("documents", {}).get(item["url"], {}).get("semantic_sha256") or "")[:12]})
        out.append({"source_id": source["id"], "host": urlsplit(url).hostname, "enabled": enabled, "status": status,
                    "failures": failures, "pending": pending.get(source["id"], 0), "attachments": len(chain),
                    "revision": (document.get("semantic_sha256") or "")[:12], "url": url, "chain": chain})
    return out


def render(config, state):
    table = rows(config, state)
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(FIELDS)
    for row in table:
        writer.writerow(["true" if v is True else "false" if v is False else v for v in (row[k] for k in FIELDS)])
    document = {"schema": "pipeline-status/1", "sources": table}
    return buffer.getvalue(), json.dumps(document, ensure_ascii=False, indent=1) + "\n"


def write(config, state, output):
    """回傳有沒有改到檔案。"""
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    changed = False
    for name, text in zip(("pipeline.csv", "pipeline.json"), render(config, state)):
        path = output / name
        if not path.exists() or path.read_text(encoding="utf-8") != text:
            path.write_text(text, encoding="utf-8", newline="\n")
            changed = True
    return changed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "data/scan-sources.json")
    parser.add_argument("--state", type=Path, default=ROOT / "work/scanner/state.json")
    parser.add_argument("--output", type=Path, default=ROOT / "status")
    args = parser.parse_args()
    if not args.state.exists():
        print("no scan state; nothing written")
        return
    config = json.loads(args.config.read_text(encoding="utf-8"))
    state = json.loads(args.state.read_text(encoding="utf-8"))
    print("changed" if write(config, state, args.output) else "unchanged")


if __name__ == "__main__":
    sys.exit(main())
