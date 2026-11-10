"""Proposals must be traceable and readable without modifying or approving the base."""
from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from scripts.propose_radar_update import ROOT,distinct_named_cards,prepare,same_program,split_site_ready,write_proposal,read
from scripts.expand_sources import prepare_response,profile_for
from scripts.extract_candidates import extract_from_in_memory_blocks
from scripts.scan_sources import digest
from scripts.audit_sources import canonical_url
from tests.test_expansion import HTML,row

def setUpModule():
    # 假網站不用等同站間隔（每站 3 秒）；間隔規則本身由 test_scanner 檢查。
    import unittest.mock
    from scripts import scan_sources
    patcher = unittest.mock.patch.object(scan_sources, "pause", lambda seconds: None)
    patcher.start()
    unittest.addModuleCleanup(patcher.stop)


class RadarProposalTests(unittest.TestCase):
    def setUp(self):
        # 正式資料的手寫卡會撤光：讀手寫基準時多標一張「網址只對應這張卡」的流程卡當素材，不寫檔。
        baseline=read(ROOT/'data/known-hand-authored-candidates.json')
        # 不從 source-review 挑：來源鏈索引綁著它的雜湊，撤掉其中一張會讓索引對不上。
        index_file=read(ROOT/'data/source-chain-index.json')['candidate_file']
        cards=[c for path in sorted((ROOT/'data/candidates').glob('*.json')) if not str(path).replace('\\','/').endswith(index_file)
               for c in read(path)['candidates']]
        urls=[canonical_url(c['source_metadata']['url']) for c in cards]
        extra=next(c for c in cards if urls.count(canonical_url(c['source_metadata']['url']))==1)
        self.known=baseline['candidate_ids']+[extra['candidate_id']]
        marked={**baseline,'candidate_ids':self.known}
        original=read
        def reader(path):
            return deepcopy(marked) if str(path).replace('\\','/').endswith('data/known-hand-authored-candidates.json') else original(path)
        stub=patch('scripts.propose_radar_update.read',reader);stub.start();self.addCleanup(stub.stop)

    def fixture(self):
        response={'url':row()['url'],'body':HTML,'headers':{'content-type':'text/html'}}
        prep=prepare_response(response,{},['example.test']);profile=profile_for(row(),prep,None)
        cs=extract_from_in_memory_blocks(profile,prep['blocks'],'a'*64,'2026-11-01T00:00:00+00:00',as_of='2026-11-01',extraction_strategy='rules_only')
        bundle={'schema_version':'1.1.0-candidate','generated_at':'2026-11-01T00:00:00+00:00','as_of':'2026-11-01',
            'timezone':'Asia/Taipei','model_enabled':False,'model_calls':0,'official_data_modified':False,'candidates':cs}
        config=read(ROOT/'data/scan-sources.json');config['sources'].append(profile)
        config['allowed_hosts'].append('example.test')
        return bundle,config,profile

    def test_new_candidate_keeps_originals_and_is_not_enabled_for_schedule(self):
        bundle,config,profile=self.fixture();before=(ROOT/'data/candidates/source-review.json').read_bytes()
        files,summary=prepare(bundle,config)
        self.assertEqual(summary['proposed_candidates'],len(json.loads(before)['candidates'])+1);self.assertEqual(summary['human_approvals'],0)
        self.assertFalse(next(p for p in files['data/scan-sources.json']['sources'] if p['id']==profile['id'])['enabled'])
        self.assertEqual(before,(ROOT/'data/candidates/source-review.json').read_bytes())
        self.assertIn('data/source-chain-batches/radar-proposal-snapshots.json',files)

    def test_new_source_on_an_approved_host_joins_the_schedule(self):
        # 網域已在 allowed_hosts（維護者核可過）的新來源直接排入巡檢；上一個測試的 example.test 是新網域，維持停用。
        bundle,config,profile=self.fixture()
        approved=read(ROOT/'data/scan-sources.json')
        with patch('scripts.propose_radar_update.read',lambda path:{**approved,'allowed_hosts':approved['allowed_hosts']+['example.test']}
                   if str(path).replace('\\','/').endswith('data/scan-sources.json') else read(path)):
            files,_=prepare(bundle,config)
        self.assertTrue(next(p for p in files['data/scan-sources.json']['sources'] if p['id']==profile['id'])['enabled'])

    def test_readable_preview_and_patch_created_offline(self):
        bundle,config,_=self.fixture()
        with TemporaryDirectory() as tmp:
            output=Path(tmp)/'proposal';summary=write_proposal(bundle,config,output)
            self.assertTrue((output/'preview/candidate-preview.html').exists())
            self.assertTrue((output/'data-pr.patch').read_text(encoding='utf-8').startswith('--- a/data/'))
            self.assertFalse(summary['published'])

    def test_proposal_keeps_committed_diagrams_in_step_with_its_data(self):
        from scripts.export_source_chain_graph import export
        bundle,config,_=self.fixture()
        with TemporaryDirectory() as tmp:
            output=Path(tmp)/'proposal';write_proposal(bundle,config,output,preview=False)
            repo=output/'repo'
            def overlay(path):return read(repo/path if (repo/path).exists() else ROOT/path)
            expected=Path(tmp)/'expected';export(expected,overlay('data/source-chain-index.json'),reader=overlay)
            for name in ('source-chain-map.html','source-chain-map.canvas'):
                self.assertEqual((repo/'docs/source-chains'/name).read_text(encoding='utf-8'),(expected/name).read_text(encoding='utf-8'))

    def hand_url(self,programs):
        known=set(self.known);at={}
        for path in (ROOT/'data/candidates').glob('*.json'):
            for card in read(path)['candidates']:
                if card['candidate_id'] in known:at.setdefault(canonical_url(card['source_metadata']['url']),[]).append(card)
        return next((url,cards) for url,cards in sorted(at.items()) if len({c['program_key'] for c in cards})==programs)

    def test_new_card_retires_the_hand_card_on_the_same_url(self):
        url,cards=self.hand_url(1);bundle,config,_=self.fixture()
        bundle['candidates'][0]['title']=cards[0]['title']
        files,summary=prepare(bundle,config,replaced_urls=[url])
        self.assertEqual({r['candidate_id'] for r in summary['retired_hand_cards']},{c['candidate_id'] for c in cards})
        self.assertEqual(summary['needs_manual_retire'],[])
        baseline=files['data/known-hand-authored-candidates.json']['candidate_ids']
        self.assertFalse({c['candidate_id'] for c in cards}&set(baseline))
        self.assertEqual(len(baseline),len(self.known)-len(cards))
        bundle_path=summary['retired_hand_cards'][0]['bundle']
        self.assertNotIn(cards[0]['candidate_id'],[c['candidate_id'] for c in files[bundle_path]['candidates']])
        self.assertEqual(len(files[bundle_path]['candidates']),len(read(ROOT/bundle_path)['candidates'])-len(cards))

    def test_card_breaking_the_site_contract_is_withheld_and_the_rest_continue(self):
        bundle,config,_=self.fixture()
        good=bundle['candidates'][0];bad=deepcopy(good);bad['candidate_id']='cand-bad'
        from scripts.build_review_workspace import candidate_preview_data
        def fussy(data,*args):
            if data['candidates'][0]['candidate_id']=='cand-bad':raise ValueError('contract')
            return candidate_preview_data(data,*args)
        with patch('scripts.build_review_workspace.candidate_preview_data',fussy):
            ready,withheld=split_site_ready([good,bad],bundle,config)
        self.assertEqual([c['candidate_id'] for c in ready],[good['candidate_id']])
        self.assertEqual([r['candidate_id'] for r in withheld],['cand-bad'])

    def test_year_range_without_a_base_date_still_fits_the_site_contract(self):
        bundle,config,_=self.fixture()
        card=bundle['candidates'][0]
        card['eligibility']['year_limit']={'mode':'range','min':1,'max':3,'assessed_at':None,'refs':deepcopy(card['eligibility']['identity']['refs'])}
        ready,withheld=split_site_ready([card],bundle,config)
        self.assertEqual((len(ready),withheld),(1,[]))

    def test_same_program_retires_the_hand_card_even_when_the_old_url_is_wrong(self):
        url,cards=self.hand_url(1);bundle,config,_=self.fixture()
        bundle['candidates'][0]['title']=cards[0]['title']
        _,summary=prepare(bundle,config)
        self.assertEqual({r['candidate_id'] for r in summary['retired_hand_cards']},{c['candidate_id'] for c in cards})

    def card(self,title,url):
        return {'candidate_id':title+url,'title':title,'source_metadata':{'url':url}}

    def test_same_document_and_same_title_become_one_card_and_are_listed(self):
        kept,dropped=distinct_named_cards([self.card('甲獎學金表格','https://a.test/x.pdf'),self.card('甲獎學金','https://a.test/p'),
            self.card('乙獎學金','https://a.test/p'),self.card('甲獎學金','https://a.test/form.pdf'),self.card('甲獎學金','https://b.test/p')])
        self.assertEqual({(c['title'],c['source_metadata']['url']) for c in kept},{('甲獎學金','https://a.test/p'),('甲獎學金表格','https://a.test/x.pdf'),('甲獎學金','https://b.test/p')})
        self.assertEqual(sorted(r['reason'] for r in dropped),['same_document','same_title_same_site'])

    def test_listing_page_title_is_not_a_program_name(self):
        for title in ('校內獎助學金一覽表  - 國立某大學','獎助學金資訊網','研究生獎助學金','校內獎學金','└ 校外獎助學金 ┘','某大學 學生事務處 | 獎助學金公告','::: 校內獎學金'):
            with self.subTest(title=title):
                self.assertEqual(distinct_named_cards([self.card(title,'https://a.test/x')])[1][0]['reason'],'generic_title')
        for title in ('國立中興大學研究生獎助學金辦法','葉文冠教授紀念獎學金','115學年度校內獎學金申請公告'):
            with self.subTest(title=title):
                self.assertEqual(distinct_named_cards([self.card(title,'https://a.test/x')])[1],[])

    def test_clause_testimonial_and_form_documents_are_not_cards(self):
        for title,url in (('七、本辦法如有未盡事宜處，由本會解釋之。','https://a.test/x'),('某宗親會獎助學金（獲奬人感言）','https://a.test/x'),
                ('其他獎學金設置要點','https://a.test/x'),('長庚大學-長庚中文站台-獎助學金','https://a.test/x'),('申請獎學金','https://a.test/x'),
                ('短期獎學金','https://a.test/2026/shinsehyo_list1.pdf'),('短期獎學金','https://a.test/8.houkokusho_list5.pdf'),('甲獎學金流程','https://a.test/x'),('甲要點修正對照表','https://a.test/x'),('甲獎學金','https://a.test/%E7%94%B3%E8%AB%8B%E8%A1%A8.pdf')):
            with self.subTest(title=title):
                self.assertEqual(distinct_named_cards([self.card(title,url)])[0],[])

    def test_different_program_on_the_same_url_is_left_for_a_person(self):
        url,cards=self.hand_url(1);bundle,config,_=self.fixture()
        files,summary=prepare(bundle,config,replaced_urls=[url])
        self.assertEqual(summary['retired_hand_cards'],[])
        self.assertEqual({r['candidate_id'] for r in summary['needs_manual_retire']},{c['candidate_id'] for c in cards})
        self.assertNotIn('data/known-hand-authored-candidates.json',files)

    def test_same_program_needs_a_real_title_match(self):
        self.assertTrue(same_program('Google PhD fellowship program','Google PhD Fellowship Program (East Asia / Taiwan)'))
        self.assertFalse(same_program('國立中山大學學生急難救助金','中山大學西灣優秀學生與研究生卓越獎學金'))
        self.assertFalse(same_program('獎學金','財團法人某基金會獎學金'))

    def test_same_url_but_another_program_is_left_for_a_person(self):
        # 同網址不代表同方案（同校首頁可能有急難金和獎學金）：標題認不出是同一方案就不刪。
        url,cards=self.hand_url(1);bundle,config,_=self.fixture()
        self.assertFalse(any(same_program(c['title'],new['title']) for c in cards for new in bundle['candidates']))
        files,summary=prepare(bundle,config,replaced_urls=[url])
        self.assertEqual(summary['retired_hand_cards'],[])
        self.assertEqual({r['candidate_id'] for r in summary['needs_manual_retire']},{c['candidate_id'] for c in cards})
        self.assertNotIn('data/known-hand-authored-candidates.json',files)

    def test_no_accepted_card_retires_nothing(self):
        url,_=self.hand_url(1);bundle,config,_=self.fixture()
        bundle['candidates'][0]['verification']['status']='failed_automated_checks'
        _,summary=prepare(bundle,config,replaced_urls=[url])
        self.assertEqual(summary['retired_hand_cards'],[])

    def test_failed_checks_withheld_and_approval_claim_rejected(self):
        bundle,config,_=self.fixture();bundle['candidates'][0]['verification']['status']='failed_automated_checks'
        files,summary=prepare(bundle,config);self.assertEqual(files['data/candidates/source-review.json']['candidates'],read(ROOT/'data/candidates/source-review.json')['candidates'])
        bundle,config,_=self.fixture();bundle['candidates'][0]['review']['promotion_ready']=True
        with self.assertRaises(ValueError):prepare(bundle,config)

    def test_manual_scan_usage_is_not_relabelled_as_zero_model_calls(self):
        bundle,config,_=self.fixture();bundle.update(model_enabled=True,model_calls=1)
        files,_=prepare(bundle,config)
        merged=files['data/candidates/source-review.json']
        self.assertTrue(merged['model_enabled']);self.assertEqual(merged['model_calls'],1)

    def test_new_revision_cannot_reuse_old_chain_events_or_dependent_rules(self):
        base=read(ROOT/'data/candidates/source-review.json')
        from scripts.export_source_chain_graph import load_graph
        graph=load_graph();rule_docs={ref['document_id'] for p in graph['programs'] for r in p['rules'] for ref in r['evidence_refs']}
        urls={d['url'] for d in graph['documents'].values() if d['id'] in rule_docs and d['status'] in ('changed','unchanged','unchanged_304')}
        c=deepcopy(next(c for c in base['candidates'] if c['source_metadata']['url'] in urls))
        old=c['source_metadata']['revision_id'];new='b'*64
        c['candidate_id']='SYNTH-revision';c['source_metadata']['revision_id']=new
        for e in c['field_evidence']:
            if e.get('revision_id')==old:e['revision_id']=new
        base['candidates']=[c]
        files,summary=prepare(base,read(ROOT/'data/scan-sources.json'))
        self.assertTrue(summary['invalidated_timeline_documents'])
        index=files['data/source-chain-index.json']
        bad=set(summary['invalidated_timeline_documents'])
        self.assertFalse(any(ref['document_id'] in bad for p in index['programs'] for r in p['rules'] for ref in r['evidence_refs']))

    def test_same_bytes_allow_explicit_revision_rebinding_without_new_dates(self):
        base=read(ROOT/'data/candidates/source-review.json');index=read(ROOT/'data/source-chain-index.json')
        from scripts.export_source_chain_graph import load_graph
        docs=[d for d in load_graph()['documents'].values() if d.get('raw_sha256') and d['status'] in ('changed','unchanged','unchanged_304')]
        c=deepcopy(next(c for c in base['candidates'] if any(d['url']==c['source_metadata']['url'] for d in docs)))
        doc=next(d for d in docs if d['url']==c['source_metadata']['url']);old=c['source_metadata']['revision_id'];new='b'*64
        c['candidate_id']='SYNTH-byte-revision';c['source_metadata']['revision_id']=new
        for e in c['field_evidence']:
            if e.get('revision_id')==old:e['revision_id']=new
        base['candidates']=[c]
        observation={'records':[{'url':doc['url'],'revision_id':new,'raw_sha256':doc['raw_sha256'],'content_verified':True}]}
        files,summary=prepare(base,read(ROOT/'data/scan-sources.json'),observation)
        self.assertIn(doc['id'],summary['byte_identical_rebound_documents'])
        self.assertNotIn(doc['id'],summary['invalidated_timeline_documents'])
        changed=next(d for path in index['bundles'] for d in files[path]['documents'] if d['id']==doc['id'] and d.get('events')) if doc['events'] else None
        if changed:self.assertEqual([e['value'] for e in changed['events']],[e['value'] for e in doc['events']])

    def test_unused_discovery_aliases_do_not_break_preview_or_enable_scans(self):
        bundle,config,profile=self.fixture()
        config['sources'].append({**profile,'id':'SYNTH-unused-alias'})
        with TemporaryDirectory() as tmp:
            output=Path(tmp)/'proposal';write_proposal(bundle,config,output)
            actual=read(output/'repo/data/scan-sources.json')
            self.assertNotIn('SYNTH-unused-alias',[p['id'] for p in actual['sources']])
            self.assertFalse(next(p for p in actual['sources'] if p['id']==profile['id'])['enabled'])

    def test_stricter_document_retention_is_allowed_but_excerpts_still_rejected(self):
        from scripts.check_data import validate_candidate_snapshot
        bundle,config,profile=self.fixture()
        profile['evidence_mode']='short_excerpt'
        self.assertEqual(validate_candidate_snapshot(bundle,config),[])
        bundle['candidates'][0]['field_evidence'][0]['excerpt']='SYNTH'
        self.assertTrue(validate_candidate_snapshot(bundle,config))
        bundle,config,profile=self.fixture()
        bundle['candidates'][0]['source_metadata']['evidence_mode']='short_excerpt'
        self.assertIn('candidate evidence policy differs from its source profile',validate_candidate_snapshot(bundle,config))
