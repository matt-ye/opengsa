"""Export the canonical source graph to linked notes and a conservative crawl queue.

No HTTP, model, upload or approval actions. Refuse to overwrite edited generated notes.
"""
import argparse
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import re
import sys

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from scripts.export_source_chain_graph import load_graph,canvas,ROLE
from scripts.scan_sources import digest

VERSION='obsidian-export-1'
MANIFEST='.generated-manifest.json'
LABELS={'checked':'已有讀取快照，日期請看最後觀察','ready':'可分批掃描，仍須新查robots','needs_profile':'需補來源規格','manual_only':'人工查核／自動掃描受阻','reference_only':'參考資料，不當獎助掃描','format_deferred':'格式待支援','needs_https':'先驗證HTTPS入口'}

def read(path):return json.loads((ROOT/path).read_text(encoding='utf-8'))
def alias(text):return re.sub(r'[\[\]|\r\n]',' ',text).strip()
def wiki(path,title):return '[['+path.removesuffix('.md')+'|'+alias(title)+']]'
def note(properties,body):
    return '---\n'+'\n'.join(k+': '+json.dumps(v,ensure_ascii=False) for k,v in properties.items())+'\n---\n\n'+body.rstrip()+'\n'
def fingerprint(text):
    # Canvas rewrites JSON indentation on open. Content edits still block regeneration.
    try:text=json.dumps(json.loads(text),ensure_ascii=False,sort_keys=True,separators=(',',':'))
    except ValueError:pass
    return digest(text.replace('\r\n','\n').encode())
def source_path(doc_id):return 'Generated/Sources/'+doc_id+'.md'
def program_path(key):return 'Generated/Programs/'+key+'.md'
def rule_path(key):return 'Generated/Rules/'+key+'.md'

def sources_and_queue(graph):
    audit=read('data/audits/source-coverage-2026-10-31.json')
    rows={r['url']:r for r in audit['rows']}
    sources={d['url']:deepcopy(d) for d in graph['documents'].values()}
    for url,row in rows.items():
        if url not in sources:
            sources[url]={'id':'doc-'+digest(url)[:24],'url':url,'title':row['title'],'role':'seed_entry',
                          'format':'unknown','status':row['scan_status'],'clarity':'seed','observed_at':audit['as_of'],
                          'evidence_mode':'hash_only','events':[],'links':[]}
    profiles={}
    for p in read('data/scan-sources.json')['sources']:
        for url in [p['url'],*p.get('known_attachment_urls',[])]:
            profiles.setdefault(url,[]).append({'registry':'data/scan-sources.json','profile':p['id'],'enabled':p.get('enabled',True),'evidence_mode':p['evidence_mode']})
    for file in read('data/source-chain-index.json')['batch_configs']+['data/source-chain-sources.json']:
        for i,p in enumerate(read(file)['sources']):
            profiles.setdefault(p['url'],[]).append({'registry':file,'profile':'sources['+str(i)+']','enabled':True,'evidence_mode':p['evidence_mode']})
    queue=[]
    for url,doc in sorted(sources.items()):
        seed=rows.get(url,{});registry_status=seed.get('scan_status','not_in_older_inventory');bindings=profiles.get(url,[])
        # Older explicit access restrictions and disabled profiles are not silently relaxed.
        if any(not p['enabled'] for p in bindings) or re.search('robots_|login_only|http_403|host_paused',registry_status):state='manual_only'
        elif url.startswith('http://'):state='needs_https'
        elif seed.get('pipeline_role')=='supporting_documentation' or registry_status in ('crawl_policy_reference','overseas_degree_placeholder_deferred'):state='reference_only'
        elif re.search(r'\.(docx?|odt|xlsx)(?:[?#]|$)',url,re.I):state='format_deferred'
        elif doc['clarity']=='read':state='checked'
        elif bindings:state='ready'
        else:state='needs_profile'
        doc['queue_state']=state;doc['registry_role']=seed.get('pipeline_role','source_graph');doc['registry_status']=registry_status
        doc['title']=doc.get('title') or url
        queue.append({'document_id':doc['id'],'url':url,'title':doc['title'],'queue_state':state,
                      'profiles':bindings,'evidence_mode':doc['evidence_mode'],'requires_fresh_robots_check':True,
                      'raw_retention':'memory_only','model_mode':'off','registry_status':registry_status})
    return sources,{'schema_version':VERSION,'as_of':graph['as_of'],'model_mode':'off','scheduled':False,
                   'network_requests':0,'limits':{'max_requests_per_run':20,'max_documents_per_run':12,'minimum_host_interval_seconds':3},
                   'source_inventory_rows':len(rows),'counts':dict(sorted(Counter(q['queue_state'] for q in queue).items())),'items':queue}

def build_files(graph=None):
    graph=graph or load_graph();sources,queue=sources_and_queue(graph);files={}
    docs={d['id']:d for d in sources.values()};members={key:[] for key in docs};rule_members={key:[] for key in docs}
    for p in graph['programs']:
        for doc_id in p['document_ids']:members[doc_id].append(p)
        for rule in p['rules']:
            for ref in rule['evidence_refs']:rule_members[ref['document_id']].append(rule)
    warning='> [!info] 自動產生的資料檢視\n> 正式來源是 repo 的 JSON；請把人工補充寫入 Reviews。改動此頁會令重建停止，不會被靜默覆寫。\n\n'
    for p in graph['programs']:
        props={'entity_type':'program','entity_id':p['key'],'aliases':[p['title']],'review_status':p['audit_status'],
               'batch':p['audited_batch'] or 'baseline','candidate_count':len(p['candidate_ids']),'managed':True,'tags':['opengsa/program']}
        body='# '+p['title']+'\n\n'+warning+'## 尚待確認\n\n'+'\n'.join('- '+g for g in p['gaps'])+'\n\n## 來源文件\n\n'
        body+='\n'.join('- '+wiki(source_path(i),docs[i]['title'])+' · '+docs[i]['format']+' · '+docs[i]['status'] for i in p['document_ids'])
        body+='\n\n## 待審規則\n\n'+('\n'.join('- '+wiki(rule_path(r['id']),r['summary']) for r in p['rules']) or '本批尚未整理規則。')
        body+='\n\n## 候選對照\n\n```text\n'+'\n'.join(p['candidate_ids'])+'\n```\n'
        files[program_path(p['key'])]=note(props,body)
    for doc_id,d in sorted(docs.items()):
        props={'entity_type':'source','entity_id':doc_id,'aliases':[d['title']],'source_url':d['url'],'source_role':d['role'],
               'format':d['format'],'read_state':d['clarity'],'fetch_status':d['status'],'queue_state':d['queue_state'],'queue_label':LABELS[d['queue_state']],
               'last_checked':d['observed_at'][:10],'evidence_mode':d['evidence_mode'],'managed':True,'tags':['opengsa/source']}
        body='# '+d['title']+'\n\n'+warning+'[官方來源／原入口](<'+d['url']+'>)\n\n'
        body+='此筆是來源文件或入口，不能僅憑網址當成可申請獎學金。佇列：**'+LABELS[d['queue_state']]+'**。\n\n'
        body+='## 方案與來源版本\n\n'+('\n'.join('- '+wiki(program_path(p['key']),p['title']) for p in members[doc_id]) or '尚未配對到具名方案；保留為來源種子。')
        body+='\n\n```text\nrevision: '+d.get('revision_id','not_available')+'\nsource_status: '+d['status']+'\nolder_inventory_status: '+d['registry_status']+'\n```\n\n## 文件關係\n\n'
        edges=[e for e in graph['edges'] if e['source']==doc_id]
        body+='\n'.join('- '+wiki(source_path(e['target']),docs[e['target']]['title'])+' · '+ROLE.get(e['role'],e['role'])+' · '+e['origin'] for e in edges) or '尚未整理已配對的出向關係。'
        body+='\n\n## 引用本頁的規則\n\n'+('\n'.join('- '+wiki(rule_path(r['id']),r['summary']) for r in {r['id']:r for r in rule_members[doc_id]}.values()) or '尚無待審規則引用。')
        files[source_path(doc_id)]=note(props,body)
    for p in graph['programs']:
        for r in p['rules']:
            props={'entity_type':'rule','entity_id':r['id'],'aliases':[r['summary']],'rule_kind':r['kind'],'actor':r['actor'],
                   'scope':r['scope'],'cycle':r['cycle'],'review_status':'pending','managed':True,'tags':['opengsa/rule']}
            body='# '+r['summary']+'\n\n'+warning+wiki(program_path(p['key']),p['title'])+'\n\n## 結構化欄位\n\n```json\n'+json.dumps(r['value'],ensure_ascii=False,indent=2)+'\n```\n\n## 證據\n\n'
            for ref in r['evidence_refs']:
                body+='- '+wiki(source_path(ref['document_id']),docs[ref['document_id']]['title'])+' · '+ref['locator']+'\n  - revision: `'+ref['revision_id']+'`\n  - block hash: `'+ref['block_sha256']+'`\n'
            if r['value'].get('anchor_rule_id'):body+='\n## 依賴的上游規則\n\n'+wiki(rule_path(r['value']['anchor_rule_id']),r['value']['anchor_rule_id'])+'\n'
            files[rule_path(r['id'])]=note(props,body)
    # Bases are editable static views over generated properties; native Obsidian owns their YAML layout.
    network=canvas(graph)
    targets={digest('program:'+p['key'])[:16]:program_path(p['key']) for p in graph['programs']}
    targets.update({digest(doc_id)[:16]:source_path(doc_id) for doc_id in graph['documents']})
    for n in network['nodes']:
        if n['id'] in targets:n.pop('text',None);n['type']='file';n['file']=targets[n['id']]
    files['Maps/來源資訊鏈.canvas']=json.dumps(network,ensure_ascii=False,indent=2)+'\n'
    files['Views/crawl-queue.json']=json.dumps(queue,ensure_ascii=False,indent=2)+'\n'
    home='# OpenGSA 研究工作台\n\nJSON 是資料主檔；這個 vault 是研究、連結與例外筆記工作台。來源可讀不等於規則完整或已核准。\n\n'
    home+='## 先從這裡開始\n\n- [[Maps/來源資訊鏈.canvas|來源資訊鏈 Canvas]]：筆記卡片可直接開啟來源，不再只是文字卡片。\n- [[Views/來源與待爬清單.base|來源／待爬清單]]：145筆舊來源盤查與本批文件去重整合，按處理狀態篩選。\n- [[Views/待審規則.base|待審規則表]]：只釐清真衝突與缺口，不逐筆補齊未知。\n- [[Reviews/README|人工補充與隱私]]：人工筆記獨立保存，不被資料更新蓋掉。\n\n'
    home+='## 快速選一個方案\n\n'+'\n'.join('- '+wiki(program_path(p['key']),p['title']) for p in graph['programs'])
    home+='\n\n## 如何看關聯\n\n開啟方案筆記，再使用「Open local graph／開啟局部關聯圖」，深度先設1–2層。全域圖以Generated/Programs、Generated/Sources、Generated/Rules分組；未配對種子先用表格處理，避免把全域圖塞成毛球。Canvas箭頭有角色標籤，原生關聯圖只顯示筆記連結。\n\n'
    home+='## 抓取與更新\n\n本次只整理資料與佇列，沒有發出新的HTTP或模型請求。ready代表已有來源規格，仍須在每次抓取時重查robots、套用請求上限；人工／登入／限制來源不會因此解鎖。預設模型off、原文僅記憶體，沒有大量PDF快取或雲端同步。\n\n'
    home+='## 目前數量\n\n'+json.dumps({'programs':len(graph['programs']),'source_notes':len(sources),'rule_notes':sum(len(p['rules']) for p in graph['programs']),'queue':queue['counts']},ensure_ascii=False)+'\n'
    files['00-首頁.md']=home
    return files,queue

def export_vault(destination,check=False):
    root=Path(destination).resolve();files,queue=build_files();manifest_path=root/MANIFEST
    if not manifest_path.resolve().is_relative_to(root):raise ValueError('unsafe_manifest_path')
    old=json.loads(manifest_path.read_text(encoding='utf-8')) if manifest_path.exists() else {'version':VERSION,'files':{}}
    if old.get('version')!=VERSION:raise ValueError('vault_manifest_version_mismatch')
    # Validate every target before any mutation, including deletion of stale owned files.
    for relative in set(files)|set(old['files']):
        target=(root/relative).resolve()
        safe=target.is_relative_to(root)
        canonical=target.relative_to(root).as_posix() if safe else ''
        allowed=canonical in ('00-首頁.md','Views/crawl-queue.json') or canonical.startswith(('Generated/Programs/','Generated/Sources/','Generated/Rules/','Maps/'))
        if not safe or canonical!=relative or not allowed:
            raise ValueError('unsafe_generated_path')
        if target.exists():
            current=fingerprint(target.read_text(encoding='utf-8'))
            expected=old['files'].get(relative)
            if expected is None and (relative not in files or current!=fingerprint(files[relative])):
                raise ValueError('unowned_file_conflict: '+relative)
            if expected is not None and current!=expected:raise ValueError('edited_generated_file: '+relative)
    wanted={name:fingerprint(text) for name,text in files.items()}
    changes=[name for name,sha in wanted.items() if not (root/name).exists() or fingerprint((root/name).read_text(encoding='utf-8'))!=sha]
    stale=set(old['files'])-set(files)
    if not check:
        root.mkdir(parents=True,exist_ok=True)
        for relative in stale:(root/relative).unlink(missing_ok=True)
        for relative in changes:
            path=root/relative;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(files[relative],encoding='utf-8',newline='\n')
        manifest_path.write_text(json.dumps({'version':VERSION,'files':wanted},ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    return {'generated_files':len(files),'source_notes':len(queue['items']),'program_notes':sum(p.startswith('Generated/Programs/') for p in files),'rule_notes':sum(p.startswith('Generated/Rules/') for p in files),
            'queue_counts':queue['counts'],'network_requests':0,'model_calls':0,'changed':len(changes),'stale':len(stale),'check':check}

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,default=ROOT/'vault');parser.add_argument('--check',action='store_true');args=parser.parse_args()
    result=export_vault(args.output,args.check);print(json.dumps(result,ensure_ascii=False));
    if args.check and (result['changed'] or result['stale']):raise SystemExit(1)
