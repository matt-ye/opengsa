"""Synthetic decisions and mock GET only; never approve or alter production data."""
from copy import deepcopy
import json
import subprocess
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.build_review_workspace import build_workspace, merge_decisions
from scripts.check_data import validate, validate_candidate_snapshot
from scripts.extract_candidates import extract_from_in_memory_blocks
from scripts.review_candidates import build_review_report, candidate_fingerprint
from scripts.review_context import refresh_context
from scripts.scan_sources import Fetcher, VERSION, digest, html_document, normalized
from scripts.verify_candidates import classify_review_gaps, verify_candidate

ROOT=Path(__file__).resolve().parents[1]


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


class ReviewWorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.config=read(ROOT/"data/scan-sources.json")
        self.source=deepcopy(next(s for s in self.config["sources"] if s["id"]=="taipei-ai-tools"))
        self.source["title"]="SYNTH 合成 AI 工具補助"
        self.config["sources"]=[self.source]
        self.pilot=read(ROOT/"data/pilot.json")
        self.ledger={"schema_version":"1.1.0","reviews":[]}
        texts=["SYNTH：AI工具合成測試，不是真實補助。",
            "18歲以上至35歲、設籍臺北市6個月以上青年。",
            "具學籍或本年度應屆畢業資格。",
            "補助期間115年（以下同）8月1日至10月31日止。",
            "每人每年最高補助以新臺幣4,000元為限；本市低收入戶最高補助以8,000元為限。",
            "最後達成日次日起1個月內申請，最遲11月10日前提出申請。",
            "申請日以送達本局之日為準。", "本計畫申請文件應以書面方式提出。", "經費用罄可提前停止。"]
        self.html=("<html><nav>counter 1</nav><div class='wysiwyg'><div class='content'>"+
            "".join("<p>"+t+"</p>" for t in texts)+"</div></div></html>").encode()
        self.blocks,attachments=html_document(self.html,self.source,self.source["url"],self.config["allowed_hosts"])
        semantic=digest([[normalized(b["text"]) for b in self.blocks],attachments])
        revision=digest([self.source["url"],semantic,digest([VERSION,self.source])])
        self.cand=extract_from_in_memory_blocks(self.source,self.blocks,revision,"2026-10-30T12:00:00+08:00",
            as_of="2026-10-30",extraction_strategy="rules_only")[0]
        self.bundle={"schema_version":"1.1.0-candidate","generated_at":"2026-10-30T12:00:00+08:00",
            "as_of":"2026-10-30","timezone":"Asia/Taipei","model_enabled":False,"model_calls":0,
            "official_data_modified":False,"candidates":[self.cand]}
        self.decisions={"schema_version":"1.1.0","reviews":[{
            "candidate_id":self.cand["candidate_id"],"source_id":self.source["id"],"revision_id":revision,
            "candidate_sha256":candidate_fingerprint(self.cand),"action":"applied","reviewer":"SYNTH-independent",
            "reviewed_on":"2026-10-30","reason":"SYNTH offline test only, not an actual human approval"}]}

    def refresh(self,html=None,config=None):
        body=html if html is not None else self.html
        def transport(url,headers,limit):
            if url.endswith("/robots.txt"):return {"status":404,"headers":{},"body":b""}
            self.assertEqual(url,self.source["url"])
            return {"status":200,"headers":{"content-type":"text/html; charset=utf-8"},"body":body}
        config=config or self.config
        fetcher=Fetcher(config,transport=transport,sleeper=lambda _:None)
        return refresh_context(self.bundle,config,fetcher)

    def test_personal_and_operational_gaps_do_not_confer_personal_eligibility(self):
        self.assertEqual(validate_candidate_snapshot(self.bundle,self.config),[])
        self.assertEqual(self.cand["verification"]["status"],"passed_automated_checks")
        groups=classify_review_gaps(self.cand)
        self.assertEqual(groups["source"],[])
        self.assertTrue(groups["personal"] and groups["operational"])
        self.assertEqual(self.cand["application"]["state"],"unknown")
        changed=deepcopy(self.cand)
        changed["gaps_and_conflicts"]["missing_fields"].append("ai_tools:age_reference_date")
        checked=verify_candidate(changed,in_memory_blocks=self.blocks)
        self.assertEqual(checked["verification"]["status"],"passed_with_gaps")
        changed["gaps_and_conflicts"]["missing_fields"]=["unclassified_source_requirement"]
        self.assertEqual(verify_candidate(changed,in_memory_blocks=self.blocks)["verification"]["status"],"passed_with_gaps")

    def test_semantic_revision_ignores_navigation_but_detects_source_and_profile_changes(self):
        contexts,status,count=self.refresh(self.html.replace(b"counter 1",b"counter 999"))
        self.assertEqual(count,2)  # One robots GET and one official page GET, mock only.
        self.assertEqual(status[self.cand["candidate_id"]],"fresh_semantic_revision_matched")
        self.assertEqual(contexts[self.source["url"]],self.blocks)
        for html,config in [(self.html.replace(b"4,000",b"4,500"),None),(self.html,deepcopy(self.config))]:
            if config:config["sources"][0]["review_note"]+=" SYNTH changed profile"
            contexts,status,_=self.refresh(html,config)
            self.assertEqual(contexts,{})
            self.assertEqual(status[self.cand["candidate_id"]],"source_revision_changed_requires_rescan")

    def test_disabled_or_unregistered_source_never_fetched(self):
        self.config["sources"][0]["enabled"]=False
        with patch("scripts.review_context.Fetcher") as factory:
            fetcher=factory.return_value;fetcher.count=0
            contexts,status,count=refresh_context(self.bundle,self.config,fetcher)
            fetcher.get.assert_not_called()
        self.assertEqual(contexts,{})
        self.assertEqual(count,0)
        self.assertEqual(status[self.cand["candidate_id"]],"source_disabled_or_unregistered")

    def test_intents_bound_to_all_claims_and_independent_identity(self):
        for field,value in [("candidate_id","wrong"),("source_id","wrong"),("revision_id","0"*64),
                ("candidate_sha256","0"*64),("reviewer"," "),("reason"," "),
                ("reviewer"," "+self.cand["review"]["editor"].upper()+" "),("reviewed_on","2999-01-01")]:
            decisions=deepcopy(self.decisions);decisions["reviews"][0][field]=value
            with self.subTest(field=field,value=value),self.assertRaises(ValueError):
                merge_decisions(self.ledger,decisions,self.bundle)
        for mutate in [lambda c:c["gaps_and_conflicts"]["missing_fields"].clear(),
                lambda c:c.update(opportunity_id="SYNTH-different-target"),
                lambda c:c["review"].update(editor="SYNTH-other-editor")]:
            bundle=deepcopy(self.bundle);mutate(bundle["candidates"][0])
            with self.assertRaises(ValueError):merge_decisions(self.ledger,self.decisions,bundle)

    def test_offline_preview_does_not_publish_or_reuse_outputs(self):
        original=deepcopy(self.pilot)
        with tempfile.TemporaryDirectory() as directory:
            output=Path(directory)/"review"
            result=build_workspace(self.bundle,self.pilot,self.config,output,export_draft=True)
            self.assertEqual(result["publication_status"],"no_approved_candidates")
            self.assertEqual(result["promotion_ready"],0)
            self.assertFalse(result["published"])
            self.assertFalse((output/"data-pr.patch").exists())
            html=(output/"candidate-preview.html").read_text(encoding="utf-8")
            self.assertIn('data-review-preview="true"',html)
            self.assertIn("未核准／未發布",html)
            self.assertIn(self.cand["title"],html)
            self.assertEqual(self.pilot,original)
            with self.assertRaises(ValueError):build_workspace(self.bundle,self.pilot,self.config,output)

    def test_synthetic_approval_builds_valid_proposals_without_mutating_official_files(self):
        before={p:(ROOT/p).read_bytes() for p in ["data/pilot.json","data/scan-reviews.json","data/candidates/ai-tools-115.json"]}
        contexts,status,count=self.refresh()
        with tempfile.TemporaryDirectory() as directory:
            output=Path(directory)/"review"
            result=build_workspace(self.bundle,self.pilot,self.config,output,ledger=self.ledger,decisions=self.decisions,
                contexts=contexts,context_status=status,http_requests=count,export_draft=True)
            self.assertEqual(result["publication_status"],"proposal_generated_not_published")
            proposal=read(output/"pilot-proposal.json")
            self.assertEqual(validate(proposal),[])
            self.assertEqual(len(proposal["opportunities"]),len(self.pilot["opportunities"])+1)
            self.assertEqual(proposal["as_of"],"2026-10-30")
            self.assertEqual(proposal["sources"][:len(self.pilot["sources"])],self.pilot["sources"])
            self.assertTrue(all(o["application"]["as_of"]==proposal["as_of"] for o in proposal["opportunities"]))
            promoted=next(o for o in proposal["opportunities"] if o["id"]==self.cand["opportunity_id"])
            self.assertEqual(promoted["application"]["state"],"unknown")
            self.assertEqual(promoted["review"]["independent_reviewer"],"SYNTH-independent")
            patch_text=(output/"data-pr.patch").read_text(encoding="utf-8")
            self.assertIn("a/data/pilot.json",patch_text)
            self.assertIn("a/data/scan-reviews.json",patch_text)
            applied_check=subprocess.run(["git","apply","--check",str(output/"data-pr.patch")],cwd=ROOT,capture_output=True)
            self.assertEqual(applied_check.returncode,0,applied_check.stderr.decode(errors="replace"))
            self.assertEqual(read(output/"reviews-proposal.json"),self.decisions)
            self.assertIn('"publication_status": "proposal_generated_not_published"',(output/"review.html").read_text(encoding="utf-8"))
        for path,content in before.items():self.assertEqual((ROOT/path).read_bytes(),content)

    def test_missing_or_changed_source_context_blocks_export_even_with_signed_intent(self):
        contexts,status,_=self.refresh()
        changed_context,changed_status,_=self.refresh(self.html.replace(b"4,000",b"4,500"))
        for context,state in [(None,None),(contexts,None),(changed_context,changed_status)]:
            with tempfile.TemporaryDirectory() as directory:
                result=build_workspace(self.bundle,self.pilot,self.config,Path(directory)/"review",decisions=self.decisions,
                    contexts=context,context_status=state,export_draft=True)
                self.assertEqual(result["publication_status"],"blocked")
                self.assertFalse((Path(directory)/"review/data-pr.patch").exists())

    def test_candidate_cannot_self_approve_and_malformed_bundle_cannot_promote(self):
        contexts={self.source["url"]:self.blocks}
        bundle=deepcopy(self.bundle)
        bundle["candidates"][0]["review"].update(status="reviewed",promotion_ready=True,
            independent_reviewer="SYNTH-forged",reviewed_on="2026-10-30",
            approved_candidate_sha256=candidate_fingerprint(self.cand))
        verified,summary,_=build_review_report(bundle,self.pilot,reviews_data=self.ledger,in_memory_blocks_by_source=contexts)
        self.assertEqual(summary["promotion_ready"],0)
        self.assertEqual(verified["candidates"][0]["review"]["status"],"pending")
        bundle=deepcopy(self.bundle);del bundle["generated_at"]
        _,summary,_=build_review_report(bundle,self.pilot,reviews_data=self.decisions,in_memory_blocks_by_source=contexts)
        self.assertTrue(summary["bundle_schema_errors"])
        self.assertEqual(summary["promotion_ready"],0)

    def test_intent_fingerprint_invalid_after_candidate_content_change(self):
        bundle=deepcopy(self.bundle);bundle["candidates"][0]["title"]+=" edited after review"
        with tempfile.TemporaryDirectory() as directory,self.assertRaises(ValueError):
            build_workspace(bundle,self.pilot,self.config,Path(directory)/"review",decisions=self.decisions)


if __name__=="__main__":unittest.main()
