"""Actions boundaries and time-only API proposals; synthetic transport, no keys."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.temporal_model import model_review, source_allowed, model_for_temporal, temporal_units
from scripts.run_temporal_action import select_sources, run
from scripts.temporal_reextract import replay, ROOT, read
from scripts.extract_candidates import _verify_quote_and_reparse, OpenAICompatibleAdapter, safe_rate_metadata
from scripts.document_ir import evidence_block_map


class FakeAdapter:
    enabled=True;calls=0;max_calls=4;rate_limited_429=False
    last_preparation={'complete':True}
    def __init__(self,value='2026-11-10'):
        self.value=value;self.calls=0
    def run_dual_track(self,source,units,candidate):
        self.calls+=1
        return {'extracted_fields':[{'field_path':'schedule.student_deadline','value':self.value,
            'actor':'student','locator':units[0]['unit_id'],'quote':units[0]['text']}],'audit_findings':[]}


class TemporalActionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundle=read(ROOT/'data/candidates/source-review.json')
        cls.profiles={p['id']:p for p in read(ROOT/'data/scan-sources.json')['sources']}
    def candidate(self,sid):
        return deepcopy(next(c for c in self.bundle['candidates'] if c['source_metadata']['source_id']==sid))

    def test_source_ids_are_an_allowlist_not_shell_or_arbitrary_urls(self):
        self.assertEqual(select_sources('taipei-ai-tools,hsinchu-ai-tools',self.bundle['candidates']),['taipei-ai-tools','hsinchu-ai-tools'])
        for value in ('','taipei-ai-tools,taipei-ai-tools','https://example.test','taipei-ai-tools; echo bad'):
            with self.assertRaises(ValueError):select_sources(value,self.bundle['candidates'])

    def test_stricter_candidate_or_registry_retention_wins_before_model(self):
        c=self.candidate('taipei-ai-tools');p=deepcopy(self.profiles['taipei-ai-tools'])
        self.assertTrue(source_allowed(c,p))
        for who in ('candidate','profile'):
            c=self.candidate('taipei-ai-tools');p=deepcopy(self.profiles['taipei-ai-tools'])
            if who=='candidate':c['source_metadata']['evidence_mode']='hash_only'
            else:p['evidence_mode']='hash_only'
            adapter=FakeAdapter()
            result=model_review(c,p,[],adapter,'a'*64)
            self.assertEqual(result['status'],'restricted_source_rules_only')
            self.assertEqual(adapter.calls,0)

    def test_verified_proposals_do_not_mutate_candidate_or_keep_quotes(self):
        c=self.candidate('taipei-ai-tools');before=deepcopy(c)
        text='學生申請截止115年11月10日。'
        result=model_review(c,self.profiles['taipei-ai-tools'],[{'locator':'SYNTH/time','text':text}],FakeAdapter(),'a'*64)
        self.assertEqual(result['claims'][0]['value'],'2026-11-10')
        self.assertNotIn(text,json.dumps(result,ensure_ascii=False))
        self.assertEqual(c,before)
        self.assertEqual(c['review']['status'],'pending')

    def test_model_wrong_year_role_or_birth_date_is_rejected(self):
        c=self.candidate('taipei-ai-tools');p=self.profiles['taipei-ai-tools']
        for text,value in [('學生申請截止115年11月10日。','2027-11-10'),
                           ('申請機構申請截止115年11月10日。','2026-11-10'),
                           ('學生出生日期115年11月10日。','2026-11-10')]:
            result=model_review(c,p,[{'locator':'SYNTH/time','text':text}],FakeAdapter(value),'a'*64)
            self.assertEqual(result['claims'],[])
            self.assertEqual(result['rejected_claims'],1)

    def test_deadline_at_end_of_explicit_range_is_reparsed_as_end(self):
        blocks=[{'locator':'SYNTH/range','text':'學生申請期間115年6月1日至7月29日早上8時止。'}]
        result=_verify_quote_and_reparse('schedule.student_deadline','2026-07-29T08:00:00+08:00',
            None,None,'SYNTH/range',blocks[0]['text'],evidence_block_map(blocks))
        self.assertTrue(result[0])
        self.assertEqual(result[3],'2026-07-29T08:00:00+08:00')

    def test_shared_table_context_saves_space_without_dropping_cells_or_text(self):
        adapter=OpenAICompatibleAdapter('https://api.example.test/v1','SYNTH',allow_local_no_key=True)
        c=self.candidate('taipei-ai-tools')
        units=[{'unit_id':f'SYNTH/{i}','locator':f'SYNTH/{i}','text':f'第{i}項',
                'headers':['期限','角色'],'row_cells':['重要例外不得刪除。'*40,'學生申請截止115年11月10日。']} for i in range(10)]
        before=deepcopy(units)
        source=adapter._build_messages(c,units,'both')[1]['content'].split('<untrusted_source_data>\n')[1].split('\n</untrusted_source_data>')[0]
        payload=json.loads(source)
        reconstructed=[]
        for row in payload['blocks']:
            row=deepcopy(row);context=payload['shared_table_context'][row.pop('context_ref')]
            reconstructed.append({**row,**context})
        self.assertEqual(reconstructed,units)
        self.assertEqual(units,before)
        self.assertLess(len(source),len(json.dumps(units,ensure_ascii=False)))

    def test_time_scope_keeps_late_exceptions_without_first_n_truncation(self):
        blocks=[{'locator':f'SYNTH/nav/{i}','text':'無關導覽選單'} for i in range(50)]
        blocks += [{'locator':'SYNTH/deadline','text':'學生申請截止115年11月10日。'},
                   {'locator':'SYNTH/exception','text':'但曾經領取者不得重複申請。'}]
        selected,total=temporal_units(blocks)
        self.assertEqual(total,52)
        self.assertTrue(any(u['locator']=='SYNTH/exception' for u in selected))
        self.assertTrue(any(u['locator']=='SYNTH/deadline' for u in selected))
        self.assertLess(len(selected),total)

    def test_runtime_request_cap_is_reserved_before_transport(self):
        calls=[]
        def transport(url,headers,limit):
            calls.append(url);return {'status':200,'headers':{'content-type':'text/plain'},'body':b''}
        (ROOT/'work').mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT/'work') as d:
            state=replay(Path(d)/'rules',source_ids=['sinica-phd-fellowship'],max_round_requests=1,transport=transport)
            self.assertEqual(len(calls),1)
            self.assertEqual(state['http_requests'],1)
            self.assertEqual(next(iter(state['records'].values()))['reason'],'run_budget_exhausted')

    def test_quota_diagnostics_do_not_retain_account_ids_or_error_text(self):
        message={'error':{'message':'SYNTH secret-user-account limit reached on tokens per minute (TPM): Limit 8000, Used 6000, Requested 3000'}}
        result=safe_rate_metadata({'Authorization':'Bearer SYNTH-secret','retry-after':'65','x-ratelimit-reset-tokens':'1m5s'},json.dumps(message))
        self.assertEqual(result['limit_unit'],'TPM')
        self.assertEqual(result['limit'],8000)
        self.assertNotIn('SYNTH',json.dumps(result))

    def test_unverified_model_capability_never_downloads_tokenizer(self):
        adapter=FakeAdapter();adapter.model='SYNTH-unknown';adapter.base_url='https://api.groq.com/openai/v1'
        with patch('scripts.temporal_model.create_model_adapter_from_env',return_value=adapter),patch('scripts.temporal_model.install_tokenizer') as download:
            result,reason=model_for_temporal('SYNTH.json')
            self.assertIsNone(result);self.assertEqual(reason,'model_capabilities_not_verified')
            download.assert_not_called()

    def test_offline_actions_orchestration_keeps_baseline_and_never_publishes(self):
        base=read(ROOT/'data/temporal-observations.json')
        cid=self.candidate('taipei-ai-tools')['candidate_id']
        state={'version':'temporal-replay-1','http_requests':1,'model_calls':0,'published':False,
            'batches':[{'http_requests':1}],'records':{cid:deepcopy(base['records'][cid])}}
        (ROOT/'work').mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT/'work') as d,patch.dict('os.environ',{'OPENGSA_MODEL_MODE':'off'}),patch('scripts.run_temporal_action.replay',return_value=state):
            report=run(Path(d)/'action','taipei-ai-tools')
            self.assertEqual(report['model_usage']['calls'],0)
            proposed=read(Path(d)/'action/temporal-observations.proposed.json')
            self.assertEqual(proposed['baseline']['previous_round_http_requests'],base['http_requests'])
            self.assertEqual(len(proposed['records']),len(base['records']))
            self.assertFalse(report['published'])
            self.assertTrue((Path(d)/'action/preview/index.html').exists())
