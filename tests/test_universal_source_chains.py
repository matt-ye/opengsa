"""Unit tests for universal source chain batches and registry integrity."""
from pathlib import Path
import unittest
import json

ROOT = Path(__file__).resolve().parents[1]

class UniversalSourceChainsTests(unittest.TestCase):
    def setUp(self):
        self.batches_dir = ROOT / "data/source-chain-batches"
        self.registry_path = self.batches_dir / "batch-registry.json"

    def test_registry_file_exists_and_valid(self):
        self.assertTrue(self.registry_path.exists(), "batch-registry.json must exist")
        with open(self.registry_path, "r", encoding="utf-8") as f:
            registry = json.load(f)

        self.assertEqual(registry["schema_version"], "source-chain-registry-1")
        self.assertGreaterEqual(registry["total_batches"], 5)
        # 總數隨資料變動：只要求和各批次加總一致，不鎖固定下限。
        self.assertEqual(registry["total_documents"], sum(b["documents"] for b in registry["batches"]))
        self.assertEqual(registry["total_edges"], sum(b["edges"] for b in registry["batches"]))
        self.assertEqual(registry["total_schemes_covered"], sum(b["candidates"] for b in registry["batches"]))

    def test_all_registered_batches_exist_and_consistent(self):
        with open(self.registry_path, "r", encoding="utf-8") as f:
            registry = json.load(f)

        valid_archetypes = {
            "higher_education_university",
            "government_statutory",
            "student_perks_identity",
            "corporate_foundation_dual_track",
            "conference_travel_grant",
            "universal_topology_probe"
        }

        for batch_meta in registry["batches"]:
            batch_id = batch_meta["batch_id"]
            file_path = ROOT / batch_meta["file"]
            self.assertTrue(file_path.exists(), f"Batch file for {batch_id} must exist")

            with open(file_path, "r", encoding="utf-8") as f:
                batch_data = json.load(f)

            self.assertEqual(batch_data["schema_version"], "source-chain-1")
            self.assertEqual(batch_meta["archetype"], batch_data.get("archetype"))
            self.assertIn(batch_meta["archetype"], valid_archetypes)

            docs = batch_data.get("documents", [])
            edges = batch_data.get("edges", [])
            bindings = batch_data.get("candidate_bindings", [])

            self.assertEqual(len(docs), batch_meta["documents"])
            self.assertEqual(len(edges), batch_meta["edges"])
            self.assertEqual(len(bindings), batch_meta["candidates"])

            # Verify no dangling edges
            doc_ids = {d["id"] for d in docs}
            for edge in edges:
                self.assertIn(edge["from"], doc_ids, f"Edge from {edge['from']} dangling in {batch_id}")
                self.assertIn(edge["to"], doc_ids, f"Edge to {edge['to']} dangling in {batch_id}")

    def test_official_pilot_and_inventory_untouched(self):
        # Guarantee no modification to official pilot.json or historical source-inventory.json
        pilot_path = ROOT / "data/pilot.json"
        with open(pilot_path, "r", encoding="utf-8") as f:
            pilot_data = json.load(f)
        self.assertEqual(len(pilot_data["opportunities"]), 10)
        self.assertEqual(len(pilot_data["sources"]), 17)

        inventory_path = ROOT / "data/source-inventory.json"
        with open(inventory_path, "r", encoding="utf-8") as f:
            inv_data = json.load(f)
        self.assertEqual(len(inv_data["rows"]), 485)

if __name__ == "__main__":
    unittest.main()
