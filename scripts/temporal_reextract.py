"""Bounded, rules-only temporal replay. Originals stay in memory; output is pending.

This sidecar deliberately does not rewrite qualification fields or rebind old
source-chain evidence to a newer page. Every temporal claim has its own revision.
"""
import argparse
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.scan_sources import Fetcher, ScanError, digest, node_get
from scripts.verify_original_sources import prepare_public
from scripts.document_ir import prepare_document
from scripts.review_candidates import candidate_fingerprint
from scripts.time_policy import policy_validator, project_time_policy
from scripts.semantic_facts import INJECTION, recurring_time, time_actor, discover_identity, labelled_date_clause
from scripts.extract_candidates import (
    extract_from_in_memory_blocks, parse_date_range_from_text,
    parse_roc_or_iso_date_from_text,
)

VERSION = 'temporal-replay-1'
ROUND_REQUEST_LIMIT = 200
TIMING = re.compile(r'申請|受理|收件|截止|送件|applications?|deadline',re.I)


def timing_contexts(blocks):
    """Join labelled dates/short PDF continuations, never cross a row or heading.

    HTML frequently puts a timing label and its value in separate text nodes.
    A bounded context is needed before date parsing, not a model-sized blob.
    """
    for index, block in enumerate(blocks):
        text=block['text']
        units=[block]
        if block.get('kind')=='table_cell' and block.get('structure_status')=='preserved':
            text=' '.join(block.get('row_cells') or [text])
        if TIMING.search(text) and len(text)<180 and not re.search(r'[。；;]$',text.strip()):
            for following in blocks[index+1:index+4]:
                if (following.get('page')!=block.get('page')
                        or following.get('kind') in ('heading','table_cell')
                        or block.get('kind')=='table_cell'
                        or following.get('section_path',[])!=block.get('section_path',[])
                        or INJECTION.search(following['text'])
                        or re.match(r'^(?:第[一二三四五六七八九十]+條|[一二三四五六七八九十]+[、.])',following['text'].strip())):
                    break
                text+=' '+following['text'];units.append(following)
                if re.search(r'[。；;]$',following['text'].strip()) or len(text)>240:
                    break
        yield {**block,'text':text,'locator':' + '.join(u['locator'] for u in units)}


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def save(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')


def extract_policy(candidate, blocks, profile, revision, observed):
    """Reuse specialized parsers, then discover explicit timing clauses generically.

    No title-derived year, publication-as-start, missing-date-as-rolling, or
    institution-as-student fallback. Unanchored month/day remains a text rule.
    """
    identity=discover_identity(blocks)
    student_document=bool(identity and identity['kind']=='eligibility_clause' and identity['degrees'])
    fresh = extract_from_in_memory_blocks(profile, blocks, revision, observed,
        url=candidate['source_metadata']['url'], extraction_strategy='rules_only')
    matches = [c for c in fresh if c['program_key'] == candidate['program_key']]
    selected = matches[0] if len(matches) == 1 else fresh[0] if len(fresh) == 1 else None
    policy = project_time_policy(selected) if selected else {
        'version':'time-policy-1', 'submission_mode':'undetermined',
        'review_mode':'not_stated', 'rules':[], 'gaps':['time_not_projected']}
    # Shared announcements with multiple branches require branch-aware parsing.
    if len(fresh) > 1:
        return policy
    rules = policy['rules']
    # Generic legacy clauses discarded extra deadlines sharing the same note.
    # Rebuild those from bounded contexts; retain the specialized rule branches.
    rules[:]=[r for r in rules if r['summary'] not in ('角色依本段辨識；未載學生期限時不以其他層級回填','學生受理期間明示起日')]
    def add(block, kind, actor, stage, summary, value=None, precision='rule'):
        claim = {'rule_id':f"replay/{len(rules)}", 'kind':kind, 'actor':actor,
            'stage':stage, 'summary':summary, 'value':value, 'precision':precision,
            'anchor_event':None, 'source_refs':[{'source':profile['id'],
                'revision_id':revision, 'locator':block['locator'],
                'evidence_path':'temporal_replay/'+stage}]}
        if not any((r['actor'],r['stage'],r['value'],r['kind'],r['summary']) ==
                   (actor,stage,value,kind,summary) for r in rules):
            rules.append(claim)

    for block in timing_contexts(blocks):
        if INJECTION.search(block['text']):
            continue
        text = re.sub(r'\s+', '', block['text'])
        # Sentences retain their own year and actor. Never join unrelated dates.
        for clause in re.split(r'[。；;\n]', text):
            if not clause or re.search(r'修正|生效|出生|年齡|購買|支出|訂閱|給付|補助期間|獎助期間', clause):
                continue
            if re.search(r'隨到隨審', clause) and not re.search(r'不採|非|停止|暫停', clause):
                add(block, 'review_cadence', 'other', 'review', '審查採隨到隨審；不等同全年受理')
                policy['review_mode'] = 'rolling'
            if not re.search(r'申請|受理|收件|送件|apply|applications?', clause, re.I):
                continue
            actor = time_actor(clause)
            if re.search(r'同學|研究生|學生|申請人|申請者|送(?:交|至).{0,12}(?:系辦|所辦)', clause):
                actor = 'student' if actor == 'unit' else actor
            if actor=='unit' and student_document and not re.search(r'學校|學院|系所|彙送|推薦名單|備函',clause):
                actor='student'
            if re.search(r'不受理|停止受理|暫停受理|不得申請|不採隨', clause):
                continue
            if re.search(r'全年(?:均可|皆可|開放)?(?:受理|申請)|隨時(?:均可|皆可|可以|可)?(?:提出)?申請|常年受理|applications?(?:are)?accepted(?:year.round|onarollingbasis)', clause, re.I):
                add(block, 'continuous', actor, 'submission', '來源明示常態受理；仍須核對資格及額度')
            elif re.search(r'(?:申請|收件|受理).{0,60}(?:依|洽|由).{0,25}(?:各|所屬).{0,12}(?:院系所|系所|學院|單位).{0,25}(?:公告|規定|訂定|自訂|確認)|(?:各|所屬)(?:系所|學院).{0,20}(?:自訂|訂定).{0,15}(?:申請|截止|收件)|(?:申請|收件)(?:時間|期限|時程).{0,20}(?:逕洽|洽詢).{0,15}(?:院系所|系所|學院|單位)', clause):
                add(block, 'unit_announced', actor, 'submission', '申請收件時程由所屬單位另訂／公告')
            if re.search(r'(?:每年|每學期).{0,20}(?:受理|申請|收件)|(?:申請|受理|收件).{0,15}(?:每年|每學期)',clause) and not recurring_time(clause):
                add(block,'recurring',actor,'submission','來源明示週期性受理；當期具體日期另查')
            # Existing specialized relative/calendar rules take precedence.
            if recurring_time(clause) or re.search(r'每年|每學期|會前|出國前|活動前|前.{0,5}(?:週|個月|天)', clause):
                continue
            if not re.search(r'申請期間|申請時程|申請時間|受理期間|收件期間|申請期限|申請截止|截止|請於.{0,80}(?:申請|送|繳)', clause):
                continue
            if re.search(r'出國期間|活動期間|研修期間|培育期間|獎勵期間|公布結果', clause):
                continue
            labelled=labelled_date_clause(clause)
            start, end = parse_date_range_from_text(labelled or '')
            # Explicit student directions are needed for a student range.
            # Otherwise preserve dates as unit procedure instead of making a bar.
            if start and end:
                if not any(r['actor']==actor and r['stage']=='application_start' and r['value']==start for r in rules):
                    add(block, 'absolute', actor, 'application_start', '來源明示受理起日', start, 'date')
                kind, value = parse_roc_or_iso_date_from_text(re.split(r'至|到|[~～]',labelled)[-1], int(end[:4])-1911)
                value = value if value and value[:10]==end else end
                if not any(r['actor']==actor and r['stage']=='submission' and r['value']==value for r in rules):
                    add(block, 'absolute', actor, 'submission', '來源明示收件截止', value, kind if value!=end else 'date')
            else:
                kind, value = parse_roc_or_iso_date_from_text(labelled or '')
                if value and re.search(r'截止|前|止|期限', clause):
                    if not any(r['actor']==actor and r['stage']=='submission' and r['value']==value for r in rules):
                        add(block, 'absolute', actor, 'submission', '來源明示收件截止', value, kind)
                elif not value and re.search(r'截止|期限|期間|時程|時間',clause):
                    month_days=list(dict.fromkeys(re.findall(r'(?<!\d)(\d{1,2})[月/](\d{1,2})(?:日)?',clause)))
                    if month_days:
                        summary='來源列示月日：'+'、'.join(f'{int(m)}月{int(d)}日' for m,d in month_days if 1<=int(m)<=12 and 1<=int(d)<=31)
                        if not summary.endswith('：'):
                            add(block,'text_rule',actor,'submission',summary+'；年份與起訖角色須查原文')

    # Keep specialized conditional/event-relative semantics; generic modes are
    # determined only by evidenced claims, never by programme/category names.
    if policy['submission_mode'] not in ('conditional_deadline','automatic','reference','event_relative','recurring','mixed'):
        submission = [r for r in rules if r['stage'] != 'review']
        kinds = {r['kind'] for r in submission}
        student = [r for r in submission if r['actor']=='student' and r['kind']=='absolute']
        if 'recurring' in kinds:
            policy['submission_mode']='recurring' if kinds=={'recurring'} else 'mixed'
        elif 'continuous' in kinds or 'unit_announced' in kinds:
            policy['submission_mode'] = 'continuous' if kinds=={'continuous'} else 'unit_announced' if kinds=={'unit_announced'} else 'mixed'
        elif student:
            start=any(r['stage']=='application_start' for r in student)
            end=any(r['stage']=='submission' for r in student)
            policy['submission_mode']='fixed_window' if start and end else 'deadline_only' if end else 'start_only'
        elif submission:
            policy['submission_mode']='procedure_only' if kinds=={'absolute'} else 'rule_text'
        elif rules:
            policy['submission_mode']='review_only'
    if not rules and policy['submission_mode'] not in ('automatic','reference'):
        policy['submission_mode']='undetermined'
    if rules:
        policy['gaps']=[g for g in policy['gaps'] if g not in ('time_not_projected','student_window_not_recorded')]
        if not any(r['actor']=='student' and r['stage']=='submission' for r in rules):
            policy['gaps'].append('student_window_not_recorded')
    policy_validator().validate(policy)
    return policy


def replay(output, previous=None, transport=node_get, source_ids=None, retry_unclassified=False, recheck=False):
    """One micro-batch <=8 URLs/20 HTTP/180 seconds; whole round <=200 HTTP.

    Resume artifacts contain no original text. Previous attempts (including
    blocked reads) are never retried automatically or reset silently.
    """
    output=Path(output).resolve()
    if not output.is_relative_to(ROOT/'work') or output.exists():
        raise ValueError('new_work_output_required')
    candidates=read(ROOT/'data/candidates/source-review.json')['candidates']
    config=read(ROOT/'data/scan-sources.json')
    profiles={p['id']:p for p in config['sources']}
    state=read(previous) if previous else {'version':VERSION,'http_requests':0,'model_calls':0,'published':False,'batches':[],'records':{}}
    if state['version']!=VERSION or state['model_calls']!=0 or state['published'] or state['http_requests']>=ROUND_REQUEST_LIMIT:
        raise ValueError('invalid_round_state_or_exhausted_budget')
    audit={r['url']:r for r in read(ROOT/'data/source-expansion/original-source-verification.json')['records']}
    urls={}
    if recheck and not source_ids:
        raise ValueError('explicit_source_ids_required_for_recheck')
    for c in candidates:
        old=state['records'].get(c['candidate_id'],{})
        retry=(recheck and old.get('status')=='replayed') or (retry_unclassified and old.get('status')=='replayed' and old['policy']['submission_mode']=='undetermined' and not old.get('history'))
        if (not old or retry) and (not source_ids or c['source_metadata']['source_id'] in source_ids):
            urls.setdefault(c['source_metadata']['url'],[]).append(c)
    output.mkdir(parents=True)
    batch={'http_requests':0,'attempted_urls':[], 'observed_at':datetime.now(timezone.utc).isoformat(timespec='seconds')}
    state['batches'].append(batch)
    def request(url, headers, limit):
        batch['http_requests']+=1
        state['http_requests']+=1
        save(output/'temporal-observations.json',state)
        return transport(url,headers,limit)
    fetcher=Fetcher({'allowed_hosts':config['allowed_hosts'],'max_requests':min(20,ROUND_REQUEST_LIMIT-state['http_requests']),
        'max_run_seconds':180,'minimum_host_interval_seconds':3},transport=request)
    for url, group in list(urls.items())[:8]:
        batch['attempted_urls'].append(url)
        records={c['candidate_id']:{'candidate_sha256':candidate_fingerprint(c),'url':url,
            'status':'not_replayed','reason':None,'observed_at':batch['observed_at']} for c in group}
        for cid,record in records.items():
            if cid in state['records']:
                record['history']=[state['records'][cid]]
        try:
            if not audit.get(url,{}).get('content_verified'):
                raise ScanError('previous_access_review_required')
            response=fetcher.get(url,{},10*1024*1024)
            if response['status']!=200:
                raise ScanError('http_'+str(response['status']))
            prepared=prepare_public(response,config['allowed_hosts'])
            blocks=prepare_document(prepared['blocks'])['units']
            parser_sha256=digest([digest(Path(__file__).read_bytes()),digest((ROOT/'scripts/extract_candidates.py').read_bytes()),digest((ROOT/'scripts/semantic_facts.py').read_bytes())])
            revision=digest([url,digest(response['body']),VERSION,parser_sha256])
            for c in group:
                profile={**deepcopy(profiles[c['source_metadata']['source_id']]),'url':url,'title':c['title'],
                    'category':c['category'],'resource_kind':c['resource_kind'],'scope':c['scope'],'evidence_mode':'hash_only'}
                policy=extract_policy(c,blocks,profile,revision,batch['observed_at'])
                records[c['candidate_id']].update(status='replayed',reason=None,raw_sha256=digest(response['body']),
                    revision_id=revision,format=prepared['kind'],policy=policy,parser_sha256=parser_sha256)
                records[c['candidate_id']]['diagnostics']=[{
                    'locator':b['locator'],'has_deadline':bool(re.search(r'截止|期限',b['text'])),
                    'has_student':bool(re.search(r'學生|同學|申請人|申請者',b['text'])),
                    'parsed_range':list(parse_date_range_from_text(b['text'])),
                    'parsed_date':list(parse_roc_or_iso_date_from_text(b['text'])),
                } for b in timing_contexts(blocks) if TIMING.search(b['text'])][:30]
        except (ScanError,ValueError) as error:
            for record in records.values():
                record.update(status='blocked',reason=str(error))
        state['records'].update(records)
        save(output/'temporal-observations.json',state)
        print(json.dumps({'url':url,'statuses':Counter(r['status'] for r in records.values()),
            'modes':[r['policy']['submission_mode'] for r in records.values() if 'policy' in r],
            'reason':next(iter(records.values()))['reason']},ensure_ascii=False),flush=True)
    return state


def follow_attachments(output, previous, source_ids, transport=node_get):
    """Re-read each parent, then at most one directly linked same-host PDF.

    Select announcement/policy by link role and label, excluding forms. Do not
    recursively crawl links or concatenate documents across years/branches.
    """
    output=Path(output).resolve()
    if not output.is_relative_to(ROOT/'work') or output.exists() or not 1<=len(source_ids)<=8:
        raise ValueError('new_work_output_and_one_to_eight_sources_required')
    state=read(previous);config=read(ROOT/'data/scan-sources.json')
    if state['version']!=VERSION or state['model_calls'] or state['published'] or state['http_requests']>=ROUND_REQUEST_LIMIT:
        raise ValueError('invalid_round_or_exhausted_budget')
    candidates=read(ROOT/'data/candidates/source-review.json')['candidates']
    profiles={p['id']:p for p in config['sources']}
    output.mkdir(parents=True)
    batch={'http_requests':0,'attempted_urls':[],'kind':'linked_pdf','observed_at':datetime.now(timezone.utc).isoformat(timespec='seconds')}
    state['batches'].append(batch)
    def request(url,headers,limit):
        state['http_requests']+=1;batch['http_requests']+=1
        save(output/'temporal-observations.json',state)
        return transport(url,headers,limit)
    fetcher=Fetcher({'allowed_hosts':config['allowed_hosts'],'max_requests':min(20,ROUND_REQUEST_LIMIT-state['http_requests']),
        'max_run_seconds':180,'minimum_host_interval_seconds':3},transport=request)
    for sid in source_ids:
        group=[c for c in candidates if c['source_metadata']['source_id']==sid]
        if len(group)!=1:
            continue  # Multi-branch documents need separate branch-specific proof.
        candidate=group[0];cid=candidate['candidate_id'];old=state['records'].get(cid,{})
        if old.get('status')!='replayed' or old['policy']['submission_mode']!='undetermined':
            continue
        parent_url=candidate['source_metadata']['url'];attempt={'parent_url':parent_url,'status':'not_read'}
        old.setdefault('attachment_attempts',[]).append(attempt)
        try:
            parent=fetcher.get(parent_url,{},10*1024*1024)
            if parent['status']!=200:raise ScanError('parent_http_'+str(parent['status']))
            prepared=prepare_public(parent,config['allowed_hosts'])
            links=[link for link in prepared['links'] if urlsplit(link['url']).hostname==urlsplit(parent_url).hostname
                and urlsplit(link['url']).path.lower().endswith('.pdf')
                and re.search(r'公告|辦法|要點|簡章|notice|guideline',link['label'],re.I)
                and not re.search(r'申請表|申請書|推薦表|申請資料|名冊|名單|個資|同意書|附件[二三四五]',link['label'])]
            if not links:
                raise ScanError('no_direct_announcement_pdf')
            link=sorted(links,key=lambda l:0 if '公告' in l['label'] else 1)[0]
            attempt['url']=link['url'];batch['attempted_urls'].append(link['url'])
            response=fetcher.get(link['url'],{},10*1024*1024)
            if response['status']!=200:raise ScanError('attachment_http_'+str(response['status']))
            child=prepare_public(response,config['allowed_hosts'])
            if child['kind']!='pdf':raise ScanError('attachment_not_pdf')
            revision=digest([link['url'],digest(response['body']),VERSION,digest(Path(__file__).read_bytes())])
            profile={**profiles[sid],'url':link['url'],'evidence_mode':'hash_only','title':candidate['title']}
            child_candidate=deepcopy(candidate);child_candidate['source_metadata']['url']=link['url']
            policy=extract_policy(child_candidate,prepare_document(child['blocks'])['units'],profile,revision,batch['observed_at'])
            for rule in policy['rules']:
                for ref in rule['source_refs']:ref['url']=link['url']
            parent_revision=digest([parent_url,digest(parent['body']),VERSION,digest(Path(__file__).read_bytes())])
            attempt.update(status='read',submission_mode=policy['submission_mode'])
            # We only replace undetermined projections, never overwrite known dates
            # with a guideline from another route. Old evidence remains in history.
            if policy['rules']:
                documents=[{'url':link['url'],'revision_id':revision,'raw_sha256':digest(response['body']),
                    'parent_url':parent_url,'parent_raw_sha256':digest(parent['body']),'format':'pdf'}]
                replacement={**old,'history':[old], 'policy':policy,'revision_id':parent_revision,
                    'raw_sha256':digest(parent['body']),'observed_at':batch['observed_at'],'documents':documents}
                # Avoid self-references when retaining the original observation.
                replacement['history']=[deepcopy(old)]
                state['records'][cid]=replacement
        except (ScanError,ValueError) as error:
            attempt.update(status='blocked',reason=str(error))
        save(output/'temporal-observations.json',state)
        print(json.dumps({'source_id':sid,**attempt},ensure_ascii=False),flush=True)
    return state


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--previous',type=Path)
    p.add_argument('--source-id',action='append')
    p.add_argument('--retry-unclassified',action='store_true',help='One explicit retry after parser changes; retain history and budget')
    p.add_argument('--recheck',action='store_true',help='Explicit source IDs only; preserve prior observations and budget')
    p.add_argument('--follow-attachments',action='store_true',help='One directly linked same-host announcement PDF per source')
    args=p.parse_args()
    if args.follow_attachments:
        if not args.previous or not args.source_id:p.error('--previous and --source-id required for attachment replay')
        result=follow_attachments(args.output,args.previous,args.source_id)
    else:
        result=replay(args.output,args.previous,source_ids=args.source_id,retry_unclassified=args.retry_unclassified,recheck=args.recheck)
    print(json.dumps({'items':len(result['records']),'http_requests':result['http_requests']},ensure_ascii=False))
