"""模型型號清單：只留穩定欄位、不帶金鑰與時間，沒變就不寫檔；workflow 只查清單、只寫一個檔。不連外。"""
import json
from pathlib import Path
import tempfile
import unittest

from scripts.model_catalog import catalog, write

ROOT = Path(__file__).resolve().parents[1]


def fake_audit(name, environ, probe=False):
    assert probe is False  # 只查清單，不做推論呼叫
    return {"provider": name, "key_present": True, "catalog_status": "success", "configured_model": "m-1",
            "model_present": True, "model_count": 2, "model_ids": ["m-1", "m-2"], "selected_model": "m-1",
            "rate_limit_headers": {"x-ratelimit-remaining": "41"}, "quota": {"used": 3}, "base_url": "https://x.test/v1"}


class ModelCatalogTests(unittest.TestCase):
    def test_only_stable_fields_are_kept(self):
        document = catalog({"OPENGSA_MODEL_API_KEY": "secret-key-123"}, audit=fake_audit)
        text = json.dumps(document, ensure_ascii=False)
        for volatile in ("x-ratelimit-remaining", "quota", "secret-key-123", "observed_at", "base_url"):
            self.assertNotIn(volatile, text)
        entry = next(iter(document["providers"].values()))
        self.assertEqual(entry["model_ids"], ["m-1", "m-2"])
        self.assertIn("inference_policy", entry)
        self.assertIn("groq", document["free_providers"])

    def test_unchanged_catalog_is_not_rewritten(self):
        document = catalog({}, audit=fake_audit)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "status/model-catalog.json"
            self.assertTrue(write(document, path))
            self.assertFalse(write(document, path))
            changed = json.loads(json.dumps(document))
            changed["providers"]["groq"]["model_ids"].append("m-3")
            self.assertTrue(write(changed, path))

    def test_workflow_lists_models_and_writes_one_file(self):
        workflow = (ROOT / ".github/workflows/model-catalog.yml").read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch", workflow)
        self.assertIn("python scripts/model_catalog.py", workflow)
        self.assertNotIn("--probe", workflow)
        self.assertIn("persist-credentials: false", workflow)
        self.assertIn("git add -- status/model-catalog.json", workflow)
        self.assertNotIn("pull-requests", workflow)


if __name__ == "__main__":
    unittest.main()
