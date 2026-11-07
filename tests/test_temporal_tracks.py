"""Unit tests for Step 1: 3-track schedule router and 3-stage incremental diff gate."""
from copy import deepcopy
from datetime import date
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.temporal_tracks import (
    TRACKS,
    classify_source_track,
    diff_document_chunks,
    evaluate_incremental_diff,
    plan_track_execution,
    track_for_weekday,
)
from scripts.run_temporal_action import resolve_action_sources, run
from scripts.review_candidates import candidate_fingerprint
from scripts.temporal_reextract import ROOT, read


class TemporalTracksAndDiffTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundle = read(ROOT / "data/candidates/source-review.json")
        cls.observations = read(ROOT / "data/temporal-observations.json")
        cls.candidates = cls.bundle["candidates"]

    def candidate(self, sid):
        return deepcopy(next(c for c in self.candidates if c["source_metadata"]["source_id"] == sid))

    def test_recurring_mode_never_carries_a_student_date(self):
        # 時間軸對 recurring 不畫座標；同時有明確學生日期就該判成 mixed。
        for cid, record in self.observations["records"].items():
            policy = record.get("policy") or {}
            if policy.get("submission_mode") == "recurring":
                with self.subTest(candidate=cid):
                    self.assertFalse([r for r in policy["rules"] if r["kind"] == "absolute" and r["actor"] == "student" and r.get("value")])

    def test_all_candidates_partition_cleanly_into_three_tracks(self):
        counts = {"gov": 0, "enterprise": 0, "other": 0}
        for c in self.candidates:
            t = classify_source_track(c)
            self.assertIn(t, counts)
            counts[t] += 1
        self.assertEqual(sum(counts.values()), len(self.candidates))
        self.assertTrue(all(counts.values()), counts)
        # Specific representative checks
        self.assertEqual(classify_source_track(self.candidate("sinica-phd-fellowship")), "gov")
        self.assertEqual(classify_source_track(self.candidate("faos-student-conference")), "enterprise")
        self.assertEqual(classify_source_track(self.candidate("taipei-ai-tools")), "other")

    def test_weekday_mapping_matches_mon_thu_tue_fri_wed_sat_schedule(self):
        # Mon (0), Thu (3) -> enterprise
        self.assertEqual(track_for_weekday(0), "enterprise")
        self.assertEqual(track_for_weekday(3), "enterprise")
        self.assertEqual(track_for_weekday(date(2026, 11, 2)), "enterprise")  # Monday
        # Tue (1), Fri (4) -> gov
        self.assertEqual(track_for_weekday(1), "gov")
        self.assertEqual(track_for_weekday(4), "gov")
        self.assertEqual(track_for_weekday("2026-11-03"), "gov")  # Tuesday
        # Wed (2), Sat (5) -> other
        self.assertEqual(track_for_weekday(2), "other")
        self.assertEqual(track_for_weekday(5), "other")
        self.assertEqual(track_for_weekday("2026-11-04"), "other")  # Wednesday
        # Sun (6) -> all
        self.assertEqual(track_for_weekday(6), "all")

    def test_three_stage_incremental_diff_skips_unchanged_resolved_and_runs_changed_or_backfill(self):
        # 1. Resolved item (taipei-ai-tools has conditional_deadline) -> SKIP_UNCHANGED
        taipei = self.candidate("taipei-ai-tools")
        res_skip = evaluate_incremental_diff(taipei, self.observations)
        self.assertFalse(res_skip["should_run"])
        self.assertEqual(res_skip["decision"], "SKIP_UNCHANGED")

        # 2. Content hash changed -> RUN_CHANGED
        res_changed = evaluate_incremental_diff(
            taipei,
            self.observations,
            observed_raw_sha256="f" * 64,
        )
        self.assertTrue(res_changed["should_run"])
        self.assertEqual(res_changed["decision"], "RUN_CHANGED")

        # 3. Candidate fingerprint changed or new candidate -> RUN_NEW
        modified = deepcopy(taipei)
        modified["title"] = "SYNTH updated title"
        res_new = evaluate_incremental_diff(modified, self.observations)
        self.assertTrue(res_new["should_run"])
        self.assertEqual(res_new["decision"], "RUN_NEW")

        # 4. Undetermined item -> RUN_BACKFILL (and cooldown when subkind is regulation/no_schedule + same parser_sha256)
        synth_obs = deepcopy(self.observations)
        synth_obs["records"][taipei["candidate_id"]]["policy"] = {
            "version": "time-policy-1",
            "submission_mode": "undetermined",
            "review_mode": "not_stated",
            "rules": [],
            "gaps": ["time_not_projected"],
        }
        res_backfill = evaluate_incremental_diff(taipei, synth_obs)
        self.assertTrue(res_backfill["should_run"])
        self.assertEqual(res_backfill["decision"], "RUN_BACKFILL")

        synth_obs["records"][taipei["candidate_id"]]["undetermined_subkind"] = "regulation_without_schedule"
        synth_obs["records"][taipei["candidate_id"]]["parser_sha256"] = "p" * 64
        res_cooldown = evaluate_incremental_diff(taipei, synth_obs, current_parser_sha256="p" * 64)
        self.assertFalse(res_cooldown["should_run"])
        self.assertEqual(res_cooldown["decision"], "SKIP_UNCHANGED")
        self.assertEqual(res_cooldown["reason"], "cooldown_regulation_without_schedule")

        # 5. Refinement mode (procedure_only) skipped by default, run when include_refinement=True
        proc_cand = next(
            c for c in self.candidates
            if self.observations["records"][c["candidate_id"]].get("policy", {}).get("submission_mode") == "procedure_only"
        )
        self.assertFalse(evaluate_incremental_diff(proc_cand, self.observations, include_refinement=False)["should_run"])
        res_refine = evaluate_incremental_diff(proc_cand, self.observations, include_refinement=True)
        self.assertTrue(res_refine["should_run"])
        self.assertEqual(res_refine["decision"], "RUN_BACKFILL")

    def test_gate_3_chunk_level_diff_reuses_completed_chunks_for_same_revision(self):
        chunks = [
            {"chunk_id": "c-111", "units": [{"unit_id": "u-1"}]},
            {"chunk_id": "c-222", "units": [{"unit_id": "u-2"}]},
        ]
        cache = {
            "c-111": {"complete": True, "source_revision": "rev-A", "claims": [{"value": "2026-10-01"}]},
        }
        pending, reused = diff_document_chunks(chunks, cache, source_revision="rev-A")
        self.assertEqual([c["chunk_id"] for c in pending], ["c-222"])
        self.assertEqual(len(reused), 1)
        self.assertEqual(reused[0]["chunk"]["chunk_id"], "c-111")

        # Revision mismatch invalidates chunk cache
        pending_new_rev, reused_new_rev = diff_document_chunks(chunks, cache, source_revision="rev-B")
        self.assertEqual(len(pending_new_rev), 2)
        self.assertEqual(len(reused_new_rev), 0)

    def test_track_execution_planner_and_incremental_action_skip(self):
        # 只看已有時間紀錄且已判定的候選；新進候選尚未回放、時間仍待補的要回填，本來就該排入執行。
        records = self.observations["records"]
        observed = [c for c in self.candidates if records.get(c["candidate_id"], {}).get("candidate_sha256") == candidate_fingerprint(c)
                    and records[c["candidate_id"]]["policy"]["submission_mode"] != "undetermined"]
        expected = sum(classify_source_track(c) == "enterprise" for c in observed)
        self.assertGreater(expected, 0)
        plan_ent = plan_track_execution(observed, self.observations, track="enterprise", max_sources=5)
        self.assertEqual(plan_ent["track"], "enterprise")
        self.assertEqual(plan_ent["total_in_track"], expected)
        self.assertEqual(plan_ent["run_candidate_count"], 0)
        self.assertEqual(plan_ent["skip_candidate_count"], expected)

        # With include_refinement=True, procedure_only items in enterprise are selected for refinement
        ids_refine, _ = resolve_action_sources(
            "track:enterprise", self.candidates, self.observations, max_sources=5, include_refinement=True
        )
        self.assertGreaterEqual(len(ids_refine), 3)

        # When incremental_only=True on already-resolved taipei-ai-tools, 0 HTTP requests are made
        (ROOT / "work").mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT / "work") as d, patch.dict("os.environ", {"OPENGSA_MODEL_MODE": "off"}):
            report = run(Path(d) / "inc", "taipei-ai-tools", incremental_only=True)
            self.assertEqual(report["source_http_requests"], 0)
            self.assertEqual(report["incremental_diff"]["skip_candidate_count"], 1)
            self.assertEqual(report["incremental_diff"]["run_candidate_count"], 0)


if __name__ == "__main__":
    unittest.main()
