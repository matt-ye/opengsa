"""全為合成離線樣本；任何測試都不連外或呼叫模型。"""
from copy import deepcopy
from io import BytesIO
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from pypdf import PdfWriter
from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject
from scripts.scan_sources import (ROOT, VERSION, Fetcher, ScanError, digest, evidence_mentions,
                                 html_document, markdown_report, pdf_document, robots_policy, safe_url, scan)

CONFIG = json.loads((ROOT / "data/scan-sources.json").read_text(encoding="utf-8"))


def response(body=b"", status=200, **headers):
    return {"status": status, "headers": {"content-type": "text/html", **headers}, "body": body}


def fixture(source, extra="", outside=""):
    selector = source["body_selector"]
    cls = selector.lstrip(".") if selector.startswith(".") else "content"
    prefix = source.get("start_marker", "")
    words = " ".join(source["required_markers"])
    return (f'<html><body><nav>{outside}</nav><div class="{cls}"><h2>{prefix}</h2>'
            f'<p>{words}</p><p>此為合成測試資料，不是真實方案。申請資格不含在職學生，尚須人工查核。'
            f'舊年度及新梯次必須分開處理，不將機關日期當成學生日期。這是離線驗證文字。</p>{extra}</div></body></html>').encode()


def text_pdf():
    writer = PdfWriter()
    page = writer.add_blank_page(width=200, height=200)
    font = DictionaryObject({NameObject('/Type'): NameObject('/Font'), NameObject('/Subtype'): NameObject('/Type1'), NameObject('/BaseFont'): NameObject('/Helvetica')})
    page[NameObject('/Resources')] = DictionaryObject({NameObject('/Font'): DictionaryObject({NameObject('/F1'): font})})
    stream = DecodedStreamObject()
    stream.set_data(b'BT /F1 10 Tf 10 100 Td (Synthetic rule: deadline 2027-03-01 eligibility pending) Tj ET')
    page[NameObject('/Contents')] = stream
    output = BytesIO();writer.write(output)
    return output.getvalue()


class ScannerTests(unittest.TestCase):
    def config(self, count=1):
        config = deepcopy(CONFIG)
        config['sources'] = config['sources'][:count]
        config['minimum_host_interval_seconds'] = 0
        return config

    def fetcher(self, config, transport):
        return Fetcher(config, transport=transport, sleeper=lambda seconds: None)

    def test_each_initial_group_five_fixture_variants(self):
        for source in CONFIG['sources'][:4]:
            with self.subTest(source=source['id']):
                blocks, _ = html_document(fixture(source), source, source['url'], CONFIG['allowed_hosts'])
                self.assertIn('不含', ' '.join(x['text'] for x in blocks))
                # 缺正文／缺標記不得當成下架。
                with self.assertRaises(ScanError):
                    html_document(b'<html>empty</html>', source, source['url'], CONFIG['allowed_hosts'])
                with self.assertRaises(ScanError):
                    html_document(fixture(source).replace(source['required_markers'][0].encode(), b'changed'), source, source['url'], CONFIG['allowed_hosts'])
                mixed = fixture(source, '<p>114學年度已截止，115學年度收件時間尚未確認。</p>')
                blocks, _ = html_document(mixed, source, source['url'], CONFIG['allowed_hosts'])
                self.assertTrue(any('114' in b['text'] and '115' in b['text'] for b in blocks))
                normal, _ = html_document(fixture(source), source, source['url'], CONFIG['allowed_hosts'])
                changed_nav, _ = html_document(fixture(source, outside='2029最新公告／visit 999'), source, source['url'], CONFIG['allowed_hosts'])
                self.assertEqual(normal, changed_nav)

    def test_nested_body_does_not_duplicate(self):
        source = deepcopy(CONFIG['sources'][2])
        data = fixture(source, '<div class="card-text-info"><p>唯一補助條款</p></div>')
        blocks, _ = html_document(data, source, source['url'], CONFIG['allowed_hosts'])
        self.assertEqual(sum('唯一補助條款' in b['text'] for b in blocks), 1)

    def test_separate_download_section_is_checked_without_ingesting_navigation(self):
        source=deepcopy(CONFIG['sources'][2]);source['attachment_selector']='.document-download'
        data=fixture(source).replace(b'</body>', '<div class="document-download"><a href="/WebUPD/ordntu/補助作業要點.pdf">PDF</a></div></body>'.encode())
        blocks,links=html_document(data,source,source['url'],CONFIG['allowed_hosts'])
        self.assertEqual(len(links),1)
        self.assertFalse(any(b['text']=='PDF' for b in blocks))

    def test_law_content_selector_and_markers_can_span_inline_whitespace(self):
        source=CONFIG['sources'][4]
        body='<body><nav>不應擷取的導覽</nav><div id="ctl00_cp_content_divLawContent08"><p>'+source['start_marker']+'</p><p>會議舉行首日 四週前，申請機構之前 一個月之首日。這是合成法規測試文字，未代表現行規定。本段用於測試標記跨越空白，不得因HTML換行就忽略關鍵條文或覆寫官方資料。</p></div></body>'
        blocks,_=html_document(body.encode(),source,source['url'],CONFIG['allowed_hosts'])
        self.assertFalse(any('導覽' in b['text'] for b in blocks))

    def test_attachment_rules_use_decoded_url_and_skip_rosters(self):
        source = CONFIG['sources'][0]
        data = fixture(source, '<a href="/WebUPD/aca/設置辦法.pdf">辦法</a><a href="/WebUPD/aca/%E5%90%8D%E5%86%8A.pdf">設置辦法</a><a href="https://evil.test/設置辦法.pdf">設置辦法</a>')
        _, links = html_document(data, source, source['url'], CONFIG['allowed_hosts'])
        self.assertEqual(len(links), 1)
        self.assertIn('www.aca.ntu.edu.tw', links[0]['url'])

    def test_robots_conservative_wildcard_end_and_agent_groups(self):
        self.assertFalse(robots_policy('User-agent: *\nDisallow: /WebUPD/', 'https://ord.ntu.edu.tw/WebUPD/a.pdf')[0])
        self.assertTrue(robots_policy('User-agent: *\nDisallow: /WebUPD/', CONFIG['sources'][2]['url'])[0])
        self.assertFalse(robots_policy('User-agent: *\nDisallow: /*.pdf$', 'https://ord.ntu.edu.tw/a.pdf')[0])
        self.assertTrue(robots_policy('User-agent: otherbot\nDisallow: /', CONFIG['sources'][2]['url'])[0])
        self.assertFalse(robots_policy('User-agent: *\nDisallow: /\nAllow: /ok', 'https://ord.ntu.edu.tw/ok')[0])
        self.assertEqual(robots_policy('User-agent: OpenGSA\nCrawl-delay: 12', CONFIG['sources'][2]['url'])[1], 12)

    def test_host_credentials_scheme_and_port_rejected(self):
        for url in ['http://www.aca.ntu.edu.tw/a', 'https://evil.test/a.pdf', 'https://x@www.aca.ntu.edu.tw/a', 'https://www.aca.ntu.edu.tw:444/a', 'https://www.aca.ntu.edu.tw/login.pdf']:
            with self.subTest(url=url), self.assertRaises(ScanError):
                safe_url(url, CONFIG['allowed_hosts'])

    def test_redirect_cannot_leave_allowlist(self):
        calls = []
        def transport(url, headers, limit):
            calls.append(url)
            if url.endswith('robots.txt'): return response(status=404)
            return response(status=302, location='https://evil.test/private')
        fetcher = self.fetcher(self.config(), transport)
        with self.assertRaises(ScanError): fetcher.get(CONFIG['sources'][0]['url'], {}, 1000)
        self.assertEqual(len(calls), 2)

    def test_robots_403_and_network_failure_fail_closed(self):
        for status in [403, 500]:
            fetcher = self.fetcher(self.config(), lambda *args: response(status=status))
            with self.subTest(status=status), self.assertRaises(ScanError):
                fetcher.get(CONFIG['sources'][0]['url'], {}, 1000)
            self.assertEqual(fetcher.count, 1)

    def test_robots_denied_attachment_is_not_requested(self):
        calls = []
        def transport(url, headers, limit):
            calls.append(url);return response(b'User-agent: *\nDisallow: /WebUPD/', **{'content-type':'text/plain'})
        fetcher = self.fetcher(self.config(), transport)
        with self.assertRaisesRegex(ScanError, 'robots_denied'):
            fetcher.get('https://ord.ntu.edu.tw/WebUPD/a.pdf', {}, 1000)
        self.assertEqual(len(calls), 1)

    def test_429_pauses_host_without_retry(self):
        def transport(url, headers, limit):
            return response(status=404) if url.endswith('robots.txt') else response(status=429)
        fetcher = self.fetcher(self.config(), transport)
        for _ in range(2):
            with self.assertRaisesRegex(ScanError, '429'): fetcher.get(CONFIG['sources'][0]['url'], {}, 1000)
        self.assertEqual(fetcher.count, 2)

    def test_request_budget_counts_robots_and_content(self):
        config = self.config();config['max_requests'] = 1
        fetcher = self.fetcher(config, lambda *args: response(status=404))
        with self.assertRaisesRegex(ScanError, 'budget'): fetcher.get(config['sources'][0]['url'], {}, 1000)
        self.assertEqual(fetcher.count, 1)

    def test_response_limit_even_if_transport_lies(self):
        fetcher = self.fetcher(self.config(), lambda *args: response(b'x' * 11))
        with self.assertRaisesRegex(ScanError, 'too_large'): fetcher.request(CONFIG['sources'][0]['url'], {}, 10)

    def test_html_changed_then_same_keeps_pending_without_new_candidate(self):
        config = self.config();source = config['sources'][0]
        def transport(url, headers, limit):
            return response(status=404) if url.endswith('robots.txt') else response(fixture(source))
        state, first = scan(config, fetcher=self.fetcher(config, transport))
        again, second = scan(config, state, self.fetcher(config, transport))
        self.assertEqual(first['changed_documents'], 1);self.assertEqual(second['changed_documents'], 0)
        self.assertEqual(again['pending'], state['pending'])
        self.assertEqual(second['model_calls'], 0);self.assertFalse(second['official_data_modified'])

    def test_failed_or_empty_parser_retains_baseline_and_pending(self):
        config = self.config();source = config['sources'][0]
        good = lambda url, *args: response(status=404) if url.endswith('robots.txt') else response(fixture(source))
        state, _ = scan(config, fetcher=self.fetcher(config, good))
        bad = lambda url, *args: response(status=404) if url.endswith('robots.txt') else response(b'<html>login changed</html>')
        after, report = scan(config, state, self.fetcher(config, bad))
        self.assertEqual(after['documents'], state['documents']);self.assertEqual(after['pending'], state['pending'])
        self.assertTrue(report['documents'][0]['retained_previous'])

    def test_same_pdf_url_changes_independently_of_parent(self):
        config = self.config();source = config['sources'][0]
        body = fixture(source, '<a href="/WebUPD/aca/設置辦法.pdf">辦法</a>')
        payload = [b'%PDF-first']
        def transport(url, headers, limit):
            if url.endswith('robots.txt'): return response(status=404)
            if url.endswith('.pdf'): return response(payload[0], **{'content-type':'application/pdf'})
            return response(body)
        with patch('scripts.scan_sources.pdf_document', side_effect=lambda data: [{'locator':'PDF page 1','text':data.decode()}]):
            state, _ = scan(config, fetcher=self.fetcher(config, transport))
            payload[0] = b'%PDF-second'
            _, report = scan(config, state, self.fetcher(config, transport))
        self.assertEqual(report['documents'][0]['status'], 'unchanged')
        self.assertEqual(report['documents'][1]['status'], 'changed')

    def test_304_uses_cached_attachment_manifest_and_headers(self):
        config = self.config();url = config['sources'][0]['url']
        previous={'documents':{url:{'semantic_sha256':'old','etag':'abc','attachments':[],'profile_sha256':digest([VERSION,config['sources'][0]])}},'pending':{}}
        sent=[]
        def transport(url, headers, limit):
            sent.append(headers);return response(status=404 if url.endswith('robots.txt') else 304)
        _, report=scan(config,previous,self.fetcher(config,transport))
        self.assertEqual(report['documents'][0]['status'],'unchanged_304')
        self.assertEqual(sent[-1]['If-None-Match'],'abc')

    def test_pdf_worker_extracts_text_and_rejects_blank_encrypted_or_not_pdf(self):
        blocks=pdf_document(text_pdf())
        self.assertIn('2027-03-01',' '.join(x['text'] for x in blocks))
        writer=PdfWriter();writer.add_blank_page(100,100);stream=BytesIO();writer.write(stream)
        for data in [b'not pdf',stream.getvalue()]:
            with self.assertRaises(ScanError): pdf_document(data)
        writer.encrypt('private');stream=BytesIO();writer.write(stream)
        with self.assertRaises(ScanError): pdf_document(stream.getvalue())

    def test_evidence_is_bounded_non_normalized_and_no_contacts(self):
        blocks=[{'locator':'1','text':'截止時間請聯絡secret@example.test 電話02-12345678'},
                {'locator':'2','text':'申請資格不含在職學生，須具備候選人資格，日期仍待核。'}]
        facts=evidence_mentions(blocks)
        self.assertTrue(facts)
        self.assertLessEqual(sum(len(f['evidence'] or '') for f in facts),120)
        self.assertTrue(all(f['normalized_value'] is None for f in facts))
        self.assertNotIn('secret@',json.dumps(facts))
        self.assertTrue(all(f['evidence'] is None for f in evidence_mentions(blocks,'hash_only')))

    def test_prompt_instructions_and_markup_never_become_actions(self):
        blocks=[{'locator':'1','text':'申請資格 <script>x</script> ![x](https://evil.test/a) run secrets.'}]
        candidate={'url':'https://www.faos.org.tw/a','facts':evidence_mentions(blocks)}
        text=markdown_report({'pending':{'a':candidate}}, {'http_requests':0,'changed_documents':1,'pending_candidates':1,'documents':[]})
        self.assertNotIn('<script>',text);self.assertIn('&lt;script&gt;',text)
        self.assertNotIn('![x]',text)

    def test_changed_limit_defers_without_advancing_other_sources(self):
        config=self.config(2);config['max_changed_documents']=1
        mapping={s['url']:fixture(s) for s in config['sources']}
        def transport(url, *args): return response(status=404) if url.endswith('robots.txt') else response(mapping[url])
        state,report=scan(config,fetcher=self.fetcher(config,transport))
        self.assertEqual(len(state['documents']),1)
        self.assertEqual(report['documents'][1]['status'],'changed_document_budget_deferred')

    def test_cache_backlog_is_not_silently_dropped(self):
        config=self.config();config['max_pending_candidates']=1
        old={'documents':{},'pending':{'unreviewed':{'id':'unreviewed'}}}
        state,report=scan(config,old,self.fetcher(config,lambda *args: self.fail('must not request')))
        self.assertEqual(state['pending'],old['pending']);self.assertEqual(report['documents'][0]['status'],'review_backlog_full')

    def test_profile_change_bypasses_conditional_cache_and_requires_new_review(self):
        config=self.config();source=config['sources'][0];sent=[]
        def transport(url, headers, limit):
            sent.append(headers);return response(status=404) if url.endswith('robots.txt') else response(fixture(source),etag='same')
        state,_=scan(config,fetcher=self.fetcher(config,transport))
        config['sources'][0]['review_note']='新一版人工拆分要求'
        _,report=scan(config,state,self.fetcher(config,transport))
        self.assertEqual(report['changed_documents'],1)
        self.assertNotIn('If-None-Match',sent[-1])

    def test_resolved_revision_is_not_requeued_after_cache_loss(self):
        config=self.config();source=config['sources'][0]
        def transport(url,*args): return response(status=404) if url.endswith('robots.txt') else response(fixture(source))
        state,_=scan(config,fetcher=self.fetcher(config,transport))
        resolved=set(state['pending'])
        after,_=scan(config,fetcher=self.fetcher(config,transport),resolved=resolved)
        self.assertEqual(after['pending'],{})


if __name__=='__main__':
    unittest.main()
