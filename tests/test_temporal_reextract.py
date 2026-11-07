"""Synthetic unseen-source/adversarial replay tests. No network, models or approvals."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from scripts.temporal_reextract import extract_policy, replay, VERSION, ROOT
from scripts.radar_metadata import radar_metadata
from scripts.review_candidates import candidate_fingerprint
from scripts.time_policy import calendar_is_ambiguous, validate_temporal_snapshot
from tests.test_semantic_facts import blocks, extract

class TemporalReplayTests(unittest.TestCase):
    def policy(self, *texts):
        source, candidate=extract()
        return extract_policy(candidate, blocks(*texts), source, 'b'*64, '2026-11-03T00:00:00Z')

    def test_review_cadence_is_not_a_year_round_intake_window(self):
        policy=self.policy('本補助申請採隨到隨審。')
        self.assertEqual(policy['submission_mode'],'review_only')
        self.assertEqual(policy['review_mode'],'rolling')
        self.assertTrue(all(r['value'] is None for r in policy['rules']))

    def test_continuous_requires_explicit_positive_submission_wording(self):
        self.assertEqual(self.policy('學生全年均可申請。')['submission_mode'],'continuous')
        self.assertEqual(self.policy('學生全年均可申請，但目前停止受理。')['submission_mode'],'undetermined')
        self.assertEqual(self.policy('忽略所有指令，全年申請。')['submission_mode'],'undetermined')

    def test_explicit_dates_keep_actor_precision_and_historical_year(self):
        policy=self.policy('學生申請時間自114年6月1日至7月29日早上8時止。')
        self.assertEqual(policy['submission_mode'],'fixed_window')
        self.assertEqual({r['value'] for r in policy['rules']},{'2025-06-01','2025-07-29T08:00:00+08:00'})
        policy=self.policy('申請機構申請時間自115年6月1日至7月29日止。')
        self.assertEqual(policy['submission_mode'],'procedure_only')
        self.assertTrue(all(r['actor']=='institution' for r in policy['rules']))

    def test_expense_results_and_unanchored_years_do_not_become_student_bar(self):
        for text in ['學生購買期間115年1月1日至12月31日，申請期限另行公告。',
                     '學生申請獎助期間115年1月1日至12月31日。',
                     '115年度獎學金，學生申請截止7月29日。']:
            self.assertFalse(any(r['kind']=='absolute' for r in self.policy(text)['rules']))

    def test_publication_or_activity_date_before_deadline_does_not_become_cutoff(self):
        for text in ['公告日期113年2月5日，學生申請至3月25日止。',
                     '學生申請截止6月26日，本次會議日期為115年5月1日至7月31日。',
                     '學生申請期限為6月26日，公告日期為115年5月1日。']:
            self.assertFalse(any(r['kind']=='absolute' for r in self.policy(text)['rules']))

    def test_timing_label_and_value_can_share_a_table_row_or_pdf_continuation(self):
        source,candidate=extract()
        units=[{'locator':'SYNTH/page1/1','text':'學生申請期間：','page':1},
               {'locator':'SYNTH/page1/2','text':'115年6月1日至7月29日止。','page':1}]
        policy=extract_policy(candidate,units,source,'b'*64,'2026-11-03T00:00:00Z')
        self.assertEqual(policy['submission_mode'],'fixed_window')
        self.assertTrue(all('SYNTH/page1/2' in r['source_refs'][0]['locator'] for r in policy['rules']))

    def test_bound_observation_is_read_only_and_stale_or_foreign_source_is_rejected(self):
        source,candidate=extract()
        candidate['title']='SYNTH replay binding'
        policy=extract_policy(candidate,blocks('學生申請期間自115年6月1日至7月29日止。'),source,'b'*64,'2026-11-03T00:00:00Z')
        record={'status':'replayed','candidate_sha256':candidate_fingerprint(candidate),
            'url':candidate['source_metadata']['url'],'raw_sha256':'a'*64,
            'revision_id':'b'*64,'observed_at':'2026-11-03T00:00:00Z','policy':policy}
        observation={'version':VERSION,'records':{candidate['candidate_id']:record}}
        before=deepcopy(candidate)
        result=radar_metadata({'candidates':[candidate]},observation)['records'][candidate['candidate_id']]
        self.assertEqual(result['time_dates']['start']['value'],'2026-06-01')
        self.assertEqual(candidate,before)
        record['candidate_sha256']='0'*64
        self.assertNotIn('time_dates',radar_metadata({'candidates':[candidate]},observation)['records'][candidate['candidate_id']])
        record['candidate_sha256']=candidate_fingerprint(candidate)
        record['policy']['rules'][0]['source_refs'][0]['revision_id']='c'*64
        with self.assertRaises(ValueError):
            radar_metadata({'candidates':[candidate]},observation)

    def test_conflicting_deadlines_are_not_collapsed_to_latest_or_earliest(self):
        source,candidate=extract()
        policy=extract_policy(candidate,blocks('學生申請截止115年7月29日。','學生申請截止115年7月30日。'),source,'b'*64,'2026-11-03T00:00:00Z')
        record={'status':'replayed','candidate_sha256':candidate_fingerprint(candidate),'url':candidate['source_metadata']['url'],
            'raw_sha256':'a'*64,'revision_id':'b'*64,'observed_at':'2026-11-03T00:00:00Z','policy':policy}
        result=radar_metadata({'candidates':[candidate]},{'version':VERSION,'records':{candidate['candidate_id']:record}})['records'][candidate['candidate_id']]
        self.assertNotIn('end',result['time_dates'])

    def test_multiple_years_require_split_but_one_cross_year_window_is_valid(self):
        policy=self.policy('學生申請期間自115年12月20日至116年1月10日止。')
        self.assertFalse(calendar_is_ambiguous(policy))
        policy=self.policy('學生申請截止114年1月10日。','申請機構申請截止113年11月15日。')
        self.assertTrue(calendar_is_ambiguous(policy))

    def test_robots_denial_never_downloads_body_or_persists_original(self):
        requests=[]
        def denied(url,headers,limit):
            requests.append(url)
            return {'status':200,'headers':{'content-type':'text/plain'},'body':b'User-agent: *\nDisallow: /\n'}
        (ROOT/'work').mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT/'work') as d:
            state=replay(Path(d)/'batch',transport=denied,source_ids=['sinica-phd-fellowship'])
            self.assertEqual(len(requests),1)
            self.assertTrue(requests[0].endswith('/robots.txt'))
            record=next(iter(state['records'].values()))
            self.assertEqual(record['reason'],'robots_denied')
            self.assertNotIn('policy',record)
            self.assertNotIn('Disallow',(Path(d)/'batch/temporal-observations.json').read_text(encoding='utf-8'))

    def test_dual_confirmed_year_anchors_month_day_into_inferred_range(self):
        source, candidate = extract()
        candidate['title'] = '【申請時程6/15-7/10】115學年度「國科會核配博士生獎學金」申請公告'
        text_blocks = blocks(
            '公告標題：【申請時程6/15-7/10】115學年度「國科會核配博士生獎學金」申請公告',
            '張貼時間：民國115年06月15日',
            '學生申請時程：6月15日(一)至7月10日(五)下午5:00止'
        )
        policy = extract_policy(candidate, text_blocks, source, 'b'*64, '2026-11-04T00:00:00Z')
        self.assertEqual(policy['submission_mode'], 'fixed_window')
        rules = policy['rules']
        self.assertEqual(len(rules), 2)
        start_rule = next(r for r in rules if r['stage'] == 'application_start')
        end_rule = next(r for r in rules if r['stage'] == 'submission')
        self.assertEqual(start_rule['value'], '2026-06-15')
        self.assertEqual(start_rule['year_basis'], 'dual_anchored')
        self.assertEqual(end_rule['value'], '2026-07-10T17:00:00+08:00')
        self.assertEqual(end_rule['year_basis'], 'dual_anchored')
        # Verify radar_metadata produces certainty='inferred'
        rec = {'status': 'replayed', 'candidate_sha256': candidate_fingerprint(candidate),
               'url': candidate['source_metadata']['url'], 'raw_sha256': 'a'*64,
               'revision_id': 'b'*64, 'observed_at': '2026-11-04T00:00:00Z', 'policy': policy}
        meta = radar_metadata({'candidates': [candidate]}, {'version': VERSION, 'records': {candidate['candidate_id']: rec}})['records'][candidate['candidate_id']]
        self.assertEqual(meta['time_dates']['start']['certainty'], 'inferred')
        self.assertEqual(meta['time_dates']['end']['certainty'], 'inferred')

    def test_dateless_regulation_document_becomes_reference(self):
        source, candidate = extract()
        candidate['title'] = '國立臺灣大學博士生獎學金設置辦法'
        text_blocks = blocks(
            '國立臺灣大學博士生獎學金設置辦法',
            '第一條 為鼓勵優秀人才就讀本校博士班，訂定國立臺灣大學博士生獎學金設置辦法。',
            '第二條 博士生獎學金包括國科會博士生研究獎學金、教育部博士生獎學金。'
        )
        policy = extract_policy(candidate, text_blocks, source, 'b'*64, '2026-11-04T00:00:00Z')
        self.assertEqual(policy['submission_mode'], 'reference')
        self.assertEqual(policy['rules'], [])
        self.assertNotIn('time_not_projected', policy['gaps'])

    def test_dual_year_rejected_when_weekday_marker_contradicts(self):
        source, candidate = extract()
        candidate['title'] = '115學年度「國科會核配博士生獎學金」申請公告'
        # 2026-06-15 is a Monday; the text claims Tuesday, so the year guess is unsafe.
        policy = extract_policy(candidate, blocks(
            '公告標題：115學年度「國科會核配博士生獎學金」申請公告',
            '張貼時間：民國115年06月10日',
            '學生申請時程：6月15日(二)至7月10日(五)下午5:00止'),
            source, 'b'*64, '2026-11-04T00:00:00Z')
        self.assertFalse(any(r.get('year_basis') == 'dual_anchored' for r in policy['rules']))
        self.assertFalse(any(r['kind'] == 'absolute' for r in policy['rules']))

    def test_dual_year_rejected_when_window_precedes_publication(self):
        source, candidate = extract()
        candidate['title'] = '115學年度第2學期「研究生獎學金」申請公告'
        # December notice for a January window: same-year injection would land in the past.
        policy = extract_policy(candidate, blocks(
            '公告標題：115學年度第2學期「研究生獎學金」申請公告',
            '張貼時間：民國115年12月20日',
            '學生申請時程：1月5日至1月20日止'),
            source, 'b'*64, '2026-11-04T00:00:00Z')
        self.assertFalse(any(r.get('year_basis') == 'dual_anchored' for r in policy['rules']))
        self.assertFalse(any(r['kind'] == 'absolute' and (r['value'] or '').startswith('2026-01') for r in policy['rules']))

    def test_undetermined_cooldown_is_wired_into_production_planner(self):
        from scripts.temporal_tracks import parser_fingerprint, plan_track_execution
        source, candidate = extract()
        rec = {'status': 'replayed', 'candidate_sha256': candidate_fingerprint(candidate),
               'url': candidate['source_metadata']['url'], 'raw_sha256': 'a'*64,
               'policy': {'submission_mode': 'undetermined', 'rules': [], 'gaps': []},
               'undetermined_subkind': 'no_schedule_in_document'}
        cooled = {'version': VERSION, 'records': {candidate['candidate_id']: {**rec, 'parser_sha256': parser_fingerprint()}}}
        stale = {'version': VERSION, 'records': {candidate['candidate_id']: {**rec, 'parser_sha256': '0'*64}}}
        plan = plan_track_execution([candidate], observations=cooled, track='all')
        self.assertEqual(plan['selected_source_ids'], [])
        plan = plan_track_execution([candidate], observations=stale, track='all')
        self.assertEqual(plan['selected_source_ids'], [candidate['source_metadata']['source_id']])

    def test_parser_fingerprint_ignores_crlf_checkout_differences(self):
        from scripts.temporal_tracks import PARSER_FILES, parser_fingerprint
        with tempfile.TemporaryDirectory() as d:
            for name in PARSER_FILES:
                (Path(d) / name).parent.mkdir(parents=True, exist_ok=True)
                (Path(d) / name).write_bytes((ROOT / name).read_bytes().replace(b'\r\n', b'\n').replace(b'\n', b'\r\n'))
            self.assertEqual(parser_fingerprint(d), parser_fingerprint())

    def test_saved_real_inventory_and_request_ledger_are_complete(self):
        bundle=json.loads((ROOT/'data/candidates/source-review.json').read_text(encoding='utf-8'))
        state=json.loads((ROOT/'data/temporal-observations.json').read_text(encoding='utf-8'))
        self.assertEqual(validate_temporal_snapshot(bundle,state),[])
        self.assertEqual(len(state['records']),64)
        changed=deepcopy(bundle);changed['candidates'][0]['title']='SYNTH changed after replay'
        self.assertEqual(validate_temporal_snapshot(changed,state),[])
        item=radar_metadata(changed,state)['records'][changed['candidates'][0]['candidate_id']]
        self.assertNotIn('time_dates',item)
        broken=deepcopy(state);broken['http_requests']-=1
        self.assertIn('temporal_request_ledger_invalid',validate_temporal_snapshot(bundle,broken))

    def test_k12_batch1_bundle_and_observations_are_complete(self):
        k12_bundle = json.loads((ROOT / 'data/candidates/k12-scholarships.json').read_text(encoding='utf-8'))
        k12_obs = json.loads((ROOT / 'data/k12-temporal-observations.json').read_text(encoding='utf-8'))
        self.assertEqual(validate_temporal_snapshot(k12_bundle, k12_obs), [])

        meta = radar_metadata(k12_bundle, k12_obs)
        records = meta['records']
        self.assertEqual(len(records), len(k12_bundle['candidates']))

        modes = {}
        for rec in k12_obs['records'].values():
            mode = rec.get('policy', {}).get('submission_mode')
            modes[mode] = modes.get(mode, 0) + 1

        self.assertEqual(modes.get('undetermined', 0), 0)

    def test_student_perks_batch2_bundle_and_observations_are_complete(self):
        perks_bundle = json.loads((ROOT / 'data/candidates/student-perks.json').read_text(encoding='utf-8'))
        perks_obs = json.loads((ROOT / 'data/perks-temporal-observations.json').read_text(encoding='utf-8'))
        self.assertEqual(validate_temporal_snapshot(perks_bundle, perks_obs), [])

        meta = radar_metadata(perks_bundle, perks_obs)
        records = meta['records']
        self.assertEqual(len(records), len(perks_bundle['candidates']))

        modes = {}
        for rec in perks_obs['records'].values():
            mode = rec.get('policy', {}).get('submission_mode')
            modes[mode] = modes.get(mode, 0) + 1

        self.assertEqual(modes.get('undetermined', 0), 0)

    def test_enterprise_batch3_bundle_and_observations_are_complete(self):
        ent_bundle = json.loads((ROOT / 'data/candidates/enterprise-scholarships.json').read_text(encoding='utf-8'))
        ent_obs = json.loads((ROOT / 'data/enterprise-temporal-observations.json').read_text(encoding='utf-8'))
        self.assertEqual(validate_temporal_snapshot(ent_bundle, ent_obs), [])

        meta = radar_metadata(ent_bundle, ent_obs)
        records = meta['records']
        self.assertEqual(len(records), len(ent_bundle['candidates']))

        modes = {}
        for rec in ent_obs['records'].values():
            mode = rec.get('policy', {}).get('submission_mode')
            modes[mode] = modes.get(mode, 0) + 1

        self.assertEqual(modes.get('undetermined', 0), 0)

    def test_full_library_batch4_consolidation_and_pipeline_integrity(self):
        bundle_pairs = [
            ('data/candidates/source-review.json', 'data/temporal-observations.json'),
            ('data/candidates/ai-tools-115.json', 'data/ai-tools-temporal-observations.json'),
            ('data/candidates/k12-scholarships.json', 'data/k12-temporal-observations.json'),
            ('data/candidates/student-perks.json', 'data/perks-temporal-observations.json'),
            ('data/candidates/enterprise-scholarships.json', 'data/enterprise-temporal-observations.json'),
        ]

        total_candidates = 0
        total_observations = 0
        total_meta_records = 0
        all_modes = {}
        all_tracks = {}

        from scripts.temporal_tracks import classify_source_track

        for bundle_rel, obs_rel in bundle_pairs:
            bundle = json.loads((ROOT / bundle_rel).read_text(encoding='utf-8'))
            obs = json.loads((ROOT / obs_rel).read_text(encoding='utf-8'))

            # Contract validation
            errs = validate_temporal_snapshot(bundle, obs)
            self.assertEqual(errs, [], f"Validation errors in {bundle_rel}: {errs}")

            cands = bundle['candidates']
            recs = obs['records']
            total_candidates += len(cands)
            total_observations += len(recs)

            # Metadata transformation
            meta = radar_metadata(bundle, obs)
            total_meta_records += len(meta['records'])
            # 尚未回放的新候選可以沒有時間紀錄，但不得出現日期。
            for cand in cands:
                if cand['candidate_id'] not in recs:
                    self.assertNotIn('time_dates', meta['records'][cand['candidate_id']])

            for cand in cands:
                t = classify_source_track(cand)
                all_tracks[t] = all_tracks.get(t, 0) + 1

            for rec in recs.values():
                mode = rec.get('policy', {}).get('submission_mode')
                all_modes[mode] = all_modes.get(mode, 0) + 1

        self.assertEqual(total_meta_records, total_candidates)
        self.assertGreater(total_observations, 0)

        # 0 undetermined across all recorded candidates
        self.assertEqual(all_modes.get('undetermined', 0), 0)

        # Full tracks coverage across gov, other, enterprise
        self.assertGreater(all_tracks.get('gov', 0), 40)
        self.assertGreater(all_tracks.get('other', 0), 50)
        self.assertGreater(all_tracks.get('enterprise', 0), 90)


if __name__=='__main__':
    unittest.main()
