"""Optional temporal proposals through the existing bounded model adapter.

No candidate mutation, automatic publication, raw prompts or response archives.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import urllib.request
from urllib.parse import urlsplit

from scripts.document_ir import prepare_document, evidence_block_map
from scripts.extract_candidates import (
    create_model_adapter_from_env, _verify_quote_and_reparse, CONTACT,
)
from scripts.semantic_facts import time_actor, labelled_date_clause
from scripts.audit_providers import NoRedirect

MODEL='qwen/qwen3.8-27b'
TOKENIZER_URL='https://huggingface.co/Qwen/Qwen3.8-27B/resolve/72a217afab8029b39e4af1c7273a829995a3dbaf/tokenizer.json'
TOKENIZER_SHA='0997f410c57a1f4e53b09e4be8f4a172d90edd9564368fb0847030937229b9f3'
FIELDS=('schedule.application_start','schedule.student_deadline','schedule.college_deadline',
        'schedule.institution_deadline','schedule.result_date')


def install_tokenizer(path):
    """Public pinned JSON only; never downloads weights or executes remote code."""
    path=Path(path)
    if not path.exists():
        with urllib.request.urlopen(TOKENIZER_URL,timeout=45) as response:
            raw=response.read(16*1024*1024+1)
        if len(raw)>16*1024*1024 or hashlib.sha256(raw).hexdigest()!=TOKENIZER_SHA:
            raise ValueError('tokenizer_download_hash_mismatch')
        path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)
    if hashlib.sha256(path.read_bytes()).hexdigest()!=TOKENIZER_SHA:
        raise ValueError('tokenizer_hash_mismatch')


def model_for_temporal(tokenizer_path):
    adapter=create_model_adapter_from_env()
    if not adapter.enabled:
        return adapter,'off_missing_key_or_cost_policy'
    if adapter.model!=MODEL or 'api.groq.com'!=urlsplit(adapter.base_url).hostname:
        return None,'model_capabilities_not_verified'
    install_tokenizer(tokenizer_path)
    from tokenizers import Tokenizer
    tokenizer=Tokenizer.from_file(str(tokenizer_path))
    # Official text tokenizer plus explicit template reserve, not a claim to
    # know Groq's private framing. Usage from the response is the actual count.
    def count(payload):
        return 256+sum(len(tokenizer.encode(m['content'],add_special_tokens=False).ids)+64
                       for m in payload['messages'])
    adapter.model_limits={'model':MODEL,'reviewed':True,'checked_on':'2026-11-03',
        'input_limit':6000,'context_limit':131042,'output_limit':16384,'output_reserve':1200,
        'shared_context':True,'thinking_reserve':0,'safety_tokens':512,'max_request_bytes':120000}
    adapter.count_tokens=count;adapter.max_calls=4;adapter.field_scope=FIELDS
    adapter.use_cache=False  # Do not retain raw model quotes/responses in artifacts.
    adapter.request_open=urllib.request.build_opener(NoRedirect()).open
    return adapter,'ready'


def source_allowed(candidate, profile):
    host=urlsplit(candidate['source_metadata']['url']).hostname
    return (candidate['source_metadata']['evidence_mode']=='short_excerpt'
            and profile['evidence_mode']=='short_excerpt'
            and host not in ('www.aca.ntu.edu.tw','aca.ntu.edu.tw','ord.ntu.edu.tw'))


def model_review(candidate, profile, blocks, adapter, revision):
    row={'candidate_id':candidate['candidate_id'],'source_id':profile['id'],
         'source_revision':revision,'status':'not_requested','claims':[],'rejected_claims':0}
    if not source_allowed(candidate,profile):
        row['status']='restricted_source_rules_only';return row
    if not adapter or not adapter.enabled:
        row['status']='model_unavailable_rules_only';return row
    if adapter.calls>=adapter.max_calls or adapter.rate_limited_429:
        row['status']='model_budget_or_quota_deferred';return row
    units=prepare_document(blocks)['units']
    # Only pure contact units can be excluded. Mixed date/exception/contact
    # text stays intact and the existing sanitization guard defers that task.
    excluded=[u for u in units if CONTACT.search(u['text']) and re.match(r'^\s*(?:聯絡|洽詢|承辦|電話|地址|Email|E-mail|Tel|Fax|傳真|©|版權)',u['text'],re.I)
              and not re.search(r'申請|受理|截止|期限|但|除外|不得|資格|對象|補件',u['text'])]
    units=[u for u in units if u not in excluded]
    row['contact_only_units_excluded']=len(excluded)
    response=adapter.run_dual_track(profile,units,candidate)
    row['preparation']=deepcopy(getattr(adapter,'last_preparation',{}))
    if not response or any(k.startswith('_') for k in response):
        row['status']=response.get('_skipped_reason','invalid_or_empty_response') if response else 'empty_response'
        return row
    block_map=evidence_block_map(units)
    mode=getattr(adapter,'mode','both')
    kinds=('audit_findings',) if mode=='audit' else ('extracted_fields',) if mode=='extract' else ('extracted_fields','audit_findings')
    for kind in kinds:
        for claim in response.get(kind,[]):
            path=claim.get('field_path')
            value=claim.get('value') if kind=='extracted_fields' else claim.get('llm_value')
            if path not in FIELDS or value in (None,'unknown','relative',''):
                row['rejected_claims']+=1;continue
            ok,reason,block,normalized=_verify_quote_and_reparse(path,value,None,None,
                claim.get('locator'),claim.get('quote'),block_map,is_audit=kind=='audit_findings')
            quote=claim.get('quote') or ''
            expected='student' if path in ('schedule.application_start','schedule.student_deadline') else 'college' if 'college' in path else 'institution' if 'institution' in path else None
            if expected and (claim.get('actor') not in (None,expected) or time_actor(quote)!=expected):
                ok=False;reason='time_actor_requires_review'
            if expected and not labelled_date_clause(re.sub(r'\s+','',quote)):
                ok=False;reason='application_date_label_requires_review'
            if path=='schedule.result_date' and not re.search(r'結果|公布|公告|核定',quote):
                ok=False;reason='result_stage_requires_review'
            if not ok:
                row['rejected_claims']+=1;continue
            # Date verification alone does not establish applicability or annual
            # cap conditions. These are proposals, never new public time rules.
            row['claims'].append({'field_path':path,'value':normalized,'actor':expected,
                'locator':block['locator'],'quote_sha256':hashlib.sha256(quote.encode()).hexdigest(),
                'kind':kind,'status':'evidence_checked_pending_review'})
    row['status']='model_completed_pending_review'
    return row
