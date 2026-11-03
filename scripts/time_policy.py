"""Read-only v1 adapter for evidenced legacy timing. No fetching or intake decisions."""
import json
import re
from functools import lru_cache
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker
from scripts.evaluate_deadlines import parse_iso_date, parse_taipei_datetime


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
