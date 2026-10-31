"""Read-only visibility; mutations below are synthetic, no GET or approval."""
from copy import deepcopy
import json
from pathlib import Path
import unittest
from scripts.radar_metadata import radar_metadata
from scripts.build_review_workspace import candidate_preview_data

ROOT=Path(__file__).resolve().parents[1]
read=lambda name:json.loads((ROOT/'data'/name).read_text(encoding='utf-8'))


class RadarMetadataTests(unittest.TestCase):
    def test_all_19_records_keep_exact_urls_and_snapshot_without_approval(self):
        bundle=read('candidates/source-review.json');before=deepcopy(bundle)
        metadata=radar_metadata(bundle)
        preview=candidate_preview_data(bundle,read('pilot.json'),read('scan-sources.json'))
        sources={s['id']:s for s in preview['sources']}
        self.assertEqual(len(metadata['records']),19)
        self.assertEqual(len(preview['opportunities']),19)
        for item,cand in zip(preview['opportunities'],bundle['candidates']):
            record=metadata['records'][item['id']]
            self.assertEqual(record['url'],cand['source_metadata']['url'])
            refs=item['eligibility']['identity']['refs']
            self.assertTrue(refs)
            self.assertEqual(sources[refs[0]['source']]['url'],record['url'])
            self.assertEqual(item['review']['status'],'draft')
        self.assertEqual(bundle,before)

    def test_gaps_allow_other_evidence_but_failed_checks_hide_claims(self):
        bundle=read('candidates/source-review.json');candidate=deepcopy(bundle['candidates'][0])
        def record(c):return radar_metadata({'candidates':[c]})['records'][c['candidate_id']]
        self.assertTrue(record(candidate)['known']['audience'])
        candidate['verification']['checks']['coverage_ok']=False
        self.assertTrue(record(candidate)['known']['audience'])
        candidate['verification']['checks']['evidence_supported']=False
        unsafe=record(candidate)
        self.assertTrue(unsafe['unsafe']);self.assertFalse(any(unsafe['known'].values()))
        self.assertEqual(unsafe['url'],candidate['source_metadata']['url'])
        candidate=deepcopy(bundle['candidates'][0]);candidate['field_evidence']=[]
        self.assertFalse(any(record(candidate)['known'].values()))


if __name__=='__main__':unittest.main()
