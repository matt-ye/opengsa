"""No network: replay must reject unknown targets and invalid shared budgets first."""
from pathlib import Path
import tempfile
import unittest
import json
from scripts.refresh_radar_subset import ROOT,refresh

class RefreshRadarSubsetTests(unittest.TestCase):
    def setUp(self):
        (ROOT/'work').mkdir(exist_ok=True)

    def test_unknown_source_and_invalid_budget_never_call_transport(self):
        calls=[]
        def transport(*args):calls.append(args);raise AssertionError('network_must_not_be_used')
        with tempfile.TemporaryDirectory(dir=ROOT/'work') as folder:
            with self.assertRaisesRegex(ValueError,'source_must_be_an_existing_primary_candidate'):
                refresh(['SYNTH-unknown'],Path(folder)/'unknown',transport=transport)
            for budget in (-1,20,True):
                with self.assertRaisesRegex(ValueError,'invalid_prior_request_budget'):
                    refresh(['SYNTH-unknown'],Path(folder)/str(budget),transport=transport,prior_requests=budget)
        self.assertEqual(calls,[])

    def test_previous_artifact_cannot_hide_model_calls_or_reset_budget(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'work') as folder:
            previous=Path(folder)/'previous';previous.mkdir()
            bundle=json.loads((ROOT/'data/candidates/source-review.json').read_text(encoding='utf-8'))
            bundle['candidates']=[c for c in bundle['candidates'] if c['source_metadata']['source_id']=='discovery-r139']
            (previous/'pending-candidates.json').write_text(json.dumps(bundle),encoding='utf-8')
            for calls,budget in [(0,2),(1,3)]:
                (previous/'report.json').write_text(json.dumps({'http_requests':3,'model_calls':calls,'published':False}),encoding='utf-8')
                with self.assertRaisesRegex(ValueError,'previous_artifact_or_budget_boundary_mismatch'):
                    refresh(['discovery-r139'],Path(folder)/('new-'+str(calls)),transport=lambda *a:self.fail('unexpected network'),
                        prior_requests=budget,previous_output=previous)

if __name__=='__main__':unittest.main()
