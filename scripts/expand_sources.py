"""Resumable, rules-only source expansion. Writes review artifacts, never publishes."""
import argparse
from collections import Counter
from copy import deepcopy
from datetime import datetime,timezone,timedelta
from io import BytesIO
import json
from pathlib import Path
import re
import subprocess
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
from scripts.source_chains import DOCUMENT_LINK,discover_links,publication
from scripts.document_ir import prepare_document,document_manifest,VERSION as IR_VERSION
from jsonschema import ValidationError
from scripts.extract_candidates import extract_from_in_memory_blocks,DisabledModelAdapter,EXTRACTOR_VERSION
from scripts.semantic_facts import discover_identity

VERSION='expansion-1'
DENIED=re.compile(r'robots_|http_403|http_429|service_retry_after')
RESOURCE=re.compile(r'獎學金|獎助學金|論文獎|著作獎|培育計畫|研究獎勵|人社論文獎勵|撰寫博士論文|補助博士生赴國外研究|出席.*會議.*補助|(?:scholarship|fellowship|travel grant)',re.I)
# 急難救助、家庭補助與學生優惠的頁面不寫「獎學金」。只在這兩類來源放寬，獎學金來源維持原規則，排程掃描不多出雜卡。
CATEGORY_RESOURCE={
    'living':re.compile(r'急難|慰助|濟助|慰問金|紓困|助學金|就學(?:金|補助)|學雜費減免|托教補助|扶助|生活津貼|培力計畫|助學計畫|幼兒園|托育|獎學|學金|補助'),
    # 學生優惠來源是人工挑的產品頁，標題提到學生或教育就算。
    'ai':re.compile(r'學生|教師|教育|students?|educat|academic|campus',re.I)}

def resource_title(title,category=None):
    pattern=CATEGORY_RESOURCE.get(category)
    return bool(RESOURCE.search(title or '') or (pattern and pattern.search(title or '')))

# 「碩博士論文獎助最新公告」這種分類列表頁的標題，結尾是最新公告或最新消息。
INDEX=re.compile(r'^(?:.{0,30}(?:最新消息|最新公告)|獎學金|獎助學金|學生獎學金|學生事務|相關辦法|法規|首頁|獎(?:助)?學金(?:資訊|公告|公告資訊網|申請辦法)|news|scholarships?)$',re.I)
INFORMATION=re.compile(r'說明會|發放訊息|發放通知|QA整理|影片.*簡報|(?:Q\s*&\s*A|FAQ)',re.I)
# 全庫擴展的預設界限；提交流程要從入口頁往下走，放寬連結範圍，並把附件也當成可能的方案文件。
DEFAULT_OPTIONS={'follow_roles':('policy',),'max_children':8,'link_limit':8,'broad_links':False,'document_candidates':False,'group_documents':False}
INTAKE_OPTIONS={'follow_roles':('policy','related_call'),'max_children':40,'link_limit':None,'broad_links':True,'document_candidates':True,'group_documents':True}
INDEX_LINK_COUNT=3
# 「接受捐贈獎學金行政運作及管理作業要點」是學校怎麼收捐款的規定，不是給學生申請的方案。
ADMIN=re.compile(r'教師(?:評審|評鑑|遴選)|院長選任|校長遴選|經費稽核委員會|預算分配委員會|電腦中心設置|接受捐[贈款]')
ACADEMIC_YEAR=re.compile(r'(\d{3})\s*學年度')

def today():return datetime.now(timezone(timedelta(hours=8))).date()

def past_year_title(title):
    """標題寫的學年度都已過去（八月起算新學年度），是往年公告；同一方案今年的公告另有一頁。寫了今年或之後的就不算。"""
    years=[int(y) for y in ACADEMIC_YEAR.findall(title or '')]
    day=today();current=day.year-1911-(day.month<8)
    return bool(years) and max(years)<current

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

BARE_CATEGORY=re.compile(r'(?:申請)?(?:急難(?:救助|慰助|濟助)|助學金|獎助學金|生活助學金)')
LABELLED_NAME=re.compile(r'(?:法規|福利|計畫|方案|補助|獎助)?名\s*稱\s*[：:]?\s*(.*)')

def labelled_name(soup,category=None):
    """「名稱：X」或「福利名稱：」下一行 X；只收看得出是方案的值。"""
    lines=[line.strip() for line in soup.get_text('\n').splitlines() if line.strip()]
    for i,line in enumerate(lines):
        match=LABELLED_NAME.fullmatch(line)
        if match:
            value=(match.group(1) or (lines[i+1] if i+1<len(lines) else '')).strip()
            if 4<=len(value)<=80 and resource_title(value,category):
                # 短名稱（「申請急難救助」）看不出是誰辦的，附上網站名稱。
                site=soup.title.get_text(' ',strip=True) if soup.title else ''
                return f'{value}（{site}）' if len(value)<=8 and site and site!=value else value
    return ''

def prepare_response(response,profile,hosts,link_limit=8,broad_links=False,category=None):
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
        # 提交流程要看短頁：公告可能只有一句話加附件，字數少不代表沒有內容。
        if broad_links:source['min_text_chars']=1
        blocks,_=html_document(str(soup).encode(),source,url,hosts)
        roots=soup.select(selector)
        heading=next((r.select_one('h1') for r in roots if r.select_one('h1')),None)
        meta=soup.select_one('meta[property="og:title"]')
        # h1、og:title、<title> 依序看：先取看得出是方案的；都看不出就取第一個有字的（有些網站的 h1 是空的 logo）。
        names=[t for t in (heading.get_text(' ',strip=True) if heading else '',meta.get('content','') if meta else '',
                           soup.title.get_text(' ',strip=True) if soup.title else '') if t.strip()]
        title=next((t for t in names if resource_title(t,category) and not INDEX.fullmatch(t)),names[0] if names else '')
        # Generic site headings often hide the actual article title in a lower heading.
        if not resource_title(title,category) or INDEX.fullmatch(title):
            found=[n.get_text(' ',strip=True) for root in roots for n in root.select('.news-title,.article-title,.entry-title,h2,h3')
                if resource_title(n.get_text(' ',strip=True),category) and not INDEX.fullmatch(n.get_text(' ',strip=True)) and len(n.get_text(' ',strip=True))<=200]
            options=list(dict.fromkeys(found))
            # 產品頁會重複放同一個方案小標題，常見問題只出現一次：學生優惠來源取出現最多次的那個。
            if category=='ai' and len(options)>1:
                ranked=sorted(options,key=found.count,reverse=True)
                if found.count(ranked[0])>found.count(ranked[1]):options=ranked[:1]
            if len(options)==1:
                # 產品頁的小標題常只寫「學生方案」，要接上產品名才看得出是哪個方案。
                title=f'{title} {options[0]}' if category=='ai' and title and len(options[0])<=8 else options[0]
        # 政府網站常把名稱放在「名稱：…」「福利名稱：…」欄位，網站標題只是系統名稱（「福利補助自己查」）。
        # h1 本身看不出是方案時，名稱欄位比網站標題準。
        if not (heading and resource_title(heading.get_text(' ',strip=True),category)):
            title=labelled_name(soup,category) or title
        # 標題只寫類別（「急難濟助」）時看不出是誰辦的，會被提案當成泛稱擋掉；接上網站名稱
        # （<title> 最後一段，例如「行天宮五大志業網」），真方案才不會被誤擋。
        site=re.split(r'\s*[|｜∣\-－–]\s*',soup.title.get_text(' ',strip=True))[-1] if soup.title else ''
        if BARE_CATEGORY.fullmatch(title.strip()) and site and not BARE_CATEGORY.fullmatch(site) and site not in title:
            title=f'{title.strip()}（{site}）'
        if SKIP.search(title):raise ScanError('private_or_result_title_not_processed')
        links=discover_links(raw,url,hosts,selector,limit=link_limit,broad=broad_links)
        links=[l for l in links if not SKIP.search(l['label']) and not ADMIN.search(l['label'])]
        pub=publication(soup,blocks,url);published=pub if pub[0] else None
    else:raise ScanError('format_parser_deferred')
    # 學生優惠的產品頁把資格放在動態區塊，標題常是唯一寫明對象的地方；只在這類來源把標題當成可引用的區塊。
    # 其他來源不加，否則所有文件的版本雜湊都會變，排程掃描會把每個來源都當成有變動。
    if category=='ai' and title and blocks and not any(b['text']==title for b in blocks):
        blocks=[{'locator':'html title','text':title,'kind':'heading'}]+blocks
    if not blocks or (sum(len(b['text']) for b in blocks)<80 and not broad_links):raise ScanError('insufficient_document_text')
    return {'kind':kind,'blocks':blocks,'links':links,'title':title,'publication':published}

# 頁面讀到了卻不成卡的原因。記在每份文件上並在摘要統計，調規則時直接看卡在哪一關，不用逐頁除錯。
NOT_CARD_REASONS={'index_page':'索引頁（列出多個方案）','category_not_carded':'這個類別不成卡','document_not_html':'不是 HTML 的附件',
    'site_root_page':'網站首頁','listing_title':'列表頁標題','admin_title':'行政公告標題','information_title':'說明會或資訊類標題','past_year_title':'過去學年度的公告',
    'title_not_a_program':'標題看不出是方案','no_eligibility_sentence':'找不到申請資格或申請對象'}

def not_card_reason(row,prepared,known,documents=False):
    """回傳不成卡的原因代碼（見 NOT_CARD_REASONS）；會成卡回傳 None。"""
    if known:return None
    title=prepared['title'] or ''
    if row['category'] in ('rights','agency','startup','unclassified'):return 'category_not_carded'
    if prepared['kind']!='html' and not documents:return 'document_not_html'
    if urlsplit(row['url']).path=='/':return 'site_root_page'
    if INDEX.fullmatch(title):return 'listing_title'
    if ADMIN.search(title):return 'admin_title'
    if INFORMATION.search(title):return 'information_title'
    if past_year_title(title):return 'past_year_title'
    if not resource_title(title,row['category']):return 'title_not_a_program'
    claim=discover_identity(prepared['blocks'],row['category'])
    if not (claim and claim['kind']=='eligibility_clause'):return 'no_eligibility_sentence'
    return None

def named_candidate(row,prepared,known,documents=False):
    return not_card_reason(row,prepared,known,documents)is None

def clean_title(title):
    """公告標題去掉網站名稱、公告分類與轉知字樣。截止日留著，讀者用得到。"""
    text=re.sub(r'\s+[-－]\s+[^-－]*(?:大學|學院|學務處|事務處|組)[^-－]*$','',(title or '').strip())
    # 表情符號、開頭的檔案編號（01-1、02_）、結尾的日期（115.6.30）都不是方案名稱。
    text=re.sub(r'[\U0001F000-\U0001FAFF☀-➿️]','',text)
    text=re.sub(r'^(?:0\d(?:-\d+)?|\d{2}-\d+|\d{2}_)[_.\s]*(?=\D)','',text)
    text=re.sub(r'\s*\d{2,3}\.\d{1,2}\.\d{1,2}$','',text)
    text=re.sub(r'^【[^】]*(?:公告|訊息|獎學金|獎助學金|組|處|中心|室)】\s*','',text)
    # 「國立嘉義大學-學生事務處生活輔導組-…」：處室名稱不是方案名稱；校名留著，讀者才知道是哪一校。
    text=re.sub(r'^([^-－\s]*大學)\s*[-－]\s*[^-－\s]*(?:處|組|中心)[^-－\s]*\s*[-－]\s*',r'\1',text)
    # 法規資料庫的頁面標題帶系統名稱，例如「教育部主管法規共用系統-法規內容-…」。
    text=re.sub(r'^[^-－]*法規[^-－]*[-－]法規內容[-－]\s*','',text)
    # 附件編號與檔名裡的民國日期不是方案名稱；去掉後，同一方案的附件才會被當成同標題去重。
    text=re.sub(r'^附件\s*\d+\s*[：:]\s*','',text)
    text=re.sub(r'(?<=\D)[-_\s]?\d?1\d{6}(?:版)?$','',text)
    text=re.sub(r'^(?:轉知|轉發)\s*(?:[「『]([^」』]+)[」』].*)?',lambda m:m.group(1) or '',text)
    # 警語與「｜某某申請說明」這種尾巴不是方案名稱；截止日照舊保留。
    text=re.sub(r'[⛔️\s]*逾時視同放棄[！!]*$','',text)
    text=re.sub(r'\s*[｜|]\s*[^｜|]*(?:申請說明|說明會?|簡介)$','',text)
    return re.sub(r'^公告\s*[「『]([^」』]+)[」』]$',r'\1',text).strip() or title


def profile_for(row,prepared,known):
    if known:
        profile=deepcopy(known)
        # 舊設定的標題只寫類別（「急難濟助」）會被提案當成泛稱擋掉，這張卡就再也更新不了；
        # 這次讀到的標題接上了網站名稱，就改用它。
        fresh=clean_title(prepared['title'])
        if BARE_CATEGORY.fullmatch((profile.get('title') or '').strip()) and not BARE_CATEGORY.fullmatch(fresh.strip()):
            profile['title']=fresh
        # 舊設定存的是當時的標題；清理規則改進後也要套上，否則這張卡永遠帶著舊雜訊。清完只剩類別名稱就不動。
        elif profile.get('title'):
            cleaned=clean_title(profile['title'])
            if not BARE_CATEGORY.fullmatch(cleaned.strip()):profile['title']=cleaned
        return profile
    category,kind={'award':('outcome_award','award'),'mobility':('international_conference','travel_grant'),
        'living':('living_tuition','scholarship'),'foundation':('living_tuition','scholarship'),'campus':('living_tuition','scholarship'),
        'identity':('living_tuition','scholarship'),'ai':('research_tools','tool_subscription')}.get(row['category'],('living_tuition','scholarship'))
    # 一般獎學金不能預設成博士：只有標題明說只給博士才算，碩博並列或博士後都不算。
    if kind=='scholarship':
        if re.search(r'急難',prepared['title'] or ''):category='living_emergency'
        elif re.search(r'博士(?!後)|ph\.?d|doctoral',prepared['title'] or '',re.I) and not re.search(r'碩|大學部|學士|master',prepared['title'] or '',re.I):category='phd_research'
    if re.search(r'赴國外研究|境外研究|出國(?:學習|研修|進修|留學|實習)|交換學生|海外研修|留學獎學金',prepared['title'] or ''):category,kind='overseas_research','travel_grant'
    if re.search(r'校長獎|院長獎|論文獎|著作獎',prepared['title'] or ''):category,kind='outcome_award','award'
    # Routing tags are preliminary; unknown degree/year/college remain unknown.
    return {'id':'discovery-'+row['id'].lower(),'title':clean_title(prepared['title']),'url':row['url'],
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

def run_batch(inventory,state,batch,state_path,config,transport=node_get,progress=print,options=DEFAULT_OPTIONS):
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
            prepared=prepare_response(response,p or {},hosts,link_limit=options['link_limit'],broad_links=options['broad_links'],category=row.get('category'))
            if options['document_candidates'] and not prepared['title']:
                # 附件沒有網頁標題：連結文字像方案名稱就用它，否則沿用連到它的公告標題。
                # 連結文字常帶檔名副檔名或「點我下載」，都不是方案名稱的一部分。
                label=re.sub(r'\s*(?:點我下載|\(PDF\)|\.(?:pdf|docx?|odt))\s*$','',row.get('title') or '',flags=re.I)
                prepared['title']=label if resource_title(label,row.get('category')) else row.get('parent_title') or label
            ir=prepare_document(prepared['blocks']);revision=digest([url,digest(response['body']),fingerprint()])
            record.update(status='read',format=prepared['kind'],title=prepared['title'],final_url=response['url'],
                raw_sha256=digest(response['body']),revision_id=revision,document_manifest=document_manifest(ir),links=prepared['links'])
            if prepared['publication']:
                value,ref=prepared['publication'];record['events']=[{'kind':'announcement','value':value,'actor':'announcer','locator':ref['locator'],
                    'block_sha256':digest(ref['text'].encode()),'document_revision':revision,'review_status':'pending'}]
            # 列出多個方案的頁面是索引，要往下走，本身不成卡。
            index_like=options['broad_links'] and sum(bool(RESOURCE.search(l['label'])) for l in prepared['links'])>=INDEX_LINK_COUNT
            # 急難救助、家庭補助與學生優惠的頁面常在導覽列掛著獎學金連結；頁面本身寫了申請對象就是方案頁，不是索引。
            if index_like and row.get('category') in CATEGORY_RESOURCE and discover_identity(prepared['blocks'],row['category']):
                index_like=False
            record['links_found'],record['links_skipped']=len(prepared['links']),0
            reason='index_page' if index_like else not_card_reason(row,prepared,p,documents=options['document_candidates'])
            # 入口頁巡檢：入口頁本身只用來找連結，不成卡（它若是來源，每天的排程會掃；重抽只會換掉卡片代號）。
            if options.get('discovery_only_roots') and record['depth']==0:reason=reason or 'index_page'
            if reason:record['not_card_reason']=reason
            if not reason:
                profile=profile_for(row,prepared,p)
                # Strictest retention for expansion: even existing short_excerpt profiles use hash-only here.
                profile['evidence_mode']='hash_only'
                candidates=extract_from_in_memory_blocks(profile,prepared['blocks'],revision,record['observed_at'],url=url,
                    as_of=datetime.fromisoformat(record['observed_at']).astimezone(timezone(timedelta(hours=8))).date().isoformat(),
                    model_adapter=DisabledModelAdapter(),extraction_strategy='rules_only')
                state['profiles'][profile['id']]=profile
                for candidate in candidates:
                    # 公告連到的辦法或附件屬於同一方案。只共用方案代號，各文件的欄位不拼接。
                    if row.get('parent_program_key'):candidate['program_key']=row['parent_program_key']
                    state['candidates'][candidate['candidate_id']]=candidate;record['candidate_ids'].append(candidate['candidate_id'])
                    if candidate['verification']['status'] in ('passed_automated_checks','passed_with_gaps'):
                        try:
                            from scripts.temporal_reextract import same_round_record
                            state.setdefault('temporal',{})[candidate['candidate_id']]=same_round_record(candidate,prepared['blocks'],digest(response['body']),profile,record['observed_at'])
                        except (ValueError,KeyError,ValidationError):
                            pass  # 判斷不出時間，卡片照樣能提案。
                record['disposition']='named_candidates_pending'
            else:record['disposition']='source_document_or_discovery_only'
            # Child links get no inherited year, deadline, eligibility or approval.
            for link in prepared['links']:
                child=canonical_url(link['url']);relation={'from_url':url,'to_url':child,'role':link['role'],'label':link['label'],'origin':'observed_link','revision_id':revision}
                if relation not in state['relations']:state['relations'].append(relation)
                # 入口頁巡檢只找新方案：已經是來源的頁面每天的排程會掃，這裡不再跟。
                if options.get('skip_known_children') and child in known:continue
                if (record['depth']<2 and link['role'] in options['follow_roles'] and child not in {r['url'] for r in inventory['rows']}
                        and child not in state['new_sources']):
                    if len([r for r in state['new_sources'].values() if r.get('root_url')==row.get('root_url',url)])>=options['max_children']:
                        record['links_skipped']+=1
                        continue
                    # 連到別的網頁可能是別的方案，只有辦法和附件才算同一方案。
                    same_program=options['group_documents'] and record['candidate_ids'] and (link['role']=='policy' or DOCUMENT_LINK.search(urlsplit(child).path))
                    parent_program=state['candidates'][record['candidate_ids'][0]]['program_key'] if same_program else None
                    new={'id':'D'+digest(child)[:16],'url':child,'batch':batch,'category':row['category'],'title':link['label'],'parent_title':prepared['title'],'parent_program_key':parent_program,
                         'root_url':row.get('root_url',url),'depth':record['depth']+1,'restrictions':[],'access_gate':'fresh_policy_and_profile_check_required'}
                    state['new_sources'][child]=new;rows.append(new)
        except (ScanError,ValueError,KeyError,zipfile.BadZipFile,ET.ParseError,TimeoutError,subprocess.TimeoutExpired) as error:
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
    save(output/'structured-candidates.json',bundle);save(output/'source-profiles.json',config);save(output/'temporal-records.json',state.get('temporal',{}))
    summary={'version':VERSION,'generated_at':now(),'http_requests':state['http_requests'],'request_count_scope':'attempts reserved before transport, includes robots/retries/preflight; may include interrupted attempts',
        'batch_requests':state['batch_requests'],'model_calls':0,'official_data_modified':False,'human_approvals':0,
        'inventory_urls':len(inventory['rows']),'source_records':len(state['records']),'new_sources':len(state['new_sources']),
        'candidate_count':len(bundle['candidates']),'statuses':dict(Counter(r['status'] for r in state['records'].values())),
        'not_card_reasons':dict(Counter(r['not_card_reason'] for r in state['records'].values() if r.get('not_card_reason'))),
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
