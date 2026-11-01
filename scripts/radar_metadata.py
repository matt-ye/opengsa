"""Field visibility for the discovery view. No approvals, fetches or source text."""
from scripts.verify_candidates import classify_review_gaps


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
                and any(name in organizations.get('receiver','') for name in ('臺大','台大','臺灣大學','台灣大學'))):
            organizations.pop('receiver',None)
            gaps=[*gaps,'organizations.receiver_scope_mismatch']
        time_steps=[{'actor':step['actor'],'action':step['action'],'deadline':step['deadline']}
            for i,step in enumerate(candidate['schedule']['steps'])
            if step['deadline']['kind']!='unknown' and supported(f'schedule.steps/{i}/deadline')]
        records[candidate['candidate_id']]={'url':candidate['source_metadata']['url'],
            'revision':candidate['source_metadata']['revision_id'],
            'observed_at':candidate['source_metadata']['observed_at'],
            'known':known,'unsafe':unsafe,'unknown_reasons':gaps,
            'organizations':organizations,'time_steps':time_steps}
    return {'version':'radar-1','records':records}
