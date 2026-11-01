"""Resumable, rules-only source expansion. Writes review artifacts, never publishes."""
import argparse
from collections import Counter
from copy import deepcopy
from datetime import datetime,timezone,timedelta
from io import BytesIO
import json
from pathlib import Path
import re
import sys
import time
from urllib.parse import urlsplit
import zipfile
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from bs4 import BeautifulSoup
from scripts.audit_sources import canonical_url
from scripts.scan_sources import Fetcher,ScanError,node_get,digest,safe_url,html_document,pdf_document,SKIP
from scripts.source_chains import discover_links,publication
from scripts.document_ir import prepare_document,document_manifest,VERSION as IR_VERSION
from scripts.extract_candidates import extract_from_in_memory_blocks,DisabledModelAdapter,EXTRACTOR_VERSION
from scripts.semantic_facts import discover_identity

VERSION='expansion-1'
DENIED=re.compile(r'robots_|http_403|http_429|service_retry_after')
RESOURCE=re.compile(r'獎學金|獎助學金|論文獎|著作獎|培育計畫|研究獎勵|人社論文獎勵|撰寫博士論文|補助博士生赴國外研究|出席.*會議.*補助|(?:scholarship|fellowship|travel grant)',re.I)
INDEX=re.compile(r'^(?:最新消息|最新公告|獎學金|獎助學金|學生獎學金|學生事務|相關辦法|法規|首頁|獎(?:助)?學金(?:資訊|公告|公告資訊網|申請辦法)|news|scholarships?)$',re.I)
INFORMATION=re.compile(r'說明會|發放訊息|發放通知|QA整理|影片.*簡報|(?:Q\s*&\s*A|FAQ)',re.I)
ADMIN=re.compile(r'教師(?:評審|評鑑|遴選)|院長選任|校長遴選|經費稽核委員會|預算分配委員會|電腦中心設置')

def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def save(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix(path.suffix+'.new');temp.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');temp.replace(path)
def now():return datetime.now(timezone.utc).isoformat(timespec='seconds')
def fingerprint():
    dependencies=['scripts/source_chains.py','scripts/extract_candidates.py','scripts/verify_candidates.py','scripts/semantic_facts.py','schema/candidate.schema.json']
    return digest([Path(__file__).read_text(encoding='utf-8'),VERSION,EXTRACTOR_VERSION,IR_VERSION,
        *[(ROOT/path).read_text(encoding='utf-8') for path in dependencies]])

def office_blocks(raw,kind):
    """Bounded OOXML/ODF conversion in memory; never follows external relationships."""
    with zipfile.ZipFile(BytesIO(raw)) as archive:
        entries=archive.infolist()
        if len(entries)>2048 or sum(e.file_size for e in entries)>32_000_000:raise ScanError('office_archive_too_large')
        name='word/document.xml' if kind=='docx' else 'content.xml'
        info=archive.getinfo(name)
        if info.file_size>8_000_000:raise ScanError('office_xml_too_large')
        xml=archive.read(name)
    if b'<!DOCTYPE' in xml.upper() or b'<!ENTITY' in xml.upper():raise ScanError('office_xml_entities_rejected')
    root=ET.fromstring(xml);blocks=[]
    namespace='http://schemas.openxmlformats.org/wordprocessingml/2006/main' if kind=='docx' else 'urn:oasis:names:tc:opendocument:xmlns:text:1.0'
    for node in root.iter():
        if node.tag not in ('{'+namespace+'}p','{'+namespace+'}h'):continue
        text=''.join(n.text or '' for n in node.iter('{'+namespace+'}t')) if kind=='docx' else ''.join(node.itertext())
        text=re.sub(r'\s+',' ',text).strip()
        if text:blocks.append({'locator':kind.upper()+' paragraph '+str(len(blocks)+1),'text':text,'kind':'paragraph','structure_status':'office_layout_unverified'})
    return blocks

def prepare_response(response,profile,hosts):
    raw=response['body'];ctype=response['headers'].get('content-type','').lower();url=response['url']
    soup=None;links=[];published=None;title=None
    if raw.startswith(b'%PDF'):
        kind='pdf';blocks=pdf_document(raw)
    elif raw.startswith(b'PK'):
        with zipfile.ZipFile(BytesIO(raw)) as z:
            kind='docx' if 'word/document.xml' in z.namelist() else 'odt' if 'content.xml' in z.namelist() else 'unsupported'
        if kind=='unsupported':raise ScanError('unsupported_archive')
        blocks=office_blocks(raw,kind)
    elif 'text/html' in ctype:
        kind='html';soup=BeautifulSoup(raw,'html.parser')
        if soup.select('input[type=password]'):raise ScanError('login_form_not_processed')
        for form in soup.select('form'):form.unwrap()
        selector=profile.get('body_selector') or next((s for s in ('article','.article-center','main','[role=main]','#content','.content') if soup.select_one(s)),'body')
        source={'body_selector':selector,'required_markers':profile.get('required_markers',[]),'pdf_include':[],'max_pdfs':0}
        blocks,_=html_document(str(soup).encode(),source,url,hosts)
        roots=soup.select(selector)
        heading=next((r.select_one('h1') for r in roots if r.select_one('h1')),None)
        meta=soup.select_one('meta[property="og:title"]')
        title=(heading.get_text(' ',strip=True) if heading else meta.get('content','') if meta else soup.title.get_text(' ',strip=True) if soup.title else '')
        # Generic site headings often hide the actual article title in a lower heading.
        if not RESOURCE.search(title) or INDEX.fullmatch(title):
            options=list(dict.fromkeys(n.get_text(' ',strip=True) for root in roots for n in root.select('.news-title,.article-title,.entry-title,h2,h3')
                if RESOURCE.search(n.get_text(' ',strip=True)) and not INDEX.fullmatch(n.get_text(' ',strip=True)) and len(n.get_text(' ',strip=True))<=200))
            if len(options)==1:title=options[0]
        if SKIP.search(title):raise ScanError('private_or_result_title_not_processed')
        links=discover_links(raw,url,hosts,selector)
        links=[l for l in links if not SKIP.search(l['label']) and not ADMIN.search(l['label'])]
        pub=publication(soup,blocks,url);published=pub if pub[0] else None
    else:raise ScanError('format_parser_deferred')
    if not blocks or sum(len(b['text']) for b in blocks)<80:raise ScanError('insufficient_document_text')
    return {'kind':kind,'blocks':blocks,'links':links,'title':title,'publication':published}

def named_candidate(row,prepared,known):
    if known:return True
    title=prepared['title'] or ''
    if row['category'] in ('rights','agency','startup','unclassified') or prepared['kind']!='html':return False
    if urlsplit(row['url']).path=='/' or INDEX.fullmatch(title) or ADMIN.search(title) or INFORMATION.search(title):return False
    claim=discover_identity(prepared['blocks'])
    return bool(RESOURCE.search(title) and claim and claim['kind']=='eligibility_clause')

def profile_for(row,prepared,known):
    if known:return deepcopy(known)
    category,kind={'award':('outcome_award','award'),'mobility':('international_conference','travel_grant'),
        'living':('living_tuition','scholarship'),'foundation':('living_tuition','scholarship'),'campus':('living_tuition','scholarship'),
        'identity':('living_tuition','scholarship'),'ai':('research_tools','tool_subscription')}.get(row['category'],('phd_research','scholarship'))
    if re.search(r'赴國外研究|境外研究',prepared['title'] or ''):category,kind='overseas_research','travel_grant'
    if re.search(r'校長獎|院長獎|論文獎|著作獎',prepared['title'] or ''):category,kind='outcome_award','award'
    # Routing tags are preliminary; unknown degree/year/college remain unknown.
    return {'id':'discovery-'+row['id'].lower(),'title':prepared['title'],'url':row['url'],
        'body_selector':'body','required_markers':[],'pdf_include':[],'max_pdfs':0,
        'review_note':'自動發現候選；具名／角色／範圍尚待覆核，不因本站網址推定個人資格。',
        'evidence_mode':'hash_only','category':category,'resource_kind':kind,
        'scope':'ntu' if urlsplit(row['url']).hostname.endswith('.ntu.edu.tw') else 'nationwide'}

def initial_state(inventory,preflight=0):
    if type(preflight) is not int or not 0<=preflight<=1200:raise ValueError('invalid_preflight_budget')
    urls=[r['url'] for r in inventory['rows']]
    if len(urls)!=len(set(urls)):raise ValueError('duplicate_inventory_url')
    return {'version':VERSION,'pipeline_sha256':fingerprint(),'inventory_sha256':digest(inventory),'started_at':now(),
        'http_requests':preflight,'preflight_http_requests':preflight,'batch_requests':{},'records':{},'new_sources':{},'relations':[],
        'host_pauses':{},'candidates':{},'profiles':{},'model_calls':0,'official_data_modified':False}

def run_batch(inventory,state,batch,state_path,config,transport=node_get,progress=print):
    if state['pipeline_sha256']!=fingerprint() or state['inventory_sha256']!=digest(inventory):raise ValueError('pipeline_or_inventory_changed_use_new_state')
    if batch not in [f'B{i}' for i in range(1,9)]:raise ValueError('unsupported_batch')
    rows=[deepcopy(r) for r in inventory['rows'] if r['batch']==batch]
    known={canonical_url(p['url']):p for p in config['sources']}
    hosts=sorted({urlsplit(r['url']).hostname for r in inventory['rows'] if r['batch'] not in ('H','X') and r['url'].startswith('https://')})
    def known_for(r):return known.get(canonical_url(r['url']))
    # Fresh known primary pages first; then the rest of the finite inventory.
    rows.sort(key=lambda r:(known_for(r) is None,r.get('kind')=='附件／表單',r['id']))
    rows.extend(deepcopy(r) for r in state['new_sources'].values() if r['batch']==batch)
    seen=set();fetcher=None;micro_documents=0
    def request(url,headers,limit):
        if state['http_requests']>=1200 or state['batch_requests'].get(batch,0)>=200:raise ScanError('expansion_budget_deferred')
        state['http_requests']+=1;state['batch_requests'][batch]=state['batch_requests'].get(batch,0)+1
        # Reserve attempts before transport so interrupted calls cannot disappear from the budget.
        save(state_path,state)
        return transport(url,headers,limit)
    def finish(r,record):
        state['records'][r['url']]=record;save(state_path,state)
        progress(r['id']+' '+batch+' '+record['status']+' requests='+str(state['http_requests']),flush=True)
    while rows:
        row=rows.pop(0);url=canonical_url(row['url']);row['url']=url
        if url in seen:continue
        seen.add(url)
        old=state['records'].get(url)
        if old and old['status'] not in ('run_budget_exhausted','expansion_budget_deferred'):continue
        p=known_for(row);host=urlsplit(url).hostname
        record={'source_id':row['id'],'url':url,'batch':batch,'observed_at':now(),'depth':row.get('depth',0),
                'evidence_mode':'hash_only','events':[],'links':[],'candidate_ids':[]}
        if row.get('access_gate')=='manual_or_policy_recheck' or (p and not p.get('enabled',True)):
            record.update(status='manual_only',reason=row.get('restrictions',[]) or ['disabled_profile']);finish(row,record);continue
        if host in state['host_pauses']:
            record.update(status='host_paused',reason=state['host_pauses'][host]);finish(row,record);continue
        if state['http_requests']>=1200 or state['batch_requests'].get(batch,0)>=200:
            record.update(status='expansion_budget_deferred');finish(row,record);continue
        if fetcher is None or fetcher.count>=16 or micro_documents>=12 or time.monotonic()-fetcher.started>140:
            old_fetcher=fetcher
            fetcher=Fetcher({'allowed_hosts':hosts,'max_requests':20,'minimum_host_interval_seconds':3,'max_run_seconds':180},transport=request)
            if old_fetcher:
                fetcher.last=old_fetcher.last.copy();fetcher.delays=old_fetcher.delays.copy()
            micro_documents=0
        try:
            safe_url(url,hosts)
            response=fetcher.get(url,{},10*1024*1024)
            if response['status']!=200:raise ScanError('http_'+str(response['status']))
            prepared=prepare_response(response,p or {},hosts)
            ir=prepare_document(prepared['blocks']);revision=digest([url,digest(response['body']),fingerprint()])
            record.update(status='read',format=prepared['kind'],title=prepared['title'],final_url=response['url'],
                raw_sha256=digest(response['body']),revision_id=revision,document_manifest=document_manifest(ir),links=prepared['links'])
            if prepared['publication']:
                value,ref=prepared['publication'];record['events']=[{'kind':'announcement','value':value,'actor':'announcer','locator':ref['locator'],
                    'block_sha256':digest(ref['text'].encode()),'document_revision':revision,'review_status':'pending'}]
            if named_candidate(row,prepared,p):
                profile=profile_for(row,prepared,p)
                # Strictest retention for expansion: even existing short_excerpt profiles use hash-only here.
                profile['evidence_mode']='hash_only'
                candidates=extract_from_in_memory_blocks(profile,prepared['blocks'],revision,record['observed_at'],url=url,
                    as_of=datetime.fromisoformat(record['observed_at']).astimezone(timezone(timedelta(hours=8))).date().isoformat(),
                    model_adapter=DisabledModelAdapter(),extraction_strategy='rules_only')
                state['profiles'][profile['id']]=profile
                for candidate in candidates:
                    state['candidates'][candidate['candidate_id']]=candidate;record['candidate_ids'].append(candidate['candidate_id'])
                record['disposition']='named_candidates_pending'
            else:record['disposition']='source_document_or_discovery_only'
            # Child links get no inherited year, deadline, eligibility or approval.
            for link in prepared['links']:
                child=canonical_url(link['url']);relation={'from_url':url,'to_url':child,'role':link['role'],'label':link['label'],'origin':'observed_link','revision_id':revision}
                if relation not in state['relations']:state['relations'].append(relation)
                if (record['depth']<2 and link['role']=='policy' and child not in {r['url'] for r in inventory['rows']}
                        and child not in state['new_sources'] and len([r for r in state['new_sources'].values() if r.get('root_url')==row.get('root_url',url)])<8):
                    new={'id':'D'+digest(child)[:16],'url':child,'batch':batch,'category':row['category'],'title':link['label'],
                         'root_url':row.get('root_url',url),'depth':record['depth']+1,'restrictions':[],'access_gate':'fresh_policy_and_profile_check_required'}
                    state['new_sources'][child]=new;rows.append(new)
        except (ScanError,ValueError,KeyError,zipfile.BadZipFile,ET.ParseError,TimeoutError) as error:
            reason=str(error) if isinstance(error,ScanError) else type(error).__name__
            record.update(status=reason)
            if DENIED.search(reason) and reason!='robots_denied':state['host_pauses'][host]=reason
        micro_documents+=1
        finish(row,record)
    return state

def export_report(inventory,state,output):
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    config=read(ROOT/'data/scan-sources.json');combined={p['id']:p for p in config['sources']};combined.update(state['profiles'])
    config['sources']=list(combined.values());config['allowed_hosts']=sorted(set(config['allowed_hosts'])|{urlsplit(p['url']).hostname for p in combined.values()})
    bundle={'schema_version':'1.1.0-candidate','generated_at':now(),'as_of':datetime.now(timezone(timedelta(hours=8))).date().isoformat(),
        'timezone':'Asia/Taipei','model_enabled':False,'model_calls':0,'official_data_modified':False,'candidates':list(state['candidates'].values())}
    from scripts.check_data import validate_candidate_snapshot
    errors=validate_candidate_snapshot(bundle,config)
    if errors:raise ValueError('invalid_expansion_candidates: '+str(errors)[:600])
    save(output/'structured-candidates.json',bundle);save(output/'source-profiles.json',config)
    summary={'version':VERSION,'generated_at':now(),'http_requests':state['http_requests'],'request_count_scope':'attempts reserved before transport, includes robots/retries/preflight; may include interrupted attempts',
        'batch_requests':state['batch_requests'],'model_calls':0,'official_data_modified':False,'human_approvals':0,
        'inventory_urls':len(inventory['rows']),'source_records':len(state['records']),'new_sources':len(state['new_sources']),
        'candidate_count':len(bundle['candidates']),'statuses':dict(Counter(r['status'] for r in state['records'].values())),
        'remaining':[r['id'] for r in inventory['rows'] if r['batch'] not in ('H','X') and r['url'] not in state['records']]}
    save(output/'summary.json',summary)
    save(output/'source-results.json',{'summary':summary,'records':list(state['records'].values()),'relations':state['relations'],'discovered_sources':list(state['new_sources'].values())})
    return summary

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inventory',type=Path,default=ROOT/'data/source-inventory.json');parser.add_argument('--batch',choices=[f'B{i}' for i in range(1,9)],required=True)
    parser.add_argument('--state',type=Path,default=ROOT/'work/expansion/state.json');parser.add_argument('--output',type=Path,default=ROOT/'work/expansion/report')
    parser.add_argument('--preflight-requests',type=int,default=0)
    args=parser.parse_args()
    if args.state.resolve().is_relative_to(ROOT/'data') or args.output.resolve().is_relative_to(ROOT/'data'):parser.error('write review artifacts outside data')
    inventory=read(args.inventory);state=read(args.state) if args.state.exists() else initial_state(inventory,args.preflight_requests)
    run_batch(inventory,state,args.batch,args.state,read(ROOT/'data/scan-sources.json'))
    print(json.dumps(export_report(inventory,state,args.output),ensure_ascii=False))

if __name__=='__main__':main()
