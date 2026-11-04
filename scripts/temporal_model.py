"""Bounded temporal extraction model pool, micro-chunking, and batch harness.

Supports all 8 repository API providers in a dynamic failover pool with
1,500-token micro-chunking, 90s timeout, header-driven pacing, lifecycle hooks,
and atomic checkpointing. No candidate mutation or automatic publication.
"""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import time
import urllib.request
from urllib.parse import urlsplit

from scripts.document_ir import prepare_document, evidence_block_map
from scripts.extract_candidates import (
    OpenAICompatibleAdapter,
    DisabledModelAdapter,
    create_model_adapter_from_env,
    _verify_quote_and_reparse,
    CONTACT,
    PII_REDACT_RE,
)
from scripts.providers import PROVIDERS, provider_settings
from scripts.semantic_facts import time_actor, labelled_date_clause
from scripts.audit_providers import NoRedirect

MODEL = "qwen/qwen3.8-27b"
TOKENIZER_URL = "https://huggingface.co/Qwen/Qwen3.8-27B/resolve/72a217afab8029b39e4af1c7273a829995a3dbaf/tokenizer.json"
TOKENIZER_SHA = "0997f410c57a1f4e53b09e4be8f4a172d90edd9564368fb0847030937229b9f3"
FIELDS = (
    "schedule.application_start",
    "schedule.student_deadline",
    "schedule.college_deadline",
    "schedule.institution_deadline",
    "schedule.result_date",
)

# Free-tier safe micro-chunking capabilities across all 8 providers:
# input_limit=1500 (effective cap=1300 after safety_tokens=200), output_reserve=600
MICRO_CHUNK_INPUT_LIMIT = 1500
MICRO_CHUNK_OUTPUT_RESERVE = 600
MICRO_CHUNK_SAFETY_TOKENS = 200
DEFAULT_HTTP_TIMEOUT = 90

PROVIDER_POOL_ORDER = (
    "groq",
    "gemini",
    "cerebras",
    "mistral",
    "sambanova",
    "openrouter",
    "siliconflow",
    "nvidia",
)

VERIFIED_PROVIDER_CAPABILITIES = {
    "groq": {
        "host": "api.groq.com",
        "model": "qwen/qwen3.8-27b",
        "context_limit": 131042,
        "output_limit": 16384,
        "min_interval": 8.0,
        "uses_qwen_tokenizer": True,
    },
    "gemini": {
        "host": "generativelanguage.googleapis.com",
        "model": "gemini-3.5-flash-lite",
        "context_limit": 128000,
        "output_limit": 8192,
        "min_interval": 4.0,
        "uses_qwen_tokenizer": False,
    },
    "cerebras": {
        "host": "api.cerebras.ai",
        "model": "gpt-oss-120b",
        "context_limit": 65536,
        "output_limit": 8192,
        "min_interval": 2.0,
        "uses_qwen_tokenizer": False,
    },
    "mistral": {
        "host": "api.mistral.ai",
        "model": "mistral-small-latest",
        "context_limit": 32768,
        "output_limit": 8192,
        "min_interval": 2.0,
        "uses_qwen_tokenizer": False,
    },
    "sambanova": {
        "host": "api.sambanova.ai",
        "model": "Meta-Llama-3.3-70B-Instruct",
        "context_limit": 16384,
        "output_limit": 4096,
        "min_interval": 3.0,
        "uses_qwen_tokenizer": False,
    },
    "openrouter": {
        "host": "openrouter.ai",
        "model": "google/gemma-4-26b-a4b-it:free",
        "context_limit": 32768,
        "output_limit": 4096,
        "min_interval": 3.0,
        "uses_qwen_tokenizer": False,
    },
    "siliconflow": {
        "host": "api.siliconflow.com",
        "model": "Qwen/Qwen2.5-7B-Instruct",
        "context_limit": 32768,
        "output_limit": 4096,
        "min_interval": 2.0,
        "uses_qwen_tokenizer": False,
    },
    "nvidia": {
        "host": "integrate.api.nvidia.com",
        "model": "openai/gpt-oss-20b",
        "context_limit": 32768,
        "output_limit": 4096,
        "min_interval": 2.5,
        "uses_qwen_tokenizer": False,
    },
}

VERIFIED_MODELS_BY_HOST = {
    (spec["host"], spec["model"]): name
    for name, spec in VERIFIED_PROVIDER_CAPABILITIES.items()
}


def build_model_limits(model_name, context_limit=131042, output_limit=16384, input_limit=MICRO_CHUNK_INPUT_LIMIT, output_reserve=MICRO_CHUNK_OUTPUT_RESERVE, safety_tokens=MICRO_CHUNK_SAFETY_TOKENS):
    return {
        "model": model_name,
        "reviewed": True,
        "checked_on": "2026-11-03",
        "input_limit": int(input_limit),
        "context_limit": int(context_limit),
        "output_limit": int(output_limit),
        "output_reserve": int(output_reserve),
        "shared_context": True,
        "thinking_reserve": 0,
        "safety_tokens": int(safety_tokens),
        "max_request_bytes": 120000,
    }


def conservative_token_estimate(payload):
    """Deterministic upper-bound token estimator for CJK + JSON envelopes across providers."""
    total = 128
    messages = payload.get("messages", []) if isinstance(payload, dict) else []
    for msg in messages:
        content = str(msg.get("content", "") if isinstance(msg, dict) else msg)
        cjk_chars = len(re.findall(r"[\u2e80-\u9fff\uf900-\ufaff\uff00-\uffef]", content))
        non_cjk_len = max(0, len(content) - cjk_chars)
        est = math.ceil(cjk_chars * 0.8 + non_cjk_len / 4.0)
        total += est + 32
    return int(total)


def make_token_counter(tokenizer=None):
    """Combine official Qwen tokenizer (when available) with conservative multi-provider estimate."""
    def count(payload):
        if tokenizer is not None and isinstance(payload, dict) and "messages" in payload:
            qwen_tokens = 256 + sum(
                len(tokenizer.encode(m["content"], add_special_tokens=False).ids) + 64
                for m in payload["messages"]
            )
            return int(qwen_tokens)
        return conservative_token_estimate(payload)
    return count


def install_tokenizer(path):
    """Public pinned JSON only; never downloads weights or executes remote code."""
    path = Path(path)
    if not path.exists():
        with urllib.request.urlopen(TOKENIZER_URL, timeout=45) as response:
            raw = response.read(16 * 1024 * 1024 + 1)
        if len(raw) > 16 * 1024 * 1024 or hashlib.sha256(raw).hexdigest() != TOKENIZER_SHA:
            raise ValueError("tokenizer_download_hash_mismatch")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    if hashlib.sha256(path.read_bytes()).hexdigest() != TOKENIZER_SHA:
        raise ValueError("tokenizer_hash_mismatch")


def _configure_single_adapter(adapter, provider_name, spec, token_counter, max_calls=24):
    adapter.provider_name = provider_name
    adapter.model_limits = build_model_limits(
        adapter.model,
        context_limit=spec["context_limit"],
        output_limit=spec["output_limit"],
    )
    adapter.count_tokens = token_counter
    adapter.max_calls = max_calls
    adapter.field_scope = FIELDS
    adapter.timeout = DEFAULT_HTTP_TIMEOUT
    adapter.use_cache = False  # Do not retain raw model quotes/responses in artifacts.
    adapter.request_open = urllib.request.build_opener(NoRedirect()).open
    adapter.minimum_request_interval_seconds = spec.get("min_interval", 5.0)
    adapter.allow_transient_failover = True
    return adapter


class ProviderFailoverPool(OpenAICompatibleAdapter):
    """Dynamic failover pool across up to 8 configured LLM API providers.

    - Performs chunk-level failover on HTTP 429, TimeoutError, 5xx, or invalid JSON.
    - Never retries 429 on the same provider (marks it rate-limited/cooled down and switches).
    - Enforces identical hash_only and short_excerpt privacy boundaries across all providers.
    """
    adapter_kind = "provider_failover_pool"

    def __init__(self, adapters, mode="both", max_calls=32):
        if not adapters:
            raise ValueError("ProviderFailoverPool requires at least one adapter")
        primary = adapters[0]
        super().__init__(
            base_url=primary.base_url,
            model=primary.model,
            api_key_env=primary.api_key_env,
            api_key=getattr(primary, "_explicit_api_key", None),
            mode=mode,
            timeout=primary.timeout,
            max_calls=max_calls,
            use_cache=False,
            allow_local_no_key=primary.allow_local_no_key,
            model_limits=deepcopy(primary.model_limits),
            count_tokens=primary.count_tokens,
            field_scope=FIELDS,
            provider_name="auto_pool",
        )
        self.adapters = list(adapters)
        for a in self.adapters:
            a.allow_transient_failover = True
        self.enabled = any(a.enabled for a in self.adapters)
        self.failover_events = []
        self.calls_by_provider = {a.provider_name: 0 for a in self.adapters}
        self.active_provider_index = 0

    def available_providers(self):
        return [a.provider_name for a in self.adapters if a.enabled]

    def _healthy_adapters(self):
        now = time.monotonic()
        healthy = []
        for idx, adapter in enumerate(self.adapters):
            ordered_idx = (self.active_provider_index + idx) % len(self.adapters)
            cand = self.adapters[ordered_idx]
            if not cand.enabled or cand.rate_limited_429:
                continue
            if getattr(cand, "cooldown_until", 0.0) > now:
                continue
            healthy.append((ordered_idx, cand))
        return healthy

    def _sync_metrics_from_child(self, child):
        self.calls = sum(a.calls for a in self.adapters)
        self.prompt_tokens = sum(a.prompt_tokens for a in self.adapters)
        self.completion_tokens = sum(a.completion_tokens for a in self.adapters)
        self.total_tokens = sum(a.total_tokens for a in self.adapters)
        self.rejected_claims = sum(a.rejected_claims for a in self.adapters)
        self.latencies_ms = [lat for a in self.adapters for lat in a.latencies_ms]
        self.last_rate_metadata = deepcopy(getattr(child, "last_rate_metadata", {}) or {})
        self.rate_limited_429 = all(
            (not a.enabled) or a.rate_limited_429 for a in self.adapters
        )

    def _run_one(self, source, blocks, draft_candidate, mode=None):
        self._guard_hash_only(source)
        if self.calls >= self.max_calls:
            return {"_skipped_reason": "rate_limited_or_budget_exhausted"}

        candidates = self._healthy_adapters()
        if not candidates:
            self.rate_limited_429 = True
            return {"_skipped_reason": "all_providers_exhausted_or_rate_limited"}

        last_error = {"_skipped_reason": "model_chunk_failed"}
        for ordered_idx, adapter in candidates:
            if self.calls >= self.max_calls:
                return {"_skipped_reason": "rate_limited_or_budget_exhausted"}
            response = adapter._run_one(source, blocks, draft_candidate, mode=mode or self.mode)
            self.calls_by_provider[adapter.provider_name] = adapter.calls
            self._sync_metrics_from_child(adapter)

            if response and not any(k.startswith("_") for k in response):
                self.active_provider_index = ordered_idx
                # Proactive rotation if remaining TPM is low on current provider
                rem_tok = self.last_rate_metadata.get("x-ratelimit-remaining-tokens")
                if rem_tok is not None and str(rem_tok).isdigit() and int(rem_tok) < 2200 and len(self.adapters) > 1:
                    adapter.cooldown_until = time.monotonic() + 25.0
                    self.active_provider_index = (ordered_idx + 1) % len(self.adapters)
                return response

            reason = (
                response.get("_skipped_reason")
                if isinstance(response, dict) and response.get("_skipped_reason")
                else ("invalid_json" if isinstance(response, dict) and response.get("_invalid_json") else "empty_response")
            )
            last_error = response if isinstance(response, dict) else {"_skipped_reason": reason}
            self.failover_events.append({
                "from_provider": adapter.provider_name,
                "model": adapter.model,
                "reason": reason,
                "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            })
            # Advance active pointer to next provider in pool
            self.active_provider_index = (ordered_idx + 1) % len(self.adapters)

        return last_error

    def usage_summary(self):
        base = super().usage_summary()
        base["providers_in_pool"] = self.available_providers()
        base["calls_by_provider"] = deepcopy(self.calls_by_provider)
        base["failover_events"] = deepcopy(self.failover_events)
        return base


def build_provider_pool_from_env(environ=None, tokenizer=None, mode=None, max_calls=32):
    """Discover all configured providers from environment and build a ProviderFailoverPool."""
    env = dict(os.environ if environ is None else environ)
    active_mode = (mode or env.get("OPENGSA_MODEL_MODE", "off")).strip().lower()
    if active_mode not in ("extract", "audit", "both"):
        return DisabledModelAdapter(), "off_mode"

    preferred = env.get("OPENGSA_MODEL_PROVIDER", "groq").strip().lower()
    order = list(PROVIDER_POOL_ORDER)
    if preferred in order:
        order.remove(preferred)
        order.insert(0, preferred)

    adapters = []
    for name in order:
        spec = VERIFIED_PROVIDER_CAPABILITIES.get(name)
        if not spec:
            continue
        local_env = dict(env)
        if name == "siliconflow" and not local_env.get("OPENGSA_SILICONFLOW_REGION"):
            # Per AGENTS.md: SiliconFlow is international cloud.siliconflow.com (region=com)
            local_env["OPENGSA_SILICONFLOW_REGION"] = "com"
        try:
            base_url, model_name, key_env = provider_settings(name, local_env)
        except ValueError:
            continue
        api_key = local_env.get(key_env, "").strip()
        if not api_key:
            continue
        host = urlsplit(base_url).hostname
        if (host, model_name) not in VERIFIED_MODELS_BY_HOST:
            continue
        counter = make_token_counter(tokenizer if spec.get("uses_qwen_tokenizer") else None)
        adapter = OpenAICompatibleAdapter(
            base_url=base_url,
            model=model_name,
            api_key_env=key_env,
            api_key=api_key,
            mode=active_mode,
            timeout=DEFAULT_HTTP_TIMEOUT,
            max_calls=max_calls,
            use_cache=False,
            field_scope=FIELDS,
            provider_name=name,
        )
        _configure_single_adapter(adapter, name, spec, counter, max_calls=max_calls)
        if adapter.enabled:
            adapters.append(adapter)

    if not adapters:
        return DisabledModelAdapter(), "off_missing_key_or_cost_policy"
    if len(adapters) == 1 and preferred != "auto_pool":
        return adapters[0], "ready"
    return ProviderFailoverPool(adapters, mode=active_mode, max_calls=max_calls), "ready"


def model_for_temporal(tokenizer_path, environ=None):
    """Initialize bounded temporal model adapter or multi-provider failover pool."""
    env = dict(os.environ if environ is None else environ)
    provider_choice = env.get("OPENGSA_MODEL_PROVIDER", "groq").strip().lower()

    # If auto_pool is requested, build multi-provider pool across all configured secrets
    if provider_choice == "auto_pool":
        tokenizer = None
        if any(env.get(k, "").strip() for k in PROVIDERS["groq"]["key_envs"]):
            try:
                install_tokenizer(tokenizer_path)
                from tokenizers import Tokenizer
                tokenizer = Tokenizer.from_file(str(tokenizer_path))
            except Exception:
                tokenizer = None
        return build_provider_pool_from_env(env, tokenizer=tokenizer)

    adapter = create_model_adapter_from_env()
    if not adapter.enabled:
        # Check if another provider in the pool is requested or available when mode != off
        mode = env.get("OPENGSA_MODEL_MODE", "off").strip().lower()
        if mode in ("extract", "audit", "both") and provider_choice in VERIFIED_PROVIDER_CAPABILITIES:
            return build_provider_pool_from_env(env, tokenizer=None, mode=mode)
        return adapter, "off_missing_key_or_cost_policy"

    host = urlsplit(getattr(adapter, "base_url", "")).hostname
    provider_name = VERIFIED_MODELS_BY_HOST.get((host, getattr(adapter, "model", "")))
    if not provider_name:
        return None, "model_capabilities_not_verified"

    spec = VERIFIED_PROVIDER_CAPABILITIES[provider_name]
    tokenizer = None
    if spec.get("uses_qwen_tokenizer"):
        install_tokenizer(tokenizer_path)
        from tokenizers import Tokenizer
        tokenizer = Tokenizer.from_file(str(tokenizer_path))

    counter = make_token_counter(tokenizer)
    _configure_single_adapter(adapter, provider_name, spec, counter, max_calls=24)

    # If multiple provider keys exist in environment and pool fallback is enabled (default),
    # attach remaining providers as failover backups behind the primary adapter.
    if env.get("OPENGSA_ENABLE_FAILOVER_POOL", "true").lower() not in ("0", "false", "off"):
        pool_env = dict(env)
        pool_env["OPENGSA_MODEL_PROVIDER"] = provider_name
        pool, status = build_provider_pool_from_env(pool_env, tokenizer=tokenizer, mode=getattr(adapter, "mode", "both"))
        if status == "ready" and isinstance(pool, ProviderFailoverPool) and len(pool.adapters) > 1:
            pool.adapters[0] = adapter
            return pool, "ready"

    return adapter, "ready"


def source_allowed(candidate, profile):
    host = urlsplit(candidate["source_metadata"]["url"]).hostname
    return (
        candidate["source_metadata"]["evidence_mode"] == "short_excerpt"
        and profile["evidence_mode"] == "short_excerpt"
        and host not in ("www.aca.ntu.edu.tw", "aca.ntu.edu.tw", "ord.ntu.edu.tw")
    )


def temporal_units(blocks):
    """Field-scoped input, not a claim to cover every non-temporal source field.

    Keep all time/date clauses, qualifications, definitions and exceptions plus
    adjacent same-section continuations. No first-N truncation or ID routing.
    """
    units = prepare_document(blocks)["units"]
    keep = set()
    pattern = r"申請|受理|截止|期限|期間|日[前後]|每年|每學期|補件|購買|訂閱|公布|結果|資格|對象|條件|例外|不得|不予|不含|除外|但|以下簡稱|\d{2,4}[年/.-]\d{1,2}[月/.-]"
    for i, unit in enumerate(units):
        if unit.get("kind") == "heading" or re.search(pattern, unit["text"]):
            keep.add(i)
            for j in (i - 1, i + 1):
                if (
                    0 <= j < len(units)
                    and units[j].get("page") == unit.get("page")
                    and units[j].get("section_path", []) == unit.get("section_path", [])
                ):
                    if unit.get("kind") != "table_cell" and units[j].get("kind") not in ("heading", "table_cell"):
                        keep.add(j)
    return [u for i, u in enumerate(units) if i in keep], len(units)


def model_review(candidate, profile, blocks, adapter, revision):
    row = {
        "candidate_id": candidate["candidate_id"],
        "source_id": profile["id"],
        "source_revision": revision,
        "status": "not_requested",
        "claims": [],
        "rejected_claims": 0,
    }
    if not source_allowed(candidate, profile):
        row["status"] = "restricted_source_rules_only"
        return row
    if not adapter or not adapter.enabled:
        row["status"] = "model_unavailable_rules_only"
        return row
    if adapter.calls >= adapter.max_calls or adapter.rate_limited_429:
        row["status"] = "model_budget_or_quota_deferred"
        return row
    units, total = temporal_units(blocks)
    row.update(
        coverage_scope="temporal_fields_and_shared_exceptions",
        source_unit_count=total,
        selected_unit_count=len(units),
        whole_source_coverage_claimed=False,
    )
    # Exclude pure contact boilerplate units; mixed date+contact units are sanitized in-place by adapter
    excluded = [
        u
        for u in units
        if CONTACT.search(u["text"])
        and re.match(r"^\s*(?:聯絡|洽詢|承辦|電話|地址|Email|E-mail|Tel|Fax|傳真|©|版權)", u["text"], re.I)
        and not re.search(r"申請|受理|截止|期限|但|除外|不得|資格|對象|補件|\d{2,4}[年/.-]\d{1,2}", u["text"])
    ]
    units = [u for u in units if u not in excluded]
    row["contact_only_units_excluded"] = len(excluded)
    if not units:
        row["status"] = "no_safe_time_units"
        return row
    response = adapter.run_dual_track(profile, units, candidate)
    row["preparation"] = deepcopy(getattr(adapter, "last_preparation", {}))
    if not response or any(k.startswith("_") for k in response):
        row["status"] = response.get("_skipped_reason", "invalid_or_empty_response") if response else "empty_response"
        return row
    block_map = evidence_block_map(units)
    mode = getattr(adapter, "mode", "both")
    kinds = (
        ("audit_findings",)
        if mode == "audit"
        else ("extracted_fields",)
        if mode == "extract"
        else ("extracted_fields", "audit_findings")
    )
    seen_claims = set()
    for kind in kinds:
        for claim in response.get(kind, []):
            path = claim.get("field_path")
            value = claim.get("value") if kind == "extracted_fields" else claim.get("llm_value")
            if path not in FIELDS or value in (None, "unknown", "relative", ""):
                row["rejected_claims"] += 1
                continue
            ok, reason, block, norm_val = _verify_quote_and_reparse(
                path,
                value,
                None,
                None,
                claim.get("locator"),
                claim.get("quote"),
                block_map,
                is_audit=(kind == "audit_findings"),
            )
            quote = claim.get("quote") or ""
            expected = (
                "student"
                if path in ("schedule.application_start", "schedule.student_deadline")
                else "college"
                if "college" in path
                else "institution"
                if "institution" in path
                else None
            )
            if expected and (claim.get("actor") not in (None, expected) or time_actor(quote) != expected):
                ok = False
                reason = "time_actor_requires_review"
            if expected and not labelled_date_clause(re.sub(r"\s+", "", quote)):
                ok = False
                reason = "application_date_label_requires_review"
            if path == "schedule.result_date" and not re.search(r"結果|公布|公告|核定", quote):
                ok = False
                reason = "result_stage_requires_review"
            if not ok:
                row["rejected_claims"] += 1
                continue
            claim_key = (path, norm_val, expected, block["locator"])
            if claim_key in seen_claims:
                continue
            seen_claims.add(claim_key)
            # Date verification alone does not establish applicability or annual
            # cap conditions. These are proposals, never new public time rules.
            row["claims"].append({
                "field_path": path,
                "value": norm_val,
                "actor": expected,
                "locator": block["locator"],
                "quote_sha256": hashlib.sha256(quote.encode()).hexdigest(),
                "kind": kind,
                "status": "evidence_checked_pending_review",
            })
    row["status"] = "model_completed_pending_review"
    return row


class TemporalBatchHarness:
    """Lifecycle Hook & Checkpoint Harness for continuous/batch/large-scale temporal extraction.

    Hooks:
    - pre_batch_hook(context)
    - pre_source_hook(source_id, candidate, profile, revision_id, blocks)
    - on_chunk_hook(source_id, revision_id, chunk_index, chunk_total, chunk, response)
    - post_source_hook(source_id, candidate, revision_id, review_row)
    - post_batch_hook(summary)
    """

    def __init__(self, adapter, checkpoint_path=None):
        self.adapter = adapter
        self.checkpoint_path = Path(checkpoint_path) if checkpoint_path else None
        self.checkpoint = self._load_checkpoint()
        self.hook_events = []
        self._custom_hooks = {
            "pre_batch": [],
            "pre_source": [],
            "on_chunk": [],
            "post_source": [],
            "post_batch": [],
        }

    def register_hook(self, stage, callback):
        if stage not in self._custom_hooks:
            raise ValueError(f"Unknown hook stage: {stage}")
        self._custom_hooks[stage].append(callback)

    def _load_checkpoint(self):
        if self.checkpoint_path and self.checkpoint_path.exists():
            try:
                data = json.loads(self.checkpoint_path.read_text(encoding="utf-8"))
                if isinstance(data, dict) and data.get("version") == "temporal-harness-checkpoint-1":
                    return data
            except Exception:
                pass
        return {
            "version": "temporal-harness-checkpoint-1",
            "updated_at": None,
            "completed_sources": {},
            "chunk_cache": {},
        }

    def _save_checkpoint(self):
        if not self.checkpoint_path:
            return
        self.checkpoint["updated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        self.checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.checkpoint_path.with_suffix(".tmp")
        tmp_path.write_text(
            json.dumps(self.checkpoint, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        os.replace(tmp_path, self.checkpoint_path)

    def pre_batch_hook(self, context):
        event = {
            "hook": "pre_batch",
            "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "planned_count": context.get("planned_count", 0),
            "resumed_sources": len(self.checkpoint.get("completed_sources", {})),
            "providers": (
                self.adapter.available_providers()
                if hasattr(self.adapter, "available_providers")
                else ([getattr(self.adapter, "provider_name", "single")] if getattr(self.adapter, "enabled", False) else [])
            ),
        }
        self.hook_events.append(event)
        for fn in self._custom_hooks["pre_batch"]:
            fn(event)
        return event

    def pre_source_hook(self, source_id, candidate, profile, revision_id, blocks):
        source_key = f"{candidate['candidate_id']}::{revision_id}"
        cached_row = self.checkpoint.get("completed_sources", {}).get(source_key)
        event = {
            "hook": "pre_source",
            "source_id": source_id,
            "candidate_id": candidate["candidate_id"],
            "revision_id": revision_id,
            "cached_complete": bool(cached_row),
            "block_count": len(blocks or []),
        }
        self.hook_events.append(event)
        for fn in self._custom_hooks["pre_source"]:
            fn(event)
        return cached_row

    def on_chunk_hook(self, source_id, revision_id, chunk_index, chunk_total, chunk, response):
        chunk_id = chunk["chunk_id"]
        bucket = self.checkpoint.setdefault("chunk_cache", {}).setdefault(f"{source_id}::{revision_id}", {})
        bucket[chunk_id] = deepcopy(response)
        self._save_checkpoint()
        event = {
            "hook": "on_chunk",
            "source_id": source_id,
            "revision_id": revision_id,
            "chunk_id": chunk_id,
            "chunk_index": chunk_index,
            "chunk_total": chunk_total,
            "input_tokens": chunk.get("input_tokens", 0),
        }
        self.hook_events.append(event)
        for fn in self._custom_hooks["on_chunk"]:
            fn(event)

    def post_source_hook(self, source_id, candidate, revision_id, review_row):
        source_key = f"{candidate['candidate_id']}::{revision_id}"
        if review_row.get("status") in ("model_completed_pending_review", "restricted_source_rules_only", "no_safe_time_units"):
            self.checkpoint.setdefault("completed_sources", {})[source_key] = deepcopy(review_row)
            # Clear transient raw chunk cache for this source once verified claims are finalized
            self.checkpoint.get("chunk_cache", {}).pop(f"{source_id}::{revision_id}", None)
            self._save_checkpoint()
        event = {
            "hook": "post_source",
            "source_id": source_id,
            "candidate_id": candidate["candidate_id"],
            "revision_id": revision_id,
            "status": review_row.get("status"),
            "verified_claims": len(review_row.get("claims", [])),
        }
        self.hook_events.append(event)
        for fn in self._custom_hooks["post_source"]:
            fn(event)

    def post_batch_hook(self, results):
        summary = {
            "hook": "post_batch",
            "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "sources_processed": len(results),
            "completed_count": sum(1 for r in results if r.get("status") == "model_completed_pending_review"),
            "verified_claim_count": sum(len(r.get("claims", [])) for r in results),
            "usage": self.adapter.usage_summary() if hasattr(self.adapter, "usage_summary") else {},
        }
        self.hook_events.append(summary)
        for fn in self._custom_hooks["post_batch"]:
            fn(summary)
        return summary

    def run_source(self, candidate, profile, blocks, revision):
        source_id = profile["id"]
        cached = self.pre_source_hook(source_id, candidate, profile, revision, blocks)
        if cached is not None:
            row = deepcopy(cached)
            row["resumed_from_checkpoint"] = True
            return row

        chunk_bucket = self.checkpoint.get("chunk_cache", {}).get(f"{source_id}::{revision}", {})
        if self.adapter is not None:
            self.adapter.chunk_cache = deepcopy(chunk_bucket)
            self.adapter.on_chunk_callback = lambda idx, total, chunk, resp: self.on_chunk_hook(
                source_id, revision, idx, total, chunk, resp
            )
        try:
            row = model_review(candidate, profile, blocks, self.adapter, revision)
        finally:
            if self.adapter is not None:
                self.adapter.chunk_cache = None
                self.adapter.on_chunk_callback = None

        self.post_source_hook(source_id, candidate, revision, row)
        return row

    def run_batch(self, batch_items):
        """Run a batch of (candidate, profile, blocks, revision) tuples through all lifecycle hooks."""
        self.pre_batch_hook({"planned_count": len(batch_items)})
        results = []
        for candidate, profile, blocks, revision in batch_items:
            row = self.run_source(candidate, profile, blocks, revision)
            results.append(row)
        summary = self.post_batch_hook(results)
        return results, summary
