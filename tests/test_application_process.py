"""Small public-source excerpts and clearly synthetic controls; no network or real approvals."""
from copy import deepcopy
import json
from pathlib import Path
import unittest
from scripts.application_process import infer_process, process_errors
from scripts.extract_candidates import extract_from_in_memory_blocks
from scripts.review_candidates import candidate_fingerprint, candidate_to_pilot_opportunity
from scripts.verify_candidates import verify_candidate

ROOT=Path(__file__).resolve().parents[1]


class ApplicationProcessTests(unittest.TestCase):
    def test_delivery_signing_and_na_cases(self):
        cases=json.loads((ROOT/'tests/fixtures/application-process-cases.json').read_text(encoding='utf-8'))
        for case in cases:
            with self.subTest(case=case['id']):
                method,app,_=infer_process([{'locator':str(i),'text':t} for i,t in enumerate(case['texts'])])
                self.assertEqual(method['mode'],case['mode'])
                self.assertEqual(method['paper_delivery'],case['paper'])
                if 'basis' in case:self.assertEqual(method['deadline_basis'],case['basis'])
                if 'signature' in case:self.assertEqual(method['handwritten_signature'],case['signature'])
                if 'na' in case:self.assertEqual(set(app),set(case['na']))

    def test_process_survives_candidate_pilot_and_hash_changes(self):
        source={'id':'sinica-phd-fellowship','url':'https://example.test/synthetic','title':'SYNTH程序測試','evidence_mode':'short_excerpt'}
        blocks=[{'locator':'id','text':'博士候選人，每月新臺幣43000元。'},
                {'locator':'process','text':'全程線上申請，無須遞交紙本。'}]
        cand=extract_from_in_memory_blocks(source,blocks,'e'*64,'2026-10-30T10:00:00+08:00',as_of='2026-10-30')[0]
        self.assertEqual(cand['application_method']['paper_delivery'],'not_required')
        exported=candidate_to_pilot_opportunity(cand)
        self.assertEqual(exported['application_method'],cand['application_method'])
        changed=deepcopy(cand);changed['application_method']['paper_delivery']='required'
        self.assertNotEqual(candidate_fingerprint(cand),candidate_fingerprint(changed))
        self.assertTrue(any('unsupported_application_method' in e for e in verify_candidate(changed,in_memory_blocks=blocks)['verification']['errors']))
        changed=deepcopy(cand)
        changed['field_applicability']={'result_date':{'status':'not_applicable','reason':'SYNTH無依據','refs':[{'source':source['id'],'locator':'process'}]}}
        self.assertIn('unsupported_not_applicable:result_date',verify_candidate(changed,in_memory_blocks=blocks)['verification']['errors'])

    def test_na_cannot_hide_a_date_or_required_qualification(self):
        record={'start':{'value':'2026-11-01'},'eligibility':{'candidate':{'mode':'required'}},'field_applicability':{
            'application_start':{'status':'not_applicable','reason':'SYNTH','refs':[{'source':'SYNTH','locator':'x'}]},
            'candidate_qualification':{'status':'not_applicable','reason':'SYNTH','refs':[]}}}
        self.assertIn('na_conflicts_with_value:application_start',process_errors(record))
        self.assertIn('na_conflicts_with_value:candidate_qualification',process_errors(record))
        self.assertIn('na_requires_evidence:candidate_qualification',process_errors(record))


if __name__=='__main__':unittest.main()
