"""反例測試；使用合成內容，不連外、不使用實際金鑰。"""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import unittest

from scripts.audit_providers import audit_provider
from scripts.check_data import validate
from scripts.evaluate_deadlines import evaluate_application_window, evaluate_eligibility
from scripts.extract_candidates import extract_from_in_memory_blocks, refetch_and_extract_candidates
from scripts.providers import provider_settings
from scripts.review_candidates import (apply_review_ledger, build_review_report,
    candidate_fingerprint, candidate_to_pilot_opportunity, validate_review_ledger, export_pr_candidate_draft)
from scripts.scan_sources import validate_config, scan, Fetcher
from scripts.verify_candidates import verify_candidate, amount_supported, date_supported

ROOT = Path(__file__).resolve().parents[1]


class ReliabilityTests(unittest.TestCase):
    def setUp(self):
        self.config=json.loads((ROOT/"data/scan-sources.json").read_text(encoding="utf-8"))
        self.pilot=json.loads((ROOT/"data/pilot.json").read_text(encoding="utf-8"))
        self.source=next(s for s in self.config["sources"] if s["id"]=="sinica-phd-fellowship")
        self.blocks=[{"locator":"id","text":"博士候選人在學學生，非全時有給職。"},
                     {"locator":"money","text":"每月新臺幣43000元。"},
                     {"locator":"dates","text":"學生申請期間2025-03-01至2025-04-10截止。"}]
        self.cand=extract_from_in_memory_blocks(self.source,self.blocks,revision_id="a"*64,
            observed_at="2026-10-30T09:17:00+08:00",as_of="2026-10-30")[0]

    def test_production_config_and_ledger_cli_offline(self):
        validate_config(self.config)
        validate_review_ledger(json.loads((ROOT/"data/scan-reviews.json").read_text(encoding="utf-8")))
        result=subprocess.run([sys.executable,"-B","scripts/scan_sources.py","--check-config"],cwd=ROOT,capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn("offline",result.stdout)
        duplicate=deepcopy(self.config)
        duplicate["sources"].append(duplicate["sources"][0])
        with self.assertRaises(ValueError): validate_config(duplicate)
        incomplete=deepcopy(self.config)
        del incomplete["sources"][0]["max_pdfs"]
        with self.assertRaises(ValueError): validate_config(incomplete)

    def test_budget_deferral_rotates_sources(self):
        config=deepcopy(self.config)
        config.update(sources=config["sources"][:2],max_changed_documents=1,minimum_host_interval_seconds=0)
        def transport(url,headers,limit):
            if url.endswith("robots.txt"):return {"status":404,"body":b"","headers":{}}
            source=next(s for s in config["sources"] if s["url"]==url)
            text=" ".join(source["required_markers"])+" 合成測試，不代表真實公告。"*15
            body=f'<div class="article-center">{text}</div>'.encode()
            return {"status":200,"headers":{"content-type":"text/html"},"body":body}
        state,report=scan(config,None,fetcher=Fetcher(config,transport=transport,sleeper=lambda _:None))
        self.assertEqual(state["next_source_index"],1)
        self.assertEqual(report["changed_documents"],1)
        _,report=scan(config,state,fetcher=Fetcher(config,transport=transport,sleeper=lambda _:None))
        self.assertEqual(report["documents"][0]["source_id"],config["sources"][1]["id"])
        self.assertEqual(report["documents"][0]["status"],"changed")

    def test_quote_budget_and_negated_candidate_are_conservative(self):
        blocks=self.blocks+[{"locator":f"q{i}","text":f"額外條款{i}：每月新臺幣{45000+i}元。"} for i in range(8)]
        rows=extract_from_in_memory_blocks(self.source,blocks,revision_id="c"*64,observed_at="2026-10-30T09:17:00+08:00",as_of="2026-10-30")
        self.assertLessEqual(sum(len(e.get("excerpt") or "") for c in rows for e in c["field_evidence"]),120)
        self.assertTrue(any(e["evidence_mode"]=="hash_only" for c in rows for e in c["field_evidence"]))
        rows=extract_from_in_memory_blocks(self.source,[{"locator":"id","text":"博士班在學學生，不需博士候選人資格。"}],revision_id="c"*64,observed_at="2026-10-30T09:17:00+08:00",as_of="2026-10-30")
        self.assertEqual(rows[0]["eligibility"]["candidate"]["mode"],"unknown")

    def test_export_refuses_to_relabel_observation_date(self):
        cand=deepcopy(self.cand)
        cand["verification"]["status"]="passed_automated_checks"
        cand["review"].update(status="reviewed",promotion_ready=True,independent_reviewer="SYNTH-reviewer")
        cand["review"]["approved_candidate_sha256"]=candidate_fingerprint(cand)
        pilot=deepcopy(self.pilot)
        pilot["as_of"]="2026-10-28"
        with self.assertRaisesRegex(ValueError,"Snapshot dates differ"):
            export_pr_candidate_draft({"candidates":[cand]},pilot,ROOT/"work/no-date-relabel.json")

    def test_wrong_year_unproven_start_and_result_rejected(self):
        cand=deepcopy(self.cand)
        cand["schedule"]["steps"][0]["deadline"]["value"]="2026-04-10"
        errors=verify_candidate(cand,in_memory_blocks=self.blocks)["verification"]["errors"]
        self.assertTrue(any("hallucinated_date" in e for e in errors))
        cand=deepcopy(self.cand)
        cand["field_evidence"]=[e for e in cand["field_evidence"] if e["field_path"]!="schedule.application_start"]
        cand["schedule"]["result_date"].update(kind="date",certainty="confirmed",value="2099-12-31")
        errors=verify_candidate(cand,in_memory_blocks=self.blocks)["verification"]["errors"]
        self.assertIn("missing_evidence:schedule.application_start",errors)
        self.assertIn("missing_evidence:schedule.result_date",errors)

    def test_report_without_context_cannot_wash_out_rejection(self):
        cand=deepcopy(self.cand)
        cand["benefit"]["items"][0].update(amount_min=44000,amount_max=44000)
        cand=verify_candidate(cand,in_memory_blocks=self.blocks)
        self.assertEqual(cand["verification"]["status"],"failed_automated_checks")
        bundle={"schema_version":"1.1.0-candidate","as_of":"2026-10-30","timezone":"Asia/Taipei","model_enabled":False,"model_calls":0,"official_data_modified":False,"candidates":[cand]}
        _,summary,_=build_review_report(bundle,self.pilot)
        self.assertEqual(summary["failed_automated_checks"],1)
        self.assertEqual(summary["promotion_ready"],0)
        self.assertEqual(verify_candidate(self.cand)["verification"]["status"],"needs_context")

    def test_review_requires_exact_source_date_content_and_no_gaps(self):
        cand=deepcopy(self.cand)
        entry={"revision_id":"a"*64,"source_id":self.source["id"],"candidate_id":cand["candidate_id"],
               "candidate_sha256":candidate_fingerprint(cand),"action":"applied","reviewer":"SYNTH-reviewer","reviewed_on":"2026-10-30","reason":"Synthetic test only"}
        for field,value in [("source_id","wrong"),("reviewed_on",None),("candidate_sha256","b"*64)]:
            broken={**entry,field:value}
            result=apply_review_ledger(cand,{"a"*64:broken})
            self.assertFalse(result["review"]["promotion_ready"])
        cand["verification"]["status"]="passed_with_gaps"
        self.assertFalse(apply_review_ledger(cand,{"a"*64:entry})["review"]["promotion_ready"])

    def test_result_and_eligibility_survive_pilot_conversion(self):
        cand=deepcopy(self.cand)
        cand["schedule"]["result_date"].update(kind="date",certainty="expected",value="2026-12-01")
        opp=candidate_to_pilot_opportunity(cand)
        self.assertEqual(opp["result"]["certainty"],"expected")
        self.assertEqual(opp["eligibility"]["employment_status"],"unemployed_or_no_fulltime_pay")
        draft=deepcopy(self.pilot)
        # Reuse an existing source ID for contract-only checks, avoiding a phantom source.
        source_id=draft["sources"][0]["id"]
        def rewrite(value):
            if isinstance(value,dict):
                if "source" in value: value["source"]=source_id
                for child in value.values(): rewrite(child)
            elif isinstance(value,list):
                for child in value: rewrite(child)
        rewrite(opp)
        opp["application"].update(as_of=draft["as_of"],state="unknown",refs=[])
        draft["opportunities"].append(opp)
        self.assertEqual(validate(draft),[])

    def test_required_unknown_identity_is_not_a_match(self):
        item={"eligibility":{"degrees":["phd"],"institution":"NTU","year_limit":{"mode":"unlimited"},"candidate":{"mode":"required"}},"compatibility":{"mode":"allowed"}}
        for profile in [{"degree":"phd","institution":"NTU","is_candidate":"unknown"},{"degree":"phd","institution":"unknown","is_candidate":True}]:
            self.assertEqual(evaluate_eligibility(item,profile)["criteria"],"needs_information")

    def test_pilot_start_is_used_but_inference_is_not_confirmed_open(self):
        item={"start":{"kind":"date","value":"2026-11-01","certainty":"confirmed"},"steps":[{"actor":"student","action":"申請","deadline":{"kind":"date","value":"2026-11-30","note":"合成期限"},"refs":[]}]}
        self.assertEqual(evaluate_application_window(item,"2026-11-05")["state"],"open")
        item["start"]["certainty"]="inferred"
        self.assertEqual(evaluate_application_window(item,"2026-11-05")["state"],"unknown")

    def test_audit_never_probes_paid_or_unknown_models_and_never_leaks_key(self):
        calls=[]
        def request(url,key,payload=None):
            calls.append((url,payload))
            return 200,{"data":[{"id":"gpt-oss-120b"}]},{}
        row=audit_provider("cerebras",{"OPENGSA_CEREBRAS_API_KEY":"SYNTH-PRIVATE-KEY"},True,request)
        self.assertEqual(len(calls),1)
        self.assertEqual(row["inference_status"],"skipped_billing_or_credits_unconfirmed")
        self.assertNotIn("SYNTH-PRIVATE-KEY",json.dumps(row))
        self.assertIsNone(row["cost_usd"])

    def test_openrouter_uses_only_catalog_confirmed_zero_prices_and_single_probe(self):
        calls=[]
        def request(url,key,payload=None):
            calls.append((url,payload))
            if url.endswith("/models"):
                return 200,{"data":[{"id":"paid","pricing":{"prompt":"1","completion":"1"}},{"id":"safe:free","pricing":{"prompt":"0","completion":"0"}}]},{}
            if url.endswith("/key"):return 200,{"data":{"free_model_daily_requests":{"remaining":20}}},{}
            self.assertEqual(payload["model"],"safe:free")
            return 429,{},{}
        row=audit_provider("openrouter",{"OPENGSA_OPENROUTER_API_KEY":"SYNTH"},True,request)
        self.assertEqual(row["inference_calls"],1)
        self.assertEqual(row["inference_status"],"http_429")
        self.assertEqual(len(calls),3)

    def test_provider_endpoint_and_region_boundaries(self):
        with self.assertRaises(ValueError):provider_settings("github",{})
        with self.assertRaises(ValueError):provider_settings("siliconflow",{})
        with self.assertRaises(ValueError):provider_settings("groq",{"OPENGSA_MODEL_BASE_URL":"https://untrusted.example/v1"})
        base,_,_=provider_settings("gemini",{"OPENGSA_MODEL_BASE_URL":"https://api.groq.com/openai/v1","OPENGSA_MODEL_NAME":"wrong"})
        self.assertIn("googleapis.com",base)

    def test_chinese_amount_grounding_handles_non_round_amounts(self):
        for amount,text in [(30400,"三萬零四百元"),(36300,"三萬六千三百元"),(41500,"四萬一千五百元"),(8000,"捌仟元")]:
            self.assertTrue(amount_supported(amount,text))
        self.assertFalse(amount_supported(4000,"44,000元"))
        self.assertFalse(amount_supported(0,"未知金額"))
        self.assertFalse(date_supported("2026-01-01","2026/1/10截止"))

    def test_disabled_source_is_not_refetched(self):
        self.config["sources"]=deepcopy(self.config["sources"])
        next(s for s in self.config["sources"] if s["id"]==self.source["id"])["enabled"]=False
        class NoNetwork:
            def get(self,*args):raise AssertionError("Disabled source must never be fetched")
        stub={"source_id":self.source["id"],"id":"c"*64,"url":self.source["url"],"facts":[]}
        bundle,statuses=refetch_and_extract_candidates([stub],self.config,fetcher=NoNetwork(),as_of="2026-10-30")
        self.assertEqual(statuses[self.source["url"]],"source_disabled_or_unregistered")
        self.assertEqual(bundle["candidates"][0]["verification"]["status"],"needs_context")

    def test_gemini_catalog_prefix_is_not_model_unavailable(self):
        row=audit_provider("gemini",{"OPENGSA_GEMINI_API_KEY":"SYNTH"},False,
            lambda *args:(200,{"models":[{"name":"models/gemini-3.5-flash-lite"}]},{}))
        self.assertTrue(row["model_present"])
        self.assertEqual(row["authentication_status"],"not_proven_by_catalog")
        self.assertEqual(row["inference_calls"],0)


if __name__ == "__main__":
    unittest.main()
