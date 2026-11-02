"""Close the finite URL review with explicit external limitations; never mark blocked content verified."""
from collections import Counter,defaultdict
from copy import deepcopy
from html import escape
from pathlib import Path
import json
import re
import sys

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from scripts.expand_sources import read,save,now
from scripts.verify_original_sources import FORM,NONSTUDENT,INFO

def close(inventory,state,audit):
    expected={r['id'] for r in inventory['rows']}
    if set(audit['records'])!=expected:raise ValueError('not_all_original_sources_reviewed')
    original={r['id']:r for r in inventory['rows']};byraw=defaultdict(list)
    for rid,result in audit['records'].items():
        old=state['records'].get(result['url'],{})
        if not result.get('raw_sha256') and result['content_verified']:result['raw_sha256']=old.get('raw_sha256')
        if result.get('raw_sha256'):byraw[result['raw_sha256']].append(rid)
    # Prefer the established public profile over a second URL of the exact same document.
    for keys in byraw.values():
        ready=[audit['records'][key] for key in keys if audit['records'][key]['card_ready']]
        if len(ready)<2:continue
        ready.sort(key=lambda r:(all(audit['candidates'][cid]['source_metadata']['source_id'].startswith('discovery-') for cid in r['candidate_ids']),r['source_id']))
        primary=ready[0]
        for duplicate in ready[1:]:
            duplicate.update(status='byte_identical_document_alias',card_ready=False,equivalent_resource_source_ids=[primary['source_id']],superseded_candidate_ids=duplicate['candidate_ids'])
            for cid in duplicate['candidate_ids']:audit['candidates'].pop(cid,None)
            duplicate['candidate_ids']=[]
    for rid,result in audit['records'].items():
        # Attachment headings from a parent article are not that article's resource title.
        bad_heading=bool(re.search(r'^附件\s*[一二三四五六七八九十\d]|CV範例|受獎生.*範例',result['title']))
        if result['card_ready'] and bad_heading:
            result.update(card_ready=False,status='article_identity_requires_manual_confirmation',reason='擷取到附件／範例標題；卡片隔離，不能當文章名稱。')
            for cid in result['candidate_ids']:audit['candidates'].pop(cid,None)
            result['superseded_candidate_ids']=result['candidate_ids'];result['candidate_ids']=[]
        cs=[audit['candidates'][cid] for cid in result['candidate_ids'] if cid in audit['candidates']]
        student_named=re.search(r'學生|研究生|博士|碩士|獎學金|獎助學金|scholarship|fellowship|graduate|phd',result['title'],re.I)
        if result['card_ready'] and not student_named and cs and all(c['resource_kind'] in ('scholarship','travel_grant') and not c['eligibility']['degrees'] and c['eligibility']['identity']['text'].startswith('身分條件請至來源定位核對') for c in cs):
            result.update(status='nonstudent_or_unresolved_applicant_reference',card_ready=False,reason='未確認學生為申請／受益對象；保留機關方案參考，不作學生獎學金卡。')
            for cid in result['candidate_ids']:audit['candidates'].pop(cid,None)
            result['superseded_candidate_ids']=result['candidate_ids'];result['candidate_ids']=[]
        # Exact bytes may establish an alias, never transfer dates between different bytes.
        aliases=[audit['records'][key] for key in byraw.get(result.get('raw_sha256'),[]) if key!=rid and audit['records'][key]['card_ready']]
        if aliases and not result['card_ready'] and result['content_verified']:
            result['equivalent_resource_source_ids']=[a['source_id'] for a in aliases]
            if result['status'].startswith('supporting_document'):result['status']='byte_identical_document_alias'
        labels=[{'from_url':r['from_url'],'label':r.get('label',''),'origin':r.get('origin'),'parent_revision_id':r.get('revision_id')}
            for r in state['relations'] if r.get('to_url')==result['url']]
        result['observed_parent_links']=labels
        if result['status'].startswith('supporting_document') and any(FORM.search(r['label']) for r in labels):
            result['status']='verified_application_attachment';result['reason']='已讀格式與原頁附件標籤相符；附件不單獨建立獎學金卡。'
        if result['status']=='requires_parser_or_url_followup':
            reason=result.get('reason','')
            result['automatic_followup_exhausted']=True
            if reason in ('format_parser_deferred','unsupported_archive','pdf_requires_manual_review'):
                result.update(status='manual_format_conversion_required',next_action='必要時由官方提供可讀文字／HTML或人工核對；不將未解析附件當作已萃取。')
            elif reason in ('public_shell_or_insufficient_text','required_marker_missing','body_selector_changed','login_form_not_processed','insufficient_document_text'):
                result.update(status='manual_rendered_or_access_review_required',next_action='匿名GET未取得足夠可辨識正文；需人工渲染檢視或公開官方資料入口，不繞過登入。')
            elif reason.startswith('http_') or reason in ('transport_error','redirect_limit','url_not_allowed'):
                result.update(status='official_url_replacement_or_access_required',next_action='保留舊URL及實際錯誤／轉址證據；只採已確認的官方替代入口，不猜網址。')
            elif reason=='expansion_budget_deferred':
                result.update(status='budget_limited_content_unverified',next_action='主批／整輪預算已達上限；未解鎖額外掃描。')
            else:result.update(status='manual_parser_review_required',next_action='目前解析器未能完成；保留診斷並隔離建卡。')
        if result['status']=='extraction_checks_require_followup':
            result['automatic_followup_exhausted']=True;result['next_action']='萃取欄位未通過獨立檢核，隔離該卡；來源可讀不等於候選可用。'
        if result['status']=='supporting_document_or_unresolved_identity':
            result.update(status='read_supporting_document_identity_unresolved',next_action='文字格式已讀，尚無唯一方案名稱；作資訊鏈附件／參考，不硬建卡。')
        if result['status']=='supporting_document_needs_programme_binding':
            result['next_action']='文字已讀，需與主辦方案綁定；不從檔名推定年度與資格。'
        result['reviewed_at']=now();result['classification_review_complete']=True
        result['human_approved']=False
    # Recompute routing tags only; do not add eligibility or rewrite extracted source claims.
    from scripts.expand_sources import profile_for
    by_url={r['url']:r for r in inventory['rows']}
    for c in audit['candidates'].values():
        sid=c['source_metadata']['source_id'];row=by_url.get(c['source_metadata']['url'])
        if sid.startswith('discovery-') and row and row['category']!='ai':
            p=profile_for(row,{'title':c['title']},None)
            c.update(category=p['category'],resource_kind=p['resource_kind'])
            audit['profiles'][sid].update(category=p['category'],resource_kind=p['resource_kind'])
        if sid.startswith('discovery-'):c['participants']['beneficiary']='unknown'
    summary={'original_urls':len(expected),'in_scope_urls':sum(r['batch'] not in ('H','X') for r in original.values()),
        'all_original_urls_classified':True,'all_content_verified':all(r['content_verified'] for r in audit['records'].values() if r['batch'] not in ('H','X')),
        'readable_document_or_entry_checks':sum(r['content_verified'] for r in audit['records'].values()),
        'content_not_verified_in_scope':sum(not r['content_verified'] and r['batch'] not in ('H','X') for r in audit['records'].values()),
        'card_ready_source_urls':sum(r['card_ready'] for r in audit['records'].values()),'candidate_documents':len(audit['candidates']),
        'statuses':dict(Counter(r['status'] for r in audit['records'].values())),
        'cumulative_http_requests':state['http_requests'],'final_verification_http_requests':state.get('final_verification_http_requests',0),
        'batch_requests':state['batch_requests'],'model_calls':0,'human_approvals':0,'published':False}
    return {'schema_version':'original-source-verification-1','generated_at':now(),'parser_sha256':audit['parser_sha256'],
        'summary':summary,'records':list(audit['records'].values()),'redirect_observations':audit['redirect_observations'],
        'notes':['逐項來源檢核完成，並非所有來源內容皆可取得。受限、失效、格式及未知身分分開保留。',
            'H13與X105維持原核可範圍；不擴爬海外與技術資料。','內容可讀只表示文件／入口可驗證，不是法規解釋、學生適用或人工核准。']}

def validate_report(data,inventory):
    records=data['records'];summary=data['summary'];expected={r['id'] for r in inventory['rows']}
    if len(records)!=len(expected) or {r['source_id'] for r in records}!=expected:raise ValueError('original_source_coverage_mismatch')
    if not all(r.get('classification_review_complete') and not r.get('human_approved') for r in records):raise ValueError('source_review_boundary')
    if any(r['card_ready'] and not r['content_verified'] for r in records):raise ValueError('unread_source_cannot_be_card_ready')
    if summary['cumulative_http_requests']>1200 or any(n>200 for n in summary['batch_requests'].values()):raise ValueError('original_verification_budget_exceeded')
    if summary['all_content_verified']!=all(r['content_verified'] for r in records if r['batch'] not in ('H','X')):raise ValueError('false_all_content_verified_claim')
    if summary['model_calls'] or summary['human_approvals'] or summary['published']:raise ValueError('original_verification_publication_boundary')
    return summary

def render(data):
    lines=['<!doctype html><html lang="zh-Hant"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>OpenGSA 原始來源逐項檢核</title>',
        '<style>body{font:16px/1.6 system-ui;max-width:1200px;margin:auto;padding:24px;background:#f7f6f0;color:#213e37}table{border-collapse:collapse;width:100%;background:white}td,th{padding:12px;border:1px solid #d7dfd7;text-align:left;vertical-align:top}a{color:#15594f;overflow-wrap:anywhere}code{font-size:12px;overflow-wrap:anywhere}input{padding:12px;font:inherit;width:90%}</style>',
        '<h1>原始來源逐項檢核</h1><p>所有原始URL均有檢核結論；未取得內容者仍標示受限，不代表全部內容已驗證或獎學金可申請。</p>',
        '<pre>'+escape(json.dumps(data['summary'],ensure_ascii=False,indent=2))+'</pre>',
        '<label>搜尋來源、處置、原因 <input id="q" type="search"></label><table><thead><tr><th>來源</th><th>檢核結論</th><th>建卡／後續</th></tr></thead><tbody>']
    for r in data['records']:
        lines.append('<tr><td>'+escape(r['source_id']+' / '+r['batch'])+'<br><a href="'+escape(r['url'],quote=True)+'">'+escape(r['title'])+' ↗</a></td><td><code>'+escape(r['status'])+'</code><br>'+escape(str(r.get('reason','')))+'<br>內容讀取：'+('是' if r['content_verified'] else '否')+'</td><td>'+('可進待審建卡' if r['card_ready'] else escape(r.get('next_action','保留為入口／參考／受限；不單獨建卡')) )+'</td></tr>')
    return '\n'.join(lines)+'''</tbody></table><script>document.querySelector('#q').oninput=e=>{const q=e.target.value.toLowerCase();document.querySelectorAll('tbody tr').forEach(r=>r.hidden=!r.textContent.toLowerCase().includes(q))}</script></html>\n'''

if __name__=='__main__':
    state=read(ROOT/'work/expansion/state.json');audit=read(ROOT/'work/expansion/final-verification.json')
    data=close(read(ROOT/'data/source-inventory.json'),state,audit)
    validate_report(data,read(ROOT/'data/source-inventory.json'))
    save(ROOT/'data/source-expansion/original-source-verification.json',data)
    (ROOT/'docs/source-expansion/original-source-verification.html').write_text(render(data),encoding='utf-8',newline='\n')
    save(ROOT/'work/expansion/final-verification-reviewed.json',audit)
    print(json.dumps(data['summary'],ensure_ascii=False))
