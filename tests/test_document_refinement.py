"""Synthetic regressions for evidence-only second pass; no live source requests."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from scripts.expand_sources import initial_state
from scripts.refine_source_documents import headline,date_claims,refine
from tests.test_expansion import row,HTML

def block(text):return {'text':text,'locator':'SYNTH p1','kind':'paragraph'}

class RefinementTests(unittest.TestCase):
    def test_unique_heading_recovers_generic_site_title(self):
        p={'title':'電信所公告','blocks':[{'text':'SYNTH博士生獎學金申請公告','kind':'heading'}]}
        self.assertEqual(headline(p),'SYNTH博士生獎學金申請公告')
        p['blocks'].append({'text':'SYNTH研究生獎學金另一方案','kind':'heading'})
        self.assertEqual(headline(p),'電信所公告')

    def test_decimal_amount_support_does_not_match_decimal_tail(self):
        from scripts.verify_candidates import amount_supported
        self.assertTrue(amount_supported(25000,'獎學金2.5 萬元'))
        self.assertFalse(amount_supported(50000,'獎學金2.5萬元'))
        self.assertFalse(amount_supported(25000,'獎學金12.5萬元'))
        self.assertFalse(amount_supported(5000,'獎學金2.5萬元'))
        self.assertFalse(amount_supported(25000.5,'獎學金25000元'))
        self.assertTrue(amount_supported(25000.5,'獎學金25,000.5元'))
        self.assertTrue(amount_supported(25000,'獎學金兩萬五仟元'))
        self.assertFalse(amount_supported(5000,'獎學金兩萬五仟元'))

    def test_no_year_no_claim_and_age_or_purchase_not_window(self):
        for t in ['學生申請至7月1日截止','購買期間115年7月1日至8月1日','出生年齡須在115年7月1日前認定']:
            self.assertEqual(date_claims([block(t)],'rev'),[])

    def test_institution_result_and_policy_dates_are_not_student_deadlines(self):
        c=date_claims([block('申請機構應於115年7月1日彙送。')],'rev')[0]
        self.assertEqual(c['actor'],'institution');self.assertEqual(c['values'],['2026-07-01'])
        c=date_claims([block('115年9月1日公布結果。')],'rev')[0]
        self.assertEqual(c['kind'],'result_publication');self.assertEqual(c['actor'],'announcer')
        self.assertEqual(date_claims([block('115年6月1日修正。')],'rev')[0]['kind'],'policy_version')

    def test_since_publication_has_two_evidence_refs(self):
        p=('2026-06-01',block('公布日期115年6月1日'))
        c=date_claims([block('學生申請自即日起至115年7月1日截止。')],'rev',p)
        start=next(v for v in c if v['kind']=='application_start')
        self.assertEqual(start['values'],['2026-06-01']);self.assertIn('publication_ref',start)
        self.assertNotIn('excerpt',start)

    def test_manual_remains_blocked_and_resume_zero_network(self):
        r=row(access_gate='manual_or_policy_recheck');inv={'rows':[r]};state=initial_state(inv)
        with TemporaryDirectory() as tmp:
            p=Path(tmp)/'state.json'
            refine(inv,state,p,[r],transport=lambda *a:self.fail('manual fetched'))
            refine(inv,state,p,[r],transport=lambda *a:self.fail('resume fetched'))
        self.assertEqual(state['http_requests'],0)

    def test_rules_only_extracts_pending_hash_only_and_counts_requests(self):
        r=row();inv={'rows':[r]};state=initial_state(inv);calls=[]
        def get(url,headers,limit):
            calls.append(url)
            return {'status':404,'body':b'','headers':{}} if url.endswith('robots.txt') else {'status':200,'body':HTML,'headers':{'content-type':'text/html'}}
        with TemporaryDirectory() as tmp,patch('scripts.scan_sources.time.sleep'):
            refine(inv,state,Path(tmp)/'state.json',[r],transport=get)
        self.assertEqual(state['http_requests'],len(calls));self.assertEqual(state['model_calls'],0)
        c=next(iter(state['candidates'].values()))
        self.assertFalse(c['review']['promotion_ready'])
        self.assertTrue(all(e.get('excerpt') is None for e in c['field_evidence']))

if __name__=='__main__':unittest.main()
