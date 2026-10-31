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
        records[candidate['candidate_id']]={'url':candidate['source_metadata']['url'],
            'revision':candidate['source_metadata']['revision_id'],
            'observed_at':candidate['source_metadata']['observed_at'],
            'known':known,'unsafe':unsafe,'unknown_reasons':gaps}
    return {'version':'radar-1','records':records}
