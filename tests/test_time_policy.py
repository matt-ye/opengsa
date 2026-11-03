"""Temporal projections from the stored snapshot; synthetic mutations stay local."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from jsonschema import ValidationError
from scripts.radar_metadata import radar_metadata
from scripts.time_policy import policy_validator, project_time_policy

ROOT = Path(__file__).resolve().parents[1]


class TimePolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundle = json.loads((ROOT/'data/candidates/source-review.json').read_text(encoding='utf-8'))

    def candidate(self, source_id):
        return deepcopy(next(c for c in self.bundle['candidates'] if c['source_metadata']['source_id'] == source_id))

    def test_all_64_project_without_mutation_or_intake_state_changes(self):
        before = deepcopy(self.bundle)
        records = radar_metadata(self.bundle)['records']
        self.assertEqual(len(records), 64)
        for candidate in self.bundle['candidates']:
            policy = records[candidate['candidate_id']]['time_policy']
            policy_validator().validate(policy)
            for rule in policy['rules']:
                self.assertTrue(all(r['revision_id'] == candidate['source_metadata']['revision_id'] for r in rule['source_refs']))
        self.assertEqual(self.bundle, before)

    def test_agency_and_supplement_evidence_never_become_student_deadline(self):
        c = self.candidate('nstc-conference-rule')
        policy = project_time_policy(c)
        self.assertEqual(policy['submission_mode'], 'event_relative')
        self.assertEqual([r['actor'] for r in policy['rules']], ['institution', 'supplement'])
        self.assertTrue(all(r['value'] is None for r in policy['rules']))
        self.assertIn('student_window_not_recorded', policy['gaps'])
        self.assertIn('calendar_unverified', policy['gaps'])

    def test_recurring_month_days_are_preserved_without_inventing_a_year(self):
        c = self.candidate('nstc-abroad-dragon-rule')
        policy = project_time_policy(c)
        self.assertEqual(policy['submission_mode'], 'recurring')
        self.assertTrue(all(r['value'] is None for r in policy['rules']))
        self.assertEqual(policy['rules'][0]['actor'], 'institution')
        self.assertIn('六月一日', policy['rules'][0]['summary'])

    def test_current_revision_and_exact_field_evidence_are_required(self):
        c = self.candidate('faos-student-conference')
        c['title'] = 'SYNTH stale revision'
        c['source_metadata']['revision_id'] = '0'*64
        self.assertEqual(project_time_policy(c)['rules'], [])
        c = self.candidate('faos-student-conference')
        c['title'] = 'SYNTH unrelated evidence'
        for evidence in c['field_evidence']:
            if evidence['field_path'].startswith('schedule.'):
                evidence['field_path'] = 'benefit'
        self.assertEqual(project_time_policy(c)['rules'], [])

    def test_no_rolling_claim_from_review_wording_missing_date_or_unsafe_source(self):
        c = deepcopy(self.bundle['candidates'][0])
        c['title'] = 'SYNTH 隨到隨審，全年申請'
        c['field_evidence'] = []
        self.assertEqual(project_time_policy(c)['submission_mode'], 'undetermined')
        self.assertEqual(project_time_policy(c)['review_mode'], 'not_stated')
        unsafe = project_time_policy(self.candidate('faos-student-conference'), unsafe=True)
        self.assertEqual(unsafe['rules'], [])
        self.assertEqual(unsafe['gaps'], ['source_checks_failed'])
        c = self.candidate('faos-student-conference')
        c['verification']['checks']['evidence_supported'] = False
        self.assertEqual(project_time_policy(c)['rules'], [])

    def test_tool_deadline_conditions_are_not_added_to_every_tool_resource(self):
        c = self.candidate('taipei-ai-tools')
        self.assertEqual(project_time_policy(c)['submission_mode'], 'conditional_deadline')
        c['title'] = 'SYNTH simple tool expiry'
        c['schedule']['steps'][0]['deadline']['note'] = '明確申請截止'
        self.assertEqual(project_time_policy(c)['submission_mode'], 'deadline_only')
        c['schedule']['steps'][0]['deadline']['value'] = '2026-02-30'
        with self.assertRaises(ValueError):
            project_time_policy(c)

    def test_contract_rejects_calendar_dates_fabricated_for_relative_rules(self):
        candidate = self.candidate('faos-student-conference')
        candidate['title'] = 'SYNTH unsupported relative operator'
        candidate['schedule']['relative_rule']['rule_type'] = 'none'
        candidate['schedule']['relative_rule']['anchor_event'] = None
        fallback = project_time_policy(candidate)
        self.assertEqual(fallback['submission_mode'], 'rule_text')
        self.assertEqual(fallback['rules'][0]['kind'], 'text_rule')
        self.assertIsNone(fallback['rules'][0]['value'])
        policy = project_time_policy(self.candidate('faos-student-conference'))
        policy['rules'][0]['value'] = '2027-01-01'
        with self.assertRaises(ValidationError):
            policy_validator().validate(policy)


if __name__ == '__main__':
    unittest.main()
