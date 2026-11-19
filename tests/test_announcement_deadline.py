"""公告寫收件期限、辦法寫資格：期限帶到公告點名的那張辦法卡。全部是合成資料，不連外。"""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from scripts.expand_sources import INTAKE_OPTIONS, announces, initial_state, referenced, run_batch
from scripts.extract_candidates import announced_deadlines, extract_from_in_memory_blocks
from scripts.verify_candidates import verify_candidate


def setUpModule():
    from scripts import scan_sources
    patcher = patch.object(scan_sources, "pause", lambda seconds: None)
    patcher.start()
    unittest.addModuleCleanup(patcher.stop)


def blocks(*texts, prefix="body / text-block"):
    return [{"locator": f"{prefix} {i}", "text": t, "kind": "paragraph"} for i, t in enumerate(texts, 1)]


CALL = "合成學院研究生優秀論文獎暨大學生研究獎勵即日起至115年11月26日(四)下午5時止受理申請，逾期不受理。"
RULE = blocks("合成大學醫學院研究生優秀論文獎勵辦法", "第六條 限本院在學或畢業三年內之研究生提出申請。", prefix="PDF page")
ANNOUNCEMENT = {"source": {"id": "SYNTH-call", "url": "https://example.test/call"}, "revision_id": "b" * 64, "blocks": blocks(CALL)}


def card(linked=None, rule=RULE):
    source = {"id": "SYNTH-rule", "title": "合成大學醫學院研究生優秀論文獎勵辦法", "url": "https://example.test/rule.pdf",
              "evidence_mode": "hash_only", "category": "outcome_award", "resource_kind": "award", "scope": "nationwide"}
    return extract_from_in_memory_blocks(source, rule, "a" * 64, "2026-11-19T01:00:00+00:00", as_of="2026-11-19",
                                         extraction_strategy="rules_only", linked_documents=linked)[0]


class DeadlineSentenceTests(unittest.TestCase):
    def test_since_today_until_clock_variants(self):
        cases = {
            "即日起至115年11月26日(四)下午5時止受理申請": "2026-11-26T17:00:00+08:00",
            "即日起至115年11月26日（四）下午5時止受理申請": "2026-11-26T17:00:00+08:00",
            "即日起至115年11月26日(星期四)中午12時止受理申請": "2026-11-26T12:00:00+08:00",
            "即日起至115年11月26日(四)17:00止受理申請": "2026-11-26T17:00:00+08:00",
            "合成獎自即日起至115年11月26日下午5時止收件": "2026-11-26T17:00:00+08:00",
        }
        for text, value in cases.items():
            with self.subTest(text=text):
                self.assertEqual(announced_deadlines(blocks("合成學院研究生論文獎" + text)), {value})

    def test_since_today_alone_is_not_a_start_date(self):
        # 「即日起」沒有寫日期，不當成受理起日。
        cand = card([ANNOUNCEMENT])
        self.assertIsNone(cand["schedule"]["application_start"]["value"])


class LinkedDeadlineTests(unittest.TestCase):
    def test_announcement_deadline_lands_on_the_rule_card_with_announcement_evidence(self):
        cand = card([ANNOUNCEMENT])
        self.assertEqual(cand["verification"]["errors"], [])
        step = next(s for s in cand["schedule"]["steps"] if s["deadline"]["value"])
        self.assertEqual(step["deadline"]["value"], "2026-11-26T17:00:00+08:00")
        self.assertEqual(step["refs"], [{"source": "SYNTH-call", "locator": "body / text-block 1"}])
        evidence = [e for e in cand["field_evidence"] if e["field_path"].endswith("/deadline")]
        self.assertEqual([(e["source"], e["revision_id"]) for e in evidence], [("SYNTH-call", "b" * 64)])
        self.assertEqual(cand["source_metadata"]["linked_revisions"][0]["relation"], "announcement")
        # 辦法本身的「待確認」那一步被取代，不留兩個學生步驟。
        self.assertEqual(len([s for s in cand["schedule"]["steps"] if s["actor"] == "student"]), 1)

    def test_two_different_deadlines_leave_the_card_unconfirmed(self):
        two = {**ANNOUNCEMENT, "blocks": blocks(CALL, "大學生研究獎勵即日起至115年12月10日(四)下午5時止受理申請。")}
        cand = card([two])
        self.assertFalse(any(s["deadline"]["value"] for s in cand["schedule"]["steps"]))
        self.assertNotIn("linked_revisions", cand["source_metadata"])

    def test_rule_with_its_own_deadline_keeps_it(self):
        rule = RULE + blocks("申請期間：115年10月1日至115年10月31日止。", prefix="PDF page 2 line")
        cand = card([ANNOUNCEMENT], rule)
        values = {s["deadline"]["value"] for s in cand["schedule"]["steps"] if s["deadline"]["value"]}
        self.assertEqual(values, {"2026-10-31"})

    def test_verifier_only_accepts_declared_announcement_for_deadlines(self):
        cand = card([ANNOUNCEMENT])
        undeclared = {**cand, "source_metadata": {k: v for k, v in cand["source_metadata"].items() if k != "linked_revisions"}}
        self.assertTrue(any(e.startswith("evidence_source_or_revision_mismatch") for e in verify_candidate(undeclared)["verification"]["errors"]))
        moved = {**cand, "field_evidence": [{**e, "field_path": "eligibility.identity"} if e["source"] == "SYNTH-call" else e for e in cand["field_evidence"]]}
        self.assertTrue(any(e.startswith("evidence_source_or_revision_mismatch") for e in verify_candidate(moved)["verification"]["errors"]))
        # 帶公告進記憶體時，證據要真的對得上公告的區塊。
        wrong = {**ANNOUNCEMENT["blocks"][0], "text": "合成不同的句子"}
        result = verify_candidate(cand, in_memory_blocks=RULE, linked_blocks={"SYNTH-call": [wrong]})
        self.assertTrue(any("not_grounded" in e or "sha256_mismatch" in e for e in result["verification"]["errors"]))


    def test_site_preview_lists_the_announcement_as_a_source(self):
        import json
        from scripts.build_review_workspace import candidate_preview_data
        root = Path(__file__).resolve().parents[1] / "data"
        cand = card([ANNOUNCEMENT])
        profile = {"title": "SYNTH", "body_selector": "body", "required_markers": [], "pdf_include": [], "max_pdfs": 0,
                   "review_note": "合成", "evidence_mode": "hash_only", "enabled": False}
        config = {"sources": [{**profile, "id": "SYNTH-rule", "url": "https://example.test/rule.pdf"},
                              {**profile, "id": "SYNTH-call", "url": "https://example.test/call"}]}
        bundle = {"as_of": "2026-11-19", "candidates": [cand]}
        preview = candidate_preview_data(bundle, json.loads((root / "pilot.json").read_text(encoding="utf-8")), config)
        self.assertIn("https://example.test/call", {s["url"] for s in preview["sources"]})


class ProgrammeMatchTests(unittest.TestCase):
    def test_title_match(self):
        title = "115學年度合成學院研究生優秀論文獎暨大學生研究獎勵即日起至115年11月26日止受理申請"
        self.assertTrue(announces(title, "合成大學醫學院研究生優秀論文獎勵辦法"))
        self.assertFalse(announces(title, "合成大學學術研究績效獎勵辦法"))
        self.assertFalse(announces(title, "合成大學獎勵辦法"))  # 去掉校名後太短，分不出是哪個方案

    def test_plain_text_url_with_legacy_entity(self):
        self.assertTrue(referenced("https://example.test/form.asp?pno=27&LTPno=52", "相關文件：https://example.test/form.asp?pno=27<Pno=52"))
        self.assertFalse(referenced("https://example.test/menu.asp", "相關文件：https://example.test/form.asp"))


ANNOUNCEMENT_HTML = ("<html><head><title>合成研發處</title></head><body><nav><a href='/menu.asp'>獎學金選單</a></nav>"
                     "<main><h1>" + CALL + "</h1><p>" + CALL + "</p>"
                     "<p><a href='/file.asp?filename=letter.pdf'>函</a></p>"
                     "<p>相關文件連結：https://example.test/form.asp?pno=27</p>"
                     "<a href='/other.asp'>其他獎學金公告</a><a href='/form.asp?pno=27'>研究獎勵</a></main></body></html>").encode()
FORM_HTML = ("<html><body><main><h1>研究獎勵表單</h1>"
             "<a href='/file.asp?filename=rule.pdf'>附件1獎勵辦法</a><a href='/file.asp?filename=faculty.pdf'>合成大學學術研究績效獎勵辦法</a>"
             "</main></body></html>").encode()
PDFS = {
    b"%PDF-letter": blocks("合成學院函", "主旨：" + CALL, "限本院在學或畢業三年內之研究生提出申請。", prefix="PDF page"),
    b"%PDF-rule": RULE,
    b"%PDF-faculty": blocks("合成大學學術研究績效獎勵辦法", "申請資格：本校專任教師在學學生指導成果。", prefix="PDF page"),
}


class AnnouncementCrawlTests(unittest.TestCase):
    def test_announcement_links_only_its_programme_and_skips_navigation(self):
        pages = {"https://example.test/call": ANNOUNCEMENT_HTML, "https://example.test/form.asp?pno=27": FORM_HTML,
                 "https://example.test/file.asp?filename=letter.pdf": b"%PDF-letter",
                 "https://example.test/file.asp?filename=rule.pdf": b"%PDF-rule",
                 "https://example.test/file.asp?filename=faculty.pdf": b"%PDF-faculty"}
        calls = []

        def get(url, headers, limit):
            calls.append(url)
            if url.endswith("robots.txt"):
                return {"status": 404, "body": b"", "headers": {}}
            body = pages.get(url)
            if body is None:
                return {"status": 404, "body": b"", "headers": {}}
            return {"status": 200, "body": body, "headers": {"content-type": "application/pdf" if body.startswith(b"%PDF") else "text/html"}}

        row = {"id": "SYNTH-call", "url": "https://example.test/call", "title": "", "batch": "B1", "category": "award",
               "access_gate": "owner_approved_submission", "restrictions": []}
        inv = {"rows": [row]}
        state = initial_state(inv)
        with TemporaryDirectory() as tmp, patch("scripts.scan_sources.time.sleep"), \
                patch("scripts.expand_sources.pdf_document", side_effect=lambda raw: [dict(b) for b in PDFS[raw]]):
            run_batch(inv, state, "B1", Path(tmp) / "state.json", {"sources": []}, transport=get, options=INTAKE_OPTIONS)
            # 公告的區塊只放記憶體，不寫進存檔的 state。
            saved = (Path(tmp) / "state.json").read_text(encoding="utf-8")
            self.assertNotIn('"blocks"', saved)
        self.assertNotIn("https://example.test/menu.asp", calls)
        self.assertNotIn("https://example.test/other.asp", calls)
        cards = list(state["candidates"].values())
        self.assertEqual([c["title"] for c in cards], ["合成大學醫學院研究生優秀論文獎勵辦法"])
        step = next(s for s in cards[0]["schedule"]["steps"] if s["deadline"]["value"])
        self.assertEqual(step["deadline"]["value"], "2026-11-26T17:00:00+08:00")
        self.assertEqual(step["refs"][0]["source"], cards[0]["source_metadata"]["linked_revisions"][0]["source_id"])
        reasons = {r["url"]: r.get("not_card_reason") for r in state["records"].values()}
        self.assertEqual(reasons["https://example.test/file.asp?filename=letter.pdf"], "not_announced_programme")
        self.assertEqual(reasons["https://example.test/file.asp?filename=faculty.pdf"], "not_announced_programme")
        # 時間紀錄只讀得到辦法，會蓋掉公告的截止日，所以這張卡不做。
        self.assertNotIn(cards[0]["candidate_id"], state.get("temporal", {}))
        # 公告的 profile 停用、不排程。
        announcement_profile = state["profiles"][cards[0]["source_metadata"]["linked_revisions"][0]["source_id"]]
        self.assertFalse(announcement_profile["enabled"])


if __name__ == "__main__":
    unittest.main()
