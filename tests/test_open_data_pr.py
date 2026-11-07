"""資料 PR：路徑白名單、新網域不進 allowed_hosts、檢查沒過不推。不連外、不碰真實 repo。"""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.open_data_pr import apply_proposal, comment, pr_body, prepare, proposal_files, publish, run_gates


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value if isinstance(value, str) else json.dumps(value, ensure_ascii=False), encoding="utf-8")


SUMMARY = {"accepted_for_radar_proposal": 1, "withheld_failed_checks": 0, "temporal_records": 1, "retired_hand_cards": [], "needs_manual_retire": []}


class OpenDataPrTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name)
        self.root, self.proposal = self.base / "repo", self.base / "proposal"
        write(self.root / "data/scan-sources.json", {"allowed_hosts": ["old.example"], "sources": []})
        write(self.proposal / "summary.json", SUMMARY)
        write(self.proposal / "repo/data/scan-sources.json", {"allowed_hosts": ["new.example", "old.example"],
                                                               "sources": [{"id": "s", "url": "https://new.example/a", "enabled": False}]})

    def test_proposal_can_only_touch_data_and_chain_diagrams(self):
        self.assertEqual(proposal_files(self.proposal), ["data/scan-sources.json"])
        write(self.proposal / "repo/.github/workflows/x.yml", "on: push")
        with self.assertRaisesRegex(ValueError, "proposal_path_not_allowed"):
            proposal_files(self.proposal)

    def test_submitted_host_stays_out_of_allowed_hosts_but_is_reported(self):
        self.assertEqual(apply_proposal(self.proposal, self.root), ["new.example"])
        config = json.loads((self.root / "data/scan-sources.json").read_text(encoding="utf-8"))
        self.assertEqual(config["allowed_hosts"], ["old.example"])
        self.assertEqual(len(config["sources"]), 1)

    def test_enabled_source_on_a_new_host_is_refused(self):
        write(self.proposal / "repo/data/scan-sources.json", {"allowed_hosts": ["new.example"], "sources": [{"id": "s", "url": "https://new.example/a", "enabled": True}]})
        with self.assertRaisesRegex(ValueError, "new_host_source_enabled"):
            apply_proposal(self.proposal, self.root)

    def test_stops_at_the_first_failing_gate(self):
        seen = []
        def runner(command, **_):
            seen.append(command)
            return SimpleNamespace(returncode=1 if "scripts/check_provenance.py" in command else 0)
        self.assertEqual(run_gates(self.root, runner), "check_provenance")
        self.assertEqual(len(seen), 2)

    def prepare(self, gate_code=0, status=" M data/x.json\n"):
        calls = []
        def git(*args):
            calls.append(args)
            return status if args[0] == "status" else ""
        result = prepare(self.proposal, self.base / "out", "測試", self.root, lambda *a, **k: SimpleNamespace(returncode=gate_code), git)
        return result, calls

    def test_failed_gate_commits_nothing(self):
        result, calls = self.prepare(gate_code=1)
        self.assertEqual(result["status"], "gates_failed")
        self.assertFalse([c for c in calls if "commit" in c])

    def test_passing_gates_commit_only_data_paths(self):
        result, calls = self.prepare()
        self.assertEqual(result, {"status": "ready", "new_hosts": ["new.example"]})
        self.assertIn(("add", "--", "data", "docs/source-chains"), calls)
        self.assertIn("new.example", (self.base / "out/pr-body.md").read_text(encoding="utf-8"))

    def test_no_diff_and_no_accepted_cards_do_not_open_a_pr(self):
        self.assertEqual(self.prepare(status="")[0]["status"], "no_changes")
        write(self.proposal / "summary.json", {**SUMMARY, "accepted_for_radar_proposal": 0})
        result, calls = self.prepare()
        self.assertEqual((result["status"], calls), ("no_changes", []))

    def publish(self, create_code=0, existing=()):
        out = self.base / "out"
        write(out / "result.json", {"status": "ready", "new_hosts": []})
        write(out / "pr-body.md", "body")
        calls = []
        def runner(command, **_):
            calls.append(command)
            if command[:3] == ["gh", "pr", "list"]:
                return SimpleNamespace(returncode=0, stdout=json.dumps(list(existing)))
            return SimpleNamespace(returncode=create_code if command[:3] == ["gh", "pr", "create"] else 0, stdout="https://github.com/o/r/pull/1\n")
        return publish(out, "data/radar-proposal", "t", "o/r", "tok", runner), calls

    def test_publish_never_merges_and_only_pushes_a_data_branch(self):
        result, calls = self.publish()
        self.assertEqual(result["pr_url"], "https://github.com/o/r/pull/1")
        self.assertFalse([c for c in calls if "merge" in c])
        self.assertIn("HEAD:refs/heads/data/radar-proposal", calls[0])
        with self.assertRaisesRegex(ValueError, "branch_not_allowed"):
            publish(self.base / "out", "main", "t", "o/r", "tok", lambda *a, **k: None)

    def test_existing_pr_is_updated_instead_of_opening_another(self):
        result, calls = self.publish(existing=[{"url": "https://github.com/o/r/pull/9"}])
        self.assertEqual(result["pr_url"], "https://github.com/o/r/pull/9")
        self.assertFalse([c for c in calls if c[:3] == ["gh", "pr", "create"]])

    def test_without_permission_to_open_a_pr_it_gives_a_compare_link(self):
        result, _ = self.publish(create_code=1)
        self.assertIn("compare/main...data/radar-proposal", result["compare_url"])
        self.assertIn("還沒上架", comment(result))

    def test_body_neutralises_page_titles(self):
        summary = {**SUMMARY, "retired_hand_cards": [{"title": "@someone [連結](http://x) `code`"}]}
        body = pr_body(summary, [], "測試")
        self.assertNotIn("@someone", body)
        self.assertNotIn("[連結]", body)


if __name__ == "__main__":
    unittest.main()
