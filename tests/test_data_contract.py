"""真實風險的負向案例；不把手寫預期結果冒充資格引擎測試。"""
import copy
import unittest

from scripts.check_data import ROOT, read_json, validate


class DataContractTests(unittest.TestCase):
    def setUp(self):
        self.data = copy.deepcopy(read_json(ROOT / "data/pilot.json"))

    def test_pilot_shape_and_reference_integrity(self):
        self.assertEqual(validate(self.data), [])
        self.assertEqual(len(self.data["opportunities"]), 10)
        self.assertTrue(all(x["review"]["status"] == "draft" for x in self.data["opportunities"]))

    def test_missing_compatibility_tag_is_rejected(self):
        del self.data["opportunities"][0]["compatibility"]
        self.assertTrue(validate(self.data))

    def test_invented_midnight_for_date_only_is_rejected(self):
        self.data["opportunities"][0]["steps"][0]["deadline"]["value"] = "2026-08-13T23:59:00+08:00"
        self.assertTrue(validate(self.data))

    def test_unknown_year_is_not_numeric_unlimited(self):
        self.data["opportunities"][0]["eligibility"]["year_limit"]["max"] = 99
        self.assertTrue(validate(self.data))

    def test_orphan_source_reference_is_rejected(self):
        self.data["opportunities"][0]["steps"][0]["refs"][0]["source"] = "missing-source"
        self.assertTrue(any("unknown source" in e for e in validate(self.data)))

    def test_self_review_is_rejected(self):
        review = self.data["opportunities"][0]["review"]
        review.update(status="reviewed", independent_reviewer=review["editor"], reviewed_on="2026-10-28")
        self.assertTrue(any("independent" in e for e in validate(self.data)))

    def test_search_excerpt_cannot_be_complete(self):
        self.data["opportunities"][4]["evidence_status"] = "sufficient_for_draft"
        self.assertTrue(any("search excerpt" in e for e in validate(self.data)))

    def test_duplicate_ids_are_rejected(self):
        self.data["opportunities"][1]["id"] = self.data["opportunities"][0]["id"]
        self.assertTrue(any("duplicate" in e for e in validate(self.data)))

    def test_future_observation_is_rejected(self):
        self.data["sources"][0]["checked_on"] = "2026-10-29"
        self.assertTrue(any("after snapshot" in e for e in validate(self.data)))

    def test_institution_route_cannot_turn_into_direct_scholarship(self):
        self.data["opportunities"][9]["participants"]["applicant"] = "student"
        self.assertTrue(any("unit/institution" in e for e in validate(self.data)))


if __name__ == "__main__":
    unittest.main()
