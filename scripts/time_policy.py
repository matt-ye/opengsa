"""Read-only v1 adapter for evidenced legacy timing. No fetching or intake decisions."""
import json
import re
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit

from jsonschema import Draft202012Validator, FormatChecker, ValidationError
from scripts.evaluate_deadlines import parse_iso_date, parse_taipei_datetime
from scripts.review_candidates import candidate_fingerprint


@lru_cache(maxsize=1)
def policy_validator():
    schema = json.loads((Path(__file__).resolve().parents[1] / 'schema/time-policy.schema.json').read_text(encoding='utf-8'))
    return Draft202012Validator(schema, format_checker=FormatChecker())


def source_is_unsafe(candidate):
    verification = candidate['verification']
    return bool(verification['errors'] or candidate['gaps_and_conflicts']['conflicts']) or (
        verification['status'] in ('failed_automated_checks', 'conflict_detected', 'needs_context')) or any(
        verification['checks'].get(k) is not True for k in (
            'schema_valid', 'evidence_supported', 'date_and_amount_units_valid',
            'no_year_or_branch_mixing', 'negation_and_roles_valid', 'no_unresolved_conflicts'))


def temporal_observation(candidate, observations):
    """Fail closed on stale bindings or foreign-source claims; no silent rebinding."""
    if not observations or observations.get('version') != 'temporal-replay-1' or source_is_unsafe(candidate):
        return None
    record = observations.get('records', {}).get(candidate['candidate_id'], {})
    if (record.get('status') != 'replayed'
            or record.get('candidate_sha256') != candidate_fingerprint(candidate)
            or record.get('url') != candidate['source_metadata']['url']):
        return None
    policy = record['policy']
    policy_validator().validate(policy)
    if not all(re.fullmatch(r'[0-9a-f]{64}',record.get(k,'')) for k in ('raw_sha256','revision_id')):
        raise ValueError('temporal_observation_missing_source_hash')
    for rule in policy['rules']:
        documents={(d['url'],d['revision_id']) for d in record.get('documents',[])
                   if re.fullmatch(r'[0-9a-f]{64}',d.get('raw_sha256',''))
                   and d.get('parent_url')==record['url'] and d.get('parent_raw_sha256')==record['raw_sha256']
                   and urlsplit(d['url']).hostname==urlsplit(record['url']).hostname}
        if not all(ref['source'] == candidate['source_metadata']['source_id'] and (
                   (not ref.get('url') and ref['revision_id'] == record.get('revision_id'))
                   or (ref.get('url'),ref['revision_id']) in documents) for ref in rule['source_refs']):
            raise ValueError('temporal_observation_source_revision_mismatch')
    return record


def calendar_is_ambiguous(policy):
    dates=[r for r in policy['rules'] if r['kind']=='absolute' and r['stage']!='result']
    years={r['value'][:4] for r in dates}
    if len(years)<=1:
        return False
    # A single explicit window crossing New Year is valid; several unbound
    # school/agency/student dates from different years must first be split.
    starts={r['value'] for r in dates if r['actor']=='student' and r['stage']=='application_start'}
    ends={r['value'] for r in dates if r['actor']=='student' and r['stage']=='submission'}
    return not (len(starts)==len(ends)==1 and min(starts)<=min(ends)
                and all(min(starts)<=r['value']<=min(ends) for r in dates))


def validate_temporal_snapshot(bundle, observations):
    errors=[]
    if (observations.get('version')!='temporal-replay-1' or observations.get('model_calls')!=0
            or observations.get('published') is not False):
        return ['temporal_snapshot_boundary_invalid']
    batches=observations.get('batches',[])
    if (not batches or any(type(b.get('http_requests')) is not int or not 0<=b['http_requests']<=20 for b in batches)
            or sum(b['http_requests'] for b in batches)!=observations.get('http_requests')
            or not 0<=observations['http_requests']<=200):
        errors.append('temporal_request_ledger_invalid')
    if not isinstance(observations.get('records'),dict):
        return [*errors,'temporal_candidate_inventory_invalid']
    for candidate in bundle['candidates']:
        record=observations.get('records',{}).get(candidate['candidate_id'],{})
        # Normal candidate updates need not re-read every unrelated source.
        # Archived/stale observations are inert, never rebound to new claims.
        if not record or record.get('candidate_sha256')!=candidate_fingerprint(candidate):
            continue
        if (record.get('url')!=candidate['source_metadata']['url']
                or record.get('status') not in ('replayed','blocked')):
            errors.append('temporal_record_binding_invalid:'+candidate['candidate_id'])
        try:
            temporal_observation(candidate,observations)
        except (ValueError,KeyError,TypeError,ValidationError) as error:
            errors.append('temporal_record_invalid:'+candidate['candidate_id']+':'+str(error))
    return errors


def project_time_policy(candidate, unsafe=False):
    """Never infer rolling intake from missing dates, titles or review wording.

    The legacy schedule remains the source of truth. Each projected claim must
    match its own field, current source and revision; administrative evidence
    cannot authorize student deadlines. Summaries are existing authored facts,
    not new excerpts or reconstructed source text.
    """
    policy = {'version': 'time-policy-1', 'submission_mode': 'undetermined',
              'review_mode': 'not_stated', 'rules': [], 'gaps': []}
    if unsafe or source_is_unsafe(candidate):
        policy['gaps'] = ['source_checks_failed']
        return policy
    meta = candidate['source_metadata']
    schedule = candidate['schedule']

    def refs(path):
        return [{'source': e['source'], 'revision_id': e['revision_id'],
                 'locator': e['locator'], 'evidence_path': e['field_path']}
                for e in candidate['field_evidence']
                if (e['field_path'] == path or e['field_path'].startswith((path + '.', path + '/')))
                and e['source'] == meta['source_id'] and e['revision_id'] == meta['revision_id'] and e.get('locator')]

    def add(path, actor, stage, deadline):
        evidence = refs(path)
        if not evidence or deadline.get('kind') not in ('date', 'datetime', 'relative'):
            return
        if deadline['kind'] == 'date' and parse_iso_date(deadline.get('value')) is None:
            raise ValueError('Invalid evidenced timing date: ' + path)
        if deadline['kind'] == 'datetime' and parse_taipei_datetime(deadline.get('value')) is None:
            raise ValueError('Invalid evidenced Taipei timing datetime: ' + path)
        kind = 'absolute'
        anchor = None
        if deadline['kind'] == 'relative':
            # This prefix is emitted by our existing recurring_time normalizer,
            # not a loose keyword search over arbitrary page text.
            if deadline['note'].startswith('來源常態月日：'):
                kind = 'recurring'
            elif (schedule['relative_rule']['rule_type'] in ('nstc_ntu', 'days_before', 'months_before')
                  and schedule['relative_rule']['anchor_event'] == 'conference_start'):
                kind, anchor = 'event_relative', 'conference_start'
            else:
                kind = 'text_rule'
        policy['rules'].append({'rule_id': path, 'kind': kind, 'actor': actor,
            'stage': stage, 'summary': deadline['note'], 'value': deadline.get('value'),
            'precision': deadline['kind'] if kind == 'absolute' else 'rule',
            'anchor_event': anchor, 'source_refs': evidence})

    add('schedule.application_start', 'student', 'application_start', schedule['application_start'])
    for index, step in enumerate(schedule['steps']):
        add(f'schedule.steps/{index}/deadline', step['actor'],
            'supplement' if step['actor'] == 'supplement' else 'submission', step['deadline'])
    add('schedule.result_date', 'other', 'result', schedule['result_date'])

    rules = policy['rules']
    student = [r for r in rules if r['actor'] == 'student' and r['stage'] != 'result']
    relative = {r['kind'] for r in rules if r['kind'] != 'absolute'}
    if relative:
        policy['submission_mode'] = ('rule_text' if relative == {'text_rule'} else
                                     next(iter(relative)) if len(relative) == 1 else 'mixed')
    elif student:
        start = any(r['stage'] == 'application_start' for r in student)
        end = any(r['stage'] == 'submission' for r in student)
        policy['submission_mode'] = 'fixed_window' if start and end else 'deadline_only' if end else 'start_only'
    elif any(r['stage'] != 'result' for r in rules):
        policy['submission_mode'] = 'procedure_only'

    # Preserve the existing explicit N/A branch, rather than guessing that a
    # policy without dates or an award with no deadline is automatically exempt.
    na = candidate.get('field_applicability', {})
    if not rules and all(na.get(k, {}).get('status') == 'not_applicable'
                         and na[k].get('refs') for k in ('application_start', 'student_deadline')):
        policy['submission_mode'] = 'reference'
    if refs('application_method') and candidate.get('application_method', {}).get('mode') == 'automatic':
        policy['submission_mode'] = 'automatic'
    if (candidate['resource_kind'] == 'tool_subscription'
            and any(r['actor'] == 'student' and r['stage'] == 'submission'
                    and re.search(r'個人相對期限|個人期限.*更早', r['summary']) for r in rules)):
        policy['submission_mode'] = 'conditional_deadline'
        policy['gaps'].append('personal_conditions_required')
    if any(r['kind'] == 'event_relative' for r in rules):
        policy['gaps'].append('needs_event_date')
        if schedule['relative_rule']['holiday_policy'] == 'next_working_day_unverified':
            policy['gaps'].append('calendar_unverified')
    if rules and not any(r['actor'] == 'student' and r['stage'] == 'submission' for r in rules):
        policy['gaps'].append('student_window_not_recorded')
    if policy['submission_mode'] == 'undetermined':
        policy['gaps'].append('time_not_projected')
    policy_validator().validate(policy)
    return policy
