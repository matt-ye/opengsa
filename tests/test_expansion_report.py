"""Report compaction and output boundary checks without live network."""
import unittest
from scripts.export_expansion_report import compact,render,report,validate_artifacts
from scripts.expand_sources import initial_state
from tests.test_expansion import row

class ExpansionReportTests(unittest.TestCase):
    def test_committed_batch_contract_and_cost_boundaries(self):
        self.assertTrue(validate_artifacts()['inventory_dispositions_complete'])

    def test_manifest_compacted_without_mutating_source(self):
        original={'document_manifest':{'version':'SYNTH','document_sha256':'a'*64,'units':[{'text_sha256':'b'*64}]}}
        actual=compact(original)
        self.assertNotIn('document_manifest',actual)
        self.assertEqual(actual['document_manifest_summary']['unit_count'],1)
        self.assertIn('units',original['document_manifest'])

    def test_all_sources_accounted_and_search_alias_not_duplicate(self):
        r=row(kind='SYNTH source',origins=[],parents=[],program_keys=[])
        inv={'rows':[r]};s=initial_state(inv);s['records'][r['url']]={'status':'read','links':[]}
        d=report(inv,s,{'sources':[r]})
        self.assertTrue(d['summary']['inventory_dispositions_complete'])
        self.assertEqual(len(d['sources']),1)
        del s['records'][r['url']]
        self.assertFalse(report(inv,s,{'sources':[]})['summary']['inventory_dispositions_complete'])

    def test_source_markup_is_escaped_and_script_url_not_linked(self):
        data={'summary':{},'candidates':[],'sources':[{'batch':'B1','title':'<img onerror=evil()>','url':'javascript:evil()',
            'observation':{'status':'read'}}]}
        html=render(data)
        self.assertNotIn('<img onerror',html);self.assertIn('&lt;img',html)
        self.assertNotIn('href="javascript:',html)

if __name__=='__main__':unittest.main()
