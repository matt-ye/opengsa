"""Synthetic adaptation cases; token counts and models below are test doubles only."""
from copy import deepcopy
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from scripts.document_ir import prepare_document,document_manifest,pack_requests,evidence_block_map
from scripts.extraction_scope import compile_scope,apply_scoped_replay
from scripts.extract_candidates import OpenAICompatibleAdapter,ModelPolicyError,extract_from_in_memory_blocks,_verify_quote_and_reparse
from scripts.prepare_candidates import prepare_batch
from scripts.review_candidates import candidate_fingerprint
from scripts.scan_sources import html_document
from scripts.verify_candidates import verify_candidate

ROOT=Path(__file__).resolve().parents[1]
CONFIG=json.loads((ROOT/'data/scan-sources.json').read_text(encoding='utf-8'))


def counter(envelope):return len(json.dumps(envelope,ensure_ascii=False,sort_keys=True).encode('utf-8'))


def limits(size=1500):
    return {'model':'SYNTH-model','reviewed':True,'checked_on':'2026-10-31',
        'input_limit':size,'output_limit':200,'output_reserve':100,'max_request_bytes':100000,
        'safety_tokens':50,'shared_context':True,'context_limit':size+500,'thinking_reserve':100}


def fixture():
    source=next(s for s in CONFIG['sources'] if s['id']=='nstc-abroad-dragon-rule')
    blocks=[{'locator':'SYNTH/header','text':'SYNTH 博士班在學學生。'},
        {'locator':'SYNTH/money','text':'以一年補助新臺幣九十萬元為計算標準。'}]
    cand=extract_from_in_memory_blocks(source,blocks,'a'*64,'2026-10-31T12:00:00+08:00',as_of='2026-10-31',extraction_strategy='rules_only')[0]
    return source,blocks,cand


class PreparedExtractionTests(unittest.TestCase):
    def test_table_and_heading_context_survive_without_changing_evidence_text(self):
        source={'body_selector':'main','pdf_include':[],'max_pdfs':0,'required_markers':['資格']}
        html=('<main><h2>資格與給付</h2><p>'+('SYNTH 測試正文。'*10)+
            '</p><table><tr><th>身分</th><th>每月新臺幣</th></tr>'+
            '<tr><td>博士生</td><td>8,000元</td></tr><tr><td>碩士生</td><td>6,000元</td></tr></table><h2>申請程序</h2><p>另一章節內容</p></main>').encode()
        blocks,_=html_document(html,source,'https://example.test',['example.test'])
        money=next(b for b in blocks if b['text']=='8,000元')
        self.assertEqual(money['row_cells'],['博士生','8,000元'])
        self.assertIn('身分',money['headers'])
        self.assertEqual(money['section_path'],['資格與給付'])
        self.assertEqual(money['kind'],'table_cell')
        self.assertEqual(next(b for b in blocks if b['text']=='另一章節內容')['section_path'],['申請程序'])
        doc=prepare_document(blocks)
        self.assertEqual([u['text'] for u in doc['units']],[b['text'] for b in blocks])
        self.assertNotIn('8,000元',json.dumps(document_manifest(doc),ensure_ascii=False))

    def test_repeated_pdf_locator_has_unique_ids_and_ambiguous_quote_is_rejected(self):
        blocks=[{'locator':'PDF page 1','text':'博士生每月8000元。'},
                {'locator':'PDF page 1','text':'碩士生每月6000元。'}]
        doc=prepare_document(blocks);mapping=evidence_block_map(blocks)
        self.assertNotEqual(doc['units'][0]['unit_id'],doc['units'][1]['unit_id'])
        ok,_,block,_=_verify_quote_and_reparse('benefit.amount',8000,'per_month','TWD',
            doc['units'][0]['unit_id'],'博士生每月8000元',mapping)
        self.assertTrue(ok);self.assertEqual(block['text'],blocks[0]['text'])
        ambiguous=evidence_block_map(blocks+[blocks[0]])
        self.assertEqual(_verify_quote_and_reparse('benefit.amount',8000,'per_month','TWD',
            'PDF page 1','博士生每月8000元',ambiguous)[1],'model_locator_ambiguous')

    def test_long_paragraph_is_losslessly_split_and_each_full_envelope_fits(self):
        text=('超長但不省略的合成測試文字。'*90)+'最後的條件'
        doc=prepare_document([{'locator':'SYNTH/long','text':text}])
        render=lambda units:{'system':'SYNTH required instructions','schema':{'fields':['amount']},'units':units}
        chunks=pack_requests(doc,render,counter,limits())
        self.assertGreater(len(chunks),1)
        self.assertEqual(''.join(u['text'] for c in chunks for u in c['units']),text)
        self.assertTrue(all(counter(render(c['units']))<=1450 for c in chunks))

    def test_unknown_capability_output_limit_and_global_context_fail_before_request(self):
        doc=prepare_document([{'locator':'SYNTH/1','text':'條件'}])
        for cap,count in [(None,counter),(limits(),None),({**limits(),'reviewed':False},counter),
                          ({**limits(),'output_reserve':1000},counter)]:
            with self.assertRaises(ValueError):pack_requests(doc,lambda u:u,count,cap)
        with self.assertRaisesRegex(ValueError,'shared_context'):
            pack_requests(doc,lambda u:{'context':'x'*5000,'units':u},counter,limits())

    def test_scope_couples_amount_period_and_protects_unrelated_fields_and_approval(self):
        _,blocks,fresh=fixture();old=deepcopy(fresh)
        old['benefit']['summary']='SYNTH incorrect total';old['benefit']['items'][0]['amount_min']=999999
        old['review'].update(status='reviewed',independent_reviewer='SYNTH-reviewer',promotion_ready=True)
        plan={**compile_scope(old,fields=['benefit.summary']),'candidate_sha256':candidate_fingerprint(old),
              'prepared_document_sha256':fresh['source_metadata']['prepared_document_sha256']}
        self.assertEqual(plan['write_fields'],['benefit'])
        repaired=apply_scoped_replay(old,fresh,plan,blocks)
        self.assertEqual(repaired['benefit'],fresh['benefit'])
        self.assertEqual(repaired['eligibility'],old['eligibility'])
        self.assertFalse(repaired['review']['promotion_ready'])
        self.assertEqual(repaired['review']['status'],'pending')
        changed=deepcopy(old);changed['title']+=' altered'
        with self.assertRaisesRegex(ValueError,'candidate_content_changed'):apply_scoped_replay(changed,fresh,plan,blocks)
        altered=deepcopy(fresh);altered['source_metadata']['revision_id']='b'*64
        with self.assertRaisesRegex(ValueError,'source_revision_changed'):apply_scoped_replay(old,altered,plan,blocks)

    def test_illegal_fields_and_array_indices_are_rejected(self):
        _,_,cand=fixture()
        for field in ['review.status','source_metadata.url','application.state','benefit.items.0','eligibility.not_a_field']:
            with self.subTest(field=field),self.assertRaises(ValueError):compile_scope(cand,fields=[field])

    def test_unknown_replay_does_not_erase_a_previously_recorded_value(self):
        _,blocks,cand=fixture();new=deepcopy(cand)
        new['benefit']['items']=[]
        plan={**compile_scope(cand,groups=['benefit']),'candidate_sha256':candidate_fingerprint(cand),
              'prepared_document_sha256':cand['source_metadata']['prepared_document_sha256']}
        with self.assertRaisesRegex(ValueError,'information_regression'):apply_scoped_replay(cand,new,plan,blocks)

    def test_reverification_without_baseline_cannot_clear_regression_flags(self):
        _,blocks,cand=fixture()
        cand['verification']['warnings'].append('coverage_regression:eligibility.year_limit.mode(unlimited->unknown)')
        checked=verify_candidate(cand,blocks)
        self.assertFalse(checked['verification']['checks']['coverage_ok'])
        self.assertIn('coverage_regression:eligibility.year_limit.mode(unlimited->unknown)',checked['verification']['warnings'])

    def test_plan_only_is_offline_and_does_not_claim_a_replay(self):
        _,_,cand=fixture()
        bundle={'schema_version':'1.1.0-candidate','generated_at':'2026-10-31T12:00:00+08:00',
            'as_of':'2026-10-31','timezone':'Asia/Taipei','model_enabled':False,'model_calls':0,
            'official_data_modified':False,'candidates':[cand]}
        before=deepcopy(bundle)
        _,report=prepare_batch(bundle,CONFIG,groups=['benefit'])
        self.assertEqual(report['plans'][0]['status'],'requires_fresh_source_context')
        self.assertEqual(bundle,before);self.assertEqual(report['documents'],{})

    def test_sanitizer_keeps_late_rules_and_long_units(self):
        adapter=OpenAICompatibleAdapter('https://api.example.test/v1','SYNTH-model',allow_local_no_key=True)
        blocks=[{'locator':f'SYNTH/{i}','text':f'第{i}項正常資料'} for i in range(40)]
        blocks.append({'locator':'SYNTH/late','text':'不得重複支領。'+'長文'*500})
        sanitized=adapter._sanitize_blocks(blocks,{'evidence_mode':'short_excerpt'})
        self.assertEqual(len(sanitized),41)
        self.assertTrue(any(len(b['text'])>320 for b in sanitized))

    def model(self,**kwargs):
        return OpenAICompatibleAdapter('https://api.example.test/v1','SYNTH-model',
            allow_local_no_key=True,use_cache=False,model_limits=limits(10000),count_tokens=counter,**kwargs)

    def test_unknown_model_capabilities_and_hash_only_never_send(self):
        _,blocks,cand=fixture()
        with patch('urllib.request.urlopen') as network:
            adapter=OpenAICompatibleAdapter('https://api.example.test/v1','SYNTH-model',allow_local_no_key=True)
            self.assertEqual(adapter.run_dual_track({'evidence_mode':'short_excerpt'},blocks,cand)['_skipped_reason'],'model_capabilities_required')
            with self.assertRaises(ModelPolicyError):self.model().run_dual_track({'evidence_mode':'hash_only'},blocks,cand)
            network.assert_not_called()

    def test_late_exception_is_in_shared_context_and_exact_request_budget(self):
        _,_,cand=fixture();adapter=self.model(max_calls=6)
        blocks=[{'locator':f'SYNTH/{i}','text':('普通背景內容'*15)+str(i)} for i in range(35)]
        blocks.append({'locator':'SYNTH/late','text':'但曾領取本補助者不得申請。'})
        calls=[]
        class Response:
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def read(self):return json.dumps({'choices':[{'finish_reason':'stop','message':{'content':json.dumps({'extracted_fields':[],'audit_findings':[]})}}]}).encode()
        def network(request,timeout):
            payload=json.loads(request.data);calls.append(payload)
            self.assertLessEqual(counter(payload),9950)
            self.assertIn('但曾領取本補助者不得申請',payload['messages'][1]['content'])
            return Response()
        with patch('urllib.request.urlopen',network):
            result=adapter.run_dual_track({'evidence_mode':'short_excerpt'},blocks,cand)
        self.assertEqual(result,{'extracted_fields':[],'audit_findings':[]})
        self.assertGreater(len(calls),1)
        self.assertTrue(adapter.last_preparation['complete'])

    def test_chunk_failure_never_returns_partial_claims(self):
        _,_,cand=fixture();adapter=self.model(max_calls=1)
        blocks=[{'locator':f'SYNTH/{i}','text':'普通背景內容'*20} for i in range(40)]
        response={'extracted_fields':[],'audit_findings':[]}
        def one(*args):
            adapter.calls+=1
            return response if adapter.calls==1 else {'_skipped_reason':'rate_limited_or_budget_exhausted'}
        with patch.object(adapter,'_run_one',one):result=adapter.run_dual_track({'evidence_mode':'short_excerpt'},blocks,cand)
        self.assertIn('_skipped_reason',result)
        self.assertNotIn('extracted_fields',result)
        self.assertFalse(adapter.last_preparation['complete'])

    def test_conflicting_chunk_claims_are_not_last_write_wins(self):
        _,_,cand=fixture();adapter=self.model()
        blocks=[{'locator':f'SYNTH/{i}','text':'普通背景內容'*20} for i in range(40)]
        def one(*args):
            adapter.calls+=1
            return {'extracted_fields':[{'field_path':'eligibility.nationality',
                'value':'roc_only' if adapter.calls==1 else 'all','unit':None,'currency':None,
                'actor':None,'locator':'SYNTH/1','quote':'背景內容'}],'audit_findings':[]}
        with patch.object(adapter,'_run_one',one):result=adapter.run_dual_track({'evidence_mode':'short_excerpt'},blocks,cand)
        self.assertEqual(result['_skipped_reason'],'model_conflicting_chunk_claims')
        self.assertNotIn('extracted_fields',result)

    def test_out_of_scope_model_claims_are_rejected_atomically(self):
        _,blocks,cand=fixture();adapter=self.model(field_scope=['benefit.amount'])
        response={'extracted_fields':[{'field_path':'eligibility.nationality','value':'roc_only',
            'unit':None,'currency':None,'actor':None,'locator':'SYNTH/header','quote':'博士班'}],'audit_findings':[]}
        with patch.object(adapter,'_run_one',return_value=response):
            result=adapter.run_dual_track({'evidence_mode':'short_excerpt'},blocks,cand)
        self.assertEqual(result['_skipped_reason'],'model_field_scope_violation')


if __name__=='__main__':unittest.main()
