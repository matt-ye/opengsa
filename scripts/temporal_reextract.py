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
from scripts.time_policy import policy_validator, project_time_policy, source_is_unsafe
from scripts.semantic_facts import INJECTION, recurring_time, time_actor, is_student_document, labelled_date_clause
from scripts.extract_candidates import (
    extract_from_in_memory_blocks, parse_date_range_from_text,
    parse_roc_or_iso_date_from_text,
)

VERSION = 'temporal-replay-1'
ROUND_REQUEST_LIMIT = 200
TIMING = re.compile(r'申請|受理|收件|截止|送件|報名|兌換|期限|期程|時程|評選標準及程序|每學年頒獎一次|上課開始後|獎勵期間|applications?|apply\s+by|at\s+your\s+own\s+pace|deadline|rolling|verified\s+student|credit\s+awards?',re.I)
UNDETERMINED_SUBKINDS = (
    'unparsed_timing_clause',
    'needs_linked_document',
    'regulation_without_schedule',
    'no_schedule_in_document',
)


def _scope_blocks_for_candidate(candidate, blocks, fresh_count):
    """Scope shared multi-branch document blocks to the target candidate's branch."""
    if fresh_count <= 1:
        return blocks
    pkey = candidate.get('program_key')
    if pkey not in ('ntu-nstc-phd', 'ntu-moe-phd'):
        return None
    nstc_blocks, moe_blocks = [], []
    current_branch = None
    for b in blocks:
        txt = b['text']
        if INJECTION.search(txt):
            continue
        has_nstc = any(k in txt for k in ('國科會', '國家科學及技術委員會', '科技部'))
        has_moe = '教育部' in txt
        is_common = (
            any(k in txt for k in ('在職', '專職', '重複', '修正', '修訂', '通過'))
            and not has_nstc and not has_moe and '一至三年級' not in txt
        )
        if re.search(r'第[三四五六七八九十]+條', txt) and not has_nstc and not has_moe:
            current_branch = None
        if has_nstc and not has_moe:
            current_branch = 'nstc'
            nstc_blocks.append(b)
        elif has_moe and not has_nstc:
            current_branch = 'moe'
            moe_blocks.append(b)
        elif (has_nstc and has_moe) or is_common:
            nstc_blocks.append(b)
            moe_blocks.append(b)
        else:
            if current_branch == 'nstc':
                nstc_blocks.append(b)
            elif current_branch == 'moe':
                moe_blocks.append(b)
            else:
                nstc_blocks.append(b)
                moe_blocks.append(b)
    return nstc_blocks if pkey == 'ntu-nstc-phd' else moe_blocks


def classify_undetermined_subkind(candidate, blocks=None, diagnostics=None, links=None):
    """Classify why an observation remained undetermined for incremental routing & audit."""
    diags = diagnostics or []
    if any(
        d.get('has_deadline')
        or (d.get('parsed_range') and any(d.get('parsed_range')))
        or (isinstance(d.get('parsed_date'), list) and len(d['parsed_date']) >= 2 and d['parsed_date'][1])
        for d in diags
    ):
        return 'unparsed_timing_clause'
    parent_url = (candidate.get('source_metadata') or {}).get('url') or ''
    parent_host = urlsplit(parent_url).hostname
    for lk in (links or []):
        lk_url = lk.get('url') or ''
        lk_label = lk.get('label') or ''
        if (
            urlsplit(lk_url).hostname == parent_host
            and (urlsplit(lk_url).path.lower().endswith('.pdf') or lk_label.lower().endswith('.pdf'))
            and re.search(r'公告|辦法|要點|簡章|方案|須知|注意事項|notice|guideline', lk_label, re.I)
        ):
            return 'needs_linked_document'
    title_and_url = f"{candidate.get('title', '')} {parent_url}"
    if re.search(r'辦法|要點|規定|章程|規約|條文|policy|rule', title_and_url, re.I):
        return 'regulation_without_schedule'
    return 'no_schedule_in_document'


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


def _dual_confirmed_roc_year(blocks):
    """Return ROC year string only when publication year and programme year independently agree."""
    pub_years = set()
    prog_years = set()
    pub_pattern = re.compile(
        r'(?:公告日期|發佈日期|發布日期|張貼時間|更新日期)\s*[：:]?\s*(?:民國\s*)?(20\d{2}|11\d)\s*(?:年|[./\-])\s*\d{1,2}\s*(?:月|[./\-])\s*\d{1,2}'
    )
    safe_texts = [b['text'] for b in blocks if not INJECTION.search(b['text'])]
    combined_pairs = safe_texts + [
        safe_texts[i] + ' ' + safe_texts[i + 1] for i in range(len(safe_texts) - 1)
    ]
    for text in combined_pairs:
        for m in pub_pattern.finditer(text):
            y = int(m.group(1))
            pub_years.add(y - 1911 if y >= 1911 else y)
    for text in safe_texts:
        cleaned = pub_pattern.sub('', text)
        if re.search(r'修正|修訂|通過|備查', cleaned):
            continue
        for m in re.finditer(r'(?<!\d)(11\d)\s*(?:學年度|年度|年\s*[「『]|年人社)', cleaned):
            prog_years.add(int(m.group(1)))
        for m in re.finditer(r'補助會議舉辦期間\s*[：:]\s*(?:民國\s*)?(11\d)\s*年', cleaned):
            prog_years.add(int(m.group(1)))
        for m in re.finditer(r'(?:推出\s*[「『]?|[「『【]|_)(202\d)\s*(?:AI|\.pdf)', cleaned, re.I):
            prog_years.add(int(m.group(1)) - 1911)
    if len(pub_years) == 1 and len(prog_years) == 1 and pub_years == prog_years:
        return str(next(iter(pub_years)))
    return None


def _inject_dual_year(clause, roc_year):
    """Inject dual-confirmed ROC year into unanchored month/day ranges or deadlines."""
    out = re.sub(
        r'(申請期間|申請時間|申請時程|申請日期|受理期間|收件期間|收件日期|報名期間|報名時間)([：:\s]*)(?!(?:民國)?(?:20\d{2}|1\d{2})[年/.\-])(\d{1,2}\s*[月/]\s*\d{1,2}\s*日?(?:[（(][^）)]*[）)])?\s*(?:至|~|～|-|到)\s*)(?!(?:民國)?(?:20\d{2}|1\d{2})[年/.\-])(\d{1,2}\s*[月/]\s*\d{1,2})',
        lambda m: f"{m.group(1)}{m.group(2)}{roc_year}年{m.group(3)}{roc_year}年{m.group(4)}",
        clause,
    )
    if out != clause:
        return out
    return re.sub(
        r'(截止(?:日期|時間)?(?:為|至)?|(?:申請|兌換|報名)期限(?:為)?|(?:最遲)?應於|請於|申請至|收件至|報名至|從即日起至|自即日起至|自公告日起至)([：:\s]*)(?!(?:民國)?(?:20\d{2}|1\d{2})[年/.\-])(\d{1,2}\s*[月/]\s*\d{1,2})',
        lambda m: f"{m.group(1)}{m.group(2)}{roc_year}年{m.group(3)}",
        clause,
    )


def _publication_dates(blocks):
    """Explicit publication/posting dates (as date objects) found in safe blocks."""
    from datetime import date as _date
    found = []
    pattern = re.compile(
        r'(?:公告日期|發佈日期|發布日期|張貼時間|更新日期)\s*[：:]?\s*(?:民國\s*)?(20\d{2}|11\d)\s*(?:年|[./\-])\s*(\d{1,2})\s*(?:月|[./\-])\s*(\d{1,2})'
    )
    safe_texts = [b['text'] for b in blocks if not INJECTION.search(b['text'])]
    for text in safe_texts + [safe_texts[i] + ' ' + safe_texts[i + 1] for i in range(len(safe_texts) - 1)]:
        for m in pattern.finditer(text):
            y = int(m.group(1))
            try:
                found.append(_date(y if y >= 1911 else y + 1911, int(m.group(2)), int(m.group(3))))
            except ValueError:
                continue
    return found


_WEEKDAYS = {'一': 0, '二': 1, '三': 2, '四': 3, '五': 4, '六': 5, '日': 6, '天': 6}


def _dual_year_consistent(clause, roc_year, publication_dates):
    """Reject a dual-anchored year when the source text contradicts it.

    1. Any weekday marker next to a month/day, e.g. 6/15(一), must match.
    2. The latest month/day in the clause must not precede the publication
       date; a December notice for a January window belongs to the next year.
    """
    from datetime import date as _date
    year = int(roc_year) + 1911
    for m in re.finditer(r'(?<![\d/年.\-])(\d{1,2})\s*[月/]\s*(\d{1,2})\s*日?\s*[（(]\s*(?:星期|週|周)?\s*([一二三四五六日天])\s*[)）]', clause):
        try:
            if _date(year, int(m.group(1)), int(m.group(2))).weekday() != _WEEKDAYS[m.group(3)]:
                return False
        except ValueError:
            return False
    days = []
    # Only month/days without their own year are the ones receiving the injected year.
    for m in re.finditer(r'(?<![\d/年.\-])(\d{1,2})\s*[月/]\s*(\d{1,2})(?![\d/])', clause):
        try:
            days.append(_date(year, int(m.group(1)), int(m.group(2))))
        except ValueError:
            return False
    if days and publication_dates and max(days) < min(publication_dates):
        return False
    return True


def _is_dateless_reference_document(candidate, blocks):
    """True when a regulation/policy document contains no schedule or deadline clues."""
    if any(INJECTION.search(b['text']) for b in blocks):
        return False
    if any(re.search(r'截止|申請期限|申請期間|申請時間|申請時程|申請日期|受理期間|受理時間|收件期間|收件日期|報名期間|報名時間|停止受理|暫停受理|(?<!\d)\d{1,2}\s*[月/]\s*\d{1,2}\s*日?\s*(?:至|~|～|起|前|止)', b['text']) for b in blocks):
        return False
    title_or_url = (candidate.get('title') or '') + ' ' + ((candidate.get('source_metadata') or {}).get('url') or '')
    return bool(
        re.search(r'辦法|要點|規定|章程|規約|實施要點|作業要點|設置辦法|補助原則|支給標準', title_or_url)
        or sum(1 for b in blocks if re.search(r'第[一二三四五六七八九十]+條', b['text'])) >= 2
    )


def extract_policy(candidate, blocks, profile, revision, observed):
    """Reuse specialized parsers, then discover explicit timing clauses generically.

    No title-derived year, publication-as-start, missing-date-as-rolling, or
    institution-as-student fallback. Unanchored month/day remains a text rule.
    """
    for idx, b in enumerate(blocks):
        if '可申請研究生出席國際會議補助之機構' in b['text']:
            cut = idx - 1 if idx > 0 and '────' in blocks[idx - 1]['text'] else idx
            blocks = blocks[:cut]
            break
    student_document=is_student_document(blocks)
    fresh = extract_from_in_memory_blocks(profile, blocks, revision, observed,
        url=candidate['source_metadata']['url'], extraction_strategy='rules_only')
    matches = [c for c in fresh if c['program_key'] == candidate['program_key']]
    selected = matches[0] if len(matches) == 1 else fresh[0] if len(fresh) == 1 else None
    cand_unsafe = source_is_unsafe(candidate) if 'verification' in candidate and 'gaps_and_conflicts' in candidate else False
    policy = project_time_policy(selected, unsafe=cand_unsafe) if selected else {
        'version':'time-policy-1', 'submission_mode':'undetermined',
        'review_mode':'not_stated', 'rules':[], 'gaps':['time_not_projected']}
    # Shared announcements with multiple branches use branch-scoped blocks when supported.
    scoped_blocks = _scope_blocks_for_candidate(candidate, blocks, len(fresh))
    if scoped_blocks is None:
        return policy
    blocks = scoped_blocks
    rules = policy['rules']
    # Generic legacy clauses discarded extra deadlines sharing the same note.
    # Rebuild those from bounded contexts; retain the specialized rule branches.
    rules[:]=[r for r in rules if r['summary'] not in ('角色依本段辨識；未載學生期限時不以其他層級回填','學生受理期間明示起日')]
    def add(block, kind, actor, stage, summary, value=None, precision='rule', year_basis=None):

        claim = {'rule_id':f"replay/{len(rules)}", 'kind':kind, 'actor':actor,
            'stage':stage, 'summary':summary, 'value':value, 'precision':precision,
            **(({'year_basis':year_basis}) if year_basis else {}),
            'anchor_event':None, 'source_refs':[{'source':profile['id'],
                'revision_id':revision, 'locator':block['locator'],
                'evidence_path':'temporal_replay/'+stage}]}
        if not any((r['actor'],r['stage'],r['value'],r['kind'],r['summary']) ==
                   (actor,stage,value,kind,summary) for r in rules):
            rules.append(claim)

    _en_months = {'january':1,'february':2,'march':3,'april':4,'may':5,'june':6,'july':7,'august':8,'september':9,'october':10,'november':11,'december':12}
    _univ_nomination = any(re.search(r'nominated\s+for\s+the\s+fellowship\s+by\s+their\s+university|submitted\s+by\s+an\s+official\s+representative\s+of\s+the\s+university', b['text'], re.I) for b in blocks if not INJECTION.search(b['text']))
    _dual_roc_year = _dual_confirmed_roc_year(blocks)
    _pub_dates = _publication_dates(blocks) if _dual_roc_year else []
    _doc_same_year = None
    for b in blocks:
        if not INJECTION.search(b['text']):
            m_sy = re.search(r'(1\d{2})\s*年\s*[（(]以下同[)）]', b['text'])
            if m_sy:
                _doc_same_year = m_sy.group(1)
                break
    for block in timing_contexts(blocks):
        if INJECTION.search(block['text']):
            continue
        for m_en in re.finditer(r'Applications?\s+(open|close)[s]?\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),\s*(20\d{2})', block['text'], re.I):
            verb, m_name, d_str, y_str = m_en.groups()
            iso_val = f"{int(y_str):04d}-{_en_months[m_name.lower()]:02d}-{int(d_str):02d}"
            en_stage = 'application_start' if verb.lower().startswith('open') else 'submission'
            en_summary = '來源明示受理起日' if en_stage == 'application_start' else '來源明示收件截止'
            en_actor = 'institution' if _univ_nomination else 'student'
            add(block, 'absolute', en_actor, en_stage, en_summary, iso_val, 'date')
        for m_en_dl in re.finditer(r'(?:Apply\s+by|Application\s+deadline(?:\s*,?\s*including\s+recommendation\s+letters\s*,?\s*is)?)\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),\s*(20\d{2})', block['text'], re.I):
            m_name, d_str, y_str = m_en_dl.groups()
            iso_val = f"{int(y_str):04d}-{_en_months[m_name.lower()]:02d}-{int(d_str):02d}"
            en_actor = 'institution' if _univ_nomination else 'student'
            add(block, 'absolute', en_actor, 'submission', '來源明示收件截止', iso_val, 'date')
        # Sentences retain their own year and actor. Never join unrelated dates.
        for raw_clause in re.split(r'[。；;\n｜※◎]', block['text']):
            clause = re.sub(r'\s+', '', raw_clause)
            if not clause or re.search(r'修正|生效|出生|年齡|購買|支出|訂閱|給付|補助期間|獎助期間|會議舉辦期間|課程期間', clause):
                continue
            if re.search(r'隨到隨審|onarollingbasis', clause, re.I) and not re.search(r'不採|非|停止|暫停', clause):
                add(block, 'review_cadence', 'other', 'review', '審查採隨到隨審；不等同全年受理')
                policy['review_mode'] = 'rolling'
            if not re.search(r'申請|受理|收件|送件|報名|兌換|期程|時程|評選標準及程序|每學年頒獎一次|上課開始後|獎勵期間|apply|applications?|atyourownpace|rolling|verifiedstudent|creditawards?', clause, re.I):
                continue
            actor = time_actor(clause)
            if re.search(r'各系所彙整|系所彙整', clause):
                actor = 'department'
            elif re.search(r'同學|研究生|博士候選人|博士生|碩士生|學生|青年|申請人|申請者|國科會甄選類別.*受理線上申請|(?:送交|送至|繳交至).{0,15}(?:系辦|所辦|辦公室)', clause):
                actor = 'student' if actor == 'unit' else actor
            if actor=='unit' and student_document and not re.search(r'學校|學院|系所|彙送|推薦名單|備函',clause):
                actor='student'
            if re.search(r'不受理|停止受理|暫停受理|不得申請|不採隨', clause):
                continue
            if re.search(r'全年(?:均可|皆可|開放)?(?:受理|申請)|隨時(?:均可|皆可|可以|可)?(?:提出)?申請|常年受理|applications?(?:are)?accepted(?:year.round|onarollingbasis)|evaluate.*proposalsonarollingbasisthroughouttheyear|verifiedstudentsongithubeducationgetfreeaccess|availabletoverifiedstudents|buildyourcloudskillsatyourownpace,onyourowntime,andcompletelyforfree|reevaluatesyoureligibilityeverymonth', clause, re.I):
                add(block, 'continuous', actor if actor != 'unit' else 'student', 'submission', '來源明示常態受理；仍須核對資格及額度')
            elif re.search(r'(?:申請|收件|受理).{0,60}(?:依|洽|由).{0,25}(?:各|所屬).{0,15}(?:院系所|系所|學院|研究所|中心|單位).{0,25}(?:公告|規定|訂定|自訂|確認|辦理|送院)|(?:各|所屬)(?:系所|學院|研究所|中心)(?:[（(]處[)）])?(?:、研究中心)?自訂(?:審查|申請|收件)(?:程序)?|學院受理學生申請及甄審|評選標準及程序[,，]?由各學院訂定施行細則|(?:申請|收件|截止)(?:時間|期限|時程|日期).{0,20}(?:逕洽|洽詢|請洽).{0,25}(?:院系所|系所|學院|研究所|中心|單位)|學校應依本部公告期程.{0,25}於指定期間內.{0,15}提出申請|課程將陸續開放請持續關注|自即日起陸續開辦.{0,120}查詢課程與報名', clause):
                add(block, 'unit_announced', actor, 'submission', '申請收件時程由所屬單位另訂／公告')
            if re.search(r'(?:每年|每學年|每學期).{0,25}(?:受理|申請|收件|頒獎一次|上課開始後|獎勵期間結束前)|(?:申請|受理|收件)(?:時間|期間|期限)?[：:]?(?:每年|每學年|每學期)',clause) and not recurring_time(clause):
                add(block,'recurring',actor,'submission','來源明示週期性受理；當期具體日期另查')
            if re.search(r'creditawards?mustbeactivatedwithin\d+daysoftheprojectstartdate', clause, re.I):
                add(block, 'text_rule', 'student', 'submission', '核給額度須於計畫起日一定天數內啟用；受理期程依申請表單規定')
            # Existing specialized relative/calendar rules take precedence.
            if recurring_time(clause) or re.search(r'每年|每學年|每學期|會前|出國前|活動前|前.{0,5}(?:週|個月|天)', clause):
                continue
            if not re.search(r'申請期間|申請時程|申請時間|申請日期|受理期間|收件期間|收件日期|報名期間|報名時間|申請期限|兌換期限|報名期限|申請截止|截止|申請至|自(?:民國)?(?:20\d{2}|1\d{2})年.{0,30}止(?:受理|開放)|(?:最遲)?應於.{0,80}(?:申請|送|繳)|請於.{0,80}(?:申請|送|繳)|從即日起至|自公告日起至', clause):
                continue
            if re.search(r'出國期間|活動期間|研修期間|培育期間|獎勵期間|公布結果', clause):
                continue
            effective_clause = clause
            used_dual_year = False
            if _doc_same_year and not re.search(r'(?:20\d{2}|1\d{2})年', clause):
                effective_clause = re.sub(r'(最遲應於|截止(?:日期|時間)?(?:為|至)?|申請期限(?:為)?)(\d{1,2}月\d{1,2}日)', lambda m: m.group(1) + _doc_same_year + '年' + m.group(2), clause)
            elif _dual_roc_year and not labelled_date_clause(clause):
                injected = _inject_dual_year(clause, _dual_roc_year)
                if injected != clause and _dual_year_consistent(clause, _dual_roc_year, _pub_dates):
                    effective_clause = injected
                    used_dual_year = True
            y_basis = 'dual_anchored' if used_dual_year else None
            start_sum = '來源明示受理起日（依公告日與計畫年度雙重錨定，待核座標）' if used_dual_year else '來源明示受理起日'
            end_sum = '來源明示收件截止（依公告日與計畫年度雙重錨定，待核座標）' if used_dual_year else '來源明示收件截止'
            labelled=labelled_date_clause(effective_clause)
            start, end = parse_date_range_from_text(labelled or '')
            # Explicit student directions are needed for a student range.
            # Otherwise preserve dates as unit procedure instead of making a bar.
            if start and end:
                if not any(r['actor']==actor and r['stage']=='application_start' and r['value']==start for r in rules):
                    add(block, 'absolute', actor, 'application_start', start_sum, start, 'date', year_basis=y_basis)
                kind, value = parse_roc_or_iso_date_from_text(re.split(r'至|到|[~～]|-',labelled)[-1], int(end[:4])-1911)
                value = value if value and value[:10]==end else end
                if not any(r['actor']==actor and r['stage']=='submission' and r['value']==value for r in rules):
                    add(block, 'absolute', actor, 'submission', end_sum, value, kind if value!=end else 'date', year_basis=y_basis)
            else:
                kind, value = parse_roc_or_iso_date_from_text(labelled or '')
                if value and re.search(r'截止|前|止|期限|逾期失效|申請至|請於.{0,30}完成申請|即日起至.{0,20}報名', effective_clause):
                    if not any(r['actor']==actor and r['stage']=='submission' and r['value']==value for r in rules):
                        summary_txt = '個人相對期限與當期最遲截止並列；須同時核對個人條件與年度上限' if re.search(r'達成日次日起.*內提出申請.*但最遲應於', effective_clause) else end_sum
                        add(block, 'absolute', actor if not re.search(r'兌換期限', effective_clause) else 'student', 'submission', summary_txt, value, kind, year_basis=y_basis)

                        if re.search(r'達成日次日起.*內提出申請.*但最遲應於', effective_clause):
                            policy['submission_mode'] = 'conditional_deadline'
                            if 'personal_conditions_required' not in policy['gaps']:
                                policy['gaps'].append('personal_conditions_required')
                elif not value and re.search(r'截止|期限|期間|時程|時間|報名|申請至|請於|應於',clause):
                    month_days=list(dict.fromkeys(re.findall(r'(?<!\d)(\d{1,2})[月/](\d{1,2})(?:日)?',clause)))
                    if month_days:
                        summary='來源列示月日：'+'、'.join(f'{int(m)}月{int(d)}日' for m,d in month_days if 1<=int(m)<=12 and 1<=int(d)<=31)
                        if not summary.endswith('：'):
                            add(block,'text_rule',actor,'submission',summary+'；年份與起訖角色須查原文')

    # Keep specialized conditional/event-relative semantics; generic modes are
    # determined only by evidenced claims, never by programme/category names.
    datetime_days = {(r['actor'], r['stage'], r['value'][:10]) for r in rules if r['kind'] == 'absolute' and r['precision'] == 'datetime' and r.get('value')}
    if datetime_days:
        rules[:] = [r for r in rules if not (r['kind'] == 'absolute' and r['precision'] == 'date' and (r['actor'], r['stage'], r['value']) in datetime_days)]
        for idx_r, r in enumerate(rules):
            if r['rule_id'].startswith('replay/'):
                r['rule_id'] = f'replay/{idx_r}'
    # 卡片排程先給的 recurring 不能擋重算：回放若又抽到明確日期，就是 mixed，不能留著 recurring 卻帶座標。
    if policy['submission_mode'] not in ('conditional_deadline','automatic','reference','event_relative','mixed'):
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
        if _is_dateless_reference_document(candidate, blocks):
            policy['submission_mode']='reference'
            policy['gaps']=[g for g in policy['gaps'] if g!='time_not_projected']
        else:
            policy['submission_mode']='undetermined'
    if rules:
        policy['gaps']=[g for g in policy['gaps'] if g not in ('time_not_projected','student_window_not_recorded',*(('source_checks_failed',) if not cand_unsafe else ()))]
        if not any(r['actor']=='student' and r['stage']=='submission' for r in rules):
            policy['gaps'].append('student_window_not_recorded')
    policy_validator().validate(policy)
    return policy


def timing_diagnostics(blocks):
    return [{
        'locator':b['locator'],'has_deadline':bool(re.search(r'截止|期限',b['text'])),
        'has_student':bool(re.search(r'學生|同學|申請人|申請者',b['text'])),
        'parsed_range':list(parse_date_range_from_text(b['text'])),
        'parsed_date':list(parse_roc_or_iso_date_from_text(b['text'])),
    } for b in timing_contexts(blocks) if TIMING.search(b['text'])][:30]


def same_round_record(candidate, blocks, raw_sha256, profile, observed):
    """用抽卡當輪的內文判斷時間，不多發請求。只留判斷結果與定位，內文不離開記憶體。

    綁定卡片內容的雜湊要等提案時才算，所以這裡只記它來自哪個版本。
    """
    from scripts.temporal_tracks import parser_fingerprint
    url=candidate['source_metadata']['url'];parser_sha256=parser_fingerprint()
    revision=digest([url,raw_sha256,VERSION,parser_sha256])
    units=prepare_document(blocks)['units']
    profile={**deepcopy(profile),'url':url,'title':candidate['title'],'category':candidate['category'],
        'resource_kind':candidate['resource_kind'],'scope':candidate['scope'],'evidence_mode':'hash_only'}
    record={'url':url,'status':'replayed','reason':None,'observed_at':observed,'raw_sha256':raw_sha256,'revision_id':revision,
        'format':'pdf' if urlsplit(url).path.lower().endswith('.pdf') else 'html','parser_sha256':parser_sha256,
        'card_revision_id':candidate['source_metadata']['revision_id'],
        'policy':extract_policy(candidate,units,profile,revision,observed),'diagnostics':timing_diagnostics(units)}
    if record['policy'].get('submission_mode')=='undetermined':
        record['undetermined_subkind']=classify_undetermined_subkind(candidate,units,record['diagnostics'],[])
    return record


def replay(output, previous=None, transport=node_get, source_ids=None, retry_unclassified=False, recheck=False,
           max_round_requests=ROUND_REQUEST_LIMIT, on_document=None, track=None,
           baseline_observations=None, skip_unchanged_model=False):
    """One micro-batch <=8 URLs/20 HTTP/180 seconds; whole round <=200 HTTP.

    Resume artifacts contain no original text. Previous attempts (including
    blocked reads) are never retried automatically or reset silently.
    """
    from scripts.temporal_tracks import classify_source_track, evaluate_incremental_diff, parser_fingerprint, track_for_weekday
    output=Path(output).resolve()
    if not output.is_relative_to(ROOT/'work') or output.exists():
        raise ValueError('new_work_output_required')
    candidates=read(ROOT/'data/candidates/source-review.json')['candidates']
    config=read(ROOT/'data/scan-sources.json')
    profiles={p['id']:p for p in config['sources']}
    state=read(previous) if previous else {'version':VERSION,'http_requests':0,'model_calls':0,'published':False,'batches':[],'records':{}}
    if not 1<=max_round_requests<=ROUND_REQUEST_LIMIT:
        raise ValueError('invalid_request_limit')
    if state['version']!=VERSION or state['model_calls']!=0 or state['published'] or state['http_requests']>=max_round_requests:
        raise ValueError('invalid_round_state_or_exhausted_budget')
    audit={r['url']:r for r in read(ROOT/'data/source-expansion/original-source-verification.json')['records']}
    q_snap_path = ROOT / 'data/source-chain-batches/radar-proposal-snapshots.json'
    if q_snap_path.exists():
        for snap in read(q_snap_path).get('documents', []):
            if snap.get('status') == 'candidate_snapshot' and snap.get('url'):
                audit.setdefault(snap['url'], {'url': snap['url'], 'content_verified': True})
    resolved_track=track_for_weekday() if track=='auto' else track
    urls={}
    if recheck and not source_ids:
        raise ValueError('explicit_source_ids_required_for_recheck')
    for c in candidates:
        if resolved_track and resolved_track!='all' and classify_source_track(c)!=resolved_track:
            continue
        old=state['records'].get(c['candidate_id'],{})
        retry=(recheck and old.get('status') in ('replayed','blocked') and old.get('reason')!='robots_denied') or (retry_unclassified and old.get('status')=='replayed' and old['policy']['submission_mode']=='undetermined' and not old.get('history'))
        if (not old or retry) and (not source_ids or c['source_metadata']['source_id'] in source_ids):
            urls.setdefault(c['source_metadata']['url'],[]).append(c)
    output.mkdir(parents=True)
    batch={'http_requests':0,'attempted_urls':[], 'observed_at':datetime.now(timezone.utc).isoformat(timespec='seconds')}
    if resolved_track:
        batch['track']=resolved_track
    state['batches'].append(batch)
    def request(url, headers, limit):
        batch['http_requests']+=1
        state['http_requests']+=1
        save(output/'temporal-observations.json',state)
        return transport(url,headers,limit)
    fetcher=Fetcher({'allowed_hosts':config['allowed_hosts'],'max_requests':min(20,max_round_requests-state['http_requests']),
        'max_run_seconds':2400 if on_document else 180,'minimum_host_interval_seconds':3},transport=request)
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
            raw_hash=digest(response['body'])
            prepared=prepare_public(response,config['allowed_hosts'])
            blocks=prepare_document(prepared['blocks'])['units']
            parser_sha256=parser_fingerprint()
            revision=digest([url,raw_hash,VERSION,parser_sha256])
            for c in group:
                profile={**deepcopy(profiles[c['source_metadata']['source_id']]),'url':url,'title':c['title'],
                    'category':c['category'],'resource_kind':c['resource_kind'],'scope':c['scope'],'evidence_mode':'hash_only'}
                policy=extract_policy(c,blocks,profile,revision,batch['observed_at'])
                records[c['candidate_id']].update(status='replayed',reason=None,raw_sha256=raw_hash,
                    revision_id=revision,format=prepared['kind'],policy=policy,parser_sha256=parser_sha256)
                records[c['candidate_id']]['diagnostics']=timing_diagnostics(blocks)
                if policy.get('submission_mode') == 'undetermined':
                    records[c['candidate_id']]['undetermined_subkind'] = classify_undetermined_subkind(
                        c, blocks, records[c['candidate_id']]['diagnostics'], prepared.get('links', [])
                    )
                if on_document:
                    if skip_unchanged_model and baseline_observations:
                        diff_decision=evaluate_incremental_diff(c,observations=baseline_observations,observed_raw_sha256=raw_hash,current_parser_sha256=parser_sha256)
                        if not diff_decision['should_run']:
                            records[c['candidate_id']]['incremental_decision']=diff_decision['decision']
                            continue
                    on_document(c,blocks,revision,batch['observed_at'])
        except (ScanError,ValueError) as error:
            for record in records.values():
                record.update(status='blocked',reason=str(error))
        state['records'].update(records)
        save(output/'temporal-observations.json',state)
        print(json.dumps({'url':url,'statuses':Counter(r['status'] for r in records.values()),
            'modes':[r['policy']['submission_mode'] for r in records.values() if 'policy' in r],
            'reason':next(iter(records.values()))['reason']},ensure_ascii=False),flush=True)
    return state


def follow_attachments(output, previous, source_ids, transport=node_get, max_round_requests=ROUND_REQUEST_LIMIT, on_document=None):
    """Re-read each parent, then at most one directly linked same-host PDF.

    Select announcement/policy by link role and label, excluding forms. Do not
    recursively crawl links or concatenate documents across years/branches.
    """
    from scripts.temporal_model import merge_parent_and_child_policies
    output=Path(output).resolve()
    if not output.is_relative_to(ROOT/'work') or output.exists() or not 1<=len(source_ids)<=8:
        raise ValueError('new_work_output_and_one_to_eight_sources_required')
    state=read(previous);config=read(ROOT/'data/scan-sources.json')
    if not 1<=max_round_requests<=ROUND_REQUEST_LIMIT:
        raise ValueError('invalid_request_limit')
    if state['version']!=VERSION or state['model_calls'] or state['published'] or state['http_requests']>=max_round_requests:
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
    fetcher=Fetcher({'allowed_hosts':config['allowed_hosts'],'max_requests':min(20,max_round_requests-state['http_requests']),
        'max_run_seconds':2400 if on_document else 180,'minimum_host_interval_seconds':3},transport=request)
    for sid in source_ids:
        group=[c for c in candidates if c['source_metadata']['source_id']==sid]
        if len(group)!=1:
            continue  # Multi-branch documents need separate branch-specific proof.
        candidate=group[0];cid=candidate['candidate_id'];old=state['records'].get(cid,{})
        if old.get('status')!='replayed' or old['policy']['submission_mode'] not in ('undetermined','start_only','procedure_only','rule_text','review_only'):
            continue
        parent_url=candidate['source_metadata']['url'];attempt={'parent_url':parent_url,'status':'not_read'}
        old.setdefault('attachment_attempts',[]).append(attempt)
        try:
            parent=fetcher.get(parent_url,{},10*1024*1024)
            if parent['status']!=200:raise ScanError('parent_http_'+str(parent['status']))
            prepared=prepare_public(parent,config['allowed_hosts'])
            links=[link for link in prepared['links'] if urlsplit(link['url']).hostname==urlsplit(parent_url).hostname
                and (urlsplit(link['url']).path.lower().endswith('.pdf') or link['label'].lower().endswith('.pdf'))
                and re.search(r'公告|辦法|要點|簡章|方案|須知|注意事項|notice|guideline',link['label'],re.I)
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
            child_units=prepare_document(child['blocks'])['units']
            policy=extract_policy(child_candidate,child_units,profile,revision,batch['observed_at'])
            for rule in policy['rules']:
                for ref in rule['source_refs']:ref['url']=link['url']
            parent_revision=digest([parent_url,digest(parent['body']),VERSION,digest(Path(__file__).read_bytes())])
            # Re-bind parent rules to parent_revision before Map-Reduce merge
            parent_policy=deepcopy(old['policy'])
            for prule in parent_policy.get('rules',[]):
                for pref in prule.get('source_refs',[]):
                    if not pref.get('url'):
                        pref['revision_id']=parent_revision
            merged_policy=merge_parent_and_child_policies(parent_policy,policy) if policy['rules'] else parent_policy
            attempt.update(status='read',submission_mode=merged_policy['submission_mode'])
            if policy['rules']:
                documents=[{'url':link['url'],'revision_id':revision,'raw_sha256':digest(response['body']),
                    'parent_url':parent_url,'parent_raw_sha256':digest(parent['body']),'format':'pdf'}]
                replacement={**old,'history':[deepcopy(old)],'policy':merged_policy,'revision_id':parent_revision,
                    'raw_sha256':digest(parent['body']),'observed_at':batch['observed_at'],'documents':documents}
                state['records'][cid]=replacement
            if on_document:
                on_document(candidate,child_units,revision,batch['observed_at'],doc_url=link['url'],doc_raw_sha256=digest(response['body']))
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
    p.add_argument('--track',choices=['gov','enterprise','other','all','auto'])
    p.add_argument('--retry-unclassified',action='store_true',help='One explicit retry after parser changes; retain history and budget')
    p.add_argument('--recheck',action='store_true',help='Explicit source IDs only; preserve prior observations and budget')
    p.add_argument('--follow-attachments',action='store_true',help='One directly linked same-host announcement PDF per source')
    args=p.parse_args()
    if args.follow_attachments:
        if not args.previous or not args.source_id:p.error('--previous and --source-id required for attachment replay')
        result=follow_attachments(args.output,args.previous,args.source_id)
    else:
        result=replay(args.output,args.previous,source_ids=args.source_id,retry_unclassified=args.retry_unclassified,recheck=args.recheck,track=args.track)
    print(json.dumps({'items':len(result['records']),'http_requests':result['http_requests']},ensure_ascii=False))
