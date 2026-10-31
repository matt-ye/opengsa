"""Build local review/preview artifacts and optional approved data-PR proposals. No publishing."""
import argparse
from copy import deepcopy
from datetime import datetime, timezone, timedelta
import difflib
import json
from pathlib import Path
import sys
from collections import Counter
from urllib.parse import urlsplit

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
if str(ROOT/"scripts") not in sys.path:sys.path.insert(0,str(ROOT/"scripts"))
from scripts.check_data import validate as validate_pilot, validate_candidate_snapshot
from scripts.evaluate_deadlines import evaluate_application_window, taipei_today
from scripts.export_wireframes import export
from scripts.review_candidates import (build_review_report,candidate_fingerprint,candidate_to_pilot_opportunity,
    export_pr_candidate_draft,validate_review_ledger)
from scripts.review_context import refresh_context
from scripts.scan_sources import validate_config
from scripts.verify_candidates import classify_review_gaps


def merge_decisions(ledger, decisions, bundle):
    validate_review_ledger(ledger);validate_review_ledger(decisions)
    candidates={c["candidate_id"]:c for c in bundle["candidates"]}
    combined={(r["revision_id"],r.get("candidate_id")):deepcopy(r) for r in ledger["reviews"]}
    for decision in decisions["reviews"]:
        cand=candidates.get(decision.get("candidate_id"))
        if (not cand or decision["source_id"]!=cand["source_metadata"]["source_id"]
                or decision["revision_id"]!=cand["source_metadata"]["revision_id"]
                or decision.get("candidate_sha256")!=candidate_fingerprint(cand)):
            raise ValueError("Decision does not match the candidate/source/content; regenerate the review workspace")
        if not decision["reason"].strip() or not decision["reviewer"].strip():raise ValueError("Reviewer and reason cannot be blank")
        if decision["reviewer"].strip().casefold()==cand["review"]["editor"].strip().casefold():raise ValueError("An independent reviewer is required")
        combined[(decision["revision_id"],decision["candidate_id"])]=deepcopy(decision)
    result={"schema_version":"1.1.0","reviews":list(combined.values())}
    validate_review_ledger(result)
    return result


def add_sources(dataset, candidates, config):
    profiles={s["id"]:s for s in config["sources"]}
    for cand in candidates:
        meta=cand["source_metadata"];sid=meta["source_id"]
        if any(s["id"]==sid for s in dataset["sources"]):continue
        observed=datetime.fromisoformat(meta["observed_at"]).astimezone(timezone(timedelta(hours=8))).date().isoformat()
        dataset["sources"].append({"id":sid,"title":profiles[sid]["title"],"url":meta["url"],"authority":"official_page",
            "access":"public","checked_on":observed,"locator":"候選來源觀察；未代表獨立人工核准","owner":None,
            "ownership_status":"unassigned","proposed_review_frequency":"依來源台帳與人工覆核","automation":"not_enabled",
            "crawl_permission":"not_reviewed","next_action":"完成獨立人工覆核","redistribution":"link_and_original_summary_only"})


def candidate_preview_data(bundle,pilot,config):
    dataset=deepcopy(pilot)
    dataset["as_of"]=bundle["as_of"]
    dataset["opportunities"]=[]
    identities=Counter(c.get("opportunity_id") or c["candidate_id"] for c in bundle["candidates"])
    for candidate in bundle["candidates"]:
        cand=deepcopy(candidate)
        # Preview never presents a review intent as a published/reviewed opportunity.
        cand["review"].update(status="pending",independent_reviewer=None,reviewed_on=None,promotion_ready=False)
        item=candidate_to_pilot_opportunity(cand)
        # Each document candidate is distinct in an unpublished review, even for the same program.
        item["id"]=cand["candidate_id"]
        if identities[cand.get("opportunity_id") or cand["candidate_id"]]>1:
            kind="PDF" if urlsplit(cand["source_metadata"]["url"]).path.lower().endswith(".pdf") else "HTML"
            item["title"]+=f"（{kind}文件候選，待整併）"
        window=evaluate_application_window(item,bundle["as_of"])
        item["application"].update(state=window["state"],as_of=bundle["as_of"],reason=window["reason"])
        dataset["opportunities"].append(item)
    add_sources(dataset,bundle["candidates"],config)
    errors=validate_pilot(dataset)
    if errors:raise ValueError("Candidate preview violates the pilot contract: "+str(errors))
    return dataset


def refresh_snapshot_states(pilot,as_of):
    """Explicitly recalculate old application states; do not relabel old source observations."""
    proposal=deepcopy(pilot);proposal["as_of"]=as_of
    sources={s["id"]:s for s in proposal["sources"]}
    for item in proposal["opportunities"]:
        window=evaluate_application_window(item,as_of,sources_by_id=sources)
        item["application"].update(state=window["state"],as_of=as_of,
            reason="依既有來源重算（非重新查核來源）："+window["reason"])
    return proposal


def patch_text(before,after,path):
    return "".join(difflib.unified_diff((json.dumps(before,ensure_ascii=False,indent=2)+"\n").splitlines(True),
        (json.dumps(after,ensure_ascii=False,indent=2)+"\n").splitlines(True),fromfile="a/"+path,tofile="b/"+path))


def build_workspace(bundle,pilot,config,output,ledger=None,decisions=None,contexts=None,context_status=None,
                    export_draft=False,as_of=None,http_requests=0):
    output=Path(output).resolve()
    if output.is_relative_to(ROOT/"data"):raise ValueError("Review artifacts cannot be written into formal data")
    if output.exists() and any(output.iterdir()):raise ValueError("Use a fresh empty output directory; existing review artifacts are preserved")
    validate_config(config)
    ledger=ledger or {"schema_version":"1.1.0","reviews":[]}
    decisions=decisions or {"schema_version":"1.1.0","reviews":[]}
    errors=validate_candidate_snapshot(bundle,config)
    if errors:raise ValueError("Invalid pending candidate input: "+str(errors))
    merged=merge_decisions(ledger,decisions,bundle)
    working=deepcopy(bundle);working["as_of"]=as_of or bundle["as_of"]
    for cand in working["candidates"]:
        window=evaluate_application_window(cand,working["as_of"])
        cand["application"].update(state=window["state"],as_of=working["as_of"],reason=window["reason"])
    verified,summary,markdown=build_review_report(working,pilot,reviews_data=merged,in_memory_blocks_by_source=contexts)
    preview=candidate_preview_data(verified,pilot,config)
    rows=[]
    previous={o["id"]:o for o in pilot["opportunities"]}
    for original,cand in zip(bundle["candidates"],verified["candidates"]):
        converted=candidate_to_pilot_opportunity(cand)
        keys=("title","cycle","category","resource_kind","scope","participants","organizations","benefit","eligibility",
              "compatibility","hardship","application_method","expense_period","start","steps","result",
              "field_applicability","policy_version","evidence_status")
        old=previous.get(converted["id"])
        rows.append({"candidate_id":cand["candidate_id"],"title":cand["title"],"source":cand["source_metadata"],
            "fingerprint":candidate_fingerprint(original),"editor":cand["review"]["editor"],
            "last_verification":original["verification"]["status"],"verification":cand["verification"],
            "context_status":(context_status or {}).get(cand["candidate_id"],"offline_context_not_refreshed"),
            "gaps":classify_review_gaps(cand),"before":{k:old.get(k) for k in keys} if old else None,
            "after":{k:converted.get(k) for k in keys},"evidence":cand["field_evidence"],
            "questions":cand["gaps_and_conflicts"]["open_questions"],"review":cand["review"]})
    manifest={"as_of":working["as_of"],"candidate_ids":[c["candidate_id"] for c in verified["candidates"]],
        "promotion_ready":summary["promotion_ready"],"http_requests":http_requests,"model_calls":0,
        "official_data_modified":False,"publication_status":"not_requested","published":False}
    output.mkdir(parents=True,exist_ok=True)
    export(output/"candidate-preview.html",pilot_data=preview,review_preview=True)
    payload={"as_of":working["as_of"],"rows":rows,"manifest":manifest}
    template=(ROOT/"docs/design/review-workspace.html").read_text(encoding="utf-8")
    script=(ROOT/"docs/design/review-workspace.js").read_text(encoding="utf-8")
    (output/"review-summary.md").write_text(markdown,encoding="utf-8")
    (output/"verified-candidates.json").write_text(json.dumps(verified,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    applied={r["candidate_id"] for r in decisions["reviews"] if r["action"]=="applied"}
    ready={c["candidate_id"] for c in verified["candidates"] if c["review"]["promotion_ready"]}
    if export_draft:
        selected_ids=[c.get("opportunity_id") or c["candidate_id"] for c in verified["candidates"] if c["candidate_id"] in applied]
        if not applied:manifest["publication_status"]="no_approved_candidates"
        elif len(selected_ids)!=len(set(selected_ids)):
            manifest.update(publication_status="blocked",blocking_reason="same_opportunity_multiple_documents_require_reconciliation")
        elif (not applied.issubset(ready) or summary["bundle_schema_errors"]
                or any(classify_review_gaps(c)["source"] for c in verified["candidates"] if c["candidate_id"] in applied)
                or any((context_status or {}).get(cid)!="fresh_semantic_revision_matched" for cid in applied)):
            manifest["publication_status"]="blocked"
        else:
            selected={**verified,"candidates":[c for c in verified["candidates"] if c["candidate_id"] in applied]}
            proposal=refresh_snapshot_states(pilot,working["as_of"])
            export_pr_candidate_draft(selected,proposal,output/"pilot-proposal.json",scan_sources_config=config)
            proposed=json.loads((output/"pilot-proposal.json").read_text(encoding="utf-8"))
            (output/"reviews-proposal.json").write_text(json.dumps(merged,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
            patch=patch_text(pilot,proposed,"data/pilot.json")+patch_text(ledger,merged,"data/scan-reviews.json")
            (output/"data-pr.patch").write_text(patch,encoding="utf-8")
            (output/"PR-DRAFT.md").write_text("# 待提交的資料PR\n\n候選："+", ".join(sorted(applied))+"\n\n來源版本及獨立覆核已於本次程序檢核；仍須維護者審查此patch。既有受理狀態依快照日重算，原來源checked_on不改寫。這份草稿未提交、合併或部署。\n",encoding="utf-8")
            manifest["publication_status"]="proposal_generated_not_published"
    html=template.replace("<!--REVIEW-DATA-->",'<script id="review-data" type="application/json">'+json.dumps(payload,ensure_ascii=False).replace("<","\\u003c")+'</script>')
    html=html.replace('<!--REVIEW-SCRIPT-->','<script>\n'+script+'\n</script>')
    (output/"review.html").write_text(html,encoding="utf-8")
    (output/"manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return manifest


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates",type=Path,default=ROOT/"data/candidates/source-review.json")
    parser.add_argument("--source-id",action="append",help="Review a bounded subset; repeat for a small batch of source IDs")
    parser.add_argument("--pilot",type=Path,default=ROOT/"data/pilot.json")
    parser.add_argument("--config",type=Path,default=ROOT/"data/scan-sources.json")
    parser.add_argument("--ledger",type=Path,default=ROOT/"data/scan-reviews.json")
    parser.add_argument("--decisions",type=Path)
    parser.add_argument("--output",type=Path,default=ROOT/"work/review-workspace")
    parser.add_argument("--refresh",action="store_true",help="Bounded official-source GET, memory only; no model calls")
    parser.add_argument("--export-draft",action="store_true")
    parser.add_argument("--as-of")
    args=parser.parse_args()
    read=lambda p:json.loads(p.read_text(encoding="utf-8"))
    bundle,pilot,config=read(args.candidates),read(args.pilot),read(args.config)
    if args.source_id:
        available={c["source_metadata"]["source_id"] for c in bundle["candidates"]}
        if set(args.source_id)-available:parser.error("Unknown candidate source ID")
        bundle={**bundle,"candidates":[c for c in bundle["candidates"] if c["source_metadata"]["source_id"] in args.source_id]}
    validate_config(config)
    errors=validate_candidate_snapshot(bundle,config)
    if errors:parser.error("Invalid pending candidates: "+str(errors))
    ledger=read(args.ledger)
    decisions=read(args.decisions) if args.decisions else {"schema_version":"1.1.0","reviews":[]}
    merge_decisions(ledger,decisions,bundle)  # Reject invalid intents before any GET.
    contexts,status,count=None,None,0
    if args.output.exists() and any(args.output.iterdir()):parser.error("Use a fresh empty output directory")
    if args.refresh:contexts,status,count=refresh_context(bundle,config)
    result=build_workspace(bundle,pilot,config,args.output,ledger=ledger,
        decisions=decisions,contexts=contexts,context_status=status,
        export_draft=args.export_draft,as_of=args.as_of or (taipei_today() if args.refresh else bundle["as_of"]),http_requests=count)
    print(json.dumps(result,ensure_ascii=False))
    if result["publication_status"]=="blocked":raise SystemExit(2)


if __name__=="__main__":main()
