"""Final, bounded audit of every original seed; pending cards remain separate from publication."""
import argparse
from collections import Counter
from copy import deepcopy
from datetime import datetime,timezone,timedelta
import json
from pathlib import Path
import re
import sys
import time
from urllib.parse import urlsplit,unquote,urljoin
import zipfile
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from bs4 import BeautifulSoup
from scripts.expand_sources import read,save,now,prepare_response,profile_for,RESOURCE,INDEX,INFORMATION,ADMIN,DENIED
from scripts.refine_source_documents import date_claims
from scripts.scan_sources import Fetcher,ScanError,node_get,digest,SKIP,html_document
from scripts.extract_candidates import extract_from_in_memory_blocks,DisabledModelAdapter
from scripts.document_ir import prepare_document
from scripts.check_data import validate_candidate_snapshot
from scripts.verify_candidates import verify_candidate

VERSION='original-audit-1'
RESOURCE_NAME=re.compile(RESOURCE.pattern+r'|獎助|獎勵|補助|學費|急難|研究點數|學生優惠|student.*(?:pack|free)|free.*student|credits? for research|research credits|AWS Educate',re.I)
GENERIC=re.compile(r'^(?:首頁|學生|最新消息|內文標題|獎學金資訊|獎助學金申請辦法|獎學金公告|獎學金|.*(?:一覽表|一覽|公告列表)|.*學系|.*學院|電信所公告|國家科學及技術委員會|國立臺灣大學.*處)$')
FORM=re.compile(r'申請(?:表|書|資料表)|推薦(?:表|書|函)|同意書|摘要彙整表|登記表|證明書|收據|請款|報告(?:書|表)|合約|範本|範例|檢核表|checklist|application.form',re.I)
NONSTUDENT=re.compile(r'教師評|院長選任|校長遴選|研究中心設置|委員會設置|院務會議代表|博士後|飛躍講座|企業跨域研發|創育機構補助|微型創業獎勵|共同種子計畫|TUKUC')
INFO=re.compile(INFORMATION.pattern+r'|得獎|獲獎|錄取名單|申請逕行修讀博士學位|單獨招生|國際學位生第一梯次申請|隱私權|資訊安全政策',re.I)
ROOT_SELECTORS=('article','.article-center','.entry-content','.item-page','.news-content','.newsContent','.mcont','[role=main]','main','#content','#main-content','.content','body')

def parser_hash():
    return digest([Path(__file__).read_text(encoding='utf-8'),*[(ROOT/p).read_text(encoding='utf-8') for p in
        ['scripts/expand_sources.py','scripts/extract_candidates.py','scripts/verify_candidates.py','scripts/semantic_facts.py','scripts/document_ir.py']]])

def prepare_public(response,hosts):
    """Read only anonymously returned content; never submits or fills a login form."""
    if response['body'].startswith((b'%PDF',b'PK')):return prepare_response(response,{},hosts)
    if 'text/html' not in response['headers'].get('content-type','').lower():return prepare_response(response,{},hosts)
    soup=BeautifulSoup(response['body'],'html.parser');removed_login=False
    for password in list(soup.select('input[type=password]')):
        container=password.find_parent(['dialog']) or password.find_parent(class_=re.compile('modal|login',re.I)) or password.find_parent('form')
        if container is None:raise ScanError('login_form_not_processed')
        # A public main/article outside the login container is necessary evidence.
        public=[n for n in soup.select('main,article,.article-center,.item-page') if container not in n.parents and n is not container and container not in n.descendants and len(n.get_text(' ',strip=True))>=160]
        if not public:raise ScanError('login_form_not_processed')
        container.decompose();removed_login=True
    for form in soup.select('form'):form.unwrap()
    selected=None
    for selector in ROOT_SELECTORS:
        nodes=soup.select(selector)
        if any(len(n.get_text(' ',strip=True))>=80 for n in nodes):selected=selector;break
    if not selected:raise ScanError('public_shell_or_insufficient_text')
    prepared=prepare_response({**response,'body':str(soup).encode()}, {'body_selector':selected},hosts)
    title=prepared['title'] or ''
    if re.search(r'404|Not Found|找不到.*頁|系統發生錯誤|拒絕存取|Access Denied',title,re.I):raise ScanError('http_200_error_document')
    if GENERIC.fullmatch(title) or not RESOURCE_NAME.search(title):
        labeled=[]
        for tr in soup.select('tr'):
            cells=tr.find_all(['td','th'],recursive=False)
            if len(cells)==2 and re.sub(r'[\s：:]','',cells[0].get_text()).lower() in ('公告標題','標題','公告主旨','主旨','title','subject'):
                value=cells[1].get_text(' ',strip=True)
                if 8<=len(value)<=200 and RESOURCE_NAME.search(value) and not SKIP.search(value):labeled.append(value)
        explicit=[n.get_text(' ',strip=True) for n in soup.select('.news-title,.article-title,.entry-title,.subject,.news_subject,h2,h3,h4') if not n.find_parent(['a','nav','footer'])]
        titles=list(dict.fromkeys(t for t in explicit if 10<=len(t)<=200 and RESOURCE_NAME.search(t) and not GENERIC.fullmatch(t) and not SKIP.search(t) and not FORM.search(t) and not t.startswith('附件')))
        if len(set(labeled))==1:titles=list(set(labeled));prepared['title_basis']='labeled_title_table'
        # Legacy article templates use a standalone table cell/span as their heading.
        if not titles and ('shownews.php' in response['url']):
            titles=list(dict.fromkeys(b['text'] for b in prepared['blocks'][:18] if 12<=len(b['text'])<=160 and RESOURCE_NAME.search(b['text'])
                and not re.search(r'申請資格|申請對象|請於|應於|每名|每月|。|；',b['text']) and not SKIP.search(b['text'])))
        if len(titles)==1:prepared['title']=titles[0]
    prepared.update(selected_root=selected,login_widget_removed=removed_login)
    return prepared

def classify(row,prepared):
    title=prepared.get('title') or '';url=row['url'];filename=unquote(url)
    texts=[b['text'] for b in prepared['blocks']]
    if NONSTUDENT.search(title):return 'nonstudent_or_administrative_reference',False
    if INFO.search(title):return 'information_or_admission_reference',False
    if re.search(r'^附件\s*[一二三四五六七八九十\d]|方案報您知|懶人包|總覽',title):return 'source_index_or_organisation_entry',False
    if prepared['kind']!='html' and FORM.search(title+' '+filename):return 'application_form_or_procedure_attachment',False
    if row['category']=='rights':return 'rights_or_legal_reference',False
    if row['category']=='agency':return 'agency_or_nonstudent_resource_entry',False
    if prepared['kind']=='html' and (GENERIC.fullmatch(title) or INDEX.fullmatch(title) or (urlsplit(url).path in ('','/') and row['category'] in ('campus','foundation','doctoral'))):return 'source_index_or_organisation_entry',False
    if FORM.search(title) and not re.search(r'獎學金.*辦法|補助.*辦法|獎助.*辦法',title):return 'application_portal_or_form',False
    resource=bool(RESOURCE_NAME.search(title))
    if not resource and prepared['kind']!='html':
        headings=[t for t in texts[:10] if 8<=len(t)<=160 and RESOURCE_NAME.search(t) and not FORM.search(t) and not re.search('。|；|申請人|每名',t)]
        if len(headings)==1:prepared['title']=title=headings[0];resource=True
    if resource and not ADMIN.search(title):
        if prepared['kind']!='html' and not re.search(r'辦法|要點|須知|公告|獎學金|獎助',title):return 'supporting_document_needs_programme_binding',False
        if row['category']=='startup' and not re.search(r'學生|研究生|博士|碩士',title):return 'nonstudent_or_administrative_reference',False
        return ('named_policy_reference' if re.search(r'辦法|要點|準則|作業規定',title) else 'named_opportunity_document'),True
    return 'supporting_document_or_unresolved_identity',False

def quarantine_unproven(candidate,blocks):
    """Keep independently supported fields; only recognized date/amount failures can be downgraded."""
    errors=candidate['verification']['errors'];paths=set()
    if not errors:return candidate,[]
    for error in errors:
        m=re.fullmatch(r'hallucinated_date_not_in_source:(schedule\.steps/\d+/deadline|schedule\.application_start|schedule\.result_date):.*',error)
        if m:paths.add(m[1]);continue
        m=re.fullmatch(r'(?:hallucinated_amount_not_in_source|benefit_missing_unit):(benefit\.items/\d+)(?::.*)?',error)
        if m:paths.add(m[1]);continue
        return candidate,[]
    result=deepcopy(candidate)
    for path in paths:
        if path.startswith('schedule.steps/'):
            result['schedule']['steps'][int(path.split('/')[1])]['deadline'].update(kind='unknown',value=None,note='日期證據未能獨立確認，請至來源核對')
        elif path.startswith('schedule.'):
            result['schedule'][path.split('.')[1]].update(kind='unknown',value=None,note='日期證據未能獨立確認，請至來源核對')
            result['schedule'][path.split('.')[1]].pop('certainty',None)
    amounts={int(p.split('/')[1]) for p in paths if p.startswith('benefit.items/')}
    if amounts:
        # Drop the entire benefit projection rather than leave shifted evidence paths or a stale summary.
        result['benefit'].update(items=[],summary='金額或給付週期不明，請至來源核對',refs=[])
    result['field_evidence']=[e for e in result['field_evidence'] if e['field_path'] not in paths and not (amounts and e['field_path'].startswith('benefit.items'))]
    result['gaps_and_conflicts']['open_questions'].append('獨立檢核無法確認，欄位已降為未知：'+','.join(sorted(paths)))
    checked=verify_candidate(result,in_memory_blocks=blocks)
    from scripts.evaluate_deadlines import evaluate_application_window
    window=evaluate_application_window(checked,checked['application']['as_of'])
    checked['application'].update(state=window['state'],reason=window['reason'])
    return checked,sorted(paths)

def verify_all(inventory,state,audit,path,budget_path,config,transport=node_get):
    if audit.get('parser_sha256')!=parser_hash():raise ValueError('audit_parser_changed_use_new_audit_state')
    old_candidates={}
    for c in state['candidates'].values():old_candidates.setdefault(c['source_metadata']['url'],[]).append(c)
    by_profile={p['url']:p for p in config['sources']};rows=inventory['rows']
    for p in config['sources']:
        for url in p.get('known_attachment_urls',[]):by_profile.setdefault(url,p)
    hosts=sorted({urlsplit(r['url']).hostname for r in rows if r['batch'] not in ('H','X') and r['url'].startswith('https://')}|set(audit.get('additional_hosts',[])))
    fetcher=None;micro_docs=0
    # Closed/public sources first; cannot consume a budget by repeatedly attempting known gates.
    for row in rows:
        url=row['url'];rid=row['id'];batch=row['batch'];host=urlsplit(url).hostname
        if rid in audit['records']:continue
        old=state['records'].get(url,{});latest=state.get('refinements',{}).get(url) or old
        result={'source_id':rid,'url':url,'batch':batch,'title':row['title'],'checked_at':now(),'review_status':'pending',
                'content_verified':False,'card_ready':False,'candidate_ids':[],'seed_restrictions':row.get('restrictions',[])}
        def finish():
            audit['records'][rid]=result;save(path,audit)
            print(rid+' '+result['status']+' http='+str(state['http_requests']),flush=True)
        if batch in ('H','X'):
            result.update(status='overseas_deferred_by_scope' if batch=='H' else 'reference_or_non_candidate_excluded',inspection_depth='scope_classification_only');finish();continue
        restricted=row.get('access_gate')=='manual_or_policy_recheck' or host in state['host_pauses'] or old.get('status') in ('robots_denied','http_403_host_paused','robots_not_plain_rules','private_or_result_title_not_processed')
        if restricted:
            result.update(status='requires_manual_access_or_policy',inspection_depth='access_boundary_verified',reason=old.get('status') or state['host_pauses'].get(host) or row.get('restrictions'));finish();continue
        cs=old_candidates.get(url,[])
        if cs and all(c['verification']['status'] in ('passed_automated_checks','passed_with_gaps') for c in cs):
            result.update(status='named_resource_extraction_verified',content_verified=True,card_ready=True,inspection_depth='prior_in_memory_extraction_and_independent_checks',
                title=cs[0]['title'],candidate_ids=[c['candidate_id'] for c in cs],revision_id=cs[0]['source_metadata']['revision_id'])
            for c in cs:audit['candidates'][c['candidate_id']]=deepcopy(c)
            finish();continue
        # Navigation, informational and rights references have a different acceptance level from named grants.
        observed=latest.get('title') or old.get('title') or '';root=urlsplit(url).path in ('','/')
        metadata_reference=(INFO.search(observed) or NONSTUDENT.search(observed) or row['category'] in ('rights','agency') or (root and old.get('status')=='read') or (GENERIC.fullmatch(observed) and row['category']=='campus'))
        manifest=old.get('document_manifest',{})
        if old.get('status')=='read' and metadata_reference and (manifest.get('units') or old.get('raw_sha256')):
            result.update(status='reference_or_entry_format_verified',content_verified=True,inspection_depth='prior_document_format_and_navigation',title=observed,
                raw_sha256=old.get('raw_sha256'),revision_id=old.get('revision_id'),links=latest.get('links') or old.get('links',[]),
                reason='入口／程序／法規／非學生資源依已讀文件格式與導覽驗收；不宣稱完成學生資格條文檢核。');finish();continue
        def request(target,headers,limit):
            if state['http_requests']>=1200 or state['batch_requests'].get(batch,0)>=200:raise ScanError('expansion_budget_deferred')
            state['http_requests']+=1;state['batch_requests'][batch]=state['batch_requests'].get(batch,0)+1
            state['final_verification_http_requests']=state.get('final_verification_http_requests',0)+1;save(budget_path,state)
            response=transport(target,headers,limit)
            if response['status'] in (301,302,303,307,308):
                audit['redirect_observations'].append({'from':target,'to':urljoin(target,response['headers'].get('location','')),'http_status':response['status']});save(path,audit)
            return response
        if fetcher is None or fetcher.count>=16 or micro_docs>=12 or time.monotonic()-fetcher.started>140:
            previous=fetcher;fetcher=Fetcher({'allowed_hosts':hosts,'max_requests':20,'max_run_seconds':180,'minimum_host_interval_seconds':3},transport=request)
            if previous:fetcher.last=previous.last.copy();fetcher.delays=previous.delays.copy()
            micro_docs=0
        try:
            response=fetcher.get(url,{},10*1024*1024)
            if response['status']!=200:raise ScanError('http_'+str(response['status']))
            prepared=prepare_public(response,hosts);kind,ready=classify(row,prepared)
            revision=digest([url,digest(response['body']),audit['parser_sha256']]);ir=prepare_document(prepared['blocks'])
            result.update(status=kind,content_verified=True,inspection_depth='fresh_anonymous_document_read',title=prepared.get('title') or row['title'],
                format=prepared['kind'],raw_sha256=digest(response['body']),revision_id=revision,unit_count=len(ir['units']),
                selected_root=prepared.get('selected_root'),login_widget_removed=prepared.get('login_widget_removed',False),links=prepared['links'],
                date_claims=[] if kind in ('source_index_or_organisation_entry','information_or_admission_reference') else date_claims(prepared['blocks'],revision,prepared['publication']))
            if ready:
                known=by_profile.get(url)
                if known and url==known['url'] and any(m not in ''.join(b['text'] for b in prepared['blocks']) for m in known.get('required_markers',[])):known=None
                p=profile_for(row,prepared,known);p.update(evidence_mode='hash_only',enabled=False)
                if row['category']=='ai':
                    p.update(category='indirect_support',resource_kind='tuition_remission') if re.search('課程|職涯營|訓練|實戰|養成班|產業新尖兵',prepared['title'] or '') else p.update(category='research_tools',resource_kind='tool_subscription')
                cs=extract_from_in_memory_blocks(p,prepared['blocks'],revision,result['checked_at'],url=url,as_of=datetime.now(timezone(timedelta(hours=8))).date().isoformat(),model_adapter=DisabledModelAdapter(),extraction_strategy='rules_only')
                normalized_blocks=prepare_document(prepared['blocks'])['units']
                corrected=[quarantine_unproven(c,normalized_blocks) for c in cs];cs=[c for c,_ in corrected]
                result['quarantined_fields']=[path for _,paths in corrected for path in paths]
                audit['profiles'][p['id']]=p
                for c in cs:audit['candidates'][c['candidate_id']]=c
                result.update(card_ready=bool(cs) and all(c['verification']['status'] in ('passed_automated_checks','passed_with_gaps') for c in cs),
                    candidate_ids=[c['candidate_id'] for c in cs],extraction_checks=[{'status':c['verification']['status'],'errors':c['verification']['errors']} for c in cs])
                if not result['card_ready']:result['status']='extraction_checks_require_followup'
        except (ScanError,ValueError,KeyError,TimeoutError,zipfile.BadZipFile,ET.ParseError) as e:
            reason=str(e) if isinstance(e,ScanError) else type(e).__name__
            result.update(status='requires_manual_access_or_policy' if DENIED.search(reason) else 'requires_parser_or_url_followup',reason=reason,inspection_depth='fresh_transport_or_parser_attempt')
            if DENIED.search(reason) and reason!='robots_denied':state['host_pauses'][host]=reason;save(budget_path,state)
        micro_docs+=1;finish()
    return audit

def export(audit,state,output):
    config=read(ROOT/'data/scan-sources.json');profiles={p['id']:p for p in config['sources']};profiles.update(audit['profiles'])
    for p in profiles.values():
        if p['id'] not in {x['id'] for x in config['sources']}:p['enabled']=False
    config.update(sources=list(profiles.values()),allowed_hosts=sorted(set(config['allowed_hosts'])|{urlsplit(p['url']).hostname for p in profiles.values()}))
    bundle={'schema_version':'1.1.0-candidate','generated_at':now(),'as_of':datetime.now(timezone(timedelta(hours=8))).date().isoformat(),'timezone':'Asia/Taipei',
        'model_enabled':False,'model_calls':0,'official_data_modified':False,'candidates':list(audit['candidates'].values())}
    errors=validate_candidate_snapshot(bundle,config)
    if errors:raise ValueError('invalid_audit_candidates:'+str(errors)[:500])
    summary={'original_urls':len(audit['records']),'scope_urls':sum(r['batch'] not in ('H','X') for r in audit['records'].values()),
        'content_verified':sum(r['content_verified'] for r in audit['records'].values()),'card_ready_sources':sum(r['card_ready'] for r in audit['records'].values()),
        'statuses':dict(Counter(r['status'] for r in audit['records'].values())),'candidate_documents':len(bundle['candidates']),
        'cumulative_http_requests':state['http_requests'],'final_verification_http_requests':state.get('final_verification_http_requests',0),'batch_requests':state['batch_requests'],
        'model_calls':0,'human_approvals':0,'published':False,'all_content_verified':False}
    save(Path(output)/'summary.json',summary);save(Path(output)/'structured-candidates.json',bundle);save(Path(output)/'source-profiles.json',config)
    return summary

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--audit',type=Path,default=ROOT/'work/expansion/final-verification.json');p.add_argument('--budget',type=Path,default=ROOT/'work/expansion/state.json');p.add_argument('--retry-source',action='append',default=[]);args=p.parse_args()
    if any(x.resolve().is_relative_to(ROOT/'data') for x in (args.audit,args.budget)):p.error('state must stay outside data')
    state=read(args.budget);inventory=read(ROOT/'data/source-inventory.json')
    audit=read(args.audit) if args.audit.exists() else {'version':VERSION,'parser_sha256':parser_hash(),'started_at':now(),'records':{},'candidates':deepcopy(state['candidates']),'profiles':deepcopy(state['profiles']),'redirect_observations':[]}
    if args.retry_source:
        if not set(args.retry_source)<={r['id'] for r in inventory['rows']}:p.error('unknown original source ID')
        old_hash=audit['parser_sha256'];audit.setdefault('parser_history',[]).append(old_hash)
        for r in audit['records'].values():r.setdefault('parser_sha256',old_hash)
        audit['parser_sha256']=parser_hash()
        for rid in args.retry_source:
            previous=audit['records'].pop(rid,None)
            if previous:
                audit.setdefault('previous_attempts',[]).append(previous)
                for cid in previous['candidate_ids']:audit['candidates'].pop(cid,None)
    verify_all(inventory,state,audit,args.audit,args.budget,read(ROOT/'data/scan-sources.json'))
    print(json.dumps(export(audit,state,ROOT/'work/expansion/verified-report'),ensure_ascii=False))
