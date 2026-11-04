"""Tests for Step 2: 8-provider failover pool, 1500-token micro-chunking, PII redaction unblock, and TemporalBatchHarness."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.temporal_model import (
    FIELDS,
    MICRO_CHUNK_INPUT_LIMIT,
    MICRO_CHUNK_OUTPUT_RESERVE,
    MICRO_CHUNK_SAFETY_TOKENS,
    ProviderFailoverPool,
    TemporalBatchHarness,
    VERIFIED_PROVIDER_CAPABILITIES,
    build_model_limits,
    build_provider_pool_from_env,
    conservative_token_estimate,
    make_token_counter,
    model_review,
)
from scripts.extract_candidates import OpenAICompatibleAdapter
from scripts.temporal_reextract import ROOT, read


class TemporalPoolAndHarnessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundle = read(ROOT / "data/candidates/source-review.json")
        cls.profiles = {p["id"]: p for p in read(ROOT / "data/scan-sources.json")["sources"]}

    def candidate(self, sid):
        return deepcopy(next(c for c in self.bundle["candidates"] if c["source_metadata"]["source_id"] == sid))

    def make_adapter(self, provider_name="groq", model="qwen/qwen3.8-27b", base_url="https://api.groq.com/openai/v1"):
        adapter = OpenAICompatibleAdapter(
            base_url=base_url,
            model=model,
            api_key="SYNTH-key",
            mode="both",
            timeout=90,
            max_calls=12,
            use_cache=False,
            model_limits=build_model_limits(model),
            count_tokens=make_token_counter(),
            field_scope=FIELDS,
            provider_name=provider_name,
        )
        adapter.allow_transient_failover = True
        return adapter

    def test_all_eight_providers_are_registered_and_discoverable_in_pool(self):
        self.assertEqual(len(VERIFIED_PROVIDER_CAPABILITIES), 8)
        synth_env = {
            "OPENGSA_MODEL_MODE": "both",
            "OPENGSA_MODEL_PROVIDER": "auto_pool",
            "OPENGSA_GROQ_API_KEY": "SYNTH-1",
            "OPENGSA_GEMINI_API_KEY": "SYNTH-2",
            "OPENGSA_CEREBRAS_API_KEY": "SYNTH-3",
            "OPENGSA_MISTRAL_API_KEY": "SYNTH-4",
            "OPENGSA_SAMBANOVA_API_KEY": "SYNTH-5",
            "OPENGSA_OPENROUTER_API_KEY": "SYNTH-6",
            "OPENGSA_SILICONFLOW_API_KEY": "SYNTH-7",
            "OPENGSA_NVIDIA_API_KEY": "SYNTH-8",
        }
        pool, status = build_provider_pool_from_env(synth_env)
        self.assertEqual(status, "ready")
        self.assertIsInstance(pool, ProviderFailoverPool)
        self.assertEqual(
            pool.available_providers(),
            ["groq", "gemini", "cerebras", "mistral", "sambanova", "openrouter", "siliconflow", "nvidia"],
        )
        # Verify SiliconFlow defaulted to international .com endpoint per AGENTS.md
        sf_adapter = next(a for a in pool.adapters if a.provider_name == "siliconflow")
        self.assertEqual(sf_adapter.base_url, "https://api.siliconflow.com/v1")
        self.assertEqual(sf_adapter.timeout, 90)
        self.assertEqual(sf_adapter.model_limits["input_limit"], MICRO_CHUNK_INPUT_LIMIT)
        self.assertEqual(sf_adapter.model_limits["output_reserve"], MICRO_CHUNK_OUTPUT_RESERVE)

    def test_pii_redaction_and_login_or_award_terms_do_not_deadlock_temporal_scope(self):
        cand = self.candidate("taipei-ai-tools")
        profile = deepcopy(self.profiles["taipei-ai-tools"])
        blocks = [
            {
                "locator": "SYNTH/pii-time",
                "text": "申請人請於115年10月15日前登入線上系統完成學生申請截止；獲獎名單於12月公告。洽詢電話：(02)2789-9999 轉 123，信箱 test@gate.sinica.edu.tw。",
            }
        ]
        adapter = self.make_adapter()

        def fake_run_one(source, units, draft_candidate, mode=None):
            adapter.calls += 1
            unit = units[0]
            # Confirm PII was redacted before reaching the model
            self.assertIn("[REDACTED]", unit["text"])
            self.assertNotIn("2789-9999", unit["text"])
            self.assertNotIn("test@gate.sinica.edu.tw", unit["text"])
            return {
                "extracted_fields": [
                    {
                        "field_path": "schedule.student_deadline",
                        "value": "2026-10-15",
                        "actor": "student",
                        "locator": unit["unit_id"],
                        "quote": "請於115年10月15日前登入線上系統完成學生申請截止",
                    }
                ],
                "audit_findings": [],
            }

        with patch.object(adapter, "_run_one", side_effect=fake_run_one):
            row = model_review(cand, profile, blocks, adapter, "a" * 64)

        self.assertEqual(row["status"], "model_completed_pending_review")
        self.assertEqual(len(row["claims"]), 1)
        self.assertEqual(row["claims"][0]["value"], "2026-10-15")
        self.assertTrue(row["preparation"]["complete"])
        self.assertEqual(len(row["preparation"]["redacted_unit_ids"]), 1)

    def test_micro_chunking_keeps_every_chunk_under_1500_tokens_even_with_heavy_background(self):
        cand = self.candidate("taipei-ai-tools")
        profile = deepcopy(self.profiles["taipei-ai-tools"])
        # Build 25 paragraphs containing background keywords ("申請對象", "不得", "補助對象") plus date clauses
        blocks = [
            {
                "locator": f"SYNTH/bg/{i}",
                "text": f"第{i}條：本計畫補助對象及申請對象資格規定，曾獲其他機關補助者不得重複申請。" + ("補充說明文字" * 18),
            }
            for i in range(20)
        ]
        blocks.append({"locator": "SYNTH/start", "text": "學生申請期間自115年3月1日起受理申請。"})
        blocks.append({"locator": "SYNTH/end", "text": "學生申請截止日期為115年11月10日止。"})

        adapter = self.make_adapter()
        seen_envelopes = []

        def fake_run_one(source, units, draft_candidate, mode=None):
            adapter.calls += 1
            payload = adapter._request_payload(draft_candidate, adapter._sanitize_blocks(units, source), "both")
            toks = adapter.count_tokens(payload)
            seen_envelopes.append(toks)
            claims = []
            for u in units:
                if "115年3月1日" in u["text"]:
                    claims.append({
                        "field_path": "schedule.application_start",
                        "value": "2026-03-01",
                        "actor": "student",
                        "locator": u["unit_id"],
                        "quote": "學生申請期間自115年3月1日起受理申請。",
                    })
                if "115年11月10日" in u["text"]:
                    claims.append({
                        "field_path": "schedule.student_deadline",
                        "value": "2026-11-10",
                        "actor": "student",
                        "locator": u["unit_id"],
                        "quote": "學生申請截止日期為115年11月10日止。",
                    })
            return {"extracted_fields": claims, "audit_findings": []}

        with patch.object(adapter, "_run_one", side_effect=fake_run_one):
            row = model_review(cand, profile, blocks, adapter, "b" * 64)

        self.assertEqual(row["status"], "model_completed_pending_review")
        self.assertGreater(len(seen_envelopes), 1)
        cap = MICRO_CHUNK_INPUT_LIMIT - MICRO_CHUNK_SAFETY_TOKENS
        self.assertTrue(all(t <= cap for t in seen_envelopes), f"Token counts exceeded {cap}: {seen_envelopes}")
        values = {c["field_path"]: c["value"] for c in row["claims"]}
        self.assertEqual(values.get("schedule.application_start"), "2026-03-01")
        self.assertEqual(values.get("schedule.student_deadline"), "2026-11-10")

    def test_provider_failover_pool_switches_on_429_and_timeout_without_losing_chunks(self):
        cand = self.candidate("taipei-ai-tools")
        profile = deepcopy(self.profiles["taipei-ai-tools"])
        blocks = [
            {"locator": f"SYNTH/sec/{i}", "text": ("申請期限與資格說明段落文字。" * 22) + f"第{i}節"}
            for i in range(10)
        ]
        blocks.append({"locator": "SYNTH/deadline", "text": "學生申請截止115年11月10日。"})

        groq_adapter = self.make_adapter("groq", "qwen/qwen3.8-27b", "https://api.groq.com/openai/v1")
        gemini_adapter = self.make_adapter(
            "gemini",
            "gemini-3.5-flash-lite",
            "https://generativelanguage.googleapis.com/v1beta/openai",
        )
        cerebras_adapter = self.make_adapter("cerebras", "gpt-oss-120b", "https://api.cerebras.ai/v1")

        # Provider 1 (Groq) hits 429 on chunk 1; Provider 2 (Gemini) succeeds on chunk 1 then hits TimeoutError on chunk 2;
        # Provider 3 (Cerebras) completes chunk 2 and remaining chunks.
        def groq_one(source, units, draft_candidate, mode=None):
            groq_adapter.calls += 1
            groq_adapter.rate_limited_429 = True
            return {"_skipped_reason": "http_429_deferred_no_retry"}

        def gemini_one(source, units, draft_candidate, mode=None):
            gemini_adapter.calls += 1
            if gemini_adapter.calls == 1:
                return {"extracted_fields": [], "audit_findings": []}
            gemini_adapter.cooldown_until = 1e18
            return {"_skipped_reason": "error_TimeoutError"}

        def cerebras_one(source, units, draft_candidate, mode=None):
            cerebras_adapter.calls += 1
            claims = []
            for u in units:
                if "115年11月10日" in u["text"]:
                    claims.append({
                        "field_path": "schedule.student_deadline",
                        "value": "2026-11-10",
                        "actor": "student",
                        "locator": u["unit_id"],
                        "quote": "學生申請截止115年11月10日。",
                    })
            return {"extracted_fields": claims, "audit_findings": []}

        groq_adapter._run_one = groq_one
        gemini_adapter._run_one = gemini_one
        cerebras_adapter._run_one = cerebras_one

        pool = ProviderFailoverPool([groq_adapter, gemini_adapter, cerebras_adapter], mode="both", max_calls=24)
        row = model_review(cand, profile, blocks, pool, "c" * 64)

        self.assertEqual(row["status"], "model_completed_pending_review")
        self.assertEqual(row["claims"][0]["value"], "2026-11-10")
        self.assertEqual(groq_adapter.calls, 1)  # Never retried after 429
        self.assertEqual(gemini_adapter.calls, 2)
        self.assertGreaterEqual(cerebras_adapter.calls, 1)
        self.assertEqual(len(pool.failover_events), 2)
        self.assertEqual(pool.failover_events[0]["from_provider"], "groq")
        self.assertEqual(pool.failover_events[0]["reason"], "http_429_deferred_no_retry")
        self.assertEqual(pool.failover_events[1]["from_provider"], "gemini")
        self.assertEqual(pool.failover_events[1]["reason"], "error_TimeoutError")

    def test_batch_harness_executes_lifecycle_hooks_and_resumes_from_checkpoint(self):
        cand = self.candidate("taipei-ai-tools")
        profile = deepcopy(self.profiles["taipei-ai-tools"])
        blocks = [
            {"locator": f"SYNTH/p/{i}", "text": ("申請期限與資格說明段落文字。" * 22) + f"第{i}節"}
            for i in range(8)
        ]
        blocks.append({"locator": "SYNTH/deadline", "text": "學生申請截止115年11月10日。"})

        with tempfile.TemporaryDirectory() as tmpdir:
            ckpt_file = Path(tmpdir) / "checkpoint.json"
            adapter1 = self.make_adapter()
            chunk_calls_run1 = []

            def run1_one(source, units, draft_candidate, mode=None):
                adapter1.calls += 1
                chunk_calls_run1.append(adapter1.calls)
                if adapter1.calls == 1:
                    return {"extracted_fields": [], "audit_findings": []}
                # Simulate interruption on chunk 2
                return {"_skipped_reason": "http_429_deferred_no_retry"}

            adapter1._run_one = run1_one
            harness1 = TemporalBatchHarness(adapter1, checkpoint_path=ckpt_file)
            hook_stages_seen = []
            for stage in ("pre_batch", "pre_source", "on_chunk", "post_source", "post_batch"):
                harness1.register_hook(stage, lambda ev, s=stage: hook_stages_seen.append(s))

            results1, _ = harness1.run_batch([(cand, profile, blocks, "rev-1")])
            self.assertEqual(results1[0]["status"], "http_429_deferred_no_retry")
            self.assertIn("on_chunk", hook_stages_seen)
            self.assertTrue(ckpt_file.exists())
            saved_ckpt = json.loads(ckpt_file.read_text(encoding="utf-8"))
            self.assertEqual(len(saved_ckpt["chunk_cache"].get("taipei-ai-tools::rev-1", {})), 1)

            # Now resume with a fresh adapter: chunk 1 is restored from checkpoint without calling _run_one!
            adapter2 = self.make_adapter()

            def run2_one(source, units, draft_candidate, mode=None):
                adapter2.calls += 1
                claims = []
                for u in units:
                    if "115年11月10日" in u["text"]:
                        claims.append({
                            "field_path": "schedule.student_deadline",
                            "value": "2026-11-10",
                            "actor": "student",
                            "locator": u["unit_id"],
                            "quote": "學生申請截止115年11月10日。",
                        })
                return {"extracted_fields": claims, "audit_findings": []}

            adapter2._run_one = run2_one
            harness2 = TemporalBatchHarness(adapter2, checkpoint_path=ckpt_file)
            results2, summary2 = harness2.run_batch([(cand, profile, blocks, "rev-1")])
            self.assertEqual(results2[0]["status"], "model_completed_pending_review")
            self.assertEqual(results2[0]["claims"][0]["value"], "2026-11-10")
            self.assertEqual(summary2["completed_count"], 1)
            # Chunk 1 was cached, so adapter2 made 1 fewer call than total planned chunks
            planned_chunks = results2[0]["preparation"]["chunks_planned"]
            self.assertEqual(adapter2.calls, planned_chunks - 1)

            # A third run on the same revision skips model execution altogether via source checkpoint
            adapter3 = self.make_adapter()
            harness3 = TemporalBatchHarness(adapter3, checkpoint_path=ckpt_file)
            results3, _ = harness3.run_batch([(cand, profile, blocks, "rev-1")])
            self.assertTrue(results3[0].get("resumed_from_checkpoint"))
            self.assertEqual(adapter3.calls, 0)


if __name__ == "__main__":
    unittest.main()
