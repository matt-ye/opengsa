"""Isolated, explicitly requested held-out scans. Never edits source registry or pilot."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from scripts.scan_sources import Fetcher,scan,validate_config
from scripts.extract_candidates import DisabledModelAdapter,refetch_and_extract_candidates
from scripts.check_data import validate_candidate_snapshot
from scripts.document_ir import document_manifest,prepare_document


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',type=Path,default=ROOT/'docs/examples/extraction-validation-sources.json')
    parser.add_argument('--output-dir',type=Path,required=True)
    args=parser.parse_args();output=args.output_dir.resolve()
    if not output.is_relative_to(ROOT/'work') or (output.exists() and any(output.iterdir())):
        parser.error('Use a fresh work directory')
    config=json.loads(args.config.read_text(encoding='utf-8'));validate_config(config)
    if config.get('validation_only') is not True:parser.error('An isolated validation-only configuration is required')
    fetcher=Fetcher(config);state,report=scan(config,fetcher=fetcher)
    bundle,statuses=refetch_and_extract_candidates(list(state['pending'].values()),config,fetcher=fetcher,
        in_memory_blocks_by_url=fetcher.in_memory_blocks,allow_network_refetch=False,model_adapter=DisabledModelAdapter())
    errors=validate_candidate_snapshot(bundle,config)
    artifacts=['scripts/semantic_facts.py','scripts/extract_candidates.py','scripts/verify_candidates.py','scripts/document_ir.py',
        'schema/candidate.schema.json']
    result={'checked_at':datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'purpose':'held_out_format_and_evidence_validation_not_accuracy_estimate',
        'http_requests':fetcher.count,'model_calls':0,'published':False,'source_registry_modified':False,
        'code_and_config_sha256':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in artifacts},
        'config_sha256':hashlib.sha256(args.config.read_bytes()).hexdigest(),
        'scan_documents':report['documents'],'candidate_validation_errors':errors,
        'documents':{url:document_manifest(prepare_document(blocks)) for url,blocks in fetcher.in_memory_blocks.items()},
        'results':[{'candidate_id':c['candidate_id'],'url':c['source_metadata']['url'],
            'verification':c['verification']['status'],'errors':c['verification']['errors'],
            'audience_extracted':not c['eligibility']['identity']['text'].startswith('身分條件請至'),
            'degree_rules':c['eligibility']['degrees'],'student_dates':[s['deadline']['value'] for s in c['schedule']['steps']
                if s['actor']=='student' and s['deadline']['value']],
            'field_evidence_count':len(c['field_evidence'])} for c in bundle['candidates']]}
    output.mkdir(parents=True)
    (output/'validation-report.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (output/'pending-candidates.json').write_text(json.dumps(bundle,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k not in ('documents','code_and_config_sha256')},ensure_ascii=False))
    if errors:raise SystemExit(2)


if __name__=='__main__':main()
