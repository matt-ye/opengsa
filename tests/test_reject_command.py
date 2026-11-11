"""資料 PR 上的 /reject：解析留言、寫進台帳、停用卡全被駁回的新來源。合成資料，不連外、不推送。"""
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from scripts.reject_command import parse, reply, run

ROOT = Path(__file__).resolve().parents[1]


def card(candidate_id, source_id):
    return {"candidate_id": candidate_id, "source_metadata": {"source_id": source_id, "revision_id": hashlib.sha256(candidate_id.encode()).hexdigest()}}


class RejectCommandTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        self.base, self.pr = self.tmp / "base", self.tmp / "pr"
        for root in (self.base, self.pr):
            (root / "data/candidates").mkdir(parents=True)
            (root / "data/scan-reviews.json").write_text(json.dumps({"schema_version": "1.1.0", "reviews": []}), encoding="utf-8")
        old = {"id": "old-source", "url": "https://a.test/old", "enabled": True}
        new = {"id": "new-source", "url": "https://a.test/new", "enabled": True}
        pair = {"id": "pair-source", "url": "https://a.test/pair", "enabled": True}
        (self.base / "data/scan-sources.json").write_text(json.dumps({"sources": [old]}), encoding="utf-8")
        (self.pr / "data/scan-sources.json").write_text(json.dumps({"sources": [old, new, pair]}), encoding="utf-8")
        cards = [card("c-old", "old-source"), card("c-new", "new-source"), card("c-pair-1", "pair-source"), card("c-pair-2", "pair-source")]
        (self.pr / "data/candidates/source-review.json").write_text(json.dumps({"candidates": cards}), encoding="utf-8")

    def sources(self):
        return {s["id"]: s["enabled"] for s in json.loads((self.pr / "data/scan-sources.json").read_text(encoding="utf-8"))["sources"]}

    def test_parse_reads_one_card_per_line_and_optional_problem_source(self):
        body = ("看過了\n/reject c-1 not_a_program 列表頁標題\n/reject c-2 往年公告\n/reject c-3\n/rejectx\n"
                "/reject c-4\tnot_a_program\t名單\n/reject `c-5` 理由")
        self.assertEqual(parse(body), [("c-1", "not_a_program", "列表頁標題"), ("c-2", "other", "往年公告"),
                                       ("/reject c-3", None, None), ("/rejectx", None, None),
                                       ("c-4", "not_a_program", "名單"), ("/reject `c-5` 理由", None, None)])

    def test_dismissals_go_to_the_ledger_and_only_fully_rejected_new_sources_are_disabled(self):
        outcome = run("/reject c-new not_a_program 不是方案\n/reject c-pair-1 source_page 往年公告\n/reject c-old extraction 抽錯",
                      "matt-ye", self.pr, self.base)
        self.assertEqual([r["status"] for r in outcome["results"]], ["dismissed"] * 3)
        reviews = json.loads((self.pr / "data/scan-reviews.json").read_text(encoding="utf-8"))["reviews"]
        self.assertEqual([(r["candidate_id"], r["problem_source"], r["reviewer"]) for r in reviews],
                         [("c-new", "not_a_program", "matt-ye"), ("c-pair-1", "source_page", "matt-ye"), ("c-old", "extraction", "matt-ye")])
        # 新來源卡全被駁回才停用；另一張卡還在的新來源、PR 之前就有的來源都不動。
        self.assertEqual(outcome["disabled_sources"], ["new-source"])
        self.assertEqual(self.sources(), {"old-source": True, "new-source": False, "pair-source": True})
        # main 的工作目錄不能被改到。
        self.assertEqual(json.loads((self.base / "data/scan-reviews.json").read_text(encoding="utf-8"))["reviews"], [])

    def test_unknown_or_repeated_cards_are_reported_and_other_lines_still_apply(self):
        outcome = run("/reject c-new 不是方案\n/reject nope 不存在\n/reject c-new 又一次", "matt-ye", self.pr, self.base)
        self.assertEqual([r["status"] for r in outcome["results"]], ["dismissed", "error", "error"])
        text = reply(outcome, pushed=True)
        self.assertIn("已駁回 1 張", text)
        self.assertIn("unknown_candidate_id", text)
        self.assertIn("already_dismissed", text)
        self.assertIn("當週合併", text)

    def test_reply_says_nothing_was_pushed_when_a_check_failed(self):
        outcome = run("/reject c-new 不是方案", "matt-ye", self.pr, self.base)
        self.assertIn("沒有推送", reply(outcome, pushed=False, failed_gate="check_data"))

    def test_workflow_only_runs_for_the_owner_on_data_branches_and_keeps_the_comment_out_of_commands(self):
        workflow = (ROOT / ".github/workflows/reject-command.yml").read_text(encoding="utf-8")
        self.assertIn("github.event.comment.user.login == github.repository_owner", workflow)
        self.assertIn("^data/[a-z0-9-]+$", workflow)
        self.assertIn("isCrossRepository", workflow)
        self.assertNotRegex(workflow, r"\$\{\{\s*github\.event\.comment\.body")
        self.assertNotIn("--force", workflow)
        self.assertEqual(workflow.count("persist-credentials: false"), 2)
        self.assertIn('.baseRefName)" != "main"', workflow)
        # 檢查用 main 的程式跑（cwd 是 main 的工作目錄），PR 分支的程式碼不執行；權杖不放進網址。
        self.assertIn("run_gates('.')", workflow)
        self.assertNotIn("run_gates('pr')", workflow)
        self.assertNotIn("x-access-token:${GH_TOKEN}@", workflow)
        self.assertNotIn("secrets.", workflow)


if __name__ == "__main__":
    unittest.main()
