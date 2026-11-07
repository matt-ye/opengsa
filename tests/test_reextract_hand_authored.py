"""手寫候選重萃：內容只來自這次抓到的頁面；抓不到或對不上就如實記錄，不連網。"""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.extract_candidates import MockModelAdapter, OpenAICompatibleAdapter
from scripts.temporal_model import VERIFIED_MODELS_BY_HOST, VERIFIED_PROVIDER_CAPABILITIES
from scripts.reextract_hand_authored import (
    MODEL_ROUND,
    SameSiteHosts,
    configure_model,
    known_candidates,
    longest_common_run,
    model_pending,
    model_skip_reason,
    page_problem,
    run,
)

CONFIG = {"max_requests": 20, "minimum_host_interval_seconds": 0, "max_run_seconds": 180, "sources": []}
PAGE = """<html><head><title>甲基金會獎學金</title></head><body>
<aside>側欄：其他方案補助8,000元</aside>
<main><h1>甲基金會獎學金</h1><p>申請資格：國內大學碩士班在學學生。</p><p>每名獎助新臺幣20,000元。</p>
<p>申請期間：115年9月1日至115年10月15日止。</p>
<p>檢附文件：申請表、在學證明、歷年成績單與推薦函各一份，請於期限內送達本會辦公室，逾期不予受理。</p></main></body></html>""".encode()


def candidate(cid="cand-a", url="https://a.org.tw/s", title="甲基金會獎學金"):
    return {"candidate_id": cid, "title": title, "source_metadata": {"source_id": "s-a", "url": url}}


def transport_for(pages):
    def transport(url, headers, limit):
        if url.endswith("/robots.txt"):
            return {"status": 404, "headers": {}, "body": b""}
        status, body = pages.get(url, (404, b""))
        return {"status": status, "headers": {"content-type": "text/html"}, "body": body}

    return transport


class PageChecks(unittest.TestCase):
    def test_soft_404_and_unrelated_pages_are_rejected(self):
        self.assertEqual(page_problem("找不到頁面", "甲基金會獎學金", ("甲基金會獎學金",)), "soft_unavailable_page")
        self.assertEqual(page_problem("首頁", "歡迎光臨本校", ("甲基金會獎學金",)), "page_does_not_mention_programme")
        self.assertIsNone(page_problem("獎助", "本會設有甲基金會獎學金", ("甲基金會獎學金",)))

    def test_common_run(self):
        self.assertEqual(longest_common_run("甲基金會", "我們 甲基 金會"), 4)
        self.assertEqual(longest_common_run("甲乙丙", "丁戊"), 0)

    def test_same_site_hosts_allows_www_only_within_site(self):
        hosts = SameSiteHosts(["a.org.tw"])
        self.assertIn("www.a.org.tw", hosts)
        self.assertNotIn("b.org.tw", hosts)


class RunTests(unittest.TestCase):
    def test_broken_source_is_recorded_and_keeps_no_old_content(self):
        results, _ = run([candidate()], CONFIG, {}, transport_for({}))
        self.assertEqual((results["cand-a"]["status"], results["cand-a"]["reason"]), ("source_unavailable", "http_404"))
        self.assertNotIn("candidate", results["cand-a"])

    def test_unrelated_page_is_not_extracted(self):
        url = "https://a.org.tw/s"
        page = ("<html><title>首頁</title><body><p>" + "歡迎光臨本校網站，這裡提供校園最新消息與活動資訊。" * 6 + "</p></body></html>").encode()
        results, _ = run([candidate()], CONFIG, {}, transport_for({url: (200, page)}))
        self.assertEqual(results["cand-a"]["status"], "page_mismatch")

    def test_real_page_yields_content_from_that_page_with_a_real_revision(self):
        url = "https://a.org.tw/s"
        results, _ = run([candidate()], CONFIG, {}, transport_for({url: (200, PAGE)}))
        row = results["cand-a"]
        self.assertIn(row["status"], ("extracted", "failed_checks"), row)
        self.assertEqual(len(row["revision_id"]), 64)
        if row["status"] == "extracted":
            self.assertEqual(row["candidate"]["candidate_id"], "cand-a")
            self.assertEqual(row["candidate"]["source_metadata"]["revision_id"], row["revision_id"])
            self.assertNotIn("8,000", row["candidate"]["benefit"]["summary"])

    def test_invalid_profile_category_does_not_fail_schema(self):
        url = "https://a.org.tw/s"
        config = {**CONFIG, "sources": [{"id": "s-a", "category": "scholarship", "scope": "school"}]}
        row = {**candidate(), "category": "phd_research", "scope": "local", "resource_kind": "scholarship"}
        results, _ = run([row], config, {}, transport_for({url: (200, PAGE)}))
        self.assertFalse([p for p in results["cand-a"].get("problems", []) if p.startswith("schema/")])

    def test_model_round_retries_only_fetched_pages_and_stops_at_its_budget(self):
        adapter = MockModelAdapter(mode="extract", max_calls=1)
        url = "https://a.org.tw/s"
        previous = {"cand-a": {"url": url, "status": "extracted"}, "cand-b": {"url": url, "status": "extracted"},
                    "cand-c": {"url": url, "status": "source_unavailable"}}
        rows = [candidate("cand-a"), candidate("cand-b"), candidate("cand-c")]
        results, _ = run(rows, CONFIG, previous, transport_for({url: (200, PAGE)}), adapter=adapter)
        self.assertGreaterEqual(results["cand-a"]["model_calls"], 1)
        self.assertNotIn("model_calls", results["cand-b"])
        self.assertEqual(results["cand-c"]["status"], "source_unavailable")

    def test_rate_limit_keeps_previous_row_for_retry(self):
        adapter = MockModelAdapter(mode="extract", max_calls=5)
        adapter.rate_limited_429 = True
        url = "https://a.org.tw/s"
        previous = {"cand-a": {"url": url, "status": "extracted"}}
        results, _ = run([candidate("cand-a")], CONFIG, previous, transport_for({url: (200, PAGE)}), adapter=adapter)
        self.assertEqual(results["cand-a"], previous["cand-a"])

    def test_row_that_never_called_the_model_stays_pending(self):
        self.assertTrue(model_pending({"status": "extracted", "model_attempted": True, "model_calls": 0}))
        self.assertTrue(model_pending({"status": "extracted", "model_calls": 2}))
        self.assertFalse(model_pending({"status": "extracted", "model_round": MODEL_ROUND}))
        self.assertFalse(model_pending({"status": "extracted", "model_skipped": "source_sanitization_requires_review"}))
        self.assertFalse(model_pending({"status": "source_unavailable"}))

    def test_skip_reason_is_read_from_verifier_warnings(self):
        self.assertEqual(model_skip_reason(["x", "model_skipped:source_sanitization_requires_review"]),
                         "source_sanitization_requires_review")
        self.assertEqual(model_skip_reason(["external_model_skipped_for_hash_only_source"]), "hash_only_source")
        self.assertIsNone(model_skip_reason([]))

    def test_general_extraction_is_not_limited_to_temporal_fields(self):
        # 選不需下載tokenizer的供應商，測試才不連網。
        host, model = next(key for key, name in VERIFIED_MODELS_BY_HOST.items()
                           if not VERIFIED_PROVIDER_CAPABILITIES[name].get("uses_qwen_tokenizer"))
        adapter = OpenAICompatibleAdapter(base_url=f"https://{host}/v1", model=model, api_key="synthetic", mode="extract")
        configure_model(adapter)
        self.assertEqual(adapter.field_scope, ())
        self.assertEqual(adapter.model_limits["model"], adapter.model)
        self.assertEqual(adapter.model_limits["input_limit"], 6000)

    def test_budget_leaves_rest_for_next_run(self):
        rows = [candidate(f"c{n}", f"https://s{n}.org.tw/p") for n in range(3)]
        first, used = run(rows, {**CONFIG, "max_requests": 4}, {}, transport_for({}))
        self.assertEqual((sorted(first), used), (["c0", "c1"], 4))
        second, _ = run(rows, CONFIG, first, transport_for({}))
        self.assertEqual(len(second), 3)

    def test_targets_every_known_hand_authored_candidate(self):
        self.assertEqual(len(known_candidates()), 190)


if __name__ == "__main__":
    unittest.main()
