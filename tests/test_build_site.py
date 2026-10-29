"""驗證發布成品邊界及預覽提示，不取代官方資料覆核。"""
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class SiteBuildTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.output = Path(cls.temp.name) / "site"
        subprocess.run([sys.executable, str(ROOT / "scripts/build_site.py"), str(cls.output)], check=True, capture_output=True)
        cls.html = (cls.output / "index.html").read_text(encoding="utf-8")

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_only_public_artifacts_are_published(self):
        files = {p.relative_to(self.output).as_posix() for p in self.output.rglob("*") if p.is_file()}
        self.assertEqual(files, {"index.html", "assets/opengsa-social-preview.jpg", ".nojekyll"})
        self.assertEqual((self.output / "assets/opengsa-social-preview.jpg").read_bytes(), (ROOT / "docs/assets/opengsa-social-preview.jpg").read_bytes())

    def test_preview_is_self_contained_and_uses_current_draft(self):
        self.assertNotIn('<script src=', self.html)
        embedded = re.search(r'<script id="pilot-data" type="application/json">(.*?)</script>', self.html, re.S)
        self.assertEqual(json.loads(embedded[1]), json.loads((ROOT / "data/pilot.json").read_text(encoding="utf-8")))
        conferences = re.search(r'<script id="conference-data" type="application/json">(.*?)</script>', self.html, re.S)
        self.assertEqual(json.loads(conferences[1]), json.loads((ROOT / "data/conference-programs.json").read_text(encoding="utf-8")))
        self.assertIn('name="robots" content="noindex, nofollow"', self.html)
        self.assertIn('property="og:image" content="https://matt-ye.github.io/opengsa/assets/opengsa-social-preview.jpg"', self.html)
        self.assertIn('href="https://matt-ye.github.io/opengsa/"', self.html)
        self.assertIn('公開預覽 · 合成示範與來源草稿，非即時申請清單', self.html)
        self.assertIn('issues/new?template=preview-feedback.yml', self.html)
        self.assertIn('請勿提交個資或私人申訴', self.html)

    def test_existing_output_is_not_overwritten_or_uploaded(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            sentinel = output / "private.txt"
            sentinel.write_text("do not publish", encoding="utf-8")
            result = subprocess.run([sys.executable, str(ROOT / "scripts/build_site.py"), str(output)], capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "do not publish")


if __name__ == "__main__":
    unittest.main()
