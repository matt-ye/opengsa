"""Prepare a review-only radar update and preview, without editing the checkout or approving data."""
import argparse
from collections import defaultdict
from copy import deepcopy
import difflib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from scripts.scan_sources import digest
from scripts.check_data import validate_candidate_snapshot
from scripts.source_chains import candidate_bindings,candidate_documents,timeline_metadata
from scripts.export_source_chain_graph import load_graph
from scripts.expand_sources import read,save,now

ACCEPT={'passed_automated_checks','passed_with_gaps'}

def prepare(incoming,config):
    errors=validate_candidate_snapshot(incoming,config)
    if errors:raise ValueError('invalid_incoming_candidates: '+str(errors)[:300])
    base=read(ROOT/'data/candidates/source-review.json')
    good=[deepcopy(c) for c in incoming['candidates'] if c['verification']['status'] in ACCEPT]
    if any(c['review']['promotion_ready'] or c['review'].get('independent_reviewer') for c in good):raise ValueError('automatic_approval_not_allowed')
    urls={c['source_metadata']['url'] for c in good}
    fresh_ids={c['candidate_id'] for c in good}
    keep=[c for c in base['candidates'] if c['source_metadata']['url'] not in urls and c['candidate_id'] not in fresh_ids]
    merged={**base,'generated_at':incoming['generated_at'],'as_of':incoming['as_of'],
        'model_enabled':incoming['model_enabled'],'model_calls':incoming['model_calls'],'candidates':keep+good}
    merged.pop('model_usage',None) # No stale usage claims from an unrelated scan.
    if 'model_usage' in incoming:merged['model_usage']=deepcopy(incoming['model_usage'])
    errors=validate_candidate_snapshot(merged,config)
    if errors:raise ValueError('invalid_merged_candidates: '+str(errors)[:300])
    files={'data/candidates/source-review.json':merged}
    oldconfig=read(ROOT/'data/scan-sources.json');profiles={p['id']:p for p in oldconfig['sources']}
    needed={c['source_metadata']['source_id'] for c in merged['candidates']}
    for p in config['sources']:
        if p['id'] not in profiles and p['id'] in needed:
            # Readable preview is not permission to add new scheduled scan targets.
            profiles[p['id']]={**p,'enabled':False}
    newconfig={**oldconfig,'sources':list(profiles.values()),'allowed_hosts':sorted(set(oldconfig['allowed_hosts'])|set(config['allowed_hosts']))}
    files['data/scan-sources.json']=newconfig
    index=read(ROOT/'data/source-chain-index.json')
    index.update(candidate_sha256=digest(merged),as_of=incoming['as_of'])
    # A fresh candidate revision must not silently inherit older timeline claims/rules.
    invalid_docs=set()
    for path in index['bundles']:
        bundle=read(ROOT/path)
        for doc in bundle['documents']:
            if doc['url'] in urls and doc.get('revision_id') not in {c['source_metadata']['revision_id'] for c in good if c['source_metadata']['url']==doc['url']}:
                doc['status']='newer_candidate_requires_chain_recheck';doc['events']=[];invalid_docs.add(doc['id'])
        if path=='data/source-chains.json':
            bundle['candidate_bindings']=candidate_bindings(merged['candidates'],read(ROOT/'data/source-chain-sources.json'))
        files[path]=bundle
    byprogram=defaultdict(list)
    for c in merged['candidates']:byprogram[c['program_key']].append(c)
    for p in index['programs']:
        p['candidate_ids']=[c['candidate_id'] for c in byprogram.pop(p['key'],[])]
        rejected={r['id'] for r in p['rules'] if any(ref['document_id'] in invalid_docs for ref in r['evidence_refs'])}
        while True:
            extra={r['id'] for r in p['rules'] if r['value'].get('anchor_rule_id') in rejected}
            if extra<=rejected:break
            rejected|=extra
        if rejected:
            p['rules']=[r for r in p['rules'] if r['id'] not in rejected]
            p['gaps'].append('本批候選來源已有新版本，舊規則先撤下待重核：'+','.join(sorted(rejected)))
    index['programs']=[p for p in index['programs'] if p['candidate_ids']]
    for key,cs in byprogram.items():
        index['programs'].append({'key':key,'title':cs[0]['title'],'candidate_ids':[c['candidate_id'] for c in cs],
            'audit_status':'baseline_pending','source_contexts':[],'gaps':['新發現雷達候選；資訊鏈與方案別名尚待核對，不代表完整閉合。'],'rules':[],'audited_batch':None})
    snapshots={'schema_version':'source-chain-1','generated_at':incoming['generated_at'],'model_calls':0,'official_data_modified':False,
        'documents':list(candidate_documents(merged).values()),'relations':[],'scopes':[],'candidate_bindings':[],'http_requests':0,'reports':[]}
    path='data/source-chain-batches/radar-proposal-snapshots.json'
    files[path]=snapshots
    if path not in index['bundles']:index['bundles'].append(path)
    index['notes'].append('本提案僅產生待審雷達快照；新來源未啟用排程，人工核准仍為0。')
    files['data/source-chain-index.json']=index
    # Validate the entire proposed reference graph without temporarily writing production data.
    original=lambda path:read(ROOT/path)
    load_graph(index,reader=lambda path:files[path] if path in files else original(path))
    timeline_metadata(files['data/source-chains.json'],merged)
    summary={'incoming':len(incoming['candidates']),'accepted_for_radar_proposal':len(good),
        'withheld_failed_checks':len(incoming['candidates'])-len(good),'retained_old_candidates':len(keep),
        'proposed_candidates':len(merged['candidates']),'replaced_urls':sorted(urls),'invalidated_timeline_documents':sorted(invalid_docs),
        'human_approvals':0,'published':False,'scheduled_sources_enabled':0}
    return files,summary

def write_proposal(incoming,config,output,preview=True):
    output=Path(output)
    if output.exists() and any(output.iterdir()):raise ValueError('proposal_output_must_be_empty')
    files,summary=prepare(incoming,config);output.mkdir(parents=True,exist_ok=True);patches=[]
    for path,value in files.items():
        text=json.dumps(value,ensure_ascii=False,indent=2)+'\n'
        old=(ROOT/path).read_text(encoding='utf-8') if (ROOT/path).exists() else ''
        if old and json.loads(old)==value:continue
        save(output/'repo'/path,value)
        patches.extend(difflib.unified_diff(old.splitlines(True),text.splitlines(True),fromfile='a/'+path,tofile='b/'+path))
    (output/'data-pr.patch').write_text(''.join(patches),encoding='utf-8')
    save(output/'summary.json',summary)
    save(output/'snapshot-base.json',{'files':{p:digest((ROOT/p).read_bytes()) if (ROOT/p).exists() else None for p in files},'generated_at':now()})
    if preview:
        from scripts.build_review_workspace import build_workspace
        # Only proposed profiles are needed; unused discovery aliases must not become active targets.
        chain=timeline_metadata(files['data/source-chains.json'],files['data/candidates/source-review.json'])
        build_workspace(files['data/candidates/source-review.json'],read(ROOT/'data/pilot.json'),files['data/scan-sources.json'],output/'preview',chain_data=chain)
    (output/'PR-DRAFT.md').write_text('# 待審雷達資料更新\n\n'+json.dumps(summary,ensure_ascii=False,indent=2)+'\n\n此提案未修改checkout、正式pilot或核准台帳。新掃描來源預設停用；未知欄位仍未知，舊版本時程不自動沿用。核可後請從同一base套用repo/內的JSON、執行check_data／測試／建置，提交資料PR。\n',encoding='utf-8')
    return summary

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--candidates',type=Path,required=True);p.add_argument('--config',type=Path,default=ROOT/'data/scan-sources.json');p.add_argument('--output',type=Path,required=True);p.add_argument('--no-preview',action='store_true');args=p.parse_args()
    if args.output.resolve().is_relative_to(ROOT/'data'):p.error('proposal must remain outside data')
    print(json.dumps(write_proposal(read(args.candidates),read(args.config),args.output,not args.no_preview),ensure_ascii=False))

if __name__=='__main__':main()
