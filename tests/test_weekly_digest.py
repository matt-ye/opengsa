"""資料 PR 每週彙整一次：排程只在週一那輪開 PR，手動執行照舊；每輪 10 份變動、待審 60 份。不連外。"""
import json
from pathlib import Path
import unittest

from scripts.scan_sources import validate_config

ROOT = Path(__file__).resolve().parents[1]


class WeeklyDigestTests(unittest.TestCase):
    def test_only_the_monday_schedule_opens_the_data_pr(self):
        workflow = (ROOT / ".github/workflows/scan-sources.yml").read_text(encoding="utf-8")
        self.assertIn("- cron: '17 1 * * 1'", workflow)
        job = workflow.split("\n  data-pr:")[1].split("\n  status:")[0]
        self.assertIn("github.event.schedule == '17 1 * * 1'", job)
        self.assertIn("github.event_name != 'schedule'", job)

    def test_budgets_follow_the_weekly_digest(self):
        config = json.loads((ROOT / "data/scan-sources.json").read_text(encoding="utf-8"))
        self.assertEqual((config["max_changed_documents"], config["max_pending_candidates"]), (10, 60))
        validate_config(config)
        with self.assertRaises(ValueError):
            validate_config({**config, "max_changed_documents": 11})


if __name__ == "__main__":
    unittest.main()
