"""Field-scoped rule replay. Source/evidence/review ownership cannot be patched by a model."""
from copy import deepcopy

GROUPS={
 'identity':('title','category','resource_kind','scope','cycle','participants','organizations','institution_scope'),
 'eligibility':('eligibility','hardship'),
 'benefit':('benefit','compatibility'),
 'process':('application_method','schedule','expense_period','field_applicability'),
 'version':('policy_version',),
}


def get_path(value,path):
    for part in path.split('.'):
        if not isinstance(value,dict) or part not in value:raise ValueError('unknown_field:'+path)
        value=value[part]
    return value


def overlaps(a,b):
    a=a.replace('/','.');b=b.replace('/','.')
    return a==b or a.startswith(b+'.') or b.startswith(a+'.')


def loses_information(old,new):
    if isinstance(old,dict) and isinstance(new,dict):
        return any(loses_information(value,new.get(key)) for key,value in old.items() if key not in ('refs','note','summary'))
    if isinstance(old,list) and isinstance(new,list):
        return len(new)<len(old) or any(loses_information(a,b) for a,b in zip(old,new))
    return old not in (None,'unknown',[],{}) and new in (None,'unknown',[],{})


def compile_scope(candidate,groups=None,fields=None):
    targets=set(fields or [])
    for group in groups or []:
        if group not in GROUPS:raise ValueError('unknown_group:'+group)
        targets.update(k for k in GROUPS[group] if k in candidate)
    if not targets:raise ValueError('explicit_fields_or_groups_required')
    allowed={p for paths in GROUPS.values() for p in paths}
    for path in list(targets):
        if path.split('.')[0] not in allowed or any(part.isdigit() for part in path.split('.')):
            raise ValueError('field_scope_not_allowed:'+path)
        get_path(candidate,path)
        # Coupled values have one evidence/meaning boundary, never patch an array index.
        for parent in ('benefit','eligibility.year_limit','eligibility.candidate','schedule','application_method'):
            if overlaps(parent,path) and path.startswith(parent+'.'):
                targets.remove(path);targets.add(parent);break
    process={'application_method','schedule','field_applicability'}
    if any(overlaps(path,parent) for path in targets for parent in process):
        # N/A, delivery and deadlines jointly determine the student window.
        targets.update(path for path in process if path in candidate)
    targets={p for p in targets if not any(p!=other and p.startswith(other+'.') for other in targets)}
    return {'write_fields':sorted(targets),
        'read_dependencies':['cycle','participants','institution_scope','eligibility','benefit','schedule','policy_version'],
        'revalidate':'whole_candidate','model_field_support':'existing_adapter_allowlist_only'}


def apply_scoped_replay(original,refreshed,plan,blocks):
    from scripts.review_candidates import candidate_fingerprint
    from scripts.verify_candidates import verify_candidate
    if plan.get('candidate_sha256')!=candidate_fingerprint(original):raise ValueError('candidate_content_changed')
    if any(original['source_metadata'].get(k)!=refreshed['source_metadata'].get(k) for k in ('source_id','url','revision_id')):
        raise ValueError('source_revision_changed_requires_full_replay')
    if plan.get('prepared_document_sha256')!=refreshed['source_metadata'].get('prepared_document_sha256'):
        raise ValueError('prepared_document_changed')
    scope=compile_scope(original,fields=plan['write_fields'])
    result=deepcopy(original)
    for path in scope['write_fields']:
        if loses_information(get_path(original,path),get_path(refreshed,path)):
            raise ValueError('scoped_information_regression_requires_review:'+path)
        parts=path.split('.');parent=result
        for part in parts[:-1]:parent=parent[part]
        parent[parts[-1]]=deepcopy(get_path(refreshed,path))
    def selected(path):return any(overlaps(path,target) for target in scope['write_fields'])
    result['field_evidence']=[e for e in result['field_evidence'] if not selected(e['field_path'])]
    result['field_evidence']+=deepcopy([e for e in refreshed['field_evidence'] if selected(e['field_path'])])
    gaps=result['gaps_and_conflicts']
    gaps['missing_fields']=[g for g in gaps['missing_fields'] if not selected(g)]
    gaps['missing_fields']+= [g for g in refreshed['gaps_and_conflicts']['missing_fields'] if selected(g) and g not in gaps['missing_fields']]
    # Never erase unresolved conflicts merely because a replay did not repeat them.
    for conflict in refreshed['gaps_and_conflicts']['conflicts']:
        if conflict not in gaps['conflicts']:gaps['conflicts'].append(deepcopy(conflict))
    result['review'].update(status='pending',independent_reviewer=None,reviewed_on=None,
        ledger_action='unreviewed',promotion_ready=False)
    result['review'].pop('approved_candidate_sha256',None)
    result['source_metadata'].update({k:refreshed['source_metadata'][k] for k in
        ('extractor_version','normalizer_version','prepared_document_sha256') if k in refreshed['source_metadata']})
    # Derived state belongs to the merged candidate, not the old or partial replay.
    from scripts.evaluate_deadlines import evaluate_application_window
    window=evaluate_application_window(result,original['application']['as_of'])
    result['application']={**{k:window[k] for k in ('state','as_of','reason')},'refs':
        [{'source':result['source_metadata']['source_id'],'locator':blocks[0]['locator']}]
        if window['state']!='unknown' and blocks else []}
    from scripts.extract_candidates import limit_evidence_excerpts
    limit_evidence_excerpts(result,120)
    return verify_candidate(result,blocks)
