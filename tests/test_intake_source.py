"""來源提交入口：只有 owner 核可才處理，公開輸入不進指令也不進留言。"""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.intake_source import APPROVAL_LABEL, CATEGORIES, IntakeRejected, build_request, comment, form_fields, validated_url

BODY = """### 資源名稱

合成基金會 @someone `惡意`

### 公開來源網址

https://example.test/news/1

### 資源類型

研究成果獎／學術獎項

### 大致適用對象（選填）

_No response_
"""


def event(**over):
    base = {"action": "labeled", "label": {"name": APPROVAL_LABEL}, "sender": {"login": "owner"},
            "repository": {"owner": {"login": "owner"}}, "issue": {"number": 7, "body": BODY}}
    return {**base, **over}


class IntakeSourceTests(unittest.TestCase):
    def test_form_parsing_matches_the_issue_template(self):
        fields = form_fields(BODY)
        self.assertEqual(fields["公開來源網址"], "https://example.test/news/1")
        self.assertNotIn("大致適用對象（選填）", fields)
        template = (ROOT / ".github/ISSUE_TEMPLATE/resource-source.yml").read_text(encoding="utf-8")
        self.assertIn("label: 公開來源網址", template)
        for label in CATEGORIES:
            self.assertIn(label, template)

    def test_accepted_request_keeps_only_validated_fields(self):
        request = build_request(event())
        self.assertEqual((request["status"], request["issue"], request["url"], request["category"]), ("accepted", 7, "https://example.test/news/1", "award"))
        self.assertFalse(request["already_registered"])
        self.assertFalse(request["published"])
        self.assertNotIn("合成基金會", json.dumps(request, ensure_ascii=False))
        self.assertNotIn("@someone", comment(request))

    def test_registered_url_is_flagged_not_rejected(self):
        self.assertTrue(build_request(event(), ["https://example.test/news/1"])["already_registered"])

    def test_only_owner_label_counts_as_approval(self):
        for bad in ({"sender": {"login": "someone"}}, {"label": {"name": "other"}}, {"action": "opened"}, {"repository": {"owner": {}}}):
            with self.subTest(bad), self.assertRaises(IntakeRejected) as caught:
                build_request(event(**bad))
            self.assertEqual(str(caught.exception), "not_approved_by_owner")

    def test_unsafe_urls_are_rejected(self):
        cases = {"http://example.test/a": "invalid_url", "https://user:pw@example.test/a": "invalid_url", "https://example.test:8443/a": "invalid_url",
                 "https://example.test/a b": "invalid_url", "ftp://example.test/a": "invalid_url", "not a url": "invalid_url", "": "missing_url", "https://": "invalid_url",
                 "https://127.0.0.1/a": "private_host", "https://[::1]/a": "private_host", "https://169.254.169.254/latest": "private_host",
                 "https://localhost/a": "private_host", "https://intranet/a": "private_host", "https://svc.internal/a": "private_host",
                 "https://example.test/login": "restricted_url", "https://example.test/a?token=abc": "restricted_url", "https://example.test/名冊.pdf": "restricted_url"}
        for raw, reason in cases.items():
            with self.subTest(raw), self.assertRaises(IntakeRejected) as caught:
                validated_url(raw)
            self.assertEqual(str(caught.exception), reason)

    def test_cli_writes_a_comment_for_rejected_submissions(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "event.json"
            path.write_text(json.dumps(event(issue={"number": 7, "body": "### 公開來源網址\n\nhttp://example.test/"}), ensure_ascii=False), encoding="utf-8")
            subprocess.run([sys.executable, str(ROOT / "scripts/intake_source.py"), "--event", str(path), "--output", str(Path(tmp) / "out")], check=True, capture_output=True)
            self.assertEqual(json.loads((Path(tmp) / "out/request.json").read_text(encoding="utf-8"))["reason"], "invalid_url")
            self.assertIn("未處理", (Path(tmp) / "out/comment.md").read_text(encoding="utf-8"))

    def test_workflow_keeps_public_input_out_of_commands_and_cannot_push(self):
        workflow = (ROOT / ".github/workflows/source-intake.yml").read_text(encoding="utf-8")
        self.assertNotRegex(workflow, r"github\.event\.issue\.(body|title)")
        self.assertIn("github.event.sender.login == github.repository_owner", workflow)
        self.assertNotIn("contents: write", workflow)
        self.assertNotIn("secrets.", workflow)


if __name__ == "__main__":
    unittest.main()
