"""Focused second pass: recover article headings and evidence-bound date claims, in memory."""
import argparse
from collections import Counter
from datetime import datetime,timezone,timedelta
import json
from pathlib import Path
import re
import sys
import time
import zipfile
import xml.etree.ElementTree as ET
from urllib.parse import urlsplit

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from scripts.expand_sources import (read,save,now,prepare_response,profile_for,RESOURCE,INDEX,ADMIN,INFORMATION,DENIED,export_report)
from scripts.scan_sources import Fetcher,ScanError,node_get,digest,SKIP
from scripts.source_chains import dates
from scripts.semantic_facts import time_actor,discover_identity
from scripts.extract_candidates import extract_from_in_memory_blocks,DisabledModelAdapter

VERSION='document-refinement-2'

def headline(prepared):
    title=prepared['title'] or ''
    if RESOURCE.search(title) and not INDEX.fullmatch(title):return title[:200]
    options=list(dict.fromkeys(b['text'].strip() for b in prepared['blocks']
        if b.get('kind')=='heading' and len(b['text'])<=200 and RESOURCE.search(b['text']) and not INDEX.fullmatch(b['text']) and not SKIP.search(b['text']) and not ADMIN.search(b['text'])))
    return options[0] if len(options)==1 else title[:200]

def date_claims(blocks,revision,published=None):
    """No assumed year or role. Ambiguous claims stay sidecar facts, never application state."""
    result=[]
    def add(kind,values,actor,block,basis='explicit',pub=None):
        claim={'kind':kind,'values':values,'actor':actor,'basis':basis,'locator':block['locator'],
               'block_sha256':digest(block['text'].encode()),'revision_id':revision,'review_status':'pending'}
        if pub:claim['publication_ref']={'value':pub[0],'locator':pub[1]['locator'],'block_sha256':digest(pub[1]['text'].encode())}
        if claim not in result:result.append(claim)
    for block in blocks:
        text=block['text']
        if re.search(r'出生|年齡|身分證|學號|購買|訂閱|獎助期間|補助期間|聘任期間',text):continue
        if not re.search(r'申請|受理|截止|送件|送達|彙送|補件|補正|核定|結果|公布|公告|修正|生效',text):continue
        if not re.search(r'(?<!\d)(?:20\d{2}|1\d{2})[年/.-]',text):continue
        values=dates(text,None)
        if not values:continue
        kind=('policy_version' if re.search(r'修正|生效|發布日施行',text) else 'supplement_deadline' if re.search(r'補件|補正',text)
              else 'result_publication' if re.search(r'公布.*結果|結果.*公告|核定.*名單',text)
              else 'application_window' if re.search(r'申請|受理|截止|送件|送達|彙送',text) else 'announcement_or_decision')
        actor='announcer' if kind in ('result_publication','policy_version','announcement_or_decision') else time_actor(text)
        add(kind,values,actor,block)
        if kind=='application_window' and '即日起' in text and published:
            add('application_start',[published[0]],actor,block,'since_publication',published)
    return result

def refine(inventory,state,state_path,extras=(),transport=node_get,max_documents=32,extras_only=False,refresh=False):
    lookup={r['url']:r for r in inventory['rows']};targets=[]
    for url,record in state['records'].items():
        row=lookup.get(url)
        if not row or row['batch'] not in ('B1','B3') or record['status']!='read' or record.get('format')!='html' or record.get('candidate_ids'):continue
        if urlsplit(url).path=='/':continue
        if row['category'] in ('doctoral','award') or urlsplit(url).hostname in ('gice.ntu.edu.tw','www.aca.ntu.edu.tw'):targets.append(row)
    targets=([] if extras_only else targets[:20])+list(extras)
    hosts=sorted({urlsplit(r['url']).hostname for r in inventory['rows'] if r['batch'] not in ('H','X')}|{urlsplit(r['url']).hostname for r in extras})
    blocked={urlsplit(r['url']).hostname for r in inventory['rows'] if any(re.search('robots_not_plain_rules|robots_unavailable|http_403_host_paused',s) for s in r.get('restrictions',[]))}
    records=state.setdefault('refinements',{});fetcher=None;seen=set();count=0;micro_documents=0
    for row in targets:
        url=row['url'];batch=row['batch'];host=urlsplit(url).hostname
        if url in seen or (url in records and not refresh):continue
        seen.add(url)
        rec={'url':url,'source_id':row['id'],'batch':batch,'version':VERSION,'observed_at':now()}
        if host in state['host_pauses'] or host in blocked or row.get('access_gate')=='manual_or_policy_recheck':
            rec['status']='manual_or_host_pause_preserved';records[url]=rec;save(state_path,state);continue
        if count>=max_documents:break
        count+=1
        def request(target,headers,limit):
            if state['http_requests']>=1200 or state['batch_requests'].get(batch,0)>=200:raise ScanError('expansion_budget_deferred')
            state['http_requests']+=1;state['batch_requests'][batch]=state['batch_requests'].get(batch,0)+1
            state['refinement_http_requests']=state.get('refinement_http_requests',0)+1;save(state_path,state)
            return transport(target,headers,limit)
        if fetcher is None or fetcher.count>=16 or micro_documents>=12 or time.monotonic()-fetcher.started>140:
            previous=fetcher;fetcher=Fetcher({'allowed_hosts':hosts,'max_requests':20,'max_run_seconds':180,'minimum_host_interval_seconds':3},transport=request)
            if previous:fetcher.last=previous.last.copy();fetcher.delays=previous.delays.copy()
            micro_documents=0
        try:
            resp=fetcher.get(url,{},10*1024*1024)
            if resp['status']!=200:raise ScanError('http_'+str(resp['status']))
            prepared=prepare_response(resp,{},hosts);title=headline(prepared);prepared['title']=title
            revision=digest([url,digest(resp['body']),VERSION])
            claims=[] if INDEX.fullmatch(title) or INFORMATION.search(title) else date_claims(prepared['blocks'],revision,prepared['publication'])
            rec.update(status='read',title=title,format=prepared['kind'],revision_id=revision,raw_sha256=digest(resp['body']),date_claims=claims,links=prepared['links'],candidate_ids=[])
            # Title confirms the named resource; it does not populate degree/year eligibility filters.
            student_named=bool(re.search(r'學生|研究生|博士|碩士',title))
            identity=discover_identity(prepared['blocks'])
            if (prepared['kind']=='html' and RESOURCE.search(title) and not INDEX.fullmatch(title) and not ADMIN.search(title) and not INFORMATION.search(title)
                    and (student_named or (identity and identity['kind']=='eligibility_clause')) and row['category'] not in ('rights','agency','startup')):
                p=profile_for(row,prepared,None)
                p['evidence_mode']='hash_only'
                cs=extract_from_in_memory_blocks(p,prepared['blocks'],revision,rec['observed_at'],
                    as_of=datetime.fromisoformat(rec['observed_at']).astimezone(timezone(timedelta(hours=8))).date().isoformat(),
                    model_adapter=DisabledModelAdapter(),extraction_strategy='rules_only')
                superseded=[cid for cid,c in state['candidates'].items() if c['source_metadata']['url']==url]
                rec['superseded_candidate_ids']=superseded
                for cid in superseded:del state['candidates'][cid]
                state['profiles'][p['id']]=p
                for c in cs:state['candidates'][c['candidate_id']]=c;rec['candidate_ids'].append(c['candidate_id'])
            for l in prepared['links']:
                relation={'from_url':url,'to_url':l['url'],'role':l['role'],'label':l['label'],'origin':'refinement_observed_link','revision_id':revision}
                if relation not in state['relations']:state['relations'].append(relation)
        except (ScanError,ValueError,KeyError,TimeoutError,zipfile.BadZipFile,ET.ParseError) as error:
            rec['status']=str(error) if isinstance(error,ScanError) else type(error).__name__
            if DENIED.search(rec['status']) and rec['status']!='robots_denied':state['host_pauses'][host]=rec['status']
        micro_documents+=1;records[url]=rec;save(state_path,state)
        print(row['id']+' refinement '+rec['status']+' requests='+str(state['http_requests']),flush=True)
    return records

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--state',type=Path,default=ROOT/'work/expansion/state.json');p.add_argument('--extras',type=Path);p.add_argument('--max-documents',type=int,default=32)
    p.add_argument('--extras-only',action='store_true');p.add_argument('--refresh',action='store_true',help='Explicitly reread selected public documents; host pauses remain in force');args=p.parse_args()
    if args.state.resolve().is_relative_to(ROOT/'data'):p.error('state must remain outside data')
    if not 1<=args.max_documents<=40:p.error('max-documents must be 1..40')
    inventory=read(ROOT/'data/source-inventory.json');state=read(args.state)
    extras=read(args.extras)['sources'] if args.extras else []
    refine(inventory,state,args.state,extras,max_documents=args.max_documents,extras_only=args.extras_only,refresh=args.refresh)
    summary=export_report(inventory,state,ROOT/'work/expansion/refined-report')
    save(ROOT/'work/expansion/refined-report/date-claims.json',{'version':VERSION,'records':list(state.get('refinements',{}).values()),'model_calls':0})
    print(json.dumps(summary,ensure_ascii=False))
