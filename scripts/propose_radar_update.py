"""Prepare a review-only radar update and preview, without editing the checkout or approving data."""
import argparse
from collections import defaultdict
from copy import deepcopy
import difflib
import json
from pathlib import Path
import re
import sys

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from scripts.scan_sources import digest
from scripts.check_data import validate_candidate_snapshot
from scripts.review_candidates import candidate_fingerprint
from scripts.time_policy import validate_temporal_snapshot
from scripts.source_chains import candidate_bindings,candidate_documents,timeline_metadata
from scripts.export_source_chain_graph import load_graph,export as export_graph
from scripts.expand_sources import read,save,now
from scripts.audit_sources import canonical_url

ACCEPT={'passed_automated_checks','passed_with_gaps'}
HAND_BASELINE='data/known-hand-authored-candidates.json'

def same_program(left,right):
    """標題互相包含才算同一方案；太短的通稱（例如「獎學金」）不算。"""
    left,right=(re.sub(r'\W+','',title).casefold() for title in (left,right))
    return min(len(left),len(right))>=6 and (left in right or right in left)

def retire_hand_cards(good,replaced_urls=()):
    """新卡取代同網址、同方案的手寫卡。同網址不代表同方案（同校首頁可能有急難金和獎學金），認不出來就不刪，交給人判斷。"""
    baseline=read(ROOT/HAND_BASELINE);known=set(baseline['candidate_ids'])
    targets={canonical_url(c['source_metadata']['url']) for c in good}|({canonical_url(u) for u in replaced_urls} if good else set())
    bundles={};at_url=defaultdict(list)
    for path in sorted((ROOT/'data/candidates').glob('*.json')):
        bundle=read(path);rel='data/candidates/'+path.name;bundles[rel]=bundle
        for card in bundle['candidates']:
            url=canonical_url(card['source_metadata']['url'])
            if url in targets:at_url[url].append((rel,card))
    retired,manual,files=[],[],{}
    for url,cards in sorted(at_url.items()):
        hand=[(rel,card) for rel,card in cards if card['candidate_id'] in known]
        if not hand:continue
        for rel,card in hand:
            row={'url':url,'candidate_id':card['candidate_id'],'title':card['title']}
            if len({other['program_key'] for _,other in hand})==1 and any(same_program(card['title'],new['title']) for new in good):
                retired.append({**row,'bundle':rel})
            else:
                manual.append(row)
    gone={row['candidate_id'] for row in retired}
    for rel in {row['bundle'] for row in retired}:
        files[rel]={**bundles[rel],'candidates':[c for c in bundles[rel]['candidates'] if c['candidate_id'] not in gone]}
    if gone:files[HAND_BASELINE]={**baseline,'candidate_ids':[i for i in baseline['candidate_ids'] if i not in gone]}
    return files,retired,manual

def merge_temporal(merged,good,temporal,observed):
    """當輪的時間紀錄和卡片一起進提案。只收同一版本內容讀到的；已被取代的卡，舊紀錄一併移除。"""
    records={}
    for card in good:
        record=(temporal or {}).get(card['candidate_id'])
        if record and record.get('card_revision_id')==card['source_metadata']['revision_id']:
            records[card['candidate_id']]={**record,'candidate_sha256':candidate_fingerprint(card)}
    if not records:return None,0
    base=read(ROOT/'data/temporal-observations.json');alive={c['candidate_id'] for c in merged['candidates']}
    batch={'http_requests':0,'kind':'same_round','attempted_urls':sorted({r['url'] for r in records.values()}),'observed_at':observed}
    result={**base,'batches':base['batches']+[batch],'records':{**{k:v for k,v in base['records'].items() if k in alive},**records}}
    errors=validate_temporal_snapshot(merged,result)
    if errors:raise ValueError('invalid_temporal_records: '+str(errors)[:300])
    return result,len(records)

def split_site_ready(cards,incoming,config):
    """一張卡不符合網站資料規格，不能讓整批提案和網站建置一起失敗；扣下來並列出原因。"""
    from scripts.build_review_workspace import candidate_preview_data
    pilot=read(ROOT/'data/pilot.json');ready,withheld=[],[]
    for card in cards:
        try:
            candidate_preview_data({**incoming,'candidates':[card]},pilot,config)
            ready.append(card)
        except (ValueError,KeyError) as error:
            withheld.append({'candidate_id':card['candidate_id'],'title':card['title'],'url':card['source_metadata']['url'],'error':str(error)[:300]})
    return ready,withheld

def prepare(incoming,config,observations=None,replaced_urls=(),temporal=None):
    errors=validate_candidate_snapshot(incoming,config)
    if errors:raise ValueError('invalid_incoming_candidates: '+str(errors)[:300])
    base=read(ROOT/'data/candidates/source-review.json')
    good=[deepcopy(c) for c in incoming['candidates'] if c['verification']['status'] in ACCEPT]
    good,withheld_contract=split_site_ready(good,incoming,config)
    if any(c['review']['promotion_ready'] or c['review'].get('independent_reviewer') for c in good):raise ValueError('automatic_approval_not_allowed')
    urls={c['source_metadata']['url'] for c in good}
    fresh_ids={c['candidate_id'] for c in good}
    keep=[c for c in base['candidates'] if c['source_metadata']['url'] not in urls and c['candidate_id'] not in fresh_ids]
    merged={**base,'generated_at':base['generated_at'] if incoming['as_of']<base['as_of'] else incoming['generated_at'],'as_of':max(base['as_of'],incoming['as_of']),
        'model_enabled':incoming['model_enabled'],'model_calls':incoming['model_calls'],'candidates':keep+good}
    merged.pop('model_usage',None) # No stale usage claims from an unrelated scan.
    if 'model_usage' in incoming:merged['model_usage']=deepcopy(incoming['model_usage'])
    errors=validate_candidate_snapshot(merged,config)
    if errors:raise ValueError('invalid_merged_candidates: '+str(errors)[:300])
    files={'data/candidates/source-review.json':merged}
    observed,temporal_count=merge_temporal(merged,good,temporal,incoming['generated_at'])
    if observed:files['data/temporal-observations.json']=observed
    retired_files,retired,manual=retire_hand_cards(good,replaced_urls)
    files.update(retired_files)
    oldconfig=read(ROOT/'data/scan-sources.json');profiles={p['id']:p for p in oldconfig['sources']}
    needed={c['source_metadata']['source_id'] for c in merged['candidates']}
    for p in config['sources']:
        if p['id'] not in profiles and p['id'] in needed:
            # Readable preview is not permission to add new scheduled scan targets.
            profiles[p['id']]={**p,'enabled':False}
    newconfig={**oldconfig,'sources':list(profiles.values()),'allowed_hosts':sorted(set(oldconfig['allowed_hosts'])|set(config['allowed_hosts']))}
    files['data/scan-sources.json']=newconfig
    index=read(ROOT/'data/source-chain-index.json')
    index.update(candidate_sha256=digest(merged),as_of=merged['as_of'])
    # A fresh candidate revision must not silently inherit older timeline claims/rules.
    invalid_docs=set();rebound={};observed={r['url']:r for r in (observations or {}).get('records',[]) if r.get('content_verified')}
    for path in index['bundles']:
        bundle=read(ROOT/path)
        for doc in bundle['documents']:
            if doc['url'] in urls and doc['status'] in ('candidate_snapshot','discovered_not_read'):
                revisions={c['source_metadata']['revision_id'] for c in good if c['source_metadata']['url']==doc['url']}
                if len(revisions)==1:
                    doc.update(revision_id=next(iter(revisions)),events=[],candidate_ids=[c['candidate_id'] for c in good if c['source_metadata']['url']==doc['url']])
                continue
            if doc['url'] in urls and doc.get('revision_id') not in {c['source_metadata']['revision_id'] for c in good if c['source_metadata']['url']==doc['url']}:
                revisions={c['source_metadata']['revision_id'] for c in good if c['source_metadata']['url']==doc['url']}
                observation=observed.get(doc['url'],{})
                if (len(revisions)==1 and observation.get('revision_id') in revisions and doc.get('raw_sha256')
                        and doc['raw_sha256']==observation.get('raw_sha256')):
                    old_revision=doc['revision_id'];revision=next(iter(revisions));rebound[(doc['id'],old_revision)]=revision
                    doc.update(revision_id=revision,status='unchanged',candidate_ids=[c['candidate_id'] for c in good if c['source_metadata']['url']==doc['url']])
                    for event in doc['events']:
                        event['revision_id']=revision;event['id']='event-'+digest({k:v for k,v in event.items() if k!='id'})[:24]
                else:
                    doc['status']='newer_candidate_requires_chain_recheck';doc['events']=[];invalid_docs.add(doc['id'])
        if path=='data/source-chains.json':
            bundle['candidate_bindings']=candidate_bindings(merged['candidates'],read(ROOT/'data/source-chain-sources.json'))
        files[path]=bundle
    # Bundles can contain a baseline snapshot and a later actual read of the same URL.
    # Apply the same precedence as the graph loader before deciding which rules to withdraw.
    effective={}
    for path in index['bundles']:
        for doc in files[path]['documents']:
            if doc['id'] in effective and doc['status'] in ('candidate_snapshot','discovered_not_read'):continue
            effective[doc['id']]=doc
    invalid_docs={key for key,doc in effective.items() if doc['status']=='newer_candidate_requires_chain_recheck'}
    byprogram=defaultdict(list)
    for c in merged['candidates']:byprogram[c['program_key']].append(c)
    for p in index['programs']:
        p['candidate_ids']=[c['candidate_id'] for c in byprogram.pop(p['key'],[])]
        for rule in p['rules']:
            for ref in rule['evidence_refs']:
                if (ref['document_id'],ref['revision_id']) in rebound:ref['revision_id']=rebound[(ref['document_id'],ref['revision_id'])]
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
        'withheld_failed_checks':len(incoming['candidates'])-len(good)-len(withheld_contract),'withheld_site_contract':withheld_contract,'retained_old_candidates':len(keep),
        'proposed_candidates':len(merged['candidates']),'replaced_urls':sorted(urls),'invalidated_timeline_documents':sorted(invalid_docs),
        'byte_identical_rebound_documents':sorted({key[0] for key in rebound}-invalid_docs),
        'retired_hand_cards':retired,'needs_manual_retire':manual,'temporal_records':temporal_count,
        'human_approvals':0,'published':False,'scheduled_sources_enabled':0}
    return files,summary

def write_proposal(incoming,config,output,preview=True,observations=None,replaced_urls=(),temporal=None):
    output=Path(output)
    if output.exists() and any(output.iterdir()):raise ValueError('proposal_output_must_be_empty')
    files,summary=prepare(incoming,config,observations,replaced_urls,temporal);output.mkdir(parents=True,exist_ok=True);patches=[]
    for path,value in files.items():
        text=json.dumps(value,ensure_ascii=False,indent=2)+'\n'
        old=(ROOT/path).read_text(encoding='utf-8') if (ROOT/path).exists() else ''
        if old and json.loads(old)==value:continue
        save(output/'repo'/path,value)
        patches.extend(difflib.unified_diff(old.splitlines(True),text.splitlines(True),fromfile='a/'+path,tofile='b/'+path))
    # 已提交的資訊鏈圖要和資料一致（CI會比對），所以跟著提案一起更新。
    diagrams=output/'repo/docs/source-chains'
    export_graph(diagrams,files['data/source-chain-index.json'],reader=lambda path:files[path] if path in files else read(ROOT/path))
    for file in sorted(diagrams.iterdir()):
        path='docs/source-chains/'+file.name
        old=(ROOT/path).read_text(encoding='utf-8') if (ROOT/path).exists() else ''
        patches.extend(difflib.unified_diff(old.splitlines(True),file.read_text(encoding='utf-8').splitlines(True),fromfile='a/'+path,tofile='b/'+path))
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
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--candidates',type=Path,required=True);p.add_argument('--config',type=Path,default=ROOT/'data/scan-sources.json');p.add_argument('--output',type=Path,required=True);p.add_argument('--no-preview',action='store_true');p.add_argument('--observations',type=Path);p.add_argument('--temporal',type=Path,help='掃描當輪產出的時間紀錄');args=p.parse_args()
    if args.output.resolve().is_relative_to(ROOT/'data'):p.error('proposal must remain outside data')
    print(json.dumps(write_proposal(read(args.candidates),read(args.config),args.output,not args.no_preview,read(args.observations) if args.observations else None,temporal=read(args.temporal) if args.temporal and args.temporal.exists() else None),ensure_ascii=False))

if __name__=='__main__':main()
