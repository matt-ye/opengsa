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
        index=json.loads((ROOT/'data/source-chain-index.json').read_text(encoding='utf-8'))
        gaps=[gap for p in index['programs'] for gap in p['gaps']]
        # 來源改版時，舊版本上的規則會撤下待重核，並記在方案的缺口（排程掃描的正常結果）。
        # 規則還在就檢查值；撤下了就要有紀錄，不能無聲消失。
        def kept_or_withdrawn(rule_id,check):
            if rule_id in rules:check(rules[rule_id])
            else:self.assertTrue(any(rule_id in gap for gap in gaps),rule_id+' disappeared without a gap note')
        kept_or_withdrawn('faos-agency-months',lambda r:self.assertEqual(r['value']['unit'],'calendar_month'))
        kept_or_withdrawn('faos-ntu-paper-days',lambda r:self.assertEqual(r['value']['day_basis'],'not_stated'))
        kept_or_withdrawn('dragon-116-central',lambda r:self.assertEqual(r['actor'],'institution'))
        dragon=next(p for p in index['programs'] if p['key']=='nstc-abroad-dragon')
        self.assertNotIn('dragon-116-ntu',rules)
        self.assertTrue(any('dragon-116-ntu' in gap for gap in dragon['gaps']))
        self.assertTrue(all(r['review_status']=='pending' for r in rules.values()))

    def test_withdrawn_rule_is_accepted_only_with_a_gap_note(self):
        # 模擬排程掃到新版本：依附的規則一起撤下，缺口記上 id（和流程實際寫法相同）。
        index=json.loads((ROOT/'data/source-chain-index.json').read_text(encoding='utf-8'))
        program=next((p for p in index['programs'] if any(r['id']=='faos-agency-months' for r in p['rules'])),None)
        if program is None:self.skipTest('faos rules already withdrawn in the current data')
        gone={'faos-agency-months','faos-ntu-paper-days'}
        program['rules']=[r for r in program['rules'] if r['id'] not in gone]
        program['gaps'].append('本批候選來源已有新版本，舊規則先撤下待重核：'+','.join(sorted(gone)))
        rules={r['id'] for p in load_graph(index)['programs'] for r in p['rules']}
        self.assertFalse(gone&rules)
        self.assertTrue(any('faos-agency-months' in gap for p in index['programs'] for gap in p['gaps']))

    def test_stale_evidence_and_cross_program_anchor_rejected(self):
        index=json.loads((ROOT/'data/source-chain-index.json').read_text(encoding='utf-8'))
        changed=deepcopy(index);p=next(p for p in changed['programs'] if p['rules']);p['rules'][0]['evidence_refs'][0]['revision_id']='0'*64
        with self.assertRaisesRegex(ValueError,'current_read_revision'):load_graph(changed)
        changed=deepcopy(index);p=next(p for p in changed['programs'] if p['rules']);p['rules'][0]['value']['anchor_rule_id']='dragon-116-central'
        with self.assertRaisesRegex(ValueError,'cross_program'):load_graph(changed)
