"""Synthetic source coverage controls; all HTTP/PDF transports are mocked."""
from copy import deepcopy
import json
from pathlib import Path
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from scripts.audit_sources import canonical_url,collect_inventory,HOST_FAILURES
from scripts.check_data import validate_candidate_snapshot
from scripts.extract_candidates import extract_from_in_memory_blocks
from scripts.review_context import refresh_context
from scripts.scan_sources import Fetcher,scan,VERSION,digest,pdf_document,ScanError
from scripts.verify_candidates import verify_candidate

ROOT=Path(__file__).resolve().parents[1]


class SourceAuditTests(unittest.TestCase):
    def setUp(self):
        self.config=json.loads((ROOT/"data/scan-sources.json").read_text(encoding="utf-8"))

    def extract(self,sid,texts,url=None):
        source=next(s for s in self.config["sources"] if s["id"]==sid)
        blocks=[{"locator":f"SYNTH/{i}","text":text} for i,text in enumerate(texts)]
        return extract_from_in_memory_blocks(source,blocks,"a"*64,"2026-10-31T05:00:00+00:00",
            url=url,as_of="2026-10-31",extraction_strategy="rules_only"),blocks

    def test_query_keys_are_not_html_entities_and_path_denial_is_not_host_denial(self):
        url="https://rd.mc.ntu.edu.tw/bomrd/ntu2/form0.asp?pno=25&LTPno=47"
        self.assertEqual(canonical_url(url),url)
        self.assertEqual(canonical_url(url.replace("&","&amp;")),url)
        self.assertNotIn("robots_denied",HOST_FAILURES)
        self.assertIn("robots_not_plain_rules",HOST_FAILURES)
        with self.assertRaises(ValueError):canonical_url(url.replace("&LT","<"))

    def test_one_transport_retry_is_bounded_but_access_denial_is_not_retried(self):
        url="https://www.aca.ntu.edu.tw/SYNTH"
        calls=[]
        def transient(target,headers,limit):
            calls.append(target)
            if len(calls)==1:raise ScanError("transport_error")
            return {"status":404 if target.endswith("robots.txt") else 200,"headers":{},"body":b"SYNTH"}
        fetcher=Fetcher(self.config,transport=transient,sleeper=lambda _:None)
        self.assertEqual(fetcher.get(url,{},100)["status"],200)
        self.assertEqual(fetcher.count,3)
        denied=[]
        def forbidden(target,headers,limit):
            denied.append(target)
            return {"status":403,"headers":{},"body":b""}
        with self.assertRaises(ScanError):Fetcher(self.config,transport=forbidden,sleeper=lambda _:None).get(url,{},100)
        self.assertEqual(len(denied),1)

    def test_inventory_preserves_origin_and_correct_medical_source(self):
        rows=collect_inventory()
        self.assertTrue(any("pno=25&LTPno=47" in r["url"] for r in rows))
        self.assertTrue(all(r["used_in"] and "<" not in r["url"] for r in rows))
        self.assertEqual(len(rows),len({r["url"] for r in rows}))

    def test_split_salary_heading_supports_minimum_monthly_amount_and_grade(self):
        candidates,blocks=self.extract("nstc-assistant-rule",[
            "SYNTH 研究生兼任人員規則。", "專任人員月支酬金不得低於下列金額：",
            "專科級：", "三萬零四百元。", "學士級：三萬六千三百元。", "碩士級（含）以上：四萬一千五百元。",
            "二、兼任人員費用：", "研究生每月均應至少支給新臺幣六千元。"])
        cand=candidates[0]
        self.assertEqual(cand["verification"]["errors"],[])
        self.assertEqual(cand["eligibility"]["degrees"],["master","phd"])
        self.assertEqual([b["amount_min"] for b in cand["benefit"]["items"]],[30400,36300,41500,6000])
        self.assertEqual([b["branch_or_tier"] for b in cand["benefit"]["items"][:3]],["專任人員／專科級","專任人員／學士級","專任人員／碩士級"])
        self.assertTrue(all(b["unit"]=="per_month" and b["basis"]=="minimum" and b["amount_max"] is None for b in cand["benefit"]["items"]))
        wrong=deepcopy(cand)
        wrong["field_evidence"]=[e for e in wrong["field_evidence"] if e["locator"]!="SYNTH/1"]
        errors=verify_candidate(wrong,in_memory_blocks=blocks)["verification"]["errors"]
        self.assertTrue(any(e.startswith("unsupported_monthly_salary_context") for e in errors))

    def test_annual_application_pdf_is_not_policy_or_a_prohibited_funder_branch(self):
        candidates,_=self.extract("ntu-doctoral-funding",[
            "SYNTH 115學年度第2梯次教育部博士生獎學金申請說明", "本國籍非在職博士班一至三年級在學學生。",
            "不得兼領國科會獎學金。", "另有配合款10,000元，單位待核。"],
            "https://www.aca.ntu.edu.tw/SYNTH-application.pdf")
        self.assertEqual(len(candidates),1)
        cand=candidates[0]
        self.assertEqual(cand["program_key"],"ntu-moe-phd")
        self.assertEqual(cand["cycle"]["kind"],"academic_year")
        self.assertEqual(cand["cycle"]["year"],115)
        self.assertEqual(cand["benefit"]["items"],[])
        self.assertIn("benefit.unit_and_payee",cand["gaps_and_conflicts"]["missing_fields"])
        self.assertFalse(cand["review"]["promotion_ready"])

    def test_missing_year_is_unknown_in_doctoral_calls(self):
        candidates,_=self.extract("ntu-doctoral-funding",["SYNTH 教育部博士生獎學金，本國籍博士班在學學生，每月四萬元。"])
        self.assertIsNone(candidates[0]["cycle"]["year"])
        self.assertEqual(candidates[0]["cycle"]["year_system"],"unknown")
        self.assertNotIn("None",candidates[0]["title"])
        self.assertIn("coverage_gap:cycle_year_unknown",candidates[0]["verification"]["warnings"])

    def test_pending_attachment_requires_exact_parent_and_registered_url(self):
        bundle=json.loads((ROOT/"data/candidates/ai-tools-115.json").read_text(encoding="utf-8"))
        bundle["candidates"]=bundle["candidates"][:1]
        source=next(s for s in self.config["sources"] if s["id"]=="taipei-ai-tools")
        source["known_attachment_urls"]=["https://youth.gov.taipei/SYNTH.pdf"]
        meta=bundle["candidates"][0]["source_metadata"]
        meta.update(url=source["known_attachment_urls"][0],parent_url=source["url"])
        self.assertEqual(validate_candidate_snapshot(bundle,self.config),[])
        source["evidence_mode"]="hash_only"
        self.assertTrue(any("evidence policy" in e for e in validate_candidate_snapshot(bundle,self.config)))
        source["evidence_mode"]="short_excerpt"
        meta["parent_url"]="https://youth.gov.taipei/wrong"
        self.assertTrue(validate_candidate_snapshot(bundle,self.config))
        meta["parent_url"]=source["url"];meta["url"]="https://youth.gov.taipei/unregistered.pdf"
        self.assertTrue(validate_candidate_snapshot(bundle,self.config))

    def test_primary_pdf_source_uses_pdf_parser_and_required_markers(self):
        config=deepcopy(self.config)
        source=deepcopy(next(s for s in config["sources"] if s["id"]=="ntu-eecs-scholarship"))
        config["sources"]=[source];source["required_markers"]=["SYNTH 合成規則"]
        def transport(url,headers,limit):
            return {"status":404 if url.endswith("robots.txt") else 200,"headers":{},"body":b"" if url.endswith("robots.txt") else b"%PDF-SYNTH"}
        for text,expected in [("SYNTH 合成規則：每月1,000元。","changed"),("SYNTH wrong document","required_marker_missing")]:
            with patch("scripts.scan_sources.pdf_document",return_value=[{"locator":"PDF page 1","text":text}]),patch("scripts.scan_sources.html_document") as html_parser:
                _,report=scan(config,fetcher=Fetcher(config,transport=transport,sleeper=lambda _:None))
                html_parser.assert_not_called()
                self.assertEqual(report["documents"][0]["status"],expected)

    def test_pdf_compatibility_glyphs_are_canonical_before_date_extraction(self):
        payload=json.dumps([{"page":1,"text":"１１５學年度\nSYNTH 合成控制"}],ensure_ascii=False).encode()
        with patch("scripts.scan_sources.subprocess.run",return_value=SimpleNamespace(returncode=0,stdout=payload)):
            blocks=pdf_document(b"%PDF-SYNTH")
        self.assertEqual(blocks[0]["text"],"115學年度")

    def test_attachment_refresh_requires_fresh_parent_discovery_before_pdf(self):
        source=deepcopy(next(s for s in self.config["sources"] if s["id"]=="ntu-president-award"))
        pdf="https://www.aca.ntu.edu.tw/SYNTH-rules.pdf"
        source["known_attachment_urls"]=[pdf]
        blocks=[{"locator":"PDF page 1","text":"SYNTH 合成規則"}]
        revision=digest([pdf,digest([[b["text"] for b in blocks],[]]),digest([VERSION,source])])
        candidate={"candidate_id":"SYNTH","source_metadata":{"source_id":source["id"],"url":pdf,"parent_url":source["url"],"revision_id":revision}}
        config={**self.config,"sources":[source]}
        for discovered in (False,True):
            calls=[]
            def transport(url,headers,limit):
                calls.append(url)
                if url.endswith("robots.txt"):return {"status":404,"headers":{},"body":b""}
                if url==pdf:return {"status":200,"headers":{},"body":b"%PDF-SYNTH"}
                body='<div class="article-center"><p>研究生校長獎申請時間，SYNTH合成說明。'+"合成控制資料。"*20+'</p>'
                if discovered:body+='<a href="'+pdf+'">設置辦法.pdf</a>'
                return {"status":200,"headers":{"content-type":"text/html"},"body":(body+'</div>').encode()}
            with patch("scripts.review_context.pdf_document",return_value=blocks):
                contexts,status,_=refresh_context({"candidates":[candidate]},config,Fetcher(config,transport=transport,sleeper=lambda _:None))
            if discovered:self.assertEqual(status["SYNTH"],"fresh_semantic_revision_matched")
            else:
                self.assertEqual(contexts,{})
                self.assertEqual(status["SYNTH"],"attachment_not_discovered")
                self.assertNotIn(pdf,calls)


if __name__=="__main__":unittest.main()
