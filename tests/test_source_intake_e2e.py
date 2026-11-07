"""新來源到上架的離線端到端測試：在 repo 副本跑真實指令，傳輸換成本機假頁。

通過代表「已登記的來源」能一路走到網站與 RSS，不代表流程已自動化。

"""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.audit_sources import canonical_url

FIXTURES = ROOT / "tests/fixtures/source-intake"
NESTED = "OPENGSA_INTAKE_E2E_NESTED"
HOST = "scholarship.opengsa-synthetic.example"
BASE = f"https://{HOST}"
SOURCE_ID = "synthetic-foundation-2026"
TITLE = "合成基金會115學年度研究生獎學金"
INTAKE_TITLE = "合成丁基金會115學年度研究生獎學金"
REPLACE_TITLE = "合成己基金會115學年度研究生獎學金"
NEW_HOST_TITLE = "合成庚基金會115學年度研究生獎學金"
NEW_HOST_URL = "https://other.opengsa-synthetic.example/news/intake-2026"
REPLACE_CYCLE = "115學年度"
PROFILE = {"id": SOURCE_ID, "title": TITLE, "url": f"{BASE}/news/phd-2026", "body_selector": "article", "required_markers": ["申請資格"],
           "pdf_include": [], "max_pdfs": 0, "review_note": "合成來源，端到端測試用。", "evidence_mode": "short_excerpt",
           "category": "phd_research", "resource_kind": "scholarship", "scope": "nationwide"}
PAGES = {f"{BASE}/news/phd-2026": "announcement.html", f"{BASE}/policy/rules": "policy.html", f"{BASE}/scholarships": "index.html",
         f"{BASE}/news/intake-2026": "intake.html", f"{BASE}/news/thin": "thin.html", f"{BASE}/files/a.pdf": "a.pdf", f"{BASE}/news/a": "news-a.html", f"{BASE}/news/b": "news-b.html", f"{BASE}/news/c": "news-c.html"}
GATES = {"check_data": ["scripts/check_data.py"], "check_provenance": ["scripts/check_provenance.py"], "check_config": ["scripts/scan_sources.py", "--check-config"]}


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def save(path, value):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


PDF_LINES = ["一、申請資格：國內大學碩士班、博士班在學學生。", "二、獎助金額：每名新臺幣四萬元。", "三、申請期間：自115年3月1日起至115年4月1日止，逾期不受理。", "四、應備文件：申請表與成績單。"]


def text_pdf(lines):
    """產生可抽文字的最小 PDF：repo 沒有 PDF 產生套件，中文靠 ToUnicode 對照表。"""
    chars = sorted(set("".join(lines)))
    cid = {char: index + 1 for index, char in enumerate(chars)}
    show = "".join(f"<{''.join(f'{cid[c]:04X}' for c in line)}> Tj 0 -20 Td " for line in lines)
    content = f"BT /F1 12 Tf 72 720 Td {show}ET".encode()
    pairs = "".join(f"<{cid[c]:04X}> <{ord(c):04X}>\n" for c in chars)
    cmap = (f"/CIDInit /ProcSet findresource begin 12 dict begin begincmap /CMapName /Synthetic def /CMapType 2 def "
            f"1 begincodespacerange <0000> <FFFF> endcodespacerange {len(chars)} beginbfchar\n{pairs}endbfchar endcmap end end").encode()
    objects = [b"<< /Type /Catalog /Pages 2 0 R >>", b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
               b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
               b"<< /Length %d >>\nstream\n%s\nendstream" % (len(content), content),
               b"<< /Type /Font /Subtype /Type0 /BaseFont /Synthetic /Encoding /Identity-H /DescendantFonts [6 0 R] /ToUnicode 7 0 R >>",
               b"<< /Type /Font /Subtype /CIDFontType2 /BaseFont /Synthetic /CIDSystemInfo << /Registry (Adobe) /Ordering (Identity) /Supplement 0 >> >>",
               b"<< /Length %d >>\nstream\n%s\nendstream" % (len(cmap), cmap)]
    out, offsets = bytearray(b"%PDF-1.4\n"), []
    for number, body in enumerate(objects, 1):
        offsets.append(len(out))
        out += b"%d 0 obj\n%s\nendobj\n" % (number, body)
    start = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    out += b"".join(b"%010d 00000 n \n" % offset for offset in offsets)
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objects) + 1, start)
    return bytes(out)


@unittest.skipIf(os.environ.get(NESTED), "副本內重跑全部測試時不再巢狀執行自己")
class SourceIntakeE2ETests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        base = Path(cls.temp.name)
        cls.repo, cls.pages = base / "repo", base / "pages"
        shutil.copytree(ROOT, cls.repo, ignore=shutil.ignore_patterns(".git", "work", "dist", "__pycache__", "node_modules"))
        shutil.copytree(FIXTURES, cls.pages)
        (cls.pages / "a.pdf").write_bytes(text_pdf(PDF_LINES))
        shutil.copy(FIXTURES / "mock_http_get.cjs", cls.repo / "scripts/http_get.cjs")
        save(cls.pages / "map.json", PAGES)
        # 不帶任何金鑰，模型一律關閉。
        cls.env = {**{k: v for k, v in os.environ.items() if not k.endswith("_API_KEY")},
                   "OPENGSA_FIXTURES": str(cls.pages), "OPENGSA_MODEL_MODE": "off", "PYTHONUTF8": "1", "PYTHONDONTWRITEBYTECODE": "1", NESTED: "1"}
        cls.results, cls.base_total = {}, cls.library_size()
        cls.base_review = len(read(cls.repo / "data/candidates/source-review.json")["candidates"])
        try:
            cls.run_flow(base)
        except subprocess.TimeoutExpired as error:
            cls.results["timeout"] = (1, str(error))

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    @classmethod
    def library_size(cls):
        code = "import json;from scripts.build_site import load_full_library as l;print(len(l()[0]['candidates']))"
        return int(subprocess.run([sys.executable, "-c", code], cwd=cls.repo, env=cls.env, capture_output=True, text=True, check=True).stdout.strip())

    @classmethod
    def sh(cls, step, *cmd):
        result = subprocess.run([sys.executable, *map(str, cmd)], cwd=cls.repo, env=cls.env, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
        cls.results[step] = (result.returncode, (result.stdout + result.stderr)[-1500:])
        return result.returncode == 0

    @classmethod
    def round(cls, name, base, preview=True):
        """跑一輪和 scan job 相同的指令，套用提案後過 CI 閘門並建置。"""
        report, proposal = f"work/{name}/report", f"work/{name}/proposal"
        if not cls.sh(f"{name}.scan", "scripts/scan_sources.py", "--config", base / "only.json", "--state", "work/state.json", "--output", report):
            return False
        args = ["--no-preview"] if not preview else []
        if not cls.sh(f"{name}.propose", "scripts/propose_radar_update.py", "--candidates", f"{report}/structured-candidates.json", "--temporal", f"{report}/temporal-records.json", "--output", proposal, *args):
            return False
        cls.sh(f"{name}.apply", "scripts/open_data_pr.py", "--apply-only", "--proposal", proposal)
        for gate, cmd in GATES.items():
            cls.sh(f"{name}.{gate}", *cmd)
        return cls.sh(f"{name}.build_site", "scripts/build_site.py", base / f"site-{name}")

    @classmethod
    def run_flow(cls, base):
        # 第 3 步目前沒有工具，代替維護者手動登記來源。
        config = read(cls.repo / "data/scan-sources.json")
        config["sources"].append(PROFILE)
        config["allowed_hosts"] = sorted(set(config["allowed_hosts"]) | {HOST})
        save(cls.repo / "data/scan-sources.json", config)
        save(base / "only.json", {**config, "sources": [PROFILE]})
        finished = cls.round("new", base)
        cls.new_cards = cls.synthetic_cards()
        if not finished:
            return
        page = cls.pages / "announcement.html"
        page.write_text(page.read_text(encoding="utf-8").replace("115年4月15日", "115年5月20日"), encoding="utf-8")
        if not cls.round("update", base, preview=False):
            return
        cls.updated_cards = cls.synthetic_cards()
        cls.review_after_update = len(read(cls.repo / "data/candidates/source-review.json")["candidates"])
        if not cls.intake_round(base) or not cls.replace_round(base) or not cls.new_host_round(base):
            return
        # 新增、更新、提交都套用後才重跑全部測試：寫死總數或版本的測試會在這裡現形。
        cls.sh("update.unittest", "-m", "unittest", "discover", "-s", "tests")
        # 排在全測之後：有測試假設台帳是空的。
        cls.dismiss_round(base)

    @classmethod
    def intake_round(cls, base):
        """第 1 到 11 步：owner 核可 Issue，只跑該來源，再套用提案（開 PR 那一步需要真實 repo，另有單元測試）。"""
        body = f"### 資源名稱\n\n任意 @someone 名稱\n\n### 公開來源網址\n\n{BASE}/news/intake-2026\n\n### 資源類型\n\n獎學金／研究獎助\n"
        save(base / "event.json", {"action": "labeled", "label": {"name": "source-approved"}, "sender": {"login": "owner"},
                                   "repository": {"owner": {"login": "owner"}}, "issue": {"number": 7, "body": body}})
        if not cls.sh("intake.validate", "scripts/intake_source.py", "--event", base / "event.json", "--output", "work/intake"):
            return False
        if not cls.sh("intake.run", "scripts/run_source_intake.py", "--request", "work/intake/request.json", "--output", "work/intake"):
            return False
        if not (cls.repo / "work/intake/proposal/repo").exists():
            cls.results["intake.proposal"] = (1, (cls.repo / "work/intake/result.json").read_text(encoding="utf-8")[-1500:])
            return False
        cls.sh("intake.apply", "scripts/open_data_pr.py", "--apply-only", "--proposal", "work/intake/proposal")
        for gate, cmd in GATES.items():
            cls.sh(f"intake.{gate}", *cmd)
        return cls.sh("intake.build_site", "scripts/build_site.py", base / "site-intake")

    @classmethod
    def replace_round(cls, base):
        """提交一個已有手寫卡的網址（只有這個方案），假頁回傳新內容；手寫卡要被提案取代。"""
        known = set(read(cls.repo / "data/known-hand-authored-candidates.json")["candidate_ids"])
        cards = [c for path in sorted((cls.repo / "data/candidates").glob("*.json")) for c in read(path)["candidates"]]
        urls = {}
        for card in cards:
            urls.setdefault(card["source_metadata"]["url"], []).append(card)
        cls.hand_card = next(rows[0] for url, rows in sorted(urls.items()) if len(rows) == 1 and rows[0]["candidate_id"] in known and urlsplit(url).path not in ("", "/") and "獎學金" in rows[0]["title"])
        url = cls.hand_card["source_metadata"]["url"]
        pages = read(cls.pages / "map.json")
        # 假頁換成同一方案的名稱：不同方案的新卡不該取代手寫卡。
        page = (cls.pages / "replace.html").read_text(encoding="utf-8").replace(REPLACE_TITLE, cls.hand_card["title"] + REPLACE_CYCLE)
        (cls.pages / "replace-live.html").write_text(page, encoding="utf-8")
        pages[canonical_url(url)] = "replace-live.html"
        save(cls.pages / "map.json", pages)
        save(cls.repo / "work/replace.json", {"status": "accepted", "issue": 9, "url": canonical_url(url), "category": "scholarship", "already_registered": True})
        if not cls.sh("replace.run", "scripts/run_source_intake.py", "--request", "work/replace.json", "--output", "work/replace"):
            return False
        if not (cls.repo / "work/replace/proposal/repo").exists():
            cls.results["replace.proposal"] = (1, (cls.repo / "work/replace/result.json").read_text(encoding="utf-8")[-1500:])
            return False
        cls.sh("replace.apply", "scripts/open_data_pr.py", "--apply-only", "--proposal", "work/replace/proposal")
        for gate, cmd in GATES.items():
            cls.sh(f"replace.{gate}", *cmd)
        return cls.sh("replace.build_site", "scripts/build_site.py", base / "site-replace")

    @classmethod
    def new_host_round(cls, base):
        """提交沒登記過的網域：網域不進 allowed_hosts，卡片照樣過檢查、上網站。"""
        page = (cls.pages / "intake.html").read_text(encoding="utf-8").replace(INTAKE_TITLE, NEW_HOST_TITLE)
        (cls.pages / "new-host.html").write_text(page, encoding="utf-8")
        pages = read(cls.pages / "map.json")
        pages[NEW_HOST_URL] = "new-host.html"
        pages[NEW_HOST_URL.replace("/news/intake-2026", "/policy/rules")] = "policy.html"
        save(cls.pages / "map.json", pages)
        save(cls.repo / "work/newhost.json", {"status": "accepted", "issue": 11, "url": NEW_HOST_URL, "category": "scholarship"})
        if not cls.sh("newhost.run", "scripts/run_source_intake.py", "--request", "work/newhost.json", "--output", "work/newhost"):
            return False
        cls.sh("newhost.apply", "scripts/open_data_pr.py", "--apply-only", "--proposal", "work/newhost/proposal")
        for gate, cmd in GATES.items():
            cls.sh(f"newhost.{gate}", *cmd)
        return cls.sh("newhost.build_site", "scripts/build_site.py", base / "site-newhost")

    @classmethod
    def dismiss_round(cls, base):
        """駁回一張卡：照常建置，卡片留在候選檔，網站和 RSS 不再顯示。"""
        cls.dismissed = cls.synthetic_cards()[0]
        if not cls.sh("dismiss.run", "scripts/dismiss_candidate.py", "--candidate-id", cls.dismissed["candidate_id"], "--reason", "合成：日期抽錯", "--problem-source", "extraction"):
            return False
        for gate, cmd in GATES.items():
            cls.sh(f"dismiss.{gate}", *cmd)
        return cls.sh("dismiss.build_site", "scripts/build_site.py", base / "site-dismiss")

    @classmethod
    def synthetic_cards(cls):
        rows = read(cls.repo / "data/candidates/source-review.json")["candidates"]
        return [c for c in rows if c["source_metadata"]["source_id"] == SOURCE_ID]

    def assert_step(self, step):
        self.assertIn(step, self.results, f"流程沒有跑到 {step}；已跑：{list(self.results)}")
        code, tail = self.results[step]
        self.assertEqual(code, 0, f"{step} 失敗：\n{tail}")

    def require(self, step):
        if self.results.get(step, (1,))[0] != 0:
            self.skipTest(f"{step} 沒有成功，已知斷點無從判斷")

    def site(self, name):
        directory = Path(self.temp.name) / f"site-{name}"
        return (directory / "index.html").read_text(encoding="utf-8"), (directory / "feed.xml").read_text(encoding="utf-8")

    def test_new_source_extracts_a_pending_candidate(self):
        self.assert_step("new.scan")
        self.assert_step("new.propose")
        self.assertEqual(len(self.new_cards), 1)
        card = self.new_cards[0]
        self.assertIn(card["verification"]["status"], ("passed_automated_checks", "passed_with_gaps"))
        self.assertEqual(card["review"]["status"], "pending")
        self.assertFalse(card["review"]["promotion_ready"])
        summary = read(self.repo / "work/new/proposal/summary.json")
        self.assertEqual((summary["human_approvals"], summary["published"]), (0, False))

    def test_applied_proposal_passes_gates_and_reaches_site_and_feed(self):
        for gate in GATES:
            self.assert_step(f"new.{gate}")
        self.assert_step("new.build_site")
        page, feed = self.site("new")
        self.assertIn(TITLE, page)
        self.assertIn(TITLE, feed)
        self.assertEqual(feed.count("<item>"), self.base_total + 1)

    def test_changed_source_replaces_its_card(self):
        for gate in GATES:
            self.assert_step(f"update.{gate}")
        self.assert_step("update.build_site")
        self.assertEqual(len(self.updated_cards), 1)
        self.assertNotEqual(self.updated_cards[0]["candidate_id"], self.new_cards[0]["candidate_id"])
        self.assertIn("2026-05-20", json.dumps(self.updated_cards[0]["schedule"], ensure_ascii=False))
        self.assertEqual(self.review_after_update, self.base_review + 1)
        _, feed = self.site("update")
        self.assertEqual(feed.count("<item>"), self.base_total + 1)

    def test_approved_issue_runs_alone_and_reaches_the_site_after_manual_apply(self):
        self.assert_step("intake.run")
        result = read(self.repo / "work/intake/result.json")
        self.assertEqual((result["model_calls"], result["published"]), (0, False))
        self.assertEqual(result["records"][0]["disposition"], "named_candidates_pending")
        self.assertIn(INTAKE_TITLE, [c["title"] for c in result["candidates"]])
        # 新來源不會被加進排程，名稱欄的提交內容也不會出現在留言。
        source = next(s for s in read(self.repo / "data/scan-sources.json")["sources"] if s["url"] == f"{BASE}/news/intake-2026")
        self.assertIs(source["enabled"], False)
        text = (self.repo / "work/intake/comment.md").read_text(encoding="utf-8")
        self.assertIn("還沒上架", text)
        self.assertNotIn("@someone", text)
        card = next(c for c in read(self.repo / "data/candidates/source-review.json")["candidates"] if c["title"] == INTAKE_TITLE)
        self.assertEqual(card["review"]["status"], "pending")
        for gate in GATES:
            self.assert_step(f"intake.{gate}")
        self.assert_step("intake.build_site")
        page, feed = self.site("intake")
        self.assertIn(INTAKE_TITLE, page)
        self.assertIn(INTAKE_TITLE, feed)

    def enumerate_source(self, name, path):
        request = {"status": "accepted", "issue": 8, "url": f"{BASE}{path}", "category": "scholarship"}
        save(self.repo / f"work/{name}.json", request)
        self.sh(f"{name}.run", "scripts/run_source_intake.py", "--request", f"work/{name}.json", "--output", f"work/{name}")
        self.assert_step(f"{name}.run")
        return read(self.repo / f"work/{name}/result.json")

    def test_index_page_enumerates_its_resources_and_is_not_a_card(self):
        result = self.enumerate_source("index", "/scholarships")
        self.assertEqual(result["records"][0]["disposition"], "source_document_or_discovery_only")
        self.assertEqual({c["title"] for c in result["candidates"]}, {"合成甲基金會115年度研究生獎學金", "合成乙基金會115年度清寒獎助學金", "合成丙基金會博士生論文獎"})
        # 索引頁列的是不同方案，不能併成一個。
        self.assertEqual(len({c["program_key"] for c in result["candidates"]}), 3)
        self.assertEqual(result["links_skipped"], 0)

    def test_announcement_and_its_policy_share_one_program(self):
        self.assert_step("intake.run")
        rows = read(self.repo / "work/intake/result.json")["candidates"]
        self.assertEqual(len(rows), 2)
        self.assertEqual(len({row["program_key"] for row in rows}), 1)
        self.assertIn("歸成 1 個方案", (self.repo / "work/intake/comment.md").read_text(encoding="utf-8"))
        stored = {c["title"]: c for c in read(self.repo / "data/candidates/source-review.json")["candidates"]}
        self.assertEqual(stored[INTAKE_TITLE]["program_key"], rows[0]["program_key"])

    def test_page_with_contact_details_still_extracts_and_keeps_none_of_them(self):
        result = self.enumerate_source("contact", "/news/a")
        self.assertEqual([c["title"] for c in result["candidates"]], ["合成甲基金會115年度研究生獎學金"])
        stored = (self.repo / "work/contact/report/structured-candidates.json").read_text(encoding="utf-8")
        self.assertNotIn("02-1234-5678", stored)

    def test_thin_page_with_pdf_attachment_extracts_from_the_pdf(self):
        result = self.enumerate_source("thin", "/news/thin")
        by_url = {r["url"]: r["disposition"] for r in result["records"]}
        self.assertEqual(by_url[f"{BASE}/news/thin"], "source_document_or_discovery_only")
        self.assertEqual(by_url[f"{BASE}/files/a.pdf"], "named_candidates_pending")
        self.assertEqual([c["title"] for c in result["candidates"]], ["合成戊基金會115學年度研究生獎學金"])

    def test_submission_replaces_the_hand_card_on_the_same_url(self):
        self.assert_step("replace.run")
        for gate in GATES:
            self.assert_step(f"replace.{gate}")
        self.assert_step("replace.build_site")
        summary = read(self.repo / "work/replace/result.json")["proposal"]
        self.assertEqual([r["candidate_id"] for r in summary["retired_hand_cards"]], [self.hand_card["candidate_id"]])
        page, feed = self.site("replace")
        self.assertIn(self.hand_card["title"] + REPLACE_CYCLE, feed)
        self.assertNotIn(self.hand_card["candidate_id"], page)
        self.assertNotIn(self.hand_card["candidate_id"], read(self.repo / "data/known-hand-authored-candidates.json")["candidate_ids"])

    def test_submitted_host_stays_out_of_allowed_hosts_and_the_card_still_passes(self):
        for step in ("newhost.apply", *(f"newhost.{gate}" for gate in GATES), "newhost.build_site"):
            self.assert_step(step)
        config = read(self.repo / "data/scan-sources.json")
        self.assertNotIn(urlsplit(NEW_HOST_URL).hostname, config["allowed_hosts"])
        self.assertIs(next(s for s in config["sources"] if s["url"] == NEW_HOST_URL)["enabled"], False)
        _, feed = self.site("newhost")
        self.assertIn(NEW_HOST_TITLE, feed)

    def test_dismissed_card_leaves_the_site_and_feed_and_keeps_its_reason(self):
        for gate in GATES:
            self.assert_step(f"dismiss.{gate}")
        self.assert_step("dismiss.build_site")
        card = self.dismissed
        page, feed = self.site("dismiss")
        self.assertNotIn(card["candidate_id"], page)
        self.assertNotIn(card["title"], feed)
        # 未審的其他卡還在。
        self.assertIn(INTAKE_TITLE, feed)
        entry = read(self.repo / "data/scan-reviews.json")["reviews"][-1]
        self.assertEqual((entry["candidate_id"], entry["action"], entry["problem_source"]), (card["candidate_id"], "dismissed", "extraction"))
        self.assertIn(card["candidate_id"], [c["candidate_id"] for c in read(self.repo / "data/candidates/source-review.json")["candidates"]])

    def test_whole_suite_passes_with_the_applied_data(self):
        self.assert_step("update.unittest")

    def test_flow_never_leaves_the_mock_transport(self):
        # 假傳輸不連外；這裡確認沒有請求是地圖外的頁面（robots.txt 除外，假傳輸一律回 404）。
        urls = set((self.pages / "requests.log").read_text(encoding="utf-8").splitlines())
        self.assertTrue(urls)
        known = set(read(self.pages / "map.json"))
        self.assertEqual({u for u in urls if u not in known and not u.endswith("/robots.txt")}, set())

    def test_proposal_carries_time_records_from_the_same_round(self):
        self.assert_step("new.propose")
        self.assert_step("new.scan")
        records = read(self.repo / "work/new/proposal/repo/data/temporal-observations.json")["records"]
        record = records[self.new_cards[0]["candidate_id"]]
        self.assertEqual(record["policy"]["submission_mode"], "fixed_window")
        self.assertEqual(read(self.repo / "work/new/report/scan-report.json")["http_requests"], 2)
        page, _ = self.site("new")
        self.assertIn("2026-04-15", page)

    def test_clean_page_dates_belong_to_the_student_and_gaps_are_reported(self):
        card = self.new_cards[0]
        self.assertEqual(card["schedule"]["application_start"]["value"], "2026-03-01")
        self.assertTrue(any(s["actor"] == "student" and s["deadline"]["value"] == "2026-04-15" for s in card["schedule"]["steps"]))
        # 假頁寫了兼領限制，但規則還抽不出來；要明說，不能回報沒有缺漏。
        self.assertEqual(card["compatibility"]["mode"], "unknown")
        self.assertIn("unextracted:compatibility", card["gaps_and_conflicts"]["missing_fields"])
        self.assertEqual(card["verification"]["status"], "passed_with_gaps")


if __name__ == "__main__":
    unittest.main()
