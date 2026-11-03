"""Manual Actions temporal replay + optional API proposals; never publishes."""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from scripts.temporal_reextract import read, save, replay, follow_attachments
from scripts.temporal_model import model_for_temporal, model_review, source_allowed, MODEL
from scripts.providers import PROVIDERS
from scripts.audit_providers import audit_provider, request_json
from scripts.scan_sources import digest
from scripts.time_policy import validate_temporal_snapshot


def select_sources(value, candidates):
    ids=[part.strip() for part in value.split(',')]
    allowed={c['source_metadata']['source_id'] for c in candidates}
    if not 1<=len(ids)<=8 or len(ids)!=len(set(ids)) or any(sid not in allowed for sid in ids):
        raise ValueError('select_one_to_eight_unique_existing_source_ids')
    return ids


def run(output, source_ids, attachments=False, adapter_factory=model_for_temporal):
    output=Path(output).resolve()
    if not output.is_relative_to(ROOT/'work') or output.exists():raise ValueError('new_work_output_required')
    bundle=read(ROOT/'data/candidates/source-review.json')
    ids=select_sources(source_ids,bundle['candidates'])
    config=read(ROOT/'data/scan-sources.json');profiles={p['id']:p for p in config['sources']}
    selected=[c for c in bundle['candidates'] if c['source_metadata']['source_id'] in ids]
    output.mkdir(parents=True)
    mode=os.environ.get('OPENGSA_MODEL_MODE','off')
    if mode not in ('off','audit','extract','both'):raise ValueError('invalid_model_mode')
    provider=os.environ.get('OPENGSA_MODEL_PROVIDER','groq')
    if provider not in PROVIDERS:raise ValueError('invalid_provider')
    report={'version':'temporal-action-1','observed_at':datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'manual_only':True,'published':False,'human_approvals':0,'source_ids':ids,'model_mode':mode,
        'model_provider':provider,'max_source_requests':20,'max_inference_calls':4,
        'provider_audit':None,'model_status':'off','model_reviews':[]}
    report['provider_metadata_requests']=0
    adapter=None
    if mode!='off' and any(source_allowed(c,profiles[c['source_metadata']['source_id']]) for c in selected):
        def metadata_request(url,key,payload=None):
            report['provider_metadata_requests']+=1
            return request_json(url,key,payload)
        catalog=audit_provider(provider,os.environ,probe=False,requester=metadata_request)
        # Do not duplicate the full model catalogue or account metadata here.
        report['provider_audit']={k:catalog.get(k) for k in ('provider','catalog_status','configured_model','model_present','key_present')}
        if provider!='groq':report['model_status']='capabilities_not_verified_catalog_only'
        elif catalog.get('catalog_status')!='success' or not catalog.get('model_present'):
            report['model_status']='model_catalog_unavailable_rules_only'
        else:
            try:adapter,report['model_status']=adapter_factory(ROOT/'work/tokenizers/qwen3.8-27b.json')
            except (OSError,ValueError,ImportError):report['model_status']='tokenizer_or_capabilities_unavailable_rules_only'
    elif mode!='off':report['model_status']='all_selected_sources_restricted_rules_only'

    def on_document(candidate,blocks,revision,observed):
        profile=profiles[candidate['source_metadata']['source_id']]
        try:row=model_review(candidate,profile,blocks,adapter,revision)
        except Exception as error:
            # Never log exception text: an endpoint can echo headers or source data.
            row={'candidate_id':candidate['candidate_id'],'source_id':profile['id'],
                'status':'model_review_failed_rules_retained','error_type':type(error).__name__,'claims':[]}
        report['model_reviews'].append(row)
        save(output/'report.json',report)

    state=replay(output/'rules',source_ids=ids,max_round_requests=20,on_document=on_document)
    if attachments and state['http_requests']<20:
        state=follow_attachments(output/'attachments',output/'rules/temporal-observations.json',ids,max_round_requests=20)
    baseline=read(ROOT/'data/temporal-observations.json')
    merged=deepcopy(state)
    merged['records']={**deepcopy(baseline['records']),**state['records']}
    merged['baseline']={'sha256':digest(baseline),'previous_round_http_requests':baseline['http_requests'],
        'note':'Separate manual round; unchanged records retained with their own observed_at and revisions.'}
    errors=validate_temporal_snapshot(bundle,merged)
    if errors:raise ValueError('invalid_temporal_proposal')
    save(output/'temporal-observations.proposed.json',merged)
    report.update(source_http_requests=state['http_requests'],baseline_http_requests=baseline['http_requests'],
        model_usage=adapter.usage_summary() if adapter else {'enabled':False,'calls':0,'hash_only_bytes_sent':0},
        rules_updated_candidates=len(state['records']),attachments_requested=attachments,
        rules_only_model_proposals_not_applied=True)
    report['model_configuration']={'model':getattr(adapter,'model',None),'tokenizer_model':MODEL if adapter and adapter.enabled else None,
        'input_budget_tokens':6000,'output_reserve_tokens':1200,'template_reserve_in_counter':True,
        'minimum_request_interval_seconds':getattr(adapter,'minimum_request_interval_seconds',None),
        'actual_usage_is_provider_reported':True,'cost_usd':None}
    if report['model_usage']['hash_only_bytes_sent']!=0:raise ValueError('restricted_source_leak')
    save(output/'report.json',report)
    summary=['# 時間重萃：手動待審結果','',f"來源HTTP：{state['http_requests']} / 20；模型推論：{report['model_usage']['calls']} / 4。",
        f"模型準備：{report['model_status']}；未發布、人工核准0。",
        '本輪與舊200HTTP台帳分開；保留舊紀錄不是宣稱本輪全部重新掃描。','',
        '| 來源 | 模型處置 | 有證據的待審提案 |','|---|---|---|']
    summary += [f"| {r['source_id']} | {r['status']} | {len(r.get('claims',[]))} |" for r in report['model_reviews']]
    summary+=['','模型提案未套入時間投影；規則預覽與API盤查分開。','原文、tokenizer及模型原始回應不在artifact內。']
    (output/'summary.md').write_text('\n'.join(summary)+'\n',encoding='utf-8')
    # Build an isolated view without writing proposed data into the checkout.
    from scripts.build_review_workspace import candidate_preview_data
    from scripts.export_wireframes import export
    from scripts.radar_metadata import radar_metadata
    from scripts.source_chains import timeline_metadata
    preview=candidate_preview_data(bundle,read(ROOT/'data/pilot.json'),config)
    export(output/'preview/index.html',pilot_data=preview,review_preview=True,
        radar_data=radar_metadata(bundle,merged),chain_data=timeline_metadata(read(ROOT/'data/source-chains.json'),bundle))
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,default=ROOT/'work/temporal-action')
    p.add_argument('--source-ids',default=os.environ.get('TEMPORAL_SOURCE_IDS','taipei-ai-tools,hsinchu-ai-tools'))
    p.add_argument('--attachments',action='store_true')
    args=p.parse_args();report=run(args.output,args.source_ids,args.attachments)
    print(json.dumps({'source_http_requests':report['source_http_requests'],'model_calls':report['model_usage']['calls'],
        'published':False},ensure_ascii=False))
