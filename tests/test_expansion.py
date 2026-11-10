"""Synthetic extraction, permission, cost accounting and resume regressions."""
from io import BytesIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
import zipfile
from scripts.expand_sources import initial_state,run_batch,export_report,office_blocks,prepare_response,named_candidate,profile_for
from scripts.scan_sources import ScanError

def setUpModule():
    # 假網站不用等同站間隔（每站 3 秒）；間隔規則本身由 test_scanner 檢查。
    import unittest.mock
    from scripts import scan_sources
    patcher = unittest.mock.patch.object(scan_sources, "pause", lambda seconds: None)
    patcher.start()
    unittest.addModuleCleanup(patcher.stop)


def row(n=1,**extra):
    return {'id':'SYNTH-'+str(n),'url':'https://example.test/call'+str(n),'title':'SYNTH獎學金','batch':'B1','category':'doctoral',
            'access_gate':'fresh_policy_and_profile_check_required','restrictions':[],**extra}
HTML=('<main><h1>SYNTH優秀研究獎學金</h1><p>申請資格：現正就讀博士班之在學學生，須具研究成果並經所屬系所推薦。</p>'
      '<p>學生申請期間：115年6月1日至115年7月31日。</p><p>'+('SYNTH補助辦法及說明。'*20)+'</p>'
      '<a href="/rule.pdf">申請辦法</a></main>').encode()

class ExpansionTests(unittest.TestCase):
    def transport(self,calls,fail=False):
        def get(url,headers,limit):
            calls.append(url)
            if url.endswith('robots.txt'):return {'status':404,'body':b'','headers':{}}
            if fail:return {'status':403,'body':b'','headers':{}}
            if url.endswith('rule.pdf'):return {'status':200,'body':b'UNSUPPORTED SYNTH','headers':{'content-type':'text/plain'}}
            return {'status':200,'body':HTML,'headers':{'content-type':'text/html'}}
        return get

    def test_full_pipeline_resumes_without_network_and_keeps_pending(self):
        inv={'rows':[row()]};state=initial_state(inv);calls=[]
        with TemporaryDirectory() as tmp,patch('scripts.scan_sources.time.sleep'):
            path=Path(tmp)/'state.json';run_batch(inv,state,'B1',path,{'sources':[]},transport=self.transport(calls))
            self.assertEqual(len(state['candidates']),1)
            cand=next(iter(state['candidates'].values()))
            self.assertEqual(cand['eligibility']['institution'],'unknown')
            self.assertEqual(cand['participants']['applicant'],'unknown')
            self.assertFalse(cand['review']['promotion_ready']);self.assertIsNone(cand['review']['independent_reviewer'])
            self.assertTrue(all(e.get('excerpt') is None for e in cand['field_evidence']))
            count=len(calls)
            run_batch(inv,state,'B1',path,{'sources':[]},transport=lambda *a: self.fail('resume fetched'))
            self.assertEqual(count,len(calls));self.assertEqual(state['http_requests'],count)
            summary=export_report(inv,state,Path(tmp)/'report')
            self.assertEqual(summary['candidate_count'],1);self.assertEqual(summary['model_calls'],0)
            self.assertNotIn('SYNTH補助辦法及說明。'*2,path.read_text(encoding='utf-8'))

    def test_manual_gate_and_paused_host_never_fetch(self):
        inv={'rows':[row(access_gate='manual_or_policy_recheck'),row(2)]};state=initial_state(inv)
        state['host_pauses']['example.test']='robots_not_plain_rules'
        with TemporaryDirectory() as tmp:
            run_batch(inv,state,'B1',Path(tmp)/'state.json',{'sources':[]},transport=lambda *a:self.fail('blocked GET'))
        self.assertEqual({r['status'] for r in state['records'].values()},{'manual_only','host_paused'})

    def test_403_pauses_other_urls_no_repeat(self):
        inv={'rows':[row(),row(2)]};state=initial_state(inv);calls=[]
        with TemporaryDirectory() as tmp,patch('scripts.scan_sources.time.sleep'):
            run_batch(inv,state,'B1',Path(tmp)/'state.json',{'sources':[]},transport=self.transport(calls,True))
        self.assertEqual(len(calls),2);self.assertEqual(state['records'][row(2)['url']]['status'],'host_paused')

    def test_budget_and_interrupted_attempt_reserved_before_transport(self):
        inv={'rows':[row()]};state=initial_state(inv,1199)
        with TemporaryDirectory() as tmp:
            path=Path(tmp)/'state.json'
            def interrupted(*args):
                self.assertEqual(json.loads(path.read_text(encoding='utf-8'))['http_requests'],1200)
                raise ScanError('transport_error')
            run_batch(inv,state,'B1',path,{'sources':[]},transport=interrupted)
            self.assertEqual(state['http_requests'],1200)

    def test_b0_office_formats_are_in_memory_and_external_entities_rejected(self):
        def zipped(name,text):
            out=BytesIO()
            with zipfile.ZipFile(out,'w') as z:z.writestr(name,text)
            return out.getvalue()
        xml='<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:p><w:r><w:t>SYNTH博士</w:t></w:r><w:r><w:t>班學生</w:t></w:r></w:p></w:document>'
        blocks=office_blocks(zipped('word/document.xml',xml),'docx')
        self.assertEqual(blocks[0]['text'],'SYNTH博士班學生')
        odt='<office:document xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0"><text:p>SYNTH研究生</text:p></office:document>'
        self.assertEqual(office_blocks(zipped('content.xml',odt),'odt')[0]['text'],'SYNTH研究生')
        with self.assertRaisesRegex(ScanError,'entities_rejected'):office_blocks(zipped('word/document.xml','<!DOCTYPE x>'+xml),'docx')

    def test_login_and_generic_index_do_not_create_scholarship(self):
        response={'url':row()['url'],'body':b'<main><input type=password></main>','headers':{'content-type':'text/html'}}
        with self.assertRaisesRegex(ScanError,'login_form'):prepare_response(response,{},['example.test'])
        self.assertFalse(named_candidate(row(),{'title':'獎學金','blocks':[{'text':'SYNTH博士班學生','locator':'p'}],'kind':'html'},None))
        for title in ['獎助學金申請辦法','博士生獎學金說明會影片','博士生獎學金發放訊息']:
            self.assertFalse(named_candidate(row(),{'title':title,'blocks':[{'text':'申請資格：博士班學生','locator':'p'}],'kind':'html'},None))

    def test_inventory_change_cannot_silently_reuse_state(self):
        state=initial_state({'rows':[row()]})
        with TemporaryDirectory() as tmp,self.assertRaisesRegex(ValueError,'inventory_changed'):
            run_batch({'rows':[row(2)]},state,'B1',Path(tmp)/'state.json',{'sources':[]})

    def test_invalid_preflight_does_not_relax_budget(self):
        with self.assertRaises(ValueError):initial_state({'rows':[]},-1)

    def test_source_routing_does_not_make_foundation_phd_only(self):
        p=profile_for(row(category='foundation'),{'title':'SYNTH人才獎學金'},None)
        self.assertEqual(p['category'],'living_tuition');self.assertNotIn('degrees',p)
        p=profile_for(row(),{'title':'SYNTH補助博士生赴國外研究'},None)
        self.assertEqual(p['category'],'overseas_research')

    def test_title_drops_site_name_and_notice_wrapping_but_keeps_the_deadline(self):
        for title,expected in (('【獎學金】115-1 甲同鄉會獎學金(截止日11/30)  - 國立某大學學務處生活輔導組','115-1 甲同鄉會獎學金(截止日11/30)'),
                ('轉知乙獎助學金資訊(2026)  - 國立某大學學生事務處','乙獎助學金資訊(2026)'),('公告「丙獎助學金」','丙獎助學金'),('轉知「己獎學金試辦方案」相關訊息','己獎學金試辦方案'),
                ('【生輔組公告】丁獎學金','丁獎學金'),('【戊基金會】115年戊獎學金','【戊基金會】115年戊獎學金')):
            with self.subTest(title=title):
                self.assertEqual(profile_for(row(),{'title':title},None)['title'],expected)
        self.assertEqual(profile_for(row(),{'title':'甲系學生出國研修獎勵'},None)['category'],'overseas_research')

    def test_plain_scholarship_is_not_filed_under_phd(self):
        for title,expected in (('SYNTH清寒獎學金','living_tuition'),('SYNTH碩博士獎學金','living_tuition'),('SYNTH博士後研究獎助','living_tuition'),
                ('SYNTH學生急難救助','living_emergency'),('SYNTH博士生獎學金','phd_research'),('SYNTH PhD Fellowship','phd_research')):
            with self.subTest(title=title):
                self.assertEqual(profile_for(row(category='scholarship'),{'title':title},None)['category'],expected)
