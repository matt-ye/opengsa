"""Lossless in-memory document units and bounded request packing. No fetch or persistence."""
from copy import deepcopy
from datetime import date
import hashlib
import json
import re

VERSION = 'document-ir-2'


def sha(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True).encode('utf-8')).hexdigest()


def prepare_document(blocks):
    """Keep evidence text/locators unchanged; add unique identities and structural context."""
    units=[]
    for index, block in enumerate(blocks):
        if not isinstance(block.get('text'),str) or not isinstance(block.get('locator'),str):
            raise ValueError('invalid_document_block')
        if not block['text'].strip():continue
        unit=deepcopy(block)
        unit['unit_id']='u-'+sha([index,block['locator'],block['text']])[:24]
        unit['ordinal']=index
        unit.setdefault('kind','paragraph')
        unit.setdefault('section_path',[])
        units.append(unit)
    return {'version':VERSION,'document_sha256':sha(units),'units':units}


def document_manifest(document):
    """Safe artifact: no original text, table cells or section titles are persisted."""
    return {'version':VERSION,'document_sha256':document['document_sha256'],
        'units':[{'unit_id':u['unit_id'],'ordinal':u['ordinal'],'locator':u['locator'],
                  'kind':u['kind'],'text_sha256':sha(u['text']),
                  'characters':len(u['text']),'page':u.get('page'),
                  'table_id':u.get('table_id'),'row_index':u.get('row_index'),
                  'structure_status':u.get('structure_status','preserved')}
                 for u in document['units']]}


def evidence_block_map(blocks):
    """Model uses unique unit IDs. Legacy repeated locators require disambiguation by quote."""
    result={}
    for unit in prepare_document(blocks)['units']:
        result[unit['unit_id']]=unit
        result.setdefault(unit['locator'],[]).append(unit)
    return result


def pack_requests(document, render, count_tokens, limits):
    """Count the rendered envelope, not characters. Every unit is processed or deferred.

    count_tokens is an explicitly supplied, provider-compatible local counter.
    Missing/unverified capabilities do not admit a network call.
    """
    if not limits or not callable(count_tokens):raise ValueError('model_capabilities_or_token_counter_required')
    if limits.get('reviewed') is not True or not limits.get('model') or not limits.get('checked_on'):
        raise ValueError('model_capabilities_not_reviewed')
    try:
        checked=limits['checked_on']
        if not isinstance(checked,str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}',checked):raise ValueError()
        date.fromisoformat(checked)
    except (TypeError,ValueError):raise ValueError('invalid_capability_review_date')
    if type(limits.get('shared_context')) is not bool:raise ValueError('explicit_context_type_required')
    for key in ('input_limit','output_limit','output_reserve','max_request_bytes'):
        if type(limits.get(key)) is not int or limits[key]<=0:raise ValueError('invalid_model_limit:'+key)
    if limits['output_reserve']>limits['output_limit']:raise ValueError('output_reserve_exceeds_limit')
    margin=limits.get('safety_tokens',0)
    if type(margin) is not int or margin<0:raise ValueError('invalid_safety_tokens')
    cap=limits['input_limit']-margin
    if limits.get('shared_context'):
        context=limits.get('context_limit');thinking=limits.get('thinking_reserve',0)
        if type(context) is not int or context<=0 or type(thinking) is not int or thinking<0:raise ValueError('invalid_context_limit')
        cap=min(cap,context-limits['output_reserve']-thinking-margin)
    def measure(units):
        envelope=render(units)
        wire=json.dumps(envelope,ensure_ascii=False,sort_keys=True)
        tokens=count_tokens(envelope)
        if type(tokens) is not int or tokens<0:raise ValueError('invalid_token_count')
        return tokens,len(wire.encode('utf-8'))
    def fits(units):
        t,size=measure(units)
        return t<=cap and size<=limits['max_request_bytes']
    if not fits([]):raise ValueError('shared_context_exceeds_budget')
    queue=[]
    for unit in document['units']:
        if fits([unit]):queue.append(unit);continue
        # A single oversized paragraph is split without dropping any characters.
        start=0
        while start<len(unit['text']):
            lo,hi=1,len(unit['text'])-start;best=0
            while lo<=hi:
                mid=(lo+hi)//2
                part={**unit,'text':unit['text'][start:start+mid],'span_start':start,'span_end':start+mid}
                if fits([part]):best=mid;lo=mid+1
                else:hi=mid-1
            if not best:raise ValueError('unit_context_exceeds_budget:'+unit['unit_id'])
            # Prefer sentence boundaries. Fallback is still lossless and mapped to its parent.
            prefix=unit['text'][start:start+best]
            cuts=list(re.finditer(r'[。；;！？\n]',prefix))
            if cuts and cuts[-1].end()>=best//2:
                cut=cuts[-1].end()
                # Tokenizers need not be monotonic: even a shorter prefix must fit.
                if fits([{**unit,'text':unit['text'][start:start+cut],
                          'span_start':start,'span_end':start+cut}]):best=cut
            queue.append({**unit,'text':unit['text'][start:start+best],
                          'span_start':start,'span_end':start+best})
            start+=best
    chunks=[];current=[]
    for unit in queue:
        if current and not fits(current+[unit]):
            chunks.append(current);current=[]
        current.append(unit)
    if current:chunks.append(current)
    return [{'chunk_id':'c-'+sha([(u['unit_id'],u.get('span_start'),u.get('span_end')) for u in chunk])[:24],
             'units':chunk,'input_tokens':measure(chunk)[0]} for chunk in chunks]
