"""各家模型 API 目前提供的型號清單，寫成 status/model-catalog.json，給模型呼叫與其他 agent 查用。

- 只查各家的 /models 清單，不呼叫模型、不送任何資料；沿用 audit_providers.audit_provider（不輸出金鑰）。
- 只寫穩定的欄位：型號清單、設定的型號還在不在、計費政策。不寫查詢時間與流量限制標頭，
  所以清單沒變時檔案不變，workflow 不提交。
- 打 API 發現型號不對時，手動跑一次 model-catalog workflow 就會更新。
"""
import argparse
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.audit_providers import audit_provider
from scripts.providers import PROVIDERS

OUTPUT = ROOT / "status/model-catalog.json"
KEEP = ("catalog_status", "configured_model", "model_present", "model_count", "model_ids", "zero_price_models", "selected_model")


def catalog(environ=os.environ, audit=audit_provider):
    providers = {}
    for name in sorted(PROVIDERS):
        row = audit(name, environ, probe=False)
        entry = {key: row[key] for key in KEEP if key in row}
        entry["inference_policy"] = PROVIDERS[name]["inference_policy"]
        entry["key_present"] = bool(row.get("key_present"))
        providers[name] = entry
    return {"schema_version": "model-catalog/1",
            "note": "型號清單來自各家 /models；在清單裡不代表能免費推論，計費以 inference_policy 為準。查不到時保留狀態碼，不補值。",
            "free_providers": sorted(n for n, p in PROVIDERS.items() if p["inference_policy"] in ("user_reported_free", "zero_price_free_only")),
            "providers": providers}


def write(document, path=OUTPUT):
    """內容有變才寫檔；回傳是否有變。"""
    text = json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    path = Path(path)
    if path.exists() and path.read_text(encoding="utf-8") == text:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    document = catalog()
    changed = write(document, args.output)
    summary = {n: (p.get("catalog_status"), p.get("model_count"), p.get("model_present")) for n, p in document["providers"].items()}
    print(json.dumps({"changed": changed, "providers": summary}, ensure_ascii=False))


if __name__ == "__main__":
    main()
