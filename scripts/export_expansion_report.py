"""Compact review-only source dispositions and a static, searchable information-chain tree."""
import argparse
from collections import Counter,defaultdict
from copy import deepcopy
from html import escape
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from scripts.expand_sources import read,save,now
from scripts.scan_sources import digest

LABELS={'B1':'博士研究與候選人','B2':'會議與境外研究','B3':'院系與成果獎','B4':'生活與身分支持',
        'B5':'基金會與企業','B6':'AI／算力／創業','B7':'聘任、法規與權益','B8':'機關入口與待辨識','H':'海外占位暫緩','X':'參考與排除'}

def compact(record):
    record=deepcopy(record)
    manifest=record.pop('document_manifest',None)
    if manifest:record['document_manifest_summary']={'version':manifest['version'],'document_sha256':manifest['document_sha256'],'unit_count':len(manifest['units'])}
    return record

def report(inventory,state,discoveries):
    rows={r['url']:r for r in inventory['rows']};sources=[]
    for url,r in rows.items():
        item={'id':r['id'],'url':url,'title':r['title'],'batch':r['batch'],'category':r['category'],
              'kind':r['kind'],'program_keys':r.get('program_keys',[]),'parents':r.get('parents',[]),
              'restrictions':r.get('restrictions',[]),'access_gate':r.get('access_gate'),'origins':r['origins']}
        item['observation']=compact(state['records'].get(url,{'status':'overseas_deferred' if r['batch']=='H' else 'reference_or_non_candidate_excluded'}))
        if url in state.get('refinements',{}):item['refinement']=compact(state['refinements'][url])
        sources.append(item)
    for url,r in state['new_sources'].items():
        sources.append({**r,'kind':'observed_child_document','program_keys':[],
            'observation':compact(state['records'].get(url,{'status':'discovered_not_read'}))})
    for r in discoveries['sources']:
        existing=next((s for s in sources if s['url']==r['url']),None)
        if existing:
            existing['search_discovery']=r
            continue
        sources.append({**r,'kind':'official_search_lead','program_keys':[],
            'observation':compact(state.get('refinements',{}).get(r['url'],{'status':'search_located_not_read'}))})
    for s in sources:
        if s['url'] in state.get('refinements',{}) and s['kind']!='official_search_lead':s['refinement']=compact(state['refinements'][s['url']])
    candidates=list(state['candidates'].values());summary={
        'inventory_urls':len(rows),'in_scope_inventory_urls':sum(r['batch'] not in ('H','X') for r in rows.values()),
        'inventory_dispositions_complete':all(r['url'] in state['records'] for r in rows.values() if r['batch'] not in ('H','X')),
        'first_pass_records':len(state['records']),'discovered_child_urls':len(state['new_sources']),
        'search_lead_urls':len(discoveries['sources']),'refinement_records':len(state.get('refinements',{})),
        'http_requests':state['http_requests'],'preflight_http_requests':state.get('preflight_http_requests',0),
        'refinement_http_requests':state.get('refinement_http_requests',0),'batch_requests':state['batch_requests'],
        'search_tool_calls':8,'search_query_strings':24,'model_calls':0,'human_approvals':0,'published':False,
        'candidate_documents':len(candidates),'candidate_checks':dict(Counter(c['verification']['status'] for c in candidates)),
        'first_pass_statuses':dict(Counter(r['status'] for r in state['records'].values())),
        'date_claims_pending':sum(len(r.get('date_claims',[])) for r in state.get('refinements',{}).values())}
    return {'schema_version':'source-expansion-review-1','generated_at':now(),'summary':summary,
        'limitations':['URL數不是獎項數；HTTP200只代表文件可讀，不代表學生適用。',
            '搜尋摘要不用作欄位證據；189檢索名稱未逐一完成全網搜尋。',
            '新發現關聯不是已驗證適用關係；日期事實未綁年度／梯次／範圍前不進公開甘特圖。',
            '初次掃描與集中修補為同批校準，不是盲測。','未修改公開候選、正式pilot、人工核准台帳或PR34。'],
        'first_pass_pipeline_sha256':state['pipeline_sha256'],'candidate_gate_review':state.get('candidate_gate_review'),
        'host_pauses':state['host_pauses'],'sources':sources,'relations':state['relations'],
        'candidates':[{'candidate_id':c['candidate_id'],'program_key':c['program_key'],'title':c['title'],
            'url':c['source_metadata']['url'],'verification':c['verification']['status'],
            'review_status':c['review']['status'],'promotion_ready':c['review']['promotion_ready']} for c in candidates]}

def render(data):
    def link(url,label):
        return '<a rel="noopener noreferrer" href="'+escape(url,quote=True)+'">'+escape(label)+' ↗</a>' if url.startswith(('https://','http://')) else escape(label)
    byurl={s['url']:s for s in data['sources']};out=[]
    def source(s):
        obs=s.get('refinement') or s['observation'];claims=obs.get('date_claims',[])
        text='<li>'+link(s['url'],obs.get('title') or s['title'])+' <code>'+escape(obs['status'])+'</code>'
        if obs.get('format'):text+=' <span class="muted">'+escape(obs['format'])+'</span>'
        if claims:
            text+='<ul>'+''.join('<li>待核時間：'+escape(c['kind']+' / '+c['actor']+' / '+', '.join(c['values']))+'</li>' for c in claims)+'</ul>'
        links=obs.get('links') or s['observation'].get('links',[])
        if links:
            text+='<details><summary>實際觀察到的 '+str(len(links))+' 個關聯（尚非完整鏈）</summary><ul>'
            for l in links:
                child=byurl.get(l['url']);status=child['observation']['status'] if child else 'discovered_not_read'
                text+='<li>'+escape(l['role'])+' → '+link(l['url'],l['label'])+' <code>'+escape(status)+'</code></li>'
            text+='</ul></details>'
        return text+'</li>'
    out.append('<h2>具名候選 → 原文件 → 觀察到的下層連結</h2><p>全部待審；同方案別名與作用範圍未核定。核對失敗的候選只保留診斷，不進雷達更新提案。</p>')
    groups=defaultdict(list)
    for c in data['candidates']:groups[c['program_key']].append(c)
    for key,cs in groups.items():
        out.append('<details class="tree"><summary>'+escape(cs[0]['title'])+' <code>'+escape(key)+'</code></summary><ul>')
        for c in cs:
            s=byurl.get(c['url'])
            out.append(source(s) if s else '<li>'+link(c['url'],c['title'])+'</li>')
            out.append('<li>候選檢核：'+escape(c['verification'])+'；人工：pending</li>')
        out.append('</ul></details>')
    out.append('<h2>所有來源與處置（含未形成候選的入口）</h2>')
    for batch,label in LABELS.items():
        ss=[s for s in data['sources'] if s['batch']==batch]
        out.append('<details class="tree"><summary>'+batch+' '+label+' · '+str(len(ss))+' URL</summary><ul>'+''.join(source(s) for s in ss)+'</ul></details>')
    summary=escape(json.dumps(data['summary'],ensure_ascii=False,indent=2))
    return '''<!doctype html><html lang="zh-Hant"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>OpenGSA｜全來源資訊鏈待審報告</title><style>
body{font:16px/1.7 system-ui,sans-serif;background:#f7f6f0;color:#213e37;margin:0 auto;padding:28px;max-width:1100px}a{color:#15594f;overflow-wrap:anywhere}input{box-sizing:border-box;width:100%;font:inherit;padding:12px;border:1px solid #abbdb4;border-radius:8px}summary{cursor:pointer;font-weight:600}li{margin:9px 0;overflow-wrap:anywhere}.tree{background:white;border:1px solid #d5dfd6;border-radius:8px;padding:14px;margin:12px 0}code{font-size:12px;color:#73592b;overflow-wrap:anywhere}pre{white-space:pre-wrap}.muted{color:#62716c}button{font:inherit;padding:8px}
</style><h1>OpenGSA 全來源資訊鏈：待審報告</h1><p>來源 JSON 是唯一資料依據；不需要 Obsidian。這是離線查核結果，未發布至公開網站。展開節點可看文件格式、存取處置及關聯；日期僅為有定位與hash的待核事實。</p>
<label for="q">搜尋名稱、網址或處置</label><input id="q" type="search" placeholder="例如：博士、robots、application_window"><p><button id="reset" type="button">清除搜尋並收合</button></p>
<details><summary>數量與成本（URL不是方案）</summary><pre>'''+summary+'</pre></details>'+''.join(out)+'''
<script>const q=document.querySelector('#q');q.addEventListener('input',()=>{const v=q.value.trim().toLowerCase();document.querySelectorAll('.tree').forEach(d=>{d.hidden=!!v&&!d.textContent.toLowerCase().includes(v);d.open=!!v&&!d.hidden})});document.querySelector('#reset').onclick=()=>{q.value='';document.querySelectorAll('details').forEach(d=>{d.hidden=false;d.open=false});q.focus()}</script></html>'''

def validate_artifacts(root=ROOT):
    """Cheap offline invariants for the committed batch, without reasserting source correctness."""
    folder=Path(root)/'data/source-expansion'
    data=read(folder/'run-2026-11-01.json');inventory=read(Path(root)/'data/source-inventory.json')
    urls=[s['url'] for s in data['sources']];observed={s['url']:s for s in data['sources']};summary=data['summary']
    if len(urls)!=len(set(urls)):raise ValueError('duplicate_expansion_url')
    active=[r for r in inventory['rows'] if r['batch'] not in ('H','X')]
    if not all(r['url'] in observed and observed[r['url']]['observation']['status'] not in ('discovered_not_read','overseas_deferred','reference_or_non_candidate_excluded') for r in active):raise ValueError('missing_expansion_disposition')
    if summary['in_scope_inventory_urls']!=len(active):raise ValueError('expansion_count_mismatch')
    if summary['http_requests']!=summary['preflight_http_requests']+sum(summary['batch_requests'].values()):raise ValueError('expansion_http_accounting_mismatch')
    if summary['http_requests']>1200 or any(n>200 for n in summary['batch_requests'].values()):raise ValueError('expansion_budget_exceeded')
    if summary['model_calls'] or summary['human_approvals'] or summary['published']:raise ValueError('expansion_publication_boundary')
    from scripts.check_data import validate_candidate_snapshot
    bundle=read(folder/'candidates-2026-11-01.json');config=read(folder/'profiles-2026-11-01.json')
    errors=validate_candidate_snapshot(bundle,config)
    if errors:raise ValueError('invalid_expansion_candidate_snapshot: '+str(errors)[:300])
    if len(bundle['candidates'])!=summary['candidate_documents']:raise ValueError('expansion_candidate_count_mismatch')
    baseline={s['id'] for s in read(Path(root)/'data/scan-sources.json')['sources']}
    if any(p.get('enabled',True) for p in config['sources'] if p['id'] not in baseline):raise ValueError('new_expansion_scan_target_enabled')
    return summary

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--state',type=Path,default=ROOT/'work/expansion/state.json');args=p.parse_args()
    data=report(read(ROOT/'data/source-inventory.json'),read(args.state),read(ROOT/'data/source-expansion/search-discoveries-2026-11-01.json'))
    if not data['summary']['inventory_dispositions_complete']:raise ValueError('incomplete_inventory_dispositions')
    save(ROOT/'data/source-expansion/run-2026-11-01.json',data)
    statuses={s['url']:((s.get('refinement') or s['observation'])['status']) for s in data['sources']}
    keywords=read(ROOT/'data/resource-search-targets.json')
    coverage=[]
    for item in keywords['items']:
        matches=[{'url':u,'status':statuses[u]} for u in item['urls'] if u in statuses]
        coverage.append({'id':item['id'],'name':item['name'],'batch':item['batch'],'source_observations':matches,
            'status':'has_associated_source_dispositions_not_programme_validation' if matches else 'name_only_or_unmatched_url_pending_search'})
    save(ROOT/'data/source-expansion/keyword-coverage-2026-11-01.json',{'count':len(coverage),'items':coverage,
        'note':'來源入口有處置不等於該具名方案已找到或仍開放；名稱檢索仍有待辦。'})
    output=ROOT/'docs/source-expansion/results.html';output.write_text(render(data)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(data['summary'],ensure_ascii=False))

if __name__=='__main__':main()
