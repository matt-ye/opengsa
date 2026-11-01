"""Bounded source graph and evidence-backed timeline sidecar. Never approves candidates."""
import argparse
from html import unescape
from copy import deepcopy
from datetime import date, datetime, timezone, timedelta
import json
from pathlib import Path
import re
import sys
from urllib.parse import urljoin, urlsplit, unquote

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.scan_sources import Fetcher, ScanError, digest, html_document, pdf_document, safe_url
from scripts.document_ir import prepare_document, VERSION as IR_VERSION

VERSION = 'source-chain-1'
PARSER_VERSION = 'chain-parser-1.6'
DATE = re.compile(r'(?<!\d)(?:(20\d{2}|1\d{2})[年/.-])?(\d{1,2})[月/.-](\d{1,2})(?!\d)日?')
INTERVAL = re.compile(r'申請時程|申請時間|受理期間|即日起.*(?:受理|申請)|有意申請.*至')


def dates(text, year):
    """Dates in source order; never append a closing time that is not written."""
    text = re.sub(r'[（(](?:星期|週)?[一二三四五六日天][）)]', '', text)
    text = re.sub(r'本[（(](1\d{2})[）)]年', r'\1年', text)
    result = []
    for match in DATE.finditer(text):
        if match[1]:
            year = int(match[1]) + (1911 if len(match[1]) == 3 else 0)
        try:
            value = date(year, int(match[2]), int(match[3])).isoformat()
        except (ValueError, TypeError):
            continue
        tail = text[match.end():]
        clock = re.match(r'\s*(上午|下午|中午|早上)?\s*(\d{1,2})[:時點](\d{2})?', tail)
        if clock:
            hour, minute = int(clock[2]), int(clock[3] or 0)
            if clock[1] == '下午' and hour < 12:
                hour += 12
            if clock[1] in ('上午','早上') and hour == 12:
                hour = 0
            if hour >= 24 or minute >= 60:
                continue
            value += f'T{hour:02d}:{minute:02d}:00+08:00'
        result.append(value)
    return result


def discover_links(raw, url, hosts, selector=None):
    """Parse literal public links, including window.open; never execute source JS."""
    soup = BeautifulSoup(raw, 'html.parser')
    roots = soup.select(selector) if selector else soup.select('article, main, .article-center') or [soup.body or soup]
    found = {}
    for root in roots:
        for a in root.select('a'):
            if a.find_parent(['nav','header','footer']) or a.find_parent(attrs={'role':'navigation'}):
                continue
            label = a.get_text(' ', strip=True)
            attachment = a.find_parent(class_='file-download-multiple')
            if attachment:
                label = attachment.get_text(' ', strip=True)
            if not re.search(r'辦法|要點|申請|徵件|補助|獎學金|計畫|登記|查詢|表單|須知|流程', label):
                continue
            href = a.get('href', '')
            if href in ('', '#'):
                popup = re.fullmatch(r"\s*(?:javascript:)?window\.open\(['\"]([^'\"]+)['\"](?:\s*,[^;]*)?\);?\s*", a.get('onclick', ''))
                href = popup[1] if popup else ''
            if not href or href.startswith(('javascript:', 'mailto:')):
                continue
            try:
                target = safe_url(urljoin(url, unescape(href)), hosts)
            except (ScanError, ValueError):
                continue
            if target == safe_url(url, hosts):
                continue
            role = 'policy' if re.search(r'辦法|要點', label) else 'related_call'
            found[target] = {'url': target, 'role': role, 'label': label[:100]}
    # Real attachments precede menu/list links so a bounded page budget is useful.
    return sorted(found.values(), key=lambda link: not bool(re.search(r'\.pdf|\.docx?|Download|attachments/|filedownload',link['url'],re.I)))[:8]


def publication(soup, blocks, url=None):
    for selector, attr in [('meta[property="article:published_time"]', 'content'), ('time[datetime]', 'datetime')]:
        node = soup.select_one(selector)
        if node:
            values = dates(node.get(attr, ''), None)
            if values:
                return values[0][:10], {'locator': selector, 'text': str(node.get(attr))}
    for node in soup.select('script[type="application/ld+json"]'):
        try:
            data = json.loads(node.string or '')
            entries = data.get('@graph', [data]) if isinstance(data, dict) else []
            for entry in entries:
                if not isinstance(entry, dict) or entry.get('@type') not in ('Article', 'WebPage', 'NewsArticle'):
                    continue
                if url and unquote(str(entry.get('@id','')).split('#')[0]).rstrip('/') != unquote(url).rstrip('/'):
                    continue
                value = entry.get('datePublished', '')
                values = dates(value, None)
                if values:
                    return values[0][:10], {'locator': 'JSON-LD / datePublished', 'text': value}
        except (ValueError, TypeError):
            continue
    # A labeled publication date, not the footer update clock.
    for i, b in enumerate(blocks):
        if re.search(r'上版日期|發布時間|張貼時間', b['text']):
            text = ' '.join(x['text'] for x in blocks[i:i+2])
            values = dates(text, None)
            if values:
                return values[0][:10], {'locator': b['locator'], 'text': text}
    # Some article templates present publication as a separate small element.
    for node in soup.select('[class*="date"], [class*="Date"]'):
        text = node.get_text(' ', strip=True)
        if re.fullmatch(r'20\d{2}[-/]\d{2}[-/]\d{2}', text):
            return text.replace('/', '-'), {'locator': 'publication-date element', 'text': text}
    return None, None


def extract_events(blocks, profile, doc, published=None):
    """Source-independent date group. Policies do not create current calls."""
    if profile['role'] == 'policy' or profile.get('extract_dates') is False:
        return []
    events = []
    def add(kind, value, block, basis='explicit'):
        if not value:
            return
        event = {k: profile[k] for k in ('program_key', 'scope', 'cycle', 'application_year', 'phase')}
        event.update(kind=kind, value=value, basis=basis, document_id=doc['id'], revision_id=doc['revision_id'],
                     timezone='Asia/Taipei',
                     locator=block['locator'], block_sha256=digest(block['text'].encode()),
                     review_status='pending', certainty='expected' if re.search(r'預計|預定', block['text']) else 'announced')
        if profile['evidence_mode'] == 'short_excerpt':
            event['excerpt'] = block['text'][:120]
        # Same day may occur in title without a time; retain the more precise body event.
        old = next((e for e in events if e['kind'] == kind and e['value'][:10] == value[:10]), None)
        if old:
            if old['value']==value or (len(old['value'])>10 and len(value)==10):
                return old
            if len(old['value'])==10 and len(value)>10:
                events.remove(old)
        event['id'] = 'event-' + digest(event)[:24]
        events.append(event)
        return event
    if published:
        add('announcement', published[0], published[1])
    for block in blocks:
        text = block['text']
        values = dates(text, profile['application_year'])
        if not values or re.search(r'獎助期間|補助期間|購買期間|聘任期間|報到|學位考試', text):
            continue
        if INTERVAL.search(text):
            if len(values) == 2 and re.search(r'至|到|[~～]|\d\s*-\s*\d', text):
                add('application_start', values[0], block)
                add('student_deadline', values[1], block)
            elif len(values) == 1 and re.search(r'截止|至|止', text):
                add('student_deadline', values[0], block)
                if '即日起' in text and published:
                    # Two pieces of evidence are needed for this derivation.
                    start_event = add('application_start', published[0], block, 'since_publication')
                    start_event['publication_ref'] = {'locator': published[1]['locator'],
                        'block_sha256': digest(published[1]['text'].encode())}
        elif len(values) == 1:
            kind = next((kind for pattern, kind in [
                (r'補件|補正', 'supplement_deadline'), (r'學院.*送|院送校', 'college_forward'),
                (r'校.*彙送|校送', 'university_forward'), (r'核定.*名單|校核定', 'decision'),
                (r'公布.*結果|結果公告', 'result_publication'), (r'報支|撥款', 'payment')]
                if re.search(pattern, text)), None)
            if kind:
                add(kind, values[0], block)
    remaining=120
    for e in events:
        if 'excerpt' in e:
            if remaining:
                e['excerpt']=e['excerpt'][:remaining]
                remaining-=len(e['excerpt'])
            else:
                e.pop('excerpt')
        e['id'] = 'event-' + digest({k:v for k,v in e.items() if k!='id'})[:24]
    return events


def candidate_documents(bundle):
    docs = {}
    for cand in bundle['candidates']:
        m = cand['source_metadata']
        key = 'doc-' + digest(m['url'])[:24]
        doc = docs.setdefault(key, {'id': key, 'url': m['url'], 'format': 'pdf' if urlsplit(m['url']).path.lower().endswith('.pdf') else 'html',
            'revision_id': m['revision_id'], 'observed_at': m['observed_at'], 'status': 'candidate_snapshot',
            'evidence_mode': m['evidence_mode'], 'candidate_ids': [], 'events': [], 'links': []})
        doc['candidate_ids'].append(cand['candidate_id'])
    return docs


def candidate_bindings(candidates, config):
    result=[]
    for c in candidates:
        # A phase comes from an existing label, never a particular source/program ID.
        match=re.search(r'第([一二三四五六七八九]|\d+)(?:梯|階段)', c['title'])
        phase='all'
        if match and c['cycle']['kind']!='policy_snapshot':
            number=str('一二三四五六七八九'.index(match[1])+1) if match[1] in '一二三四五六七八九' else match[1]
            phase='round'+number
        result.append({'candidate_id':c['candidate_id'],'program_key':c['program_key'],'phase':phase,
            'historical_baseline_allowed':all(p.get('historical_baseline_allowed',True)
                for p in config['sources'] if p['program_key']==c['program_key'])})
    return result


def scan_chains(config, bundle, previous=None, fetcher=None, as_of=None):
    previous = previous or {'documents': []}
    as_of = as_of or datetime.now(timezone.utc).isoformat(timespec='seconds')
    docs = candidate_documents(bundle)
    old_by_url = {d['url']: d for d in previous['documents']}
    # Preserve already-read policy metadata while rotating deferred policy children.
    # Calls are always processed from the current explicit registry; removed calls
    # cannot survive as active events through the cache.
    for old in previous['documents']:
        if old.get('role')=='policy' and not old.get('events') and old['id'] not in docs:
            docs[old['id']]=deepcopy(old)
    fetcher = fetcher or Fetcher(config)
    queue = [(deepcopy(p), 0) for p in config['sources']]
    seen, fetched_urls, relations, reports = set(), set(), [], []
    schema_sha = digest((ROOT/'schema/source-chains.schema.json').read_bytes())
    while queue:
        queue.sort(key=lambda task:(task[1]>0, old_by_url.get(task[0]['url'],{}).get('status') in ('changed','unchanged','unchanged_304')))
        p, depth = queue.pop(0)
        key = (p['url'], p['program_key'], p['scope'], p['phase'])
        if key in seen:
            continue
        if len(fetched_urls) >= config['max_documents'] and p['url'] not in fetched_urls:
            reports.append({'url': p['url'], 'status': 'document_budget_deferred'})
            continue
        seen.add(key)
        doc_id = 'doc-' + digest(p['url'])[:24]
        for parent in p.get('parent_urls', []):
            relations.append({'from': 'doc-' + digest(parent)[:24], 'to': doc_id, 'url': p['url'],
                              'role': p['role'], 'program_key': p['program_key'], 'scope': p['scope'], 'cycle': p['cycle']})
        if p['url'] in fetched_urls:
            continue
        fetched_urls.add(p['url'])
        fingerprint = digest([VERSION, PARSER_VERSION, IR_VERSION, schema_sha, p])
        old = old_by_url.get(p['url'], {})
        cache = old if old.get('profile_sha256') == fingerprint else {}
        doc = {'id': doc_id, 'url': p['url'], 'candidate_ids': docs.get(doc_id, {}).get('candidate_ids', []),
            'evidence_mode': p['evidence_mode'], 'observed_at': as_of, 'events': [], 'links': [],
            'profile_sha256': fingerprint, 'role': p['role']}
        try:
            response = fetcher.get(p['url'], cache, 2_000_000)
            if response['status'] == 304:
                if not cache.get('revision_id'):
                    raise ScanError('unexpected_304_without_baseline')
                doc.update(deepcopy(cache), observed_at=as_of, status='unchanged_304')
            elif response['status'] == 200:
                raw = response['body']
                kind = 'pdf' if raw.startswith(b'%PDF') else 'html' if 'text/html' in response['headers'].get('content-type', '').lower() else 'unsupported'
                if kind == 'unsupported':
                    raise ScanError('unsupported_format')
                if kind == 'html':
                    source = {'body_selector': p['body_selector'], 'required_markers': p['required_markers'], 'pdf_include': [], 'max_pdfs': 0}
                    soup = BeautifulSoup(raw, 'html.parser')
                    # ASP.NET public articles often live inside a page-wide form.
                    # Drop credential forms; unwrap public wrappers instead of losing the article.
                    for form in soup.select('form'):
                        if form.select('input[type="password"]'):
                            form.decompose()
                        else:
                            form.unwrap()
                    blocks, _ = html_document(str(soup).encode(), source, response['url'], config['allowed_hosts'])
                    links = discover_links(raw, response['url'], config['allowed_hosts'], p.get('link_selector'))
                    published = publication(BeautifulSoup(raw, 'html.parser'), blocks, response['url'])
                    published = published if published[0] else None
                else:
                    blocks, links, published = pdf_document(raw), [], None
                    if any(marker not in ''.join(b['text'] for b in blocks) for marker in p['required_markers']):
                        raise ScanError('required_marker_missing')
                ir = prepare_document(blocks)
                if hasattr(fetcher,'in_memory_blocks'):
                    fetcher.in_memory_blocks[p['url']] = blocks
                    fetcher.in_memory_raw_sha256[p['url']] = digest(raw)
                semantic = digest([ir['document_sha256'], links])
                doc.update(format=kind, semantic_sha256=semantic, raw_sha256=digest(raw), links=links,
                           etag=response['headers'].get('etag'), last_modified=response['headers'].get('last-modified'),
                           revision_id=digest([p['url'], semantic, fingerprint]),
                           status='unchanged' if cache.get('semantic_sha256') == semantic else 'changed')
                if doc['status'] == 'unchanged':
                    doc['events'] = deepcopy(cache['events'])
                else:
                    doc['events'] = extract_events(blocks, p, doc, published)
                # Original source text stays in memory. All events derive from bounded source blocks.
            else:
                raise ScanError('http_' + str(response['status']))
            for link in doc['links']:
                child_id = 'doc-' + digest(link['url'])[:24]
                relations.append({'from': doc_id, 'to': child_id, 'url': link['url'], 'role': link['role'],
                                  'program_key': p['program_key'], 'scope': p['scope'], 'cycle': p['cycle']})
                # Automatic expansion is restricted to policy evidence. An arbitrary
                # new call cannot inherit its parent's year, phase or local intake scope.
                if depth < config['max_depth'] and link['role'] == 'policy':
                    if urlsplit(link['url']).path.lower().endswith(('.odt', '.docx', '.doc', '.xlsx')):
                        reports.append({'url': link['url'], 'status': 'format_parser_deferred'})
                    else:
                        child = {**p, 'url': link['url'], 'role': 'policy', 'body_selector': 'body',
                                 'required_markers': [], 'parent_urls': []}
                        queue.append((child, depth + 1))
        except (ScanError, ValueError, TimeoutError) as error:
            doc.update(status=str(error), format=old.get('format', 'unknown'), events=[])
            if old.get('events'):
                doc['previous_revision_id'] = old['revision_id']
            reports.append({'url': p['url'], 'status': str(error)})
        docs[doc_id] = doc
    result = {'schema_version': VERSION, 'generated_at': as_of, 'model_calls': 0, 'official_data_modified': False,
        'documents': list(docs.values()), 'relations': relations, 'scopes': config['scopes'],
        'candidate_bindings': candidate_bindings(bundle['candidates'],config),
        'http_requests': fetcher.count, 'reports': reports}
    # A discovered link is a node even when its format/access/budget deferred reading.
    for relation in relations:
        if relation['to'] not in docs:
            docs[relation['to']] = {'id': relation['to'], 'url': relation['url'], 'format': 'unknown',
                'observed_at': as_of, 'status': 'discovered_not_read', 'evidence_mode': 'hash_only',
                'events': [], 'links': [], 'candidate_ids': []}
    result['documents'] = list(docs.values())
    validate(result)
    return result


def validate(bundle):
    """Referential/version and time checks, separate from parsing; no human approval."""
    from jsonschema import Draft202012Validator, FormatChecker
    schema = json.loads((ROOT/'schema/source-chains.schema.json').read_text(encoding='utf-8'))
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(bundle)
    docs = {d['id']: d for d in bundle['documents']}
    if len(docs) != len(bundle['documents']):
        raise ValueError('duplicate_document_id')
    for relation in bundle['relations']:
        if relation['from'] not in docs or relation['to'] not in docs or docs[relation['to']]['url'] != relation['url']:
            raise ValueError('dangling_relation')
    ids = set()
    for d in docs.values():
        if d['id'] != 'doc-' + digest(d['url'])[:24]:
            raise ValueError('document_url_identity_mismatch')
        safe_url(d['url'], [urlsplit(d['url']).hostname])
        if not urlsplit(d['url']).hostname or sum(len(e.get('excerpt','')) for e in d['events'])>120:
            raise ValueError('invalid_host_or_document_excerpt_budget')
        for e in d['events']:
            if e['id'] in ids or e['document_id'] != d['id'] or e['revision_id'] != d.get('revision_id'):
                raise ValueError('invalid_event_reference_or_revision')
            ids.add(e['id'])
            date.fromisoformat(e['value'][:10])
            if len(e['value']) > 10:
                datetime.fromisoformat(e['value'])
                if not e['value'].endswith('+08:00'):
                    raise ValueError('timeline_timezone_required')
            if d['evidence_mode'] == 'hash_only' and 'excerpt' in e:
                raise ValueError('hash_only_excerpt_forbidden')
            if e['basis'] == 'since_publication' and not e.get('publication_ref'):
                raise ValueError('publication_evidence_required')
            if e['id'] != 'event-' + digest({k:v for k,v in e.items() if k!='id'})[:24]:
                raise ValueError('event_fingerprint_mismatch')
    return True


def baselines(events, year):
    """Only prior comparable cycles. Never use the forecast year as training data."""
    if len({(e['program_key'],e['scope'],e['phase']) for e in events}) > 1:
        raise ValueError('historical_scope_or_phase_mixing')
    grouped = {}
    for e in events:
        if e['application_year'] >= year or e['certainty']!='announced' or e['kind'] not in ('application_start', 'student_deadline'):
            continue
        grouped.setdefault((e['application_year'], e['phase']), {}).setdefault(e['kind'],[]).append(e)
    windows=[]
    for values in grouped.values():
        if len(values)!=2 or any(date_conflict([e['value'] for e in records]) for records in values.values()):
            continue
        window={k:max(records,key=lambda e:len(e['value'])) for k,records in values.items()}
        if window['application_start']['value']<=window['student_deadline']['value']:
            windows.append(window)
    if not windows:
        return []
    starts = [v['application_start']['value'][5:10] for v in windows]
    ends = [v['student_deadline']['value'][5:10] for v in windows]
    offsets={(int(v['application_start']['value'][:4])-v['application_start']['application_year'],
              int(v['student_deadline']['value'][:4])-v['student_deadline']['application_year']) for v in windows}
    if len(offsets)!=1:
        return []
    start_offset,end_offset=next(iter(offsets))
    try:
        start, end = f'{year+start_offset}-{min(starts)}', f'{year+end_offset}-{max(ends)}'
        date.fromisoformat(start); date.fromisoformat(end)
    except ValueError:
        return []  # Leap-day projection needs explicit treatment, never silently shift.
    return [{'start': start, 'end': end, 'kind': 'historical_estimate' if len(windows) >= 2 else 'historical_reference',
        'sample_years': sorted({v['application_start']['application_year'] for v in windows}),
        'event_ids': [e['id'] for v in windows for e in v.values()], 'confidence': 'low' if len(windows) < 3 else 'reference'}]


def date_conflict(values):
    return len({v[:10] for v in values})>1 or len({v for v in values if len(v)>10})>1


def timeline_metadata(bundle, candidates):
    """Read-only scoped projection. No mutation of candidate eligibility or approvals."""
    validate(bundle)
    current_year = datetime.fromisoformat(bundle['generated_at']).astimezone(timezone(timedelta(hours=8))).year
    years = [current_year, current_year + 1]
    records = {}
    current_ids = {c['candidate_id']: c['program_key'] for c in candidates['candidates']}
    current_candidates={c['candidate_id']:c for c in candidates['candidates']}
    for binding in bundle['candidate_bindings']:
        if binding['candidate_id'] not in current_ids:
            continue
        if current_ids.get(binding['candidate_id']) != binding['program_key']:
            raise ValueError('candidate_binding_mismatch')
        entries = []
        documents = [d for d in bundle['documents'] if d['events'] and d['status'] in ('changed','unchanged','unchanged_304')]
        metadata=current_candidates[binding['candidate_id']].get('source_metadata',{})
        own_documents={d['id'] for d in documents if d['url']==metadata.get('url') and d.get('revision_id')==metadata.get('revision_id')
            and len({e['program_key'] for e in d['events']})==1}
        for scope in bundle['scopes']:
            # Phase stays separate, even for a broad policy snapshot.
            relevant = [e for d in documents for e in d['events'] if e['scope']==scope['id'] and (e['program_key']==binding['program_key'] or d['id'] in own_documents)
                        and binding['phase'] in ('all',e['phase'])]
            for phase in sorted({e['phase'] for e in relevant}):
                phase_events = [e for e in relevant if e['phase']==phase]
                for year in years:
                    events = [e for e in phase_events if e['application_year']==year]
                    starts = [e['value'] for e in events if e['kind']=='application_start' and e['certainty']=='announced']
                    ends = [e['value'] for e in events if e['kind']=='student_deadline' and e['certainty']=='announced']
                    conflict = date_conflict(starts) or date_conflict(ends) or bool(starts and ends and min(starts)>max(ends))
                    # 115 central NSTC scheme changed: do not forecast across its old edition.
                    baseline = baselines(phase_events,year) if binding.get('historical_baseline_allowed',True) else []
                    entries.append({'scope':scope['id'],'scope_label':scope['label'],'year':year,'phase':phase,
                        'events':events,'baselines':baseline,'conflict':conflict,
                        'document_ids':sorted({e['document_id'] for e in phase_events})})
        records[binding['candidate_id']] = {'contexts': entries}
    return {'version': VERSION, 'years': years, 'scopes': bundle['scopes'], 'records': records,
            'documents': [{'id':d['id'],'url':d['url'],'format':d['format'],'status':d['status'],
                'role':d.get('role','candidate_snapshot'),'revision_id':d.get('revision_id'),
                'checked_on':datetime.fromisoformat(d['observed_at']).astimezone(timezone(timedelta(hours=8))).date().isoformat()
                } for d in bundle['documents']], 'relations':bundle['relations']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=ROOT/'data/source-chain-sources.json')
    parser.add_argument('--previous', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.resolve().is_relative_to(ROOT/'data'):
        parser.error('Write a new work artifact; importing a snapshot requires a separate explicit step')
    if args.output.exists():
        parser.error('Use a new output file; existing artifacts are preserved')
    config = json.loads(args.config.read_text(encoding='utf-8'))
    if (not 0 < config['max_requests'] <= 20 or not 0 < config['max_documents'] <= 12 or not 0 <= config['max_depth'] <= 3
            or not 0 < config['max_run_seconds'] <= 180 or config['minimum_host_interval_seconds'] < 3):
        parser.error('Invalid bounded scan budget')
    bundle = json.loads((ROOT/'data/candidates/source-review.json').read_text(encoding='utf-8'))
    previous = json.loads(args.previous.read_text(encoding='utf-8')) if args.previous else None
    result = scan_chains(config, bundle, previous)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({'documents': len(result['documents']), 'events': sum(len(d['events']) for d in result['documents']),
        'http_requests': result['http_requests'], 'model_calls': 0, 'reports': result['reports']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
