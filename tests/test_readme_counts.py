"""README 的資料規模區塊要和資料一致，而且由資料產生、不手改。不連外。"""
from pathlib import Path
import shutil
import tempfile
import unittest

from scripts.readme_counts import END, START, refresh, render

ROOT = Path(__file__).resolve().parents[1]


class ReadmeCountsTests(unittest.TestCase):
    def test_readme_matches_the_data(self):
        text = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn(START, text)
        self.assertEqual(render(text), text, "執行 python scripts/readme_counts.py --write")

    def test_refresh_follows_a_data_change_and_skips_roots_without_a_readme(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in ("data", "docs/design"):
                shutil.copytree(ROOT / name, root / name)
            self.assertFalse(refresh(root))
            stale = (ROOT / "README.md").read_text(encoding="utf-8").replace(START, START + "\n舊的數字", 1)
            (root / "README.md").write_text(stale, encoding="utf-8")
            self.assertTrue(refresh(root))
            fresh = (root / "README.md").read_text(encoding="utf-8")
            self.assertNotIn("舊的數字", fresh)
            self.assertEqual(fresh.count(START), 1)
            self.assertEqual(fresh.count(END), 1)


if __name__ == "__main__":
    unittest.main()
