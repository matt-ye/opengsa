"""Prepare existing candidates and selectively replay rules. No model, approval or publication."""
import argparse
from copy import deepcopy
from datetime import datetime,timezone
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from scripts.check_data import validate_candidate_snapshot
from scripts.document_ir import prepare_document,document_manifest
from scripts.extraction_scope import GROUPS,compile_scope,apply_scoped_replay
from scripts.extract_candidates import extract_from_in_memory_blocks,limit_evidence_excerpts
from scripts.review_candidates import candidate_fingerprint
from scripts.review_context import refresh_context
from scripts.verify_candidates import verify_candidate


def prepare_batch(bundle,config,groups=None,fields=None,contexts=None,statuses=None,pilot=None,full_replay=False):
    errors=validate_candidate_snapshot(bundle,config)
    if errors:raise ValueError('invalid_candidate_input:'+str(errors))
    profiles={s['id']:s for s in config['sources']}
    if pilot is None:pilot=json.loads((ROOT/'data/pilot.json').read_text(encoding='utf-8'))
    pilot_by_id={o['id']:o for o in pilot['opportunities']}
    result=deepcopy(bundle);plans=[];documents={};now=datetime.now(timezone.utc).isoformat(timespec='seconds')
    by_revision_budget={}
    for index,original in enumerate(bundle['candidates']):
        meta=original['source_metadata']
        plan={**compile_scope(original,list(GROUPS) if full_replay else groups,fields),'full_replay':full_replay,'candidate_id':original['candidate_id'],
            'candidate_sha256':candidate_fingerprint(original),'source_revision':meta['revision_id'],
            'status':'requires_fresh_source_context','model_calls':0}
        blocks=(contexts or {}).get(meta['url'])
        if blocks is not None and (statuses or {}).get(original['candidate_id'])=='fresh_semantic_revision_matched':
            document=prepare_document(blocks)
            documents[meta['url']]=document_manifest(document)
            plan['prepared_document_sha256']=document['document_sha256']
            fresh=extract_from_in_memory_blocks(profiles[meta['source_id']],blocks,meta['revision_id'],
                now,url=meta['url'],as_of=bundle['as_of'],extraction_strategy='rules_only')
            matches=[c for c in fresh if c['candidate_id']==original['candidate_id']]
            if len(matches)==1:
                try:
                    # An explicit full replay recomputes the whole pending record;
                    # unlike a partial patch, it can correct old unsupported defaults.
                    updated=matches[0] if full_replay else apply_scoped_replay(original,matches[0],plan,blocks)
                    if full_replay:
                        # Fresh body context does not prove that an inaccessible
                        # attachment has been acquired. Preserve that boundary.
                        for gap in original['gaps_and_conflicts']['missing_fields']:
                            if any(term in gap for term in ('attachment','robots','restricted','unavailable')) and gap not in updated['gaps_and_conflicts']['missing_fields']:
                                updated['gaps_and_conflicts']['missing_fields'].append(gap)
                    result['candidates'][index]=updated
                    plan.update(status='replayed_pending_review',verification=updated['verification']['status'])
                except ValueError as error:
                    plan['status']=str(error)
            else:plan['status']='candidate_branch_changed_requires_full_replay'
        elif statuses:plan['status']=statuses.get(original['candidate_id'],'source_context_unavailable')
        plans.append(plan)
        candidate=result['candidates'][index]
        key=(meta['source_id'],meta['revision_id'])
        by_revision_budget[key]=limit_evidence_excerpts(candidate,by_revision_budget.get(key,120))
        if plan['status']=='replayed_pending_review':
            result['candidates'][index]=verify_candidate(candidate,blocks,pilot_by_id=pilot_by_id)
            plan['verification']=result['candidates'][index]['verification']['status']
    result['generated_at']=now
    if validate_candidate_snapshot(result,config):raise ValueError('scoped_result_failed_validation')
    return result,{'model_calls':0,'published':False,'plans':plans,'documents':documents}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidates',type=Path,default=ROOT/'data/candidates/source-review.json')
    parser.add_argument('--config',type=Path,default=ROOT/'data/scan-sources.json')
    parser.add_argument('--source-id',action='append')
    parser.add_argument('--group',action='append',dest='groups')
    parser.add_argument('--field',action='append',dest='fields')
    parser.add_argument('--refresh',action='store_true',help='Bounded public GET; otherwise offline plan only')
    parser.add_argument('--full-replay',action='store_true',help='Recompute every field from fresh context; never carries approvals')
    parser.add_argument('--output-dir',type=Path,required=True)
    args=parser.parse_args()
    output=args.output_dir.resolve()
    if not output.is_relative_to(ROOT/'work') or (output.exists() and any(output.iterdir())):
        raise ValueError('use_fresh_work_directory')
    bundle=json.loads(args.candidates.read_text(encoding='utf-8'))
    config=json.loads(args.config.read_text(encoding='utf-8'))
    if args.source_id:
        registered={s['id'] for s in config['sources']}
        if set(args.source_id)-registered:raise ValueError('unknown_source_id')
        bundle['candidates']=[c for c in bundle['candidates'] if c['source_metadata']['source_id'] in args.source_id]
    if not bundle['candidates']:raise ValueError('empty_candidate_selection')
    # Validate the complete scope before any possible source request.
    prepare_batch(bundle,config,args.groups,args.fields,full_replay=args.full_replay)
    contexts,statuses,count=({}, {},0)
    if args.refresh:contexts,statuses,count=refresh_context(bundle,config)
    result,report=prepare_batch(bundle,config,args.groups,args.fields,contexts,statuses,full_replay=args.full_replay)
    report['http_requests']=count;report['mode']='rule_replay' if args.refresh else 'offline_plan_only'
    output.mkdir(parents=True)
    (output/'preparation-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    if args.refresh:
        (output/'pending-candidates.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'candidates':len(bundle['candidates']),'http_requests':count,'model_calls':0,
        'states':{p['candidate_id']:p['status'] for p in report['plans']}},ensure_ascii=False))


if __name__=='__main__':main()
