"""Manual Actions temporal replay + optional API proposals; never publishes."""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.temporal_reextract import read, save, replay, follow_attachments
from scripts.temporal_model import (
    model_for_temporal,
    model_review,
    source_allowed,
    TemporalBatchHarness,
    reconcile_verified_claims_to_policy,
    MICRO_CHUNK_INPUT_LIMIT,
    MICRO_CHUNK_OUTPUT_RESERVE,
    MODEL,
)
from scripts.temporal_tracks import (
    TRACKS,
    classify_source_track,
    evaluate_incremental_diff,
    parser_fingerprint,
    plan_track_execution,
)
from scripts.providers import PROVIDERS
from scripts.audit_providers import audit_provider, request_json
from scripts.scan_sources import digest
from scripts.time_policy import validate_temporal_snapshot


def select_sources(value, candidates, max_sources=8):
    ids = [part.strip() for part in value.split(",")]
    allowed = {c["source_metadata"]["source_id"] for c in candidates}
    if not 1 <= len(ids) <= max_sources or len(ids) != len(set(ids)) or any(sid not in allowed for sid in ids):
        raise ValueError("select_one_to_eight_unique_existing_source_ids")
    return ids


def resolve_action_sources(
    value,
    candidates,
    observations=None,
    track=None,
    max_sources=8,
    include_refinement=False,
    force_recheck=False,
    as_of=None,
):
    """Resolve either explicit source_ids or a track-based incremental batch."""
    token = (value or "").strip()
    if token.startswith("track:") or token in ("auto", "all_pending") or (track and token in ("", "auto", "track")):
        target_track = token.split(":", 1)[1] if token.startswith("track:") else (track or "auto")
        if token == "all_pending" and not track:
            target_track = "all"
        plan = plan_track_execution(
            candidates,
            observations=observations,
            track=target_track,
            include_refinement=include_refinement,
            force_recheck=force_recheck,
            max_sources=max_sources,
            as_of=as_of,
        )
        return plan["selected_source_ids"], plan

    ids = select_sources(token, candidates, max_sources=max_sources)
    selected_cands = [c for c in candidates if c["source_metadata"]["source_id"] in ids]
    current_parser = parser_fingerprint()
    decisions = [
        evaluate_incremental_diff(
            c,
            observations=observations,
            include_refinement=include_refinement,
            force_recheck=force_recheck,
            current_parser_sha256=current_parser,
        )
        for c in selected_cands
    ]
    tracks_present = sorted({d["track"] for d in decisions})
    plan = {
        "track": track if track in TRACKS else (tracks_present[0] if len(tracks_present) == 1 else "mixed"),
        "total_in_track": len(selected_cands),
        "run_candidate_count": sum(1 for d in decisions if d["should_run"]),
        "skip_candidate_count": sum(1 for d in decisions if not d["should_run"]),
        "selected_source_ids": ids,
        "decisions": decisions,
    }
    return ids, plan


def run(
    output,
    source_ids,
    attachments=False,
    adapter_factory=model_for_temporal,
    track=None,
    incremental_only=False,
    include_refinement=False,
    force_recheck=False,
    max_sources=8,
    checkpoint_path=None,
    apply_verified_model_rules=True,
    baseline_path=None,
):
    output = Path(output).resolve()
    if not output.is_relative_to(ROOT / "work") or output.exists():
        raise ValueError("new_work_output_required")
    bundle = read(ROOT / "data/candidates/source-review.json")
    baseline = read(Path(baseline_path) if baseline_path else (ROOT / "data/temporal-observations.json"))
    ids, track_plan = resolve_action_sources(
        source_ids,
        bundle["candidates"],
        observations=baseline,
        track=track,
        max_sources=max_sources,
        include_refinement=include_refinement,
        force_recheck=force_recheck,
    )
    if incremental_only:
        run_sids = {d["source_id"] for d in track_plan["decisions"] if d["should_run"]}
        ids = [sid for sid in ids if sid in run_sids]
    config = read(ROOT / "data/scan-sources.json")
    profiles = {p["id"]: p for p in config["sources"]}
    selected = [c for c in bundle["candidates"] if c["source_metadata"]["source_id"] in ids]
    output.mkdir(parents=True)
    mode = os.environ.get("OPENGSA_MODEL_MODE", "off")
    if mode not in ("off", "audit", "extract", "both"):
        raise ValueError("invalid_model_mode")
    provider = os.environ.get("OPENGSA_MODEL_PROVIDER", "groq")
    if provider != "auto_pool" and provider not in PROVIDERS:
        raise ValueError("invalid_provider")
    report = {
        "version": "temporal-action-1",
        "observed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "manual_only": True,
        "published": False,
        "human_approvals": 0,
        "source_ids": ids,
        "model_mode": mode,
        "model_provider": provider,
        "max_source_requests": 20,
        "max_inference_calls": 24,
        "schedule_track": track_plan["track"],
        "incremental_diff": {
            "total_evaluated": len(track_plan["decisions"]),
            "run_candidate_count": track_plan["run_candidate_count"],
            "skip_candidate_count": track_plan["skip_candidate_count"],
            "incremental_only": incremental_only,
            "decisions": track_plan["decisions"],
        },
        "provider_audit": None,
        "model_status": "off",
        "model_reviews": [],
    }
    report["provider_metadata_requests"] = 0
    adapter = None
    if mode != "off" and any(source_allowed(c, profiles[c["source_metadata"]["source_id"]]) for c in selected):
        def metadata_request(url, key, payload=None):
            report["provider_metadata_requests"] += 1
            return request_json(url, key, payload)

        if provider == "auto_pool":
            report["provider_audit"] = {"provider": "auto_pool", "catalog_status": "pool_mode"}
            try:
                adapter, report["model_status"] = adapter_factory(ROOT / "work/tokenizers/qwen3.8-27b.json")
            except (OSError, ValueError, ImportError):
                report["model_status"] = "tokenizer_or_capabilities_unavailable_rules_only"
        else:
            audit_env = dict(os.environ)
            if provider == "siliconflow" and not audit_env.get("OPENGSA_SILICONFLOW_REGION"):
                audit_env["OPENGSA_SILICONFLOW_REGION"] = "com"
            catalog = audit_provider(provider, audit_env, probe=False, requester=metadata_request)
            report["provider_audit"] = {
                k: catalog.get(k)
                for k in ("provider", "catalog_status", "configured_model", "model_present", "key_present")
            }
            if catalog.get("catalog_status") != "success" or not catalog.get("model_present"):
                report["model_status"] = "model_catalog_unavailable_rules_only"
            else:
                try:
                    adapter, report["model_status"] = adapter_factory(ROOT / "work/tokenizers/qwen3.8-27b.json")
                except (OSError, ValueError, ImportError):
                    report["model_status"] = "tokenizer_or_capabilities_unavailable_rules_only"
    elif mode != "off":
        report["model_status"] = "all_selected_sources_restricted_rules_only"

    harness = TemporalBatchHarness(
        adapter,
        checkpoint_path=Path(checkpoint_path) if checkpoint_path else (output / "checkpoint.json"),
    )
    harness.pre_batch_hook({"planned_count": len(selected)})
    verified_by_candidate = {}

    def on_document(candidate, blocks, revision, observed, doc_url=None, doc_raw_sha256=None):
        profile = profiles[candidate["source_metadata"]["source_id"]]
        try:
            row = harness.run_source(candidate, profile, blocks, revision)
            if doc_url:
                row["document_url"] = doc_url
                row["document_revision_id"] = revision
                row["document_raw_sha256"] = doc_raw_sha256
        except Exception as error:
            # Never log exception text: an endpoint can echo headers or source data.
            row = {
                "candidate_id": candidate["candidate_id"],
                "source_id": profile["id"],
                "status": "model_review_failed_rules_retained",
                "error_type": type(error).__name__,
                "claims": [],
            }
        report["model_reviews"].append(row)
        if row.get("claims"):
            verified_by_candidate.setdefault(candidate["candidate_id"], []).append(row)
        save(output / "report.json", report)

    if ids:
        state = replay(output / "rules", source_ids=ids, max_round_requests=20, on_document=on_document)
        if attachments and state["http_requests"] < 20:
            state = follow_attachments(
                output / "attachments",
                output / "rules/temporal-observations.json",
                ids,
                max_round_requests=20,
                on_document=on_document,
            )
    else:
        state = {
            "version": "temporal-replay-1",
            "http_requests": 0,
            "model_calls": 0,
            "published": False,
            "batches": [{"http_requests": 0, "attempted_urls": [], "observed_at": report["observed_at"]}],
            "records": {},
        }

    # Map-Reduce Reconciliation: fold quote-verified model claims into proposed preview policy
    reconciled_candidates = 0
    if apply_verified_model_rules and verified_by_candidate:
        for cid, rows in verified_by_candidate.items():
            rec = state.get("records", {}).get(cid)
            if not rec or rec.get("status") != "replayed" or "policy" not in rec:
                continue
            all_claims = []
            block_doc_map = {}
            for r in rows:
                sid = r["source_id"]
                doc_url = r.get("document_url")
                doc_rev = r.get("document_revision_id")
                for cl in r.get("claims", []):
                    all_claims.append(cl)
                    if doc_url and doc_rev:
                        block_doc_map[cl["locator"]] = {"url": doc_url, "revision_id": doc_rev}
                        if not any(d.get("url") == doc_url and d.get("revision_id") == doc_rev for d in rec.get("documents", [])):
                            rec.setdefault("documents", []).append({
                                "url": doc_url,
                                "revision_id": doc_rev,
                                "raw_sha256": r.get("document_raw_sha256") or ("0" * 64),
                                "parent_url": rec["url"],
                                "parent_raw_sha256": rec["raw_sha256"],
                                "format": "pdf",
                            })
            if all_claims:
                rec["policy"] = reconcile_verified_claims_to_policy(
                    rec["policy"],
                    all_claims,
                    rows[0]["source_id"],
                    rec["revision_id"],
                    block_doc_map=block_doc_map,
                )
                reconciled_candidates += 1

    harness_summary = harness.post_batch_hook(report["model_reviews"])
    report["harness_summary"] = {
        "hook_events_count": len(harness.hook_events),
        "sources_processed": harness_summary["sources_processed"],
        "completed_count": harness_summary["completed_count"],
        "verified_claim_count": harness_summary["verified_claim_count"],
        "reconciled_candidates": reconciled_candidates,
    }
    merged = deepcopy(state)
    merged["records"] = {**deepcopy(baseline["records"]), **state["records"]}
    if baseline_path and "baseline" in baseline and baseline.get("http_requests", 0) + state["http_requests"] <= 200:
        merged["batches"] = deepcopy(baseline.get("batches", [])) + deepcopy(state["batches"])
        merged["http_requests"] = sum(b["http_requests"] for b in merged["batches"])
        merged["baseline"] = deepcopy(baseline["baseline"])
    else:
        merged["baseline"] = {
            "sha256": digest(baseline),
            "previous_round_http_requests": baseline["http_requests"],
            "note": "Separate manual round; unchanged records retained with their own observed_at and revisions.",
        }
    errors = validate_temporal_snapshot(bundle, merged)
    if errors:
        raise ValueError("invalid_temporal_proposal")
    save(output / "temporal-observations.proposed.json", merged)
    report.update(
        source_http_requests=state["http_requests"],
        baseline_http_requests=baseline["http_requests"],
        model_usage=adapter.usage_summary() if adapter else {"enabled": False, "calls": 0, "hash_only_bytes_sent": 0},
        rules_updated_candidates=len(state["records"]),
        attachments_requested=attachments,
        rules_only_model_proposals_not_applied=(not apply_verified_model_rules or reconciled_candidates == 0),
        verified_model_rules_applied_to_preview=(apply_verified_model_rules and reconciled_candidates > 0),
    )
    report["rate_limit_diagnostics"] = getattr(adapter, "last_rate_metadata", {})
    report["model_configuration"] = {
        "model": getattr(adapter, "model", None),
        "tokenizer_model": MODEL if adapter and adapter.enabled else None,
        "input_budget_tokens": MICRO_CHUNK_INPUT_LIMIT,
        "output_reserve_tokens": MICRO_CHUNK_OUTPUT_RESERVE,
        "template_reserve_in_counter": True,
        "minimum_request_interval_seconds": getattr(adapter, "minimum_request_interval_seconds", None),
        "actual_usage_is_provider_reported": True,
        "cost_usd": None,
    }
    if report["model_usage"]["hash_only_bytes_sent"] != 0:
        raise ValueError("restricted_source_leak")
    save(output / "report.json", report)
    summary = [
        "# 時間重萃：手動待審結果",
        "",
        f"來源HTTP：{state['http_requests']} / 20；模型推論：{report['model_usage']['calls']} / {report['max_inference_calls']}。",
        f"排程軌道：{report['schedule_track']}；待執行／跳過未變動：{track_plan['run_candidate_count']} / {track_plan['skip_candidate_count']}。",
        f"模型準備：{report['model_status']}；Map-Reduce 融合至甘特圖預覽：{reconciled_candidates} 筆；未發布、人工核准0。",
        "本輪與舊200HTTP台帳分開；保留舊紀錄不是宣稱本輪全部重新掃描。",
        "",
        "| 來源 | 模型處置 | 有證據的待審提案 |",
        "|---|---|---|",
    ]
    summary += [f"| {r['source_id']} | {r['status']} | {len(r.get('claims', []))} |" for r in report["model_reviews"]]
    summary += ["", "通過逐字引文核驗之模型時間規則已融合入待審預覽甘特圖；正式資料未修改。", "原文、tokenizer及模型原始回應不在artifact內。"]
    (output / "summary.md").write_text("\n".join(summary) + "\n", encoding="utf-8")
    # Build an isolated view without writing proposed data into the checkout.
    from scripts.build_review_workspace import candidate_preview_data
    from scripts.export_wireframes import export
    from scripts.radar_metadata import radar_metadata
    from scripts.source_chains import timeline_metadata
    preview = candidate_preview_data(bundle, read(ROOT / "data/pilot.json"), config)
    export(
        output / "preview/index.html",
        pilot_data=preview,
        review_preview=True,
        radar_data=radar_metadata(bundle, merged),
        chain_data=timeline_metadata(read(ROOT / "data/source-chains.json"), bundle),
    )
    return report


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", type=Path, default=ROOT / "work/temporal-action")
    p.add_argument("--source-ids", default=os.environ.get("TEMPORAL_SOURCE_IDS", "taipei-ai-tools,hsinchu-ai-tools"))
    p.add_argument("--track", default=os.environ.get("TEMPORAL_TRACK") or None)
    p.add_argument("--incremental-only", action="store_true")
    p.add_argument("--include-refinement", action="store_true")
    p.add_argument("--attachments", action="store_true")
    p.add_argument("--max-sources", type=int, default=8)
    p.add_argument("--checkpoint", type=Path, default=None)
    p.add_argument("--baseline", type=Path, default=None)
    args = p.parse_args()
    report = run(
        args.output,
        args.source_ids,
        args.attachments,
        track=args.track,
        incremental_only=args.incremental_only,
        include_refinement=args.include_refinement,
        max_sources=args.max_sources,
        checkpoint_path=args.checkpoint,
        baseline_path=args.baseline,
    )
    print(
        json.dumps(
            {
                "source_http_requests": report["source_http_requests"],
                "model_calls": report["model_usage"]["calls"],
                "schedule_track": report["schedule_track"],
                "published": False,
            },
            ensure_ascii=False,
        )
    )
