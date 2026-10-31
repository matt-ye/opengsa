"""Adversarial SYNTH cases; counters and responses are test doubles, not model evals."""
from copy import deepcopy
import json
import random
import tempfile
import unittest
from unittest.mock import patch

from scripts.document_ir import prepare_document, pack_requests
from scripts.extraction_scope import loses_information, compile_scope, apply_scoped_replay
from scripts.evaluate_deadlines import evaluate_application_window
from scripts.scan_sources import html_document, digest, normalized, VERSION
from scripts.review_context import refresh_context
from scripts.extract_candidates import extract_from_in_memory_blocks
from tests import test_prepared_extraction as prepared
from scripts.review_candidates import candidate_fingerprint

fixture, counter, limits = prepared.fixture, prepared.counter, prepared.limits


def html_blocks(body):
    source={'body_selector':'main','pdf_include':[],'max_pdfs':0,'required_markers':['SYNTH']}
    return html_document(('<main><p>'+('SYNTH 基礎說明。'*12)+'</p>'+body+'</main>').encode(),
                         source,'https://example.test',['example.test'])[0]


class AdversarialExtractionTests(unittest.TestCase):
    def test_inline_markup_does_not_split_amount_negation_or_deadline(self):
        for tag in ('span','strong','em','a'):
            with self.subTest(tag=tag):
                body=f'<p>補助四<{tag}>萬</{tag}>元。</p><p>非<{tag}>在職</{tag}>學生。</p><p>115年10月<{tag}>31</{tag}>日截止。</p>'
                texts=[b['text'] for b in html_blocks(body)]
                for text in ('補助四萬元。','非在職學生。','115年10月31日截止。'):
                    self.assertIn(text,texts)

    def test_identical_tables_and_rows_have_distinct_positions(self):
        table='<table><tr><th>身分</th><th>金額</th></tr>'+('<tr><td>博士生</td><td>8000元</td></tr>'*2)+'</table>'
        money=[b for b in html_blocks(table*2) if b['text']=='8000元']
        self.assertEqual([(b['table_id'],b['row_index']) for b in money],
                         [('table-1',1),('table-1',2),('table-2',1),('table-2',2)])

    def test_br_nested_lists_and_comments_preserve_order_without_duplicate_text(self):
        blocks=html_blocks('<div>前文<br>後文<ul><li>主項<span>金額</span><ul><li>子項</li></ul>尾文</li></ul><!--秘密-->結尾</div>')
        self.assertEqual([b['text'] for b in blocks][1:],['前文','後文','主項金額','子項','尾文','結尾'])

    def test_same_length_nested_list_cannot_hide_known_to_unknown_regression(self):
        self.assertTrue(loses_information([{'amount_min':8000,'currency':'TWD'}],
                                         [{'amount_min':None,'currency':'TWD'}]))
        self.assertFalse(loses_information([{'amount_min':8000}],[{'amount_min':9000}]))

    def test_scoped_replay_recomputes_window_from_final_schedule(self):
        _,blocks,old=fixture();fresh=deepcopy(old)
        old['application']['state']='closed'
        fresh['schedule']['application_start']={'kind':'date','value':'2026-10-01','timezone':'Asia/Taipei','note':'SYNTH derived-state test'}
        plan={**compile_scope(old,fields=['schedule']),
              'candidate_sha256':candidate_fingerprint(old),
              'prepared_document_sha256':fresh['source_metadata']['prepared_document_sha256']}
        updated=apply_scoped_replay(old,fresh,plan,blocks)
        expected=evaluate_application_window(updated,old['application']['as_of'])
        self.assertEqual(updated['application']['state'],expected['state'])
        self.assertEqual(updated['application']['reason'],expected['reason'])
        self.assertTrue(updated['verification']['checks']['schema_valid'])

    def test_process_scope_includes_na_and_schedule_dependencies(self):
        _,_,cand=fixture()
        for field in ('application_method.mode','schedule.application_start','field_applicability'):
            with self.subTest(field=field):
                self.assertEqual(compile_scope(cand,fields=[field])['write_fields'],
                    ['application_method','field_applicability','schedule'])

    def test_shared_branch_restriction_survives_joined_html_but_other_branch_does_not_leak(self):
        source=next(s for s in prepared.CONFIG['sources'] if s['id']=='ntu-yuanxue')
        for label in ('及','與','或','、'):
            blocks=html_blocks('<p>115年遠學計畫一般補助。</p>'+
                f'<p>遠學補助{label}<strong>遠學配合補助</strong>：在學期間僅得擇一補助一次。</p>'+
                '<p>配合補助專用：每月新臺幣99999元。</p>')
            cand=extract_from_in_memory_blocks(source,blocks,'a'*64,'2026-10-31T12:00:00+08:00',
                as_of='2026-10-31',extraction_strategy='rules_only')[0]
            with self.subTest(label=label):
                self.assertEqual(cand['compatibility']['mode'],'conditional')
                self.assertFalse(any(i['amount_min']==99999 for i in cand['benefit']['items']))

    def test_capabilities_require_explicit_context_type_and_real_review_date(self):
        doc=prepare_document([{'locator':'SYNTH','text':'測試'}])
        variants=[{k:v for k,v in limits().items() if k!='shared_context'},
                  {**limits(),'shared_context':'false'},{**limits(),'reviewed':'yes'},
                  {**limits(),'checked_on':'2026-02-30'}]
        for cap in variants:
            with self.subTest(cap=cap),self.assertRaises(ValueError):pack_requests(doc,lambda u:u,counter,cap)

    def test_budget_counts_bytes_and_all_unicode_survives_seeded_packing(self):
        rng=random.Random(20261031)
        for size in (600,800,1200):
            text=''.join(rng.choice(['博','🧪','e\u0301','。','不得兼領；']) for _ in range(130))
            doc=prepare_document([{'locator':'SYNTH','text':text}]);render=lambda u:{'units':u}
            cap={**limits(size),'max_request_bytes':size-50}
            chunks=pack_requests(doc,render,counter,cap)
            self.assertEqual(''.join(u['text'] for c in chunks for u in c['units']),text)
            self.assertTrue(all(counter(render(c['units']))<=size-50 for c in chunks))

    def test_sensitive_exception_is_deferred_not_silently_removed(self):
        _,_,cand=fixture()
        cases=[[{'locator':'SYNTH/1','text':'每月8000元。'},
                {'locator':'SYNTH/2','text':'獲獎者不得重複領取其他獎學金。'}],
               [{'locator':'SYNTH/1','text':'8000元','row_cells':['獲獎者不得兼領','8000元']}]]
        for blocks in cases:
            adapter=prepared.PreparedExtractionTests().model()
            with self.subTest(blocks=blocks),patch('urllib.request.urlopen') as network:
                result=adapter.run_dual_track({'evidence_mode':'short_excerpt'},blocks,cand)
            self.assertEqual(result.get('_skipped_reason'),'source_sanitization_requires_review')
            self.assertFalse(adapter.last_preparation['complete'])
            network.assert_not_called()

    def test_non_stop_finish_reasons_cannot_be_accepted_as_complete(self):
        _,blocks,cand=fixture()
        for reason in ('length','tool_calls',None,'unexpected'):
            adapter=prepared.PreparedExtractionTests().model()
            class Response:
                def __enter__(self):return self
                def __exit__(self,*args):pass
                def read(self):return json.dumps({'choices':[{'finish_reason':reason,'message':{'content':'{"extracted_fields":[],"audit_findings":[]}'}}]}).encode()
            with self.subTest(reason=reason),patch('urllib.request.urlopen',return_value=Response()):
                result=adapter.run_dual_track({'evidence_mode':'short_excerpt'},blocks,cand)
                self.assertEqual(result.get('_skipped_reason'),'incomplete_model_output')
                self.assertFalse(adapter.last_preparation['complete'])

    def test_shorter_sentence_boundary_is_recounted_with_nonmonotonic_counter(self):
        doc=prepare_document([{'locator':'SYNTH','text':('測試；'*180)+'結束'}])
        render=lambda u:{'units':u}
        def nonmonotonic(payload):
            return counter(payload)+(2000 if any(u['text'].endswith('；') for u in payload['units']) else 0)
        chunks=pack_requests(doc,render,nonmonotonic,limits(1000))
        self.assertTrue(all(nonmonotonic(render(c['units']))<=950 for c in chunks))
        self.assertEqual(''.join(u['text'] for c in chunks for u in c['units']),doc['units'][0]['text'])

    def test_metadata_only_preparation_change_requires_rescan(self):
        source,blocks,cand=fixture()
        cand['source_metadata']['revision_id']=digest([source['url'],
            digest([[normalized(b['text']) for b in blocks],[]]),digest([VERSION,source])])
        changed=deepcopy(blocks);changed[0]['section_path']=['SYNTH 不同章節']
        class Fetcher:
            count=1
            def get(self,*args):return {'status':200,'headers':{'content-type':'text/html'},'url':source['url'],'body':b'SYNTH'}
        for source_blocks,version in ((changed,cand['source_metadata']['normalizer_version']),(blocks,'SYNTH-old-version')):
            c=deepcopy(cand);c['source_metadata']['normalizer_version']=version
            with self.subTest(version=version),patch('scripts.review_context.html_document',return_value=(source_blocks,[])):
                context,states,_=refresh_context({'candidates':[c]},prepared.CONFIG,Fetcher())
            self.assertEqual(states[cand['candidate_id']],'source_preparation_changed_requires_rescan')
            self.assertFalse(context)

    def test_cached_response_is_bound_to_candidate_scope_and_prompt_version(self):
        _,blocks,cand=fixture()
        class Response:
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def read(self):return b'{"choices":[{"finish_reason":"stop","message":{"content":"{\\"extracted_fields\\":[],\\"audit_findings\\":[]}"}}]}'
        with tempfile.TemporaryDirectory() as directory:
            adapter=prepared.PreparedExtractionTests().model(max_calls=6,cache_dir=directory)
            adapter.use_cache=True
            source={'evidence_mode':'short_excerpt'}
            with patch('urllib.request.urlopen',return_value=Response()) as network:
                adapter.run_dual_track(source,blocks,cand)
                adapter.run_dual_track(source,blocks,cand)
                self.assertEqual(network.call_count,1);self.assertEqual(adapter.cache_hits,1)
                changed=deepcopy(cand);changed['title']+=' SYNTH changed'
                adapter.run_dual_track(source,blocks,changed)
                adapter.field_scope=('benefit.amount',)
                adapter.run_dual_track(source,blocks,changed)
                with patch('scripts.extract_candidates.PROMPT_VERSION','SYNTH-new-prompt'):
                    adapter.run_dual_track(source,blocks,changed)
                self.assertEqual(network.call_count,4)

    def test_failure_after_successful_chunk_returns_no_partial_claims(self):
        _,_,cand=fixture();adapter=prepared.PreparedExtractionTests().model(max_calls=6)
        blocks=[{'locator':f'SYNTH/{i}','text':'普通背景內容'*20} for i in range(40)]
        responses=[{'extracted_fields':[],'audit_findings':[]},
                   {'_skipped_reason':'http_429_deferred_no_retry'}]
        with patch.object(adapter,'_run_one',side_effect=responses) as run:
            result=adapter.run_dual_track({'evidence_mode':'short_excerpt'},blocks,cand)
        self.assertEqual(result,{'_skipped_reason':'http_429_deferred_no_retry'})
        self.assertEqual(run.call_count,2)
        self.assertEqual(adapter.last_preparation['chunks_completed'],1)
        self.assertFalse(adapter.last_preparation['complete'])


if __name__=='__main__':unittest.main()
