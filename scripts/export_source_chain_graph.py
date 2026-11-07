"""Validate the review-only chain index; generate a portable tree and JSON Canvas."""
import argparse
from collections import Counter
from copy import deepcopy
import json
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from jsonschema import Draft202012Validator, FormatChecker
from scripts.scan_sources import digest
from scripts.source_chains import validate

READ={'changed','unchanged','unchanged_304'}
ROLE={'policy':'辦法／法源','annual_call':'年度公告','local_intake':'地方收件','local_process':'校內流程','forms_index':'表格入口','application_system':'申辦入口','attachment':'附件／表單','candidate_source':'原候選來源','related_call':'待核關聯'}

def read(path):
    return json.loads((ROOT/path).read_text(encoding='utf-8'))

def load_graph(index=None,reader=None):
    read_file=reader or read
    index=deepcopy(index) if index is not None else read_file('data/source-chain-index.json')
    Draft202012Validator(read_file('schema/source-chain-index.schema.json'),format_checker=FormatChecker()).validate(index)
    if digest(read_file(index['candidate_file']))!=index['candidate_sha256']:
        raise ValueError('candidate_snapshot_changed')
    candidates=read_file(index['candidate_file'])['candidates']
    expected={c['candidate_id']:c['program_key'] for c in candidates}
    actual={cid:p['key'] for p in index['programs'] for cid in p['candidate_ids']}
    if expected!=actual or sum(len(p['candidate_ids']) for p in index['programs'])!=len(expected):
        raise ValueError('candidate_membership_mismatch')
    if len({p['key'] for p in index['programs']})!=len(index['programs']):
        raise ValueError('duplicate_program')
    docs={};edges=[];seen_edges=set()
    def edge(program,from_url,to_url,role,origin):
        source='doc-'+digest(from_url)[:24];target='doc-'+digest(to_url)[:24]
        if source not in docs or target not in docs:
            raise ValueError('unresolved_graph_edge')
        identity=(program,source,target,role,origin)
        if identity not in seen_edges:
            seen_edges.add(identity);edges.append(dict(program_key=program,source=source,target=target,role=role,origin=origin))
    bundles=[read_file(path) for path in index['bundles']]
    for bundle in bundles:
        validate(bundle)
        for document in bundle['documents']:
            # An unvisited link/snapshot cannot overwrite a successful fetch or a newer failure.
            if document['id'] in docs and document['status'] in ('candidate_snapshot','discovered_not_read'):
                continue
            docs[document['id']]=deepcopy(document)
    for relation in bundles[0]['relations']:
        edge(relation['program_key'],docs[relation['from']]['url'],relation['url'],relation['role'],'baseline_relation')
    for config_path in index['batch_configs']:
        config=read_file(config_path)
        for source in config['sources']:
            for parent in source.get('parent_urls',[]):
                edge(source['program_key'],parent,source['url'],source['role'],'registry_context')
    for link in index['included_links']:
        source=docs['doc-'+digest(link['from_url'])[:24]]
        if not any(child['url']==link['to_url'] for child in source.get('links',[])):
            raise ValueError('included_link_not_observed')
        edge(link['program_key'],link['from_url'],link['to_url'],link['role'],'observed_link')
    title_by_url={c['source_metadata']['url']:c['title'] for c in candidates}
    title_by_url.update(index['document_titles'])
    for document in docs.values():
        document['role']=document.get('role') or next((e['role'] for e in edges if e['target']==document['id']),'candidate_source')
        document['title']=title_by_url.get(document['url']) or unquote(urlsplit(document['url']).path.rsplit('/',1)[-1])[:90] or urlsplit(document['url']).hostname
        document['clarity']='read' if document['status'] in READ else 'snapshot' if document['status']=='candidate_snapshot' else 'unread' if document['status']=='discovered_not_read' else 'blocked'
        if document['evidence_mode']=='hash_only' and any('excerpt' in e for e in document.get('events',[])):
            raise ValueError('hash_only_excerpt_forbidden')
    programs=deepcopy(index['programs']);rule_ids={r['id'] for p in programs for r in p['rules']}
    if sum(len(p['rules']) for p in programs)!=len(rule_ids):
        raise ValueError('duplicate_rule')
    for program in programs:
        ids={'doc-'+digest(c['source_metadata']['url'])[:24] for c in candidates if c['program_key']==program['key']}
        ids.update('doc-'+digest(c['url'])[:24] for c in program['source_contexts'])
        for relation in edges:
            if relation['program_key']==program['key']:ids.update((relation['source'],relation['target']))
        for rule in program['rules']:
            anchor=rule['value'].get('anchor_rule_id')
            if anchor and anchor not in {r['id'] for r in program['rules']}:
                raise ValueError('cross_program_or_missing_rule_anchor')
            for ref in rule['evidence_refs']:
                document=docs.get(ref['document_id'])
                if not document or document['status'] not in READ or ref['revision_id']!=document.get('revision_id'):
                    raise ValueError('rule_evidence_not_current_read_revision')
                ids.add(document['id'])
        if not ids<=docs.keys():raise ValueError('program_document_missing')
        context_roles={c['url']:c['role'] for c in program['source_contexts']}
        order={'policy':0,'annual_call':1,'local_intake':2,'local_process':3,'forms_index':4,'application_system':5,'attachment':6}
        program['document_ids']=sorted(ids,key=lambda key:(order.get(context_roles.get(docs[key]['url'],docs[key]['role']),7),docs[key]['title'],key))
    used={doc for program in programs for doc in program['document_ids']}
    return {'schema_version':index['schema_version'],'as_of':index['as_of'],'notes':index['notes'],'current_batch':index['current_batch'],
            'programs':programs,'documents':{key:docs[key] for key in sorted(used)},'edges':edges,
            'summary':{'programs':len(programs),'candidates':len(candidates),'documents':len(used),'relations':len(edges),
                       'batch_programs':sum(p['audited_batch']==index['current_batch'] for p in programs),'rules':len(rule_ids),
                       'document_statuses':dict(sorted(Counter(docs[key]['clarity'] for key in used).items()))}}

def canvas(graph):
    nodes=[];edges=[];positions={};step=0
    node_id=lambda value:digest(value)[:16]
    for program in graph['programs']:
        program_id=node_id('program:'+program['key']);y=step
        nodes.append(dict(id=program_id,type='text',x=0,y=y,width=350,height=175,color='5',text='## '+program['title']+'\n\n'+str(len(program['candidate_ids']))+'筆候選｜'+program['audit_status']+'\n\n'+('本批已補鏈，仍有缺口' if program['rules'] else '沿用基線；待下一批查核')))
        fresh=[doc for doc in program['document_ids'] if doc not in positions]
        for i,doc_id in enumerate(fresh):
            doc=graph['documents'][doc_id];x=430+(i%4)*410;dy=y+(i//4)*300
            positions[doc_id]=(x,dy)
            text='### '+doc['title']+'\n\n'+ROLE.get(doc.get('role'),'相關來源')+' · '+doc['format']+' · '+doc['status']+'\n\n查核：'+doc['observed_at'][:10]+'\n\n[來源網站]('+doc['url']+')\n\n`'+doc_id+'`'
            nodes.append(dict(id=node_id(doc_id),type='text',x=x,y=dy,width=350,height=260,color={'read':'4','snapshot':'3','unread':'2','blocked':'1'}[doc['clarity']],text=text))
        for doc_id in program['document_ids']:
            edges.append(dict(id=node_id(program_id+doc_id),fromNode=program_id,toNode=node_id(doc_id),fromSide='right',toSide='left',toEnd='arrow',color='5',label='方案引用'))
        step+=max(1,(len(fresh)+3)//4)*300+100
    for relation in graph['edges']:
        if relation['source'] not in positions or relation['target'] not in positions:continue
        edges.append(dict(id=node_id(json.dumps(relation,sort_keys=True)),fromNode=node_id(relation['source']),toNode=node_id(relation['target']),fromSide='bottom',toSide='top',toEnd='arrow',label=ROLE.get(relation['role'],relation['role'])+'／'+relation['origin']))
    nodes.append(dict(id=node_id('legend'),type='text',x=0,y=-260,width=850,height=200,text='# OpenGSA 來源資訊鏈\n\n綠：已讀取；黃：既有快照；橙：連結未讀；紅：受阻。來源可讀不等於規則完整或已核准。共用文件只有一個節點，會跨方案連線。\n\nregistry_context＝配置的脈絡關係，不表示原頁有該超連結。observed_link＝實際觀察到的連結。規則與缺口請看同資料生成的HTML樹狀圖。'))
    ids=[n['id'] for n in nodes];eids=[e['id'] for e in edges]
    if len(ids)!=len(set(ids)) or len(eids)!=len(set(eids)) or any(e['fromNode'] not in ids or e['toNode'] not in ids for e in edges):
        raise ValueError('canvas_reference_or_identity_error')
    return {'nodes':nodes,'edges':edges}

def export(output,index=None,reader=None):
    graph=load_graph(index,reader);output=Path(output);output.mkdir(parents=True,exist_ok=True)
    template=(ROOT/'docs/design/source-chain-map.template.html').read_text(encoding='utf-8')
    payload=json.dumps(graph,ensure_ascii=False).replace('<','\\u003c')
    (output/'source-chain-map.html').write_text(template.replace('/*GRAPH_DATA*/',payload),encoding='utf-8')
    (output/'source-chain-map.canvas').write_text(json.dumps(canvas(graph),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return graph['summary']

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True);parser.add_argument('--check',action='store_true');args=parser.parse_args()
    if args.check:
        graph=load_graph();canvas(graph);print(json.dumps(graph['summary'],ensure_ascii=False))
    else:print(json.dumps(export(args.output),ensure_ascii=False))
