"""Field visibility for the discovery view. No approvals, fetches or source text."""
from scripts.verify_candidates import classify_review_gaps
import re


def programme_source(candidate, organizations):
    """Classify named scheme provenance, never the forwarding website or a student's eligibility."""
    patterns={
        'government':r'國科會|國家科學及技術委員會|教育部|衛生福利部|勞動部|政府|青年局|青年發展中心',
        'foundation':r'基金會|學會',
        'research_institute':r'中央研究院|中研院|國家實驗研究院|工研院',
        'enterprise':r'\b(?:Google|AWS|Amazon|GitHub|NVIDIA|Microsoft)\b|公司|台積電|聯發科',
        'university':r'大學|臺大|台大|學院|研究所|電信所|教務處|研發處'}
    for basis,text in [('evidenced_funder',organizations.get('funder','')),('programme_title',candidate['title'])]:
        found={kind for kind,pattern in patterns.items() if any(
            not re.search(r'(?:非由|不由|不是|不屬於|非)$',text[max(0,m.start()-4):m.start()])
            for m in re.finditer(pattern,text,re.I))}
        # A forwarding university in a title does not replace the named programme's agency.
        if len(found)>1:found.discard('university')
        if len(found)==1:
            return {'type':found.pop(),'basis':basis,'label':'資助單位文字' if basis=='evidenced_funder' else '方案名稱載明；非經費來源核定'}
        if found:return {'type':'unknown','basis':'ambiguous','label':'多類單位並列，請核對來源'}
    return {'type':'unknown','basis':'unresolved','label':'未辨識方案來源，不以公告網站代填'}


def radar_metadata(bundle):
    records={}
    for candidate in bundle['candidates']:
        gaps=classify_review_gaps(candidate)['source']
        verification=candidate['verification']
        unsafe=bool(verification['errors'] or candidate['gaps_and_conflicts']['conflicts'])
        unsafe=unsafe or verification['status'] in ('failed_automated_checks','conflict_detected','needs_context')
        unsafe=unsafe or any(verification['checks'].get(k) is not True for k in (
            'schema_valid','evidence_supported','date_and_amount_units_valid',
            'no_year_or_branch_mixing','negation_and_roles_valid','no_unresolved_conflicts'))
        evidence=candidate['field_evidence']
        def supported(path):
            return not unsafe and any(e['field_path']==path or e['field_path'].startswith((path+'.',path+'/')) for e in evidence)
        known={key:supported(path) for key,path in {
            'audience':'eligibility.identity','year':'eligibility.year_limit','candidate':'eligibility.candidate',
            'compatibility':'compatibility','hardship':'hardship',
            'start':'schedule.application_start','result':'schedule.result_date',
            'benefit':'benefit','method':'application_method'}.items()}
        known['audience']=known['audience'] and not any('identity_not_extracted' in g for g in gaps)
        student=[i for i,s in enumerate(candidate['schedule']['steps']) if s['actor']=='student']
        known['deadline']=any(supported(f'schedule.steps/{i}/deadline') for i in student)
        # Organizations are source-linked facts in the existing schema, not URL fields.
        # Keep their declared roles; receiver does not imply a named contact person.
        organizations={role:fact['text'] for role,fact in candidate['organizations'].items()
            if not unsafe and fact.get('text') not in ('待查','待確認','unknown','')
            and any(r.get('source')==candidate['source_metadata']['source_id'] and r.get('locator')
                for r in fact.get('refs',[]))}
        # Old national-policy records inherited an NTU receiver from a shared
        # extractor. Do not expose that route outside its declared school scope.
        if (candidate['institution_scope'].get('school')!='NTU'
                and any(name in organizations.get('receiver','') for name in ('臺大','台大','臺灣大學','台灣大學'))
                and not supported('organizations.receiver')):
            organizations.pop('receiver',None)
            gaps=[*gaps,'organizations.receiver_scope_mismatch']
        time_steps=[{'actor':step['actor'],'action':step['action'],'deadline':step['deadline']}
            for i,step in enumerate(candidate['schedule']['steps'])
            if step['deadline']['kind']!='unknown' and supported(f'schedule.steps/{i}/deadline')]
        records[candidate['candidate_id']]={'url':candidate['source_metadata']['url'],
            'revision':candidate['source_metadata']['revision_id'],
            'observed_at':candidate['source_metadata']['observed_at'],
            'known':known,'unsafe':unsafe,'unknown_reasons':gaps,
            'audience_kind':candidate['eligibility']['identity'].get('claim_kind','source_specific_summary'),
            'organizations':organizations,'time_steps':time_steps,
            'programme_source':programme_source(candidate,organizations) if not unsafe else {'type':'unknown','basis':'unsafe','label':'來源檢核未通過'}}
    return {'version':'radar-1','records':records}
