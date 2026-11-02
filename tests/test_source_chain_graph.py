"""Graph provenance and Canvas reference regressions; no network."""
from copy import deepcopy
import json
from pathlib import Path
import unittest
from tempfile import TemporaryDirectory
from scripts.export_source_chain_graph import load_graph,canvas,export

ROOT=Path(__file__).resolve().parents[1]
class SourceChainGraphTests(unittest.TestCase):
    def test_committed_diagrams_match_structured_sources(self):
        with TemporaryDirectory() as directory:
            export(directory)
            for name in ['source-chain-map.html','source-chain-map.canvas']:
                self.assertEqual((Path(directory)/name).read_text(encoding='utf-8'),(ROOT/'docs/source-chains'/name).read_text(encoding='utf-8'))

    def test_candidate_coverage_and_canvas_references(self):
        graph=load_graph();candidates=json.loads((ROOT/'data/candidates/source-review.json').read_text(encoding='utf-8'))['candidates']
        self.assertEqual(graph['summary']['programs'],len({c['program_key'] for c in candidates}));self.assertEqual(graph['summary']['candidates'],len(candidates))
        self.assertEqual(graph['summary']['batch_programs'],3)
        result=canvas(graph);ids={n['id'] for n in result['nodes']}
        self.assertEqual(len(ids),len(result['nodes']))
        self.assertTrue(all(e['fromNode'] in ids and e['toNode'] in ids for e in result['edges']))

    def test_pending_rules_keep_roles_and_month_units(self):
        graph=load_graph();rules={r['id']:r for p in graph['programs'] for r in p['rules']}
        self.assertEqual(rules['faos-agency-months']['value']['unit'],'calendar_month')
        self.assertEqual(rules['faos-ntu-paper-days']['value']['day_basis'],'not_stated')
        index=json.loads((ROOT/'data/source-chain-index.json').read_text(encoding='utf-8'))
        dragon=next(p for p in index['programs'] if p['key']=='nstc-abroad-dragon')
        self.assertNotIn('dragon-116-ntu',rules)
        self.assertTrue(any('dragon-116-ntu' in gap for gap in dragon['gaps']))
        self.assertEqual(rules['dragon-116-central']['actor'],'institution')
        self.assertTrue(all(r['review_status']=='pending' for r in rules.values()))

    def test_stale_evidence_and_cross_program_anchor_rejected(self):
        index=json.loads((ROOT/'data/source-chain-index.json').read_text(encoding='utf-8'))
        changed=deepcopy(index);p=next(p for p in changed['programs'] if p['rules']);p['rules'][0]['evidence_refs'][0]['revision_id']='0'*64
        with self.assertRaisesRegex(ValueError,'current_read_revision'):load_graph(changed)
        changed=deepcopy(index);p=next(p for p in changed['programs'] if p['rules']);p['rules'][0]['value']['anchor_rule_id']='dragon-116-central'
        with self.assertRaisesRegex(ValueError,'cross_program'):load_graph(changed)
