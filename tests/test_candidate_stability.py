"""Synthetic regression cases for the current batch; no network or human approvals."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from scripts.build_review_workspace import build_workspace
from scripts.evaluate_deadlines import evaluate_application_window, evaluate_eligibility, make_p1_profile
from scripts.extract_candidates import extract_from_in_memory_blocks
from scripts.review_candidates import candidate_fingerprint, candidate_to_pilot_opportunity, export_pr_candidate_draft
from scripts.verify_candidates import classify_review_gaps, verify_candidate

ROOT=Path(__file__).resolve().parents[1]
CONFIG=json.loads((ROOT/'data/scan-sources.json').read_text(encoding='utf-8'))
PILOT=json.loads((ROOT/'data/pilot.json').read_text(encoding='utf-8'))


def extract(sid, texts):
    source=next(s for s in CONFIG['sources'] if s['id']==sid)
    blocks=[{'locator':f'SYNTH-{i}','text':text} for i,text in enumerate(texts)]
    return extract_from_in_memory_blocks(source,blocks,'a'*64,'2026-10-31T12:00:00+08:00',
        as_of='2026-10-31',extraction_strategy='rules_only')[0],blocks


class CandidateStabilityTests(unittest.TestCase):
    def test_annual_calculation_is_one_benefit_and_duplicate_tampering_fails(self):
        cand,blocks=extract('nstc-abroad-dragon-rule',[
            'SYNTH 博士班在學學生。',
            '本項補助為部分補助性質，以一年補助新臺幣九十萬元為計算標準。應領補助公費計算方式為新臺幣九十萬元乘以國外研究日數除以三百六十五日。'])
        self.assertEqual(len(cand['benefit']['items']),1)
        self.assertEqual(cand['benefit']['items'][0]['unit'],'per_year')
        bad=deepcopy(cand)
        bad['benefit']['items'].append(deepcopy(bad['benefit']['items'][0]))
        bad['benefit']['items'][1]['unit']='lump_sum'
        self.assertIn('duplicate_benefit_claim:benefit.items/1',verify_candidate(bad)['verification']['errors'])

    def test_ta_monthly_ranges_keep_roles_and_summary_unit(self):
        cand,blocks=extract('ntu-ta-policy',['SYNTH 本辦法為教學助理制度規定。',
            '博士生每月新臺幣8,000至10,000元。碩士生每月新臺幣6,000至7,500元。'])
        self.assertEqual([b['branch_or_tier'] for b in cand['benefit']['items']],['博士班教學助理','碩士班教學助理'])
        self.assertNotIn('總額',cand['benefit']['summary'])
        bad=deepcopy(cand);bad['benefit']['summary']='總額新臺幣8,000至10,000元'
        self.assertIn('benefit_summary_period_conflicts_with_items',verify_candidate(bad,blocks)['verification']['errors'])

    def test_pdf_wrapped_role_and_ascii_semicolon_keep_all_three_ta_tiers(self):
        cand,blocks=extract('ntu-ta-policy',['SYNTH 本辦法為教學助理制度規定。',
            '博士生每月新臺幣8,000元至10,000元; 碩士生每月',
            '6,000元至7,500元;學士生每月4,000元至6,000元。'])
        self.assertEqual([i['branch_or_tier'] for i in cand['benefit']['items']],
            ['博士班教學助理','碩士班教學助理','學士班教學助理'])
        self.assertTrue(all(i['unit']=='per_month' for i in cand['benefit']['items']))
        self.assertEqual(cand['verification']['errors'],[])

    def test_temporary_staff_restriction_is_not_global_student_exclusion(self):
        cand,blocks=extract('nstc-assistant-rule',['SYNTH 本注意事項使研究人力約用有所依循。',
            '臨時工：臨時僱用且無專職工作之人員。非在職人員。',
            '學生兼任人員認定屬學習範疇者，支給研究津貼；僱傭關係者支給工作酬金，每月均應至少支給新臺幣六千元。'])
        self.assertEqual(cand['eligibility']['employment_status'],'unknown')
        self.assertFalse(cand['eligibility']['negated_conditions'])
        self.assertTrue(all(i['branch_or_tier'].startswith('學生兼任人員') for i in cand['benefit']['items']))
        bad=deepcopy(cand);bad['eligibility']['employment_status']='non_in_service_only'
        self.assertIn('multi_role_policy_cannot_have_global_employment_exclusion',verify_candidate(bad,blocks)['verification']['errors'])

    def test_college_filter_survives_conversion_and_excludes_medical_profile(self):
        cand,blocks=extract('ntu-eecs-scholarship',['SYNTH 電機資訊學院優秀博士生獎學金評選辦法。',
            '本院博士班學生每月新臺幣43000元。'])
        self.assertEqual(cand['institution_scope']['college'],'電機資訊學院')
        for item in (cand,candidate_to_pilot_opportunity(cand)):
            result=evaluate_eligibility(item,make_p1_profile())
            self.assertEqual(result['criteria'],'not_met')
            self.assertIn('學院不符',result['reasons'][0])
        changed=deepcopy(cand);changed['institution_scope']['college']='醫學院'
        self.assertNotEqual(candidate_fingerprint(cand),candidate_fingerprint(changed))

    def test_reference_na_does_not_claim_automatic_enrollment_or_missing_deadline_na(self):
        cand,blocks=extract('ntu-ta-policy',['SYNTH 本辦法為教學助理制度規定。'])
        self.assertEqual(cand['field_applicability']['student_deadline']['status'],'not_applicable')
        self.assertEqual(cand['application_method']['mode'],'unknown')
        window=evaluate_application_window(cand,'2026-10-31')
        self.assertEqual(window['reason_code'],'application_not_applicable')
        self.assertNotIn('免另行申請',window['reason'])
        dated,_=extract('ntu-ta-policy',['SYNTH 本辦法為教學助理制度規定。',
            '本次學生申請期間2026-10-01至2026-11-01截止。'])
        self.assertNotIn('student_deadline',dated['field_applicability'])
        recurring,_=extract('ntu-ta-policy',['SYNTH 本辦法為教學助理制度規定。',
            '學生申請期限每年六月一日至七月三十一日，當期公告另定。'])
        self.assertNotIn('student_deadline',recurring['field_applicability'])
        unknown,_=extract('ntu-eecs-scholarship',['SYNTH 博士班學生申請獎學金。'])
        self.assertNotIn('student_deadline',unknown['field_applicability'])

    def test_unparsed_identity_and_role_prevent_coverage_pass(self):
        cand,_=extract('ntu-ta-policy',['SYNTH 本辦法為教學助理制度規定。每月新臺幣8000元。'])
        self.assertEqual(cand['verification']['status'],'passed_with_gaps')
        self.assertIn('coverage_gap:benefit_role_not_extracted',cand['verification']['warnings'])
        self.assertIn('benefit_role_not_extracted',classify_review_gaps(cand)['source'])

    def test_same_opportunity_export_cannot_overwrite_another_document(self):
        cand,_=extract('ntu-ta-policy',['SYNTH 博士班教學助理每月新臺幣8000元。'])
        cand['review']['promotion_ready']=True
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError,'multiple document'):
                export_pr_candidate_draft({'candidates':[cand,deepcopy(cand)]},PILOT,Path(directory)/'proposal.json')

    def test_grouped_text_review_keeps_all_document_candidates(self):
        cand,_=extract('ntu-ta-policy',['SYNTH 本辦法為教學助理制度規定。'])
        second=deepcopy(cand);second['candidate_id']+='-other-document'
        bundle={'schema_version':'1.1.0-candidate','generated_at':'2026-10-31T12:00:00+08:00',
            'as_of':'2026-10-31','timezone':'Asia/Taipei','model_enabled':False,'model_calls':0,
            'official_data_modified':False,'candidates':[cand,second]}
        with tempfile.TemporaryDirectory() as directory:
            build_workspace(bundle,PILOT,CONFIG,Path(directory)/'review')
            text=(Path(directory)/'review/review-text.md').read_text(encoding='utf-8')
            self.assertIn('2 筆文件候選／1 組方案',text)
            self.assertIn(second['candidate_id'],text)


if __name__=='__main__':unittest.main()
