"""Tests for Step 3: Multi-document aggregation, Map-Reduce temporal reconciliation, and Gantt projection."""
from copy import deepcopy
import unittest
from unittest.mock import patch

from scripts.temporal_model import (
    FIELDS,
    aggregate_source_documents,
    build_model_limits,
    make_token_counter,
    merge_parent_and_child_policies,
    model_review,
    reconcile_verified_claims_to_policy,
)
from scripts.extract_candidates import OpenAICompatibleAdapter
from scripts.radar_metadata import radar_metadata
from scripts.review_candidates import candidate_fingerprint
from scripts.temporal_reextract import ROOT, VERSION, extract_policy, read
from scripts.time_policy import policy_validator, validate_temporal_snapshot


class TemporalMapReduceGanttTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundle = read(ROOT / "data/candidates/source-review.json")
        cls.profiles = {p["id"]: p for p in read(ROOT / "data/scan-sources.json")["sources"]}

    def candidate(self, sid):
        return deepcopy(next(c for c in self.bundle["candidates"] if c["source_metadata"]["source_id"] == sid))

    def make_adapter(self):
        return OpenAICompatibleAdapter(
            base_url="https://api.groq.com/openai/v1",
            model="qwen/qwen3.8-27b",
            api_key="SYNTH-key",
            mode="both",
            timeout=90,
            max_calls=16,
            use_cache=False,
            model_limits=build_model_limits("qwen/qwen3.8-27b"),
            count_tokens=make_token_counter(),
            field_scope=FIELDS,
            provider_name="groq",
        )

    def test_multi_document_and_multi_chunk_mapreduce_synthesizes_fixed_window_and_milestones(self):
        cand = self.candidate("taipei-ai-tools")
        cand["resource_kind"] = "scholarship"
        profile = deepcopy(self.profiles["taipei-ai-tools"])
        parent_url = cand["source_metadata"]["url"]
        from urllib.parse import urlsplit
        parent_host = urlsplit(parent_url).hostname
        child_pdf_url = f"https://{parent_host}/synth-guideline.pdf"
        parent_rev = "1" * 64
        parent_raw = "2" * 64
        child_rev = "3" * 64
        child_raw = "4" * 64

        parent_blocks = [
            {"locator": "HTML/p1", "text": "學生申請期間自115年6月1日起開放線上登錄。"},
            {"locator": "HTML/p2", "text": "各學院彙送申請截止日期為115年8月5日止。"},
        ]
        child_docs = [
            {
                "url": child_pdf_url,
                "revision_id": child_rev,
                "raw_sha256": child_raw,
                "format": "pdf",
                "blocks": [
                    {"locator": "PDF/page1", "text": ("申請規定與補充說明文字。" * 25)},
                    {"locator": "PDF/page2", "text": "學生申請截止時間為115年7月29日早上8時止。"},
                    {"locator": "PDF/page3", "text": "審查結果公告日期為115年10月15日核定公布。"},
                ],
            }
        ]

        combined_blocks, block_doc_map, docs_meta = aggregate_source_documents(
            parent_blocks,
            child_documents=child_docs,
            parent_url=parent_url,
            parent_raw_sha256=parent_raw,
        )
        self.assertEqual(len(docs_meta), 1)
        self.assertEqual(docs_meta[0]["url"], child_pdf_url)

        adapter = self.make_adapter()

        def fake_run_one(source, units, draft_candidate, mode=None):
            adapter.calls += 1
            claims = []
            for u in units:
                txt = u["text"]
                if "115年6月1日" in txt:
                    claims.append({
                        "field_path": "schedule.application_start",
                        "value": "2026-06-01",
                        "actor": "student",
                        "locator": u["unit_id"],
                        "quote": "學生申請期間自115年6月1日起開放線上登錄。",
                    })
                if "115年8月5日" in txt:
                    claims.append({
                        "field_path": "schedule.college_deadline",
                        "value": "2026-08-05",
                        "actor": "college",
                        "locator": u["unit_id"],
                        "quote": "各學院彙送申請截止日期為115年8月5日止。",
                    })
                if "115年7月29日" in txt:
                    claims.append({
                        "field_path": "schedule.student_deadline",
                        "value": "2026-07-29T08:00:00+08:00",
                        "actor": "student",
                        "locator": u["unit_id"],
                        "quote": "學生申請截止時間為115年7月29日早上8時止。",
                    })
                if "115年10月15日" in txt:
                    claims.append({
                        "field_path": "schedule.result_date",
                        "value": "2026-10-15",
                        "actor": None,
                        "locator": u["unit_id"],
                        "quote": "審查結果公告日期為115年10月15日核定公布。",
                    })
            return {"extracted_fields": claims, "audit_findings": []}

        with patch.object(adapter, "_run_one", side_effect=fake_run_one):
            review_row = model_review(cand, profile, combined_blocks, adapter, parent_rev)

        self.assertEqual(review_row["status"], "model_completed_pending_review")
        self.assertEqual(len(review_row["claims"]), 4)

        empty_policy = {
            "version": "time-policy-1",
            "submission_mode": "undetermined",
            "review_mode": "not_stated",
            "rules": [],
            "gaps": ["time_not_projected"],
        }
        reconciled = reconcile_verified_claims_to_policy(
            empty_policy,
            review_row["claims"],
            profile["id"],
            parent_rev,
            block_doc_map=block_doc_map,
        )
        self.assertEqual(reconciled["submission_mode"], "fixed_window")
        self.assertEqual(reconciled["gaps"], [])
        policy_validator().validate(reconciled)

        # Verify radar_metadata projects start, end, result, and passes validate_temporal_snapshot
        observation = {
            "version": VERSION,
            "http_requests": 2,
            "model_calls": 0,
            "published": False,
            "batches": [{"http_requests": 2}],
            "records": {
                cand["candidate_id"]: {
                    "status": "replayed",
                    "candidate_sha256": candidate_fingerprint(cand),
                    "url": parent_url,
                    "raw_sha256": parent_raw,
                    "revision_id": parent_rev,
                    "observed_at": "2026-11-03T12:00:00Z",
                    "policy": reconciled,
                    "documents": docs_meta,
                }
            },
        }
        self.assertEqual(validate_temporal_snapshot({"candidates": [cand]}, observation), [])
        radar_rec = radar_metadata({"candidates": [cand]}, observation)["records"][cand["candidate_id"]]
        self.assertEqual(radar_rec["time_dates"]["start"]["value"], "2026-06-01")
        self.assertEqual(radar_rec["time_dates"]["end"]["value"], "2026-07-29T08:00:00+08:00")
        self.assertEqual(radar_rec["time_dates"]["result"]["value"], "2026-10-15")
        college_rules = [r for r in radar_rec["time_policy"]["rules"] if r["actor"] == "college"]
        self.assertEqual(len(college_rules), 1)
        self.assertEqual(college_rules[0]["value"], "2026-08-05")

    def test_multi_cohort_deadlines_across_chunks_reconcile_to_mixed_without_discarding(self):
        cand = self.candidate("taipei-ai-tools")
        profile = deepcopy(self.profiles["taipei-ai-tools"])
        blocks = [
            {"locator": "HTML/batch1", "text": "第一梯次學生申請截止日期為115年5月15日止。"},
            {"locator": "HTML/pad", "text": ("梯次間隔補充說明文字。" * 35)},
            {"locator": "HTML/batch2", "text": "第二梯次學生申請截止日期為115年10月15日止。"},
        ]
        adapter = self.make_adapter()

        def fake_run_one(source, units, draft_candidate, mode=None):
            adapter.calls += 1
            claims = []
            for u in units:
                if "115年5月15日" in u["text"]:
                    claims.append({
                        "field_path": "schedule.student_deadline",
                        "value": "2026-05-15",
                        "actor": "student",
                        "locator": u["unit_id"],
                        "quote": "第一梯次學生申請截止日期為115年5月15日止。",
                    })
                if "115年10月15日" in u["text"]:
                    claims.append({
                        "field_path": "schedule.student_deadline",
                        "value": "2026-10-15",
                        "actor": "student",
                        "locator": u["unit_id"],
                        "quote": "第二梯次學生申請截止日期為115年10月15日止。",
                    })
            return {"extracted_fields": claims, "audit_findings": []}

        with patch.object(adapter, "_run_one", side_effect=fake_run_one):
            row = model_review(cand, profile, blocks, adapter, "a" * 64)

        self.assertEqual(row["status"], "model_completed_pending_review")
        self.assertEqual({c["value"] for c in row["claims"]}, {"2026-05-15", "2026-10-15"})

        reconciled = reconcile_verified_claims_to_policy(
            {"version": "time-policy-1", "submission_mode": "undetermined", "review_mode": "not_stated", "rules": [], "gaps": []},
            row["claims"],
            profile["id"],
            "a" * 64,
        )
        self.assertEqual(reconciled["submission_mode"], "mixed")
        self.assertEqual(len(reconciled["rules"]), 2)

    def test_merge_parent_and_child_policies_combines_start_and_pdf_deadline(self):
        parent_policy = {
            "version": "time-policy-1",
            "submission_mode": "start_only",
            "review_mode": "not_stated",
            "rules": [
                {
                    "rule_id": "replay/0",
                    "kind": "absolute",
                    "actor": "student",
                    "stage": "application_start",
                    "summary": "來源明示受理起日",
                    "value": "2026-06-01",
                    "precision": "date",
                    "anchor_event": None,
                    "source_refs": [{"source": "taipei-ai-tools", "revision_id": "1" * 64, "locator": "H1", "evidence_path": "temporal_replay/application_start"}],
                }
            ],
            "gaps": ["student_window_not_recorded"],
        }
        child_policy = {
            "version": "time-policy-1",
            "submission_mode": "deadline_only",
            "review_mode": "batch",
            "rules": [
                {
                    "rule_id": "replay/0",
                    "kind": "absolute",
                    "actor": "student",
                    "stage": "submission",
                    "summary": "來源明示收件截止",
                    "value": "2026-07-29",
                    "precision": "date",
                    "anchor_event": None,
                    "source_refs": [{
                        "source": "taipei-ai-tools",
                        "revision_id": "2" * 64,
                        "locator": "PDF/1",
                        "evidence_path": "temporal_replay/submission",
                        "url": "https://www.tpyd.gov.taipei/guideline.pdf",
                    }],
                }
            ],
            "gaps": [],
        }
        merged = merge_parent_and_child_policies(parent_policy, child_policy)
        self.assertEqual(merged["submission_mode"], "fixed_window")
        self.assertEqual(merged["review_mode"], "batch")
        self.assertEqual(merged["gaps"], [])
        self.assertEqual(len(merged["rules"]), 2)


if __name__ == "__main__":
    unittest.main()
