"""Synthetic scope, provenance and incremental-scanning regressions."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from scripts.source_chains import dates, discover_links, extract_events, scan_chains, validate, baselines
from scripts.source_chains import publication, timeline_metadata, candidate_bindings,publication_reference_events
from scripts.scan_sources import Fetcher, digest
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]


def profile():
    return {'url': 'https://example.test/call', 'program_key': 'SYNTH-program', 'scope': 'SYNTH-unit',
        'cycle': '115', 'application_year': 2026, 'phase': 'round1', 'role': 'local_intake',
        'evidence_mode': 'hash_only', 'body_selector': 'main', 'required_markers': ['SYNTH']}


def fixture():
    p = profile()
    config = {'sources': [p], 'allowed_hosts': ['example.test'], 'max_requests': 20, 'max_documents': 12,
        'max_depth': 2, 'max_run_seconds': 180, 'minimum_host_interval_seconds': 0, 'scopes': [{'id':'SYNTH-unit','label':'合成單位'}]}
    return p, config, {'candidates': []}


class SourceChainTests(unittest.TestCase):
    def test_publication_year_windows_remain_unannounced_with_dual_evidence(self):
        p=profile();doc={'id':'SYNTH-doc','revision_id':'a'*64}
        units=[{'locator':'SYNTH-window','text':'申請時程6/15至7/10'}]
        pub=('2026-06-15',{'locator':'SYNTH-publication','text':'2026-06-15'})
        events=publication_reference_events(units,p,doc,pub)
        self.assertEqual([e['value'] for e in events],['2026-06-15','2026-07-10'])
        self.assertTrue(all(e['certainty']=='expected' and e['publication_ref']['locator']=='SYNTH-publication' for e in events))
        self.assertEqual(baselines(events,2027),[])
        self.assertEqual(publication_reference_events(units,p,doc,None),[])
        self.assertEqual(publication_reference_events([{'locator':'SYNTH','text':'購買及申請期間6/15至7/10'}],p,doc,pub),[])
        self.assertEqual(publication_reference_events([{'locator':'SYNTH','text':'申請期間12/20至1/10'}],p,doc,pub),[])

    def test_attachment_priority_navigation_and_html_entity_urls(self):
        raw=('<main><nav><a href="/unrelated">計畫</a></nav>'+''.join('<a href="/list/'+str(i)+'">計畫列表</a>' for i in range(12))+
             '<a href="/attachments/real?x=1&amp;amp;y=2">申請須知</a></main>').encode()
        links=discover_links(raw,'https://example.test/index',['example.test'])
        self.assertEqual(len(links),8)
        self.assertEqual(links[0]['url'],'https://example.test/attachments/real?x=1&y=2')
        self.assertNotIn('https://example.test/unrelated',[link['url'] for link in links])

    def test_metadata_only_profile_does_not_guess_date_actor(self):
        p = profile(); p['extract_dates'] = False
        blocks = [{'locator':'SYNTH-date','text':'申請日期：115年6月1日至7月31日中午12時'}]
        self.assertEqual(extract_events(blocks,p,{'id':'SYNTH-doc','revision_id':'a'*64}),[])

    def test_date_precision_and_shared_year_with_weekdays(self):
        self.assertEqual(dates('115年7月8日(三)起至7月27日(一)17:00', 2026),
                         ['2026-07-08', '2026-07-27T17:00:00+08:00'])
        self.assertEqual(dates('6月15日(一)至7月10日(五)下午5:00止', 2026),
                         ['2026-06-15', '2026-07-10T17:00:00+08:00'])
        self.assertEqual(dates('2026/02/30', None), [])
        self.assertEqual(dates('115年7月10日25:00',2026),[])

    def test_announcement_does_not_create_opening_without_since(self):
        p = profile(); doc = {'id':'SYNTH-doc','revision_id':'a'*64}
        pub = ('2026-10-06', {'locator':'SYNTH-pub','text':'2026-10-06'})
        blocks = [{'locator':'SYNTH-date','text':'申請時程：至10月12日下午5:00止'}]
        events = extract_events(blocks, p, doc, pub)
        self.assertEqual([e['kind'] for e in events], ['announcement','student_deadline'])
        self.assertEqual(events[-1]['value'], '2026-10-12T17:00:00+08:00')
        self.assertNotIn('excerpt', events[-1])

    def test_since_publication_needs_two_refs_and_award_period_is_not_application(self):
        p = profile();doc = {'id':'SYNTH-doc','revision_id':'a'*64}
        blocks = [{'locator':'SYNTH-date','text':'即日起至本（115）年3月18日止受理申請。'},
                  {'locator':'SYNTH-award','text':'獎助期間115年7月1日至116年6月30日。'}]
        self.assertNotIn('application_start', [e['kind'] for e in extract_events(blocks,p,doc)])
        events = extract_events(blocks,p,doc,('2026-01-02',{'locator':'SYNTH-pub','text':'2026-01-02'}))
        start = next(e for e in events if e['kind']=='application_start')
        self.assertEqual(start['value'],'2026-01-02');self.assertIn('publication_ref',start)
        self.assertEqual(next(e for e in events if e['kind']=='student_deadline')['value'],'2026-03-18')
        self.assertEqual(extract_events(blocks,{**p,'role':'policy'},doc),[])

    def test_popup_discovery_is_literal_bounded_and_filters_private_urls(self):
        raw = b'''<main><a href="#" onclick="javascript:window.open('call.php?ID=2','news','scrollbars=yes');">SYNTH &#30003;&#35531;</a>
        <a href="https://evil.test/call">&#30003;&#35531;</a><a href="/login">&#30003;&#35531;</a>
        <a href="#" onclick="evil();window.open('/unsafe')">&#30003;&#35531;</a></main>'''
        links = discover_links(raw,'https://example.test/index',['example.test'])
        self.assertEqual([l['url'] for l in links],['https://example.test/call.php?ID=2'])

    def test_unchanged_parent_still_checks_child_and_parser_change_refetches(self):
        p,cfg,bundle=fixture();calls=[]
        raw=('<main>SYNTH '+('測試正文。'*20)+'<p>申請時程6/15-7/10</p><a href="/rule.pdf">辦法</a></main>').encode()
        def transport(url,headers,limit):
            calls.append((url,headers))
            if url.endswith('robots.txt'):return {'status':404,'headers':{},'body':b''}
            if url.endswith('/rule.pdf'):return {'status':403,'headers':{},'body':b''}
            return {'status':200,'headers':{'content-type':'text/html','etag':'SYNTH-v1'},'body':raw}
        first=scan_chains(cfg,bundle,fetcher=Fetcher(cfg,transport=transport),as_of='2026-11-01T00:00:00+00:00')
        def again(url,headers,limit):
            calls.append((url,headers))
            if url.endswith('robots.txt'):return {'status':404,'headers':{},'body':b''}
            if url.endswith('/rule.pdf'):return {'status':200,'headers':{},'body':b'unsupported'}
            return {'status':304,'headers':{},'body':b''} if headers.get('If-None-Match') else transport(url,headers,limit)
        second=scan_chains(cfg,bundle,first,Fetcher(cfg,transport=again),as_of='2026-11-02T00:00:00+00:00')
        self.assertEqual(next(d for d in second['documents'] if d['url']==p['url'])['status'],'unchanged_304')
        self.assertGreaterEqual(sum(url.endswith('/rule.pdf') for url,h in calls),2)
        self.assertEqual(second['model_calls'],0)
        changed=deepcopy(first);changed['documents'][0]['profile_sha256']='b'*64
        calls.clear();scan_chains(cfg,bundle,changed,Fetcher(cfg,transport=again))
        self.assertFalse(next(h for url,h in calls if url==p['url']).get('If-None-Match'))

    def test_reference_and_hash_only_boundaries(self):
        p,cfg,bundle=fixture()
        def transport(url,headers,limit):
            if url.endswith('robots.txt'):return {'status':404,'headers':{},'body':b''}
            return {'status':200,'headers':{'content-type':'text/html'},'body':('<main>SYNTH '+('合成。'*30)+'<p>申請時程6/15-7/10</p></main>').encode()}
        data=scan_chains(cfg,bundle,fetcher=Fetcher(cfg,transport=transport))
        self.assertTrue(validate(data))
        altered=deepcopy(data);altered['documents'][0]['events'][0]['revision_id']='0'*64
        with self.assertRaisesRegex(ValueError,'reference_or_revision'):validate(altered)
        altered=deepcopy(data);altered['documents'][0]['events'][0]['excerpt']='SYNTH forbidden'
        with self.assertRaisesRegex(ValueError,'hash_only'):validate(altered)

    def test_historical_forecast_does_not_train_on_current_year(self):
        p=profile();doc={'id':'SYNTH','revision_id':'a'*64}
        events=[]
        for year in (2025,2026):
            events+=extract_events([{'locator':'SYNTH','text':f'申請時程{year}/7/8至7/27'}],{**p,'application_year':year,'cycle':str(year)},doc)
        b=baselines(events,2026)[0]
        self.assertEqual(b['sample_years'],[2025]);self.assertEqual(b['kind'],'historical_reference')
        self.assertEqual(baselines(events,2027)[0]['sample_years'],[2025,2026])
        self.assertEqual(baselines(events,2025),[])
        with self.assertRaisesRegex(ValueError,'mixing'):
            baselines([*events,{**events[0],'scope':'OTHER'}],2027)

    def test_webform_article_and_publication_metadata_have_separate_roles(self):
        p,cfg,bundle=fixture();p['body_selector']='body'
        raw=('<html><body><form><main>SYNTH '+('合成。'*30)+'<p>申請時程6/15-7/10</p></main></form></body></html>').encode()
        def transport(url,headers,limit):
            return {'status':404 if url.endswith('robots.txt') else 200,'headers':{'content-type':'text/html'},'body':raw}
        result=scan_chains(cfg,bundle,fetcher=Fetcher(cfg,transport=transport))
        self.assertEqual(len(result['documents'][0]['events']),2)
        result['generated_at']='2026-12-31T18:00:00+00:00'
        self.assertEqual(timeline_metadata(result,bundle)['years'],[2027,2028])
        html='<script type="application/ld+json">'+json.dumps({'@graph':[
            {'@type':'Article','@id':'https://example.test/other','datePublished':'2025-01-01'},
            {'@type':'WebPage','@id':'https://example.test/call','datePublished':'2026-06-01','dateModified':'2026-07-01'}]})+'</script>'
        self.assertEqual(publication(BeautifulSoup(html,'html.parser'),[],'https://example.test/call')[0],'2026-06-01')

    def test_deferred_policy_children_rotate_without_losing_read_metadata(self):
        p,cfg,bundle=fixture();cfg['max_documents']=2
        def transport(url,headers,limit):
            if url.endswith('robots.txt'):return {'status':404,'headers':{},'body':b''}
            raw=('<html><body><main>SYNTH '+('合成。'*30)+'<a href="/policy-a">辦法A</a><a href="/policy-b">辦法B</a></main></body></html>').encode()
            return {'status':200,'headers':{'content-type':'text/html'},'body':raw}
        first=scan_chains(cfg,bundle,fetcher=Fetcher(cfg,transport=transport))
        self.assertEqual(next(d for d in first['documents'] if d['url'].endswith('policy-b'))['status'],'discovered_not_read')
        second=scan_chains(cfg,bundle,first,Fetcher(cfg,transport=transport))
        self.assertEqual(next(d for d in second['documents'] if d['url'].endswith('policy-b'))['status'],'changed')
        self.assertEqual(next(d for d in second['documents'] if d['url'].endswith('policy-a'))['status'],'changed')

    def test_expected_or_conflicting_history_is_not_a_baseline_and_cross_years_survive(self):
        p=profile();doc={'id':'SYNTH','revision_id':'a'*64}
        expected=extract_events([{'locator':'SYNTH','text':'預計申請時程6月15日至7月10日'}],p,doc)
        self.assertEqual(baselines(expected,2027),[])
        conflict=extract_events([{'locator':'SYNTH-a','text':'申請時程6月15日至7月10日下午5:00'},
            {'locator':'SYNTH-b','text':'申請時程6月15日至7月10日下午6:00'}],p,doc)
        self.assertEqual(len([e for e in conflict if e['kind']=='student_deadline']),2)
        self.assertEqual(baselines(conflict,2027),[])
        cross=extract_events([{'locator':'SYNTH','text':'申請時程2025/12/06至2026/01/06'}],p,doc)
        baseline=baselines(cross,2027)[0]
        self.assertEqual((baseline['start'],baseline['end']),('2026-12-06','2027-01-06'))
        arbitrary={'candidate_id':'SYNTH-new','program_key':p['program_key'],'title':'SYNTH自由補助第三梯次','cycle':{'kind':'academic_year'}}
        binding=candidate_bindings([arbitrary],{'sources':[{**p,'historical_baseline_allowed':False}]})[0]
        self.assertEqual(binding['phase'],'round3');self.assertFalse(binding['historical_baseline_allowed'])


if __name__=='__main__':unittest.main()
