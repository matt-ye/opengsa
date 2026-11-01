"""No unvisited source is green; a finite audit cannot hide original URLs."""
from copy import deepcopy
import unittest
from scripts.close_source_verification import close,validate_report
from scripts.expand_sources import read
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

class SourceClosureTests(unittest.TestCase):
    def test_all_original_ids_and_publication_boundaries(self):
        data=read(ROOT/'data/source-expansion/original-source-verification.json')
        inventory=read(ROOT/'data/source-inventory.json')
        summary=validate_report(data,inventory)
        self.assertEqual(summary['original_urls'],len(inventory['rows']))
        self.assertFalse(summary['all_content_verified'])
        self.assertTrue(any(r['status']=='byte_identical_document_alias' for r in data['records']))

    def test_missing_source_and_fake_content_success_rejected(self):
        data=read(ROOT/'data/source-expansion/original-source-verification.json');inventory=read(ROOT/'data/source-inventory.json')
        bad=deepcopy(data);bad['records'].pop()
        with self.assertRaises(ValueError):validate_report(bad,inventory)
        bad=deepcopy(data);row=next(r for r in bad['records'] if not r['content_verified']);row['card_ready']=True
        with self.assertRaises(ValueError):validate_report(bad,inventory)

    def test_cannot_close_partially_scanned_inventory(self):
        with self.assertRaisesRegex(ValueError,'not_all_original'):
            close({'rows':[{'id':'SYNTH'}]},{},{'records':{}})

if __name__=='__main__':unittest.main()
