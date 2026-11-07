"""把已知手寫候選改由真實來源重萃；結果只累積在work/，不改候選資料，由另一步一次套用。

沿用scan_sources.Fetcher的robots、單輪請求預算、同站間隔及403／429暫停；分批執行可接續。
抓不到、頁面對不上或檢核失敗就如實記錄，不補值、不沿用舊內容。
"""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import glob
import json
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import urlsplit

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.check_provenance import BASELINE, problems
from scripts.extract_candidates import create_model_adapter_from_env, extract_from_in_memory_blocks
from scripts.scan_sources import Fetcher, ScanError, digest, html_document, pdf_document
from scripts.temporal_model import (
    VERIFIED_MODELS_BY_HOST,
    VERIFIED_PROVIDER_CAPABILITIES,
    _configure_single_adapter,
    build_model_limits,
    install_tokenizer,
    make_token_counter,
)

OUTPUT = ROOT / "work/reextract/results.json"
BODY_LIMIT = 10 * 1024 * 1024
UNAVAILABLE_PAGE = re.compile(r"404|not found|找不到|頁面不存在|查無|無此頁|請先登入|please log ?in|error page", re.I)
CONTENT_SELECTORS = ("main", "article", "[role=main]", "#content", ".content")
MODEL_RETRY_STATUSES = ("extracted", "failed_checks")  # 這些頁面抓得到內容，模型才有東西可讀
MODEL_ROUND = 2  # 調整模型設定後加一，讓先前的結果重跑
PRIVACY_SKIP = "source_sanitization_requires_review"
MODEL_INPUT_LIMIT = 6000  # 時間萃取的2200對全欄位太小：共用上下文就會超過預算
MIN_NAME_MATCH = 4
MIN_CONTENT_CHARS = 80  # html_document對更短的內容回報解析失敗


class SameSiteHosts(list):
    """允許同站網域（末三段相同），讓www轉址可用；跨站轉址仍被safe_url擋下。"""

    def __contains__(self, host):
        site = ".".join((host or "").split(".")[-3:])
        return any(".".join(item.split(".")[-3:]) == site for item in self)


def longest_common_run(name, text):
    """name與text最長連續相同字元數；用來確認頁面真的在談這個方案。"""
    best, cleaned = 0, re.sub(r"\s+", "", text)
    name = re.sub(r"\s+", "", name)
    for start in range(len(name)):
        size = best + 1
        while start + size <= len(name) and name[start:start + size] in cleaned:
            best = size
            size += 1
    return best


def page_problem(heading, text, names):
    """回傳頁面不可用的原因；None代表可以萃取。"""
    if UNAVAILABLE_PAGE.search(heading):
        return "soft_unavailable_page"
    if max((longest_common_run(name, heading + text) for name in names if name), default=0) < MIN_NAME_MATCH:
        return "page_does_not_mention_programme"
    return None


def content_source(source, body):
    """通用profile的body會把側欄算進去；頁面有主要內容區時只讀那一塊。"""
    soup = BeautifulSoup(body, "html.parser")
    for selector in CONTENT_SELECTORS:
        node = soup.select_one(selector)
        if node and len(node.get_text(strip=True)) >= MIN_CONTENT_CHARS:
            return {**source, "body_selector": selector}
    return {**source, "body_selector": "body"}


def reextract(fetcher, candidate, source, now, adapter=None):
    """回傳單筆結果；預算用完往外丟，留到下一輪。"""
    url = candidate["source_metadata"]["url"]
    is_pdf = source.get("format") == "pdf" or urlsplit(url).path.lower().endswith(".pdf")
    fetcher.config["allowed_hosts"].append(urlsplit(url).hostname)
    try:
        response = fetcher.get(url, {}, BODY_LIMIT)
    except ScanError as error:
        if str(error) == "run_budget_exhausted":
            raise
        return {"status": "source_unavailable", "reason": str(error)}
    except subprocess.TimeoutExpired:
        return {"status": "source_unavailable", "reason": "transport_timeout"}
    if response["status"] != 200:
        return {"status": "source_unavailable", "reason": f"http_{response['status']}"}
    revision = digest(response["body"])
    try:
        if is_pdf:
            blocks, heading = pdf_document(response["body"]), ""
        else:
            scoped = content_source(source, response["body"])
            blocks, _ = html_document(response["body"], scoped, response["url"], fetcher.config["allowed_hosts"])
            title = BeautifulSoup(response["body"], "html.parser").title
            heading = title.get_text(" ", strip=True) if title else ""
    except ScanError as error:
        return {"status": "parse_failed", "reason": str(error), "revision_id": revision}
    text = " ".join(block["text"] for block in blocks)
    problem = page_problem(heading, text, (candidate["title"], source.get("title", "")))
    if problem:
        return {"status": "page_mismatch", "reason": problem, "revision_id": revision, "page_title": heading[:80]}
    extracted = extract_from_in_memory_blocks(source, blocks, revision_id=revision, observed_at=now,
                                              url=response["url"], model_adapter=adapter)
    if not extracted:
        return {"status": "no_extraction", "revision_id": revision, "page_title": heading[:80]}
    fresh = deepcopy(extracted[0])
    # 維持候選ID，網站連結與feed的guid才不會變；內容一律來自這次萃取。
    fresh["candidate_id"] = candidate["candidate_id"]
    found = problems(fresh)
    passed = fresh["verification"]["status"] != "failed_automated_checks" and not found
    row = {"status": "extracted" if passed else "failed_checks", "revision_id": revision, "page_title": heading[:80],
           "problems": found[:5], "verification": fresh["verification"]["status"],
           "model_skip_reason": model_skip_reason(fresh["verification"].get("warnings", [])),
           "evidence": len(fresh["field_evidence"]), "extra_documents": len(extracted) - 1}
    if passed:
        row["candidate"] = fresh
    return row


def known_candidates(root=ROOT):
    known = set(json.loads(BASELINE.read_text(encoding="utf-8"))["candidate_ids"])
    rows = []
    for path in sorted(glob.glob(str(Path(root) / "data/candidates/*.json"))):
        rows.extend(c for c in json.loads(Path(path).read_text(encoding="utf-8"))["candidates"] if c["candidate_id"] in known)
    return rows


def model_pending(row):
    """這一回合還沒處理過就要再跑；隱私過濾擋下的不重試，那不是額度問題。"""
    if row.get("model_skipped") == PRIVACY_SKIP:
        return False
    return row["status"] in MODEL_RETRY_STATUSES and row.get("model_round") != MODEL_ROUND


def configure_model(adapter):
    """通用萃取也要先設定模型容量與token計數，否則每份文件都會被model_capabilities_required跳過。

    field_scope留空：這是全欄位萃取，不是只看時間；隱私過濾因此維持嚴格，不放寬。
    """
    host = urlsplit(adapter.base_url).hostname
    provider = VERIFIED_MODELS_BY_HOST.get((host, adapter.model))
    if not provider:
        raise SystemExit(f"model_unavailable: 未核實的模型 {adapter.model}")
    spec = VERIFIED_PROVIDER_CAPABILITIES[provider]
    tokenizer = None
    if spec.get("uses_qwen_tokenizer"):
        path = ROOT / "work/tokenizers/qwen3.8-27b.json"
        install_tokenizer(path)
        from tokenizers import Tokenizer
        tokenizer = Tokenizer.from_file(str(path))
    _configure_single_adapter(adapter, provider, spec, make_token_counter(tokenizer), max_calls=24)
    adapter.field_scope = ()
    adapter.model_limits = build_model_limits(adapter.model, context_limit=spec["context_limit"],
                                              output_limit=spec["output_limit"], input_limit=MODEL_INPUT_LIMIT)
    return adapter


def model_skip_reason(warnings):
    for warning in warnings:
        if warning.startswith("model_skipped:"):
            return warning.split(":", 1)[1]
    if "external_model_skipped_for_hash_only_source" in warnings:
        return "hash_only_source"
    return None


def run(candidates, config, previous, transport=None, on_progress=None, now=None, adapter=None):
    now = now or datetime.now(timezone.utc).isoformat(timespec="seconds")
    settings = {**config, "allowed_hosts": SameSiteHosts()}
    fetcher = Fetcher(settings, transport) if transport else Fetcher(settings)
    profiles = {source["id"]: source for source in config["sources"]}
    results = dict(previous)
    for candidate in candidates:
        cid = candidate["candidate_id"]
        if cid in results and not (adapter and model_pending(results[cid])):
            continue
        # 額度或流量上限到了就停：不能讓這一筆靜默退回純規則，又被記成模型跑過。
        if adapter and (adapter.rate_limited_429 or adapter.calls >= adapter.max_calls):
            break
        calls_before = adapter.calls if adapter else 0
        rejected_before = adapter.rejected_claims if adapter else 0
        sid = candidate["source_metadata"]["source_id"]
        # 通用預設：不要求標記、不追PDF；已登記的profile設定優先。
        source = {"id": sid, "title": candidate["title"], "url": candidate["source_metadata"]["url"],
                  "evidence_mode": "short_excerpt", "body_selector": "body", "required_markers": [],
                  "pdf_include": [], "max_pdfs": 0, **profiles.get(sid, {}),
                  # 部分手加profile的分類值不合schema；分類沿用候選，不影響內容欄位。
                  "category": candidate.get("category", "phd_research"),
                  "resource_kind": candidate.get("resource_kind", "scholarship"),
                  "scope": candidate.get("scope", "nationwide")}
        try:
            row = {"url": candidate["source_metadata"]["url"], **reextract(fetcher, candidate, source, now, adapter)}
        except ScanError:
            break
        if adapter:
            if adapter.rate_limited_429:
                break
            row["model_calls"] = adapter.calls - calls_before
            row["model_round"] = MODEL_ROUND
            # 只記數量與進度，不保存模型回覆或來源原文。
            row["model_rejected_claims"] = adapter.rejected_claims - rejected_before
            prep = adapter.last_preparation or {}
            row["model_chunks"] = [prep.get("chunks_completed"), prep.get("chunks_planned")]
            row["model_tokens_total"] = adapter.total_tokens
            accepted = (row.get("candidate") or {}).get("field_evidence", [])
            row["model_accepted_claims"] = sum(e.get("extraction_method") == "model_adapter" for e in accepted)
            reason = row.get("model_skip_reason")
            if not row["model_calls"] and reason == "model_call_budget_insufficient_for_complete_task" and adapter.calls:
                break  # 這一輪額度不夠完整讀這份文件，留到額度全滿的下一輪。
            if not row["model_calls"]:
                row["model_skipped"] = reason or row["status"]
        results[cid] = row
        if on_progress:
            on_progress(results, fetcher.count)
    return results, fetcher.count


def summarize(results, total):
    counts = {}
    for row in results.values():
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    return {"candidates_total": total, "candidates_done": len(results), "by_status": counts,
            "model_pending": sum(model_pending(row) for row in results.values())}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--retry-status", action="append", default=[], help="重跑這些狀態的候選")
    parser.add_argument("--model-round", action="store_true", help="用模型重跑抓得到內容的候選；模型不可用就失敗")
    args = parser.parse_args()
    candidates = known_candidates()
    config = json.loads((ROOT / "data/scan-sources.json").read_text(encoding="utf-8"))
    previous = json.loads(args.output.read_text(encoding="utf-8")) if args.output.exists() else {}
    base = previous.get("http_requests_total", 0)
    adapter = None
    if args.model_round:
        adapter = create_model_adapter_from_env()
        if not adapter.enabled:
            raise SystemExit("model_unavailable: 模型未啟用，不以純規則充當模型結果")
        configure_model(adapter)
    base_calls = previous.get("model_calls", 0)
    previous["results"] = {k: v for k, v in previous.get("results", {}).items() if v["status"] not in args.retry_status}
    args.output.parent.mkdir(parents=True, exist_ok=True)

    def save(results, used):
        report = {"http_requests_total": base + used, "model_calls": base_calls + (adapter.calls if adapter else 0),
                  "published": False,
                  "summary": summarize(results, len(candidates)), "results": results}
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return report

    results, used = run(candidates, config, previous.get("results", {}), on_progress=save, adapter=adapter)
    report = save(results, used)
    print(json.dumps({"http_requests_total": report["http_requests_total"], "model_calls": report["model_calls"],
                      **report["summary"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
