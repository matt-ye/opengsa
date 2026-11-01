"""Synthetic tests of original-source audit boundaries and public document preparation."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from scripts.expand_sources import initial_state
from scripts.verify_original_sources import prepare_public,classify,verify_all,parser_hash,quarantine_unproven
from scripts.scan_sources import ScanError
from tests.test_expansion import row,HTML

class OriginalVerificationTests(unittest.TestCase):
    def response(self,html=HTML):return {'status':200,'url':row()['url'],'body':html,'headers':{'content-type':'text/html'}}

    def test_public_article_outside_login_widget_is_readable_without_auth(self):
        html=HTML+b'<form><input type=password><button>Login</button></form>'
        p=prepare_public(self.response(html),['example.test'])
        self.assertTrue(p['login_widget_removed']);self.assertTrue(p['blocks'])
        with self.assertRaisesRegex(ScanError,'login_form'):
            prepare_public(self.response(b'<form><input type=password><p>PRIVATE SYNTH</p></form>'),['example.test'])

    def test_empty_article_does_not_hide_readable_main(self):
        p=prepare_public(self.response(b'<article></article>'+HTML),['example.test'])
        self.assertEqual(p['selected_root'],'main')

    def test_labeled_table_title_overrides_generic_heading_and_attachment_title(self):
        html=('<body><h1>電信所公告</h1><table><tr><td>公告標題：</td><td>SYNTH115學年度博士生獎學金申請公告</td></tr></table>'
            '<h4>附件3-研究生校長獎CV範例</h4><p>'+('SYNTH在學博士生可依規定申請。'*12)+'</p></body>').encode()
        p=prepare_public(self.response(html),['example.test'])
        self.assertEqual(p['title'],'SYNTH115學年度博士生獎學金申請公告')

    def test_named_call_can_keep_unknown_eligibility_but_index_cannot_be_card(self):
        p=prepare_public(self.response(),['example.test'])
        self.assertTrue(classify(row(),p)[1])
        p['title']='獎學金資訊';self.assertFalse(classify(row(),p)[1])
        p['title']='SYNTH博士生獎學金說明會';self.assertFalse(classify(row(),p)[1])
        p['title']='SYNTH企業跨域研發補助';self.assertFalse(classify(row(),p)[1])
        for title in ['附件3-研究生校長獎受獎生CV範例','優秀學生出國開會申請補助線上登記表','租屋補助方案報您知']:
            p['title']=title;self.assertFalse(classify(row(),p)[1])

    def test_mixed_numeric_units_and_separate_monthly_clause(self):
        from scripts.extract_candidates import parse_amount_from_text
        from scripts.verify_candidates import amount_supported
        value=parse_amount_from_text('訓練費最高10萬元，每月另有8千元學習獎勵。')
        self.assertEqual(value['amount_max'],100000);self.assertIsNone(value['amount_min'])
        self.assertNotEqual(value['unit'],'per_month');self.assertTrue(amount_supported(8000,'8千元'))

    def test_unknown_date_quarantine_preserves_identity_and_rechecks_application(self):
        from scripts.expand_sources import profile_for
        from scripts.extract_candidates import extract_from_in_memory_blocks
        from scripts.document_ir import prepare_document
        p=prepare_public(self.response(),['example.test']);profile=profile_for(row(),p,None)
        blocks=prepare_document(p['blocks'])['units']
        c=extract_from_in_memory_blocks(profile,p['blocks'],'a'*64,'2026-11-02',as_of='2026-11-02',extraction_strategy='rules_only')[0]
        index=next(i for i,s in enumerate(c['schedule']['steps']) if s['deadline']['kind']!='unknown')
        c['verification']['errors']=['hallucinated_date_not_in_source:schedule.steps/'+str(index)+'/deadline:2099-01-01']
        c['schedule']['steps'][index]['deadline']['value']='2099-01-01'
        identity=c['eligibility']['identity']['text'];c['application']['state']='open'
        fixed,fields=quarantine_unproven(c,blocks)
        self.assertTrue(fields);self.assertIsNone(fixed['schedule']['steps'][index]['deadline']['value'])
        self.assertEqual(identity,fixed['eligibility']['identity']['text']);self.assertNotEqual(fixed['application']['state'],'open')

    def test_global_tools_do_not_receive_municipal_tier_requirements(self):
        from scripts.expand_sources import profile_for
        from scripts.extract_candidates import extract_from_in_memory_blocks
        p=prepare_public(self.response(),['example.test']);profile=profile_for(row(),p,None)
        profile.update(category='research_tools',resource_kind='tool_subscription')
        c=extract_from_in_memory_blocks(profile,p['blocks'],'a'*64,'2026-11-02',as_of='2026-11-02',extraction_strategy='rules_only')[0]
        self.assertFalse(any('ai_tools:' in e for e in c['verification']['errors']+c['verification']['warnings']))
        self.assertEqual(c['participants']['beneficiary'],'unknown')

    def test_manual_gate_and_out_of_scope_do_not_fetch_or_claim_content(self):
        rs=[row(access_gate='manual_or_policy_recheck'),row(2,batch='H'),row(3,batch='X')];inv={'rows':rs};state=initial_state(inv)
        audit={'parser_sha256':parser_hash(),'records':{},'candidates':{},'profiles':{},'redirect_observations':[]}
        with TemporaryDirectory() as tmp:
            verify_all(inv,state,audit,Path(tmp)/'audit',Path(tmp)/'budget',{'sources':[]},transport=lambda *a:self.fail('blocked fetched'))
        self.assertEqual(len(audit['records']),3);self.assertFalse(any(r['content_verified'] for r in audit['records'].values()))

    def test_live_path_is_hash_only_pending_and_resume_uses_no_network(self):
        inv={'rows':[row()]};state=initial_state(inv);calls=[]
        audit={'parser_sha256':parser_hash(),'records':{},'candidates':{},'profiles':{},'redirect_observations':[]}
        def get(url,headers,limit):
            calls.append(url)
            return {'status':404,'body':b'','headers':{}} if url.endswith('robots.txt') else self.response()
        with TemporaryDirectory() as tmp,patch('scripts.scan_sources.time.sleep'):
            a=Path(tmp)/'audit';b=Path(tmp)/'budget'
            verify_all(inv,state,audit,a,b,{'sources':[]},transport=get)
            verify_all(inv,state,audit,a,b,{'sources':[]},transport=lambda *a:self.fail('resume fetched'))
        self.assertEqual(state['http_requests'],len(calls));self.assertTrue(audit['records'][row()['id']]['card_ready'])
        c=next(iter(audit['candidates'].values()))
        self.assertFalse(c['review']['promotion_ready']);self.assertTrue(all(e.get('excerpt') is None for e in c['field_evidence']))

if __name__=='__main__':unittest.main()
