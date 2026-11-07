"""Refresh at most eight already-readable pending sources; originals stay in memory."""
import argparse
from copy import deepcopy
from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from scripts.scan_sources import Fetcher, ScanError, digest
from scripts.verify_original_sources import prepare_public, quarantine_unproven
from scripts.document_ir import prepare_document, VERSION as IR_VERSION
from scripts.extract_candidates import extract_from_in_memory_blocks, EXTRACTOR_VERSION
from scripts.propose_radar_update import write_proposal
from scripts.check_data import validate_candidate_snapshot

def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))
def save(path,data):path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

def refresh(source_ids,output,transport=None,prior_requests=0,previous_output=None):
    output=Path(output).resolve()
    if not output.is_relative_to(ROOT/'work') or output.exists():raise ValueError('use_new_work_directory')
    bundle=read(ROOT/'data/candidates/source-review.json');config=read(ROOT/'data/scan-sources.json')
    profiles={p['id']:p for p in config['sources']}
    urls={c['source_metadata']['url'] for c in bundle['candidates'] if c['source_metadata']['source_id'] in source_ids}
    if not 1<=len(source_ids)<=8 or len(source_ids)!=len(set(source_ids)):raise ValueError('one_to_eight_unique_sources')
    if type(prior_requests) is not int or not 0<=prior_requests<20:raise ValueError('invalid_prior_request_budget')
    if previous_output:
        previous_output=Path(previous_output).resolve()
        if not previous_output.is_relative_to(ROOT/'work'):raise ValueError('previous_output_must_be_work_artifact')
        prior_bundle=read(previous_output/'pending-candidates.json');prior_report=read(previous_output/'report.json')
        if (validate_candidate_snapshot(prior_bundle,config) or prior_bundle['model_calls']!=0 or prior_bundle['model_enabled']
                or prior_report['model_calls']!=0 or prior_report['published']
                or prior_requests<prior_report.get('total_round_requests',prior_report['http_requests'])):
            raise ValueError('previous_artifact_or_budget_boundary_mismatch')
    audit={r['url']:r for r in read(ROOT/'data/source-expansion/original-source-verification.json')['records']}
    for sid in source_ids:
        if sid not in profiles or profiles[sid]['url'] not in urls:raise ValueError('source_must_be_an_existing_primary_candidate')
        if not audit.get(profiles[sid]['url'],{}).get('content_verified'):raise ValueError('source_requires_separate_access_review')
    output.mkdir(parents=True)
    report={'schema_version':'radar-refresh-1','started_at':datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'new_round':True,'max_requests':20,'max_run_seconds':180,'max_documents':8,
        'http_requests':0,'prior_requests':prior_requests,'total_round_requests':prior_requests,'model_calls':0,'published':False,'records':[]}
    def request(url,headers,limit):
        report['http_requests']+=1
        report['total_round_requests']=prior_requests+report['http_requests']
        save(output/'report.json',report)  # Reserve every attempt before transport.
        return transport(url,headers,limit)
    from scripts.scan_sources import node_get
    transport=transport or node_get
    fetcher=Fetcher({'allowed_hosts':config['allowed_hosts'],'max_requests':20-prior_requests,'max_run_seconds':180,
        'minimum_host_interval_seconds':3},transport=request)
    fresh=[];reference_docs=[]
    registry=read(ROOT/'data/source-chain-sources.json')
    from scripts.source_chains import publication_reference_events
    from urllib.parse import urlsplit
    for sid in source_ids:
        p=deepcopy(profiles[sid]);url=p['url'];row={'source_id':sid,'url':url,'content_verified':False}
        try:
            response=fetcher.get(url,{},10*1024*1024)
            if response['status']!=200:raise ScanError('http_'+str(response['status']))
            prepared=prepare_public(response,config['allowed_hosts'])
            p['title']=prepared['title'] or p['title']
            # This bounded replay never sends an original or a quote to a model.
            p['evidence_mode']='hash_only'
            revision=digest([url,digest(response['body']),EXTRACTOR_VERSION,IR_VERSION])
            observed=datetime.now(timezone.utc).isoformat(timespec='seconds')
            as_of=datetime.now(timezone(timedelta(hours=8))).date().isoformat()
            blocks=prepare_document(prepared['blocks'])['units']
            candidates=extract_from_in_memory_blocks(p,blocks,revision,observed,url=url,as_of=as_of,extraction_strategy='rules_only')
            candidates=[quarantine_unproven(c,blocks)[0] for c in candidates]
            accepted=all(c['verification']['status'] in ('passed_automated_checks','passed_with_gaps') for c in candidates)
            row.update(content_verified=True,raw_sha256=digest(response['body']),revision_id=revision,
                candidate_ids=[c['candidate_id'] for c in candidates],accepted=accepted,
                checks=[{'status':c['verification']['status'],'errors':c['verification']['errors']} for c in candidates])
            if accepted:fresh.extend(candidates)
            if accepted and len(candidates)==1:
                scopes={s['scope'] for s in registry['sources'] if urlsplit(s['url']).hostname==urlsplit(url).hostname}
                if len(scopes)==1:
                    scope=next(iter(scopes));c=candidates[0]
                    profile={'role':'policy' if c['cycle']['kind']=='policy_snapshot' else 'local_announcement','program_key':c['program_key'],'scope':scope,
                        'cycle':c['cycle']['label'],'application_year':int(as_of[:4]),'phase':'annual'}
                    doc={'id':'doc-'+digest(url)[:24],'url':url,'format':prepared['kind'],'revision_id':revision,
                        'observed_at':observed,'status':'changed','evidence_mode':'hash_only','raw_sha256':row['raw_sha256'],
                        'candidate_ids':row['candidate_ids'],'events':[],'links':[]}
                    doc['events']=publication_reference_events(blocks,profile,doc,prepared['publication'])
                    if doc['events']:reference_docs.append(doc)
        except (ScanError,ValueError) as error:
            row['reason']=str(error)
        report['records'].append(row);save(output/'report.json',report)
        print(sid+' '+json.dumps({k:row[k] for k in ('accepted','reason','checks') if k in row},ensure_ascii=False),flush=True)
    observations=deepcopy(report)
    if previous_output:
        replacements={c['source_metadata']['url'] for c in fresh}
        fresh=[c for c in prior_bundle['candidates'] if c['source_metadata']['url'] not in replacements]+fresh
        observations['records']=prior_report['records']+report['records']
        # Later observations win in the normal proposal validator.
    incoming={**bundle,'generated_at':datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'as_of':datetime.now(timezone(timedelta(hours=8))).date().isoformat(),'model_calls':0,'model_enabled':False,'candidates':fresh}
    if validate_candidate_snapshot(incoming,config):raise ValueError('invalid_refresh_result')
    save(output/'pending-candidates.json',incoming)
    report['summary']=write_proposal(incoming,config,output/'proposal',preview=False,observations=observations)
    if reference_docs:
        proposed=output/'proposal/repo'
        def proposed_read(path):return read(proposed/path if (proposed/path).exists() else ROOT/path)
        from scripts.export_source_chain_graph import load_graph
        from scripts.source_chains import validate
        index=proposed_read('data/source-chain-index.json');graph=load_graph(index,reader=proposed_read)
        core=proposed_read('data/source-chains.json');docs={d['id']:d for d in core['documents']}
        for doc in reference_docs:
            old=graph['documents'].get(doc['id'],{})
            if old.get('revision_id')==doc['revision_id']:
                old_events=old.get('events',[])
                if any(e['kind']=='application_start' and e['certainty']=='announced' for e in old_events):doc['events']=old_events
                else:doc['events']=old_events+doc['events']
            docs[doc['id']]=doc
        core.update(documents=list(docs.values()),generated_at=incoming['generated_at'])
        validate(core);save(proposed/'data/source-chains.json',core)
        sidecar={**core,'documents':reference_docs,'relations':[],'candidate_bindings':[],'http_requests':report['http_requests']}
        path='data/source-chain-batches/radar-reference-windows.json'
        save(proposed/path,sidecar)
        if path not in index['bundles']:index['bundles'].append(path)
        save(proposed/'data/source-chain-index.json',index)
        load_graph(index,reader=proposed_read)
        report['reference_window_documents']=[d['id'] for d in reference_docs]
    finalize_proposal(output)
    save(output/'report.json',report)
    return report

def finalize_proposal(output):
    """The review patch and preview must include the enriched sidecar too."""
    import difflib
    from scripts.build_review_workspace import build_workspace
    from scripts.source_chains import timeline_metadata
    output=Path(output);proposed=output/'proposal/repo';patch=[]
    def current(path):return read(proposed/path if (proposed/path).exists() else ROOT/path)
    # 參考窗補進資料後，資訊鏈圖要重產一次，否則和提案資料不一致。
    from scripts.export_source_chain_graph import export as export_graph
    export_graph(proposed/'docs/source-chains',current('data/source-chain-index.json'),reader=current)
    for file in sorted(f for f in proposed.rglob('*') if f.is_file()):
        path=file.relative_to(proposed).as_posix()
        old=(ROOT/path).read_text(encoding='utf-8') if (ROOT/path).exists() else ''
        patch.extend(difflib.unified_diff(old.splitlines(True),file.read_text(encoding='utf-8').splitlines(True),fromfile='a/'+path,tofile='b/'+path))
    (output/'proposal/data-pr.patch').write_text(''.join(patch),encoding='utf-8')
    candidates=current('data/candidates/source-review.json')
    build_workspace(candidates,read(ROOT/'data/pilot.json'),current('data/scan-sources.json'),output/'proposal/enriched-preview',
        chain_data=timeline_metadata(current('data/source-chains.json'),candidates))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source-id',action='append',required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--prior-requests',type=int,default=0);p.add_argument('--previous-output',type=Path)
    args=p.parse_args();result=refresh(args.source_id,args.output,prior_requests=args.prior_requests,previous_output=args.previous_output);print(json.dumps(result['summary'],ensure_ascii=False))
