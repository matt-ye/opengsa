"""驗證發布成品邊界及預覽提示，不取代官方資料覆核。"""
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
from urllib.parse import urlparse, unquote
from bs4 import BeautifulSoup

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

    def test_preview_is_self_contained_and_uses_named_radar_snapshot(self):
        self.assertNotIn('<script src=', self.html)
        embedded = re.search(r'<script id="pilot-data" type="application/json">(.*?)</script>', self.html, re.S)
        snapshot=json.loads(embedded[1])
        candidates=json.loads((ROOT/'data/candidates/source-review.json').read_text(encoding='utf-8'))['candidates']
        self.assertEqual({o['id'] for o in snapshot['opportunities']},{c['candidate_id'] for c in candidates})
        self.assertEqual(len(snapshot['opportunities']),len(candidates))
        self.assertTrue(all(o['review']['status']=='draft' for o in snapshot['opportunities']))
        self.assertIn('data-radar-view="true"',self.html)
        metadata=re.search(r'<script id="radar-data" type="application/json">(.*?)</script>',self.html,re.S)
        self.assertEqual(set(json.loads(metadata[1])['records']),{c['candidate_id'] for c in candidates})
        conferences = re.search(r'<script id="conference-data" type="application/json">(.*?)</script>', self.html, re.S)
        self.assertEqual(json.loads(conferences[1]), json.loads((ROOT / "data/conference-programs.json").read_text(encoding="utf-8")))
        self.assertIn('name="robots" content="noindex, nofollow"', self.html)
        self.assertIn('property="og:image" content="https://matt-ye.github.io/opengsa/assets/opengsa-social-preview.jpg"', self.html)
        self.assertIn('href="https://matt-ye.github.io/opengsa/"', self.html)
        self.assertIn('獎助雷達預覽 · 來源摘要，非即時資格核定', self.html)
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

    def test_header_issue_actions_are_links_outside_the_four_page_tabs(self):
        soup=BeautifulSoup(self.html,'html.parser')
        header=soup.select_one('header.nav-wrap')
        tabs=header.select('[role="tab"]')
        self.assertEqual([t.get_text(strip=True) for t in tabs],['找獎助','獎助詳情','我的時間軸','權益與求助'])
        links=header.select('.header-actions a')
        self.assertEqual([a.get_text(strip=True) for a in links],['提供回饋 ↗','提供獎助來源 ↗'])
        for link,template in zip(links,['preview-feedback.yml','resource-source.yml']):
            self.assertEqual(link['href'],'https://github.com/matt-ye/opengsa/issues/new?template='+template)
            self.assertTrue((ROOT/'.github/ISSUE_TEMPLATE'/template).is_file())
            self.assertIsNone(link.find_parent(attrs={'role':'tablist'}))
            self.assertEqual(link['target'],'_blank');self.assertIn('noopener',link['rel'])
        self.assertIsNone(soup.select_one('.review-strip a'))

    def test_rights_sections_and_all_fragment_or_document_links_resolve(self):
        soup = BeautifulSoup(self.html, 'html.parser')
        ids = [tag['id'] for tag in soup.select('[id]')]
        self.assertEqual(len(ids), len(set(ids)), 'Duplicate IDs break fragment navigation')
        for link in soup.select('a[href^="#"]'):
            self.assertIn(link['href'][1:], ids)
        rights = soup.select_one('#rights')
        sections = rights.select('[data-rights-section]')
        self.assertEqual([s['data-rights-section'] for s in sections],
                         ['overview', 'pay', 'standards', 'grievance'])
        self.assertEqual([s['data-rights-section'] for s in sections if not s.has_attr('hidden')], ['overview'])
        controls = rights.select('#rights-view-switch [aria-controls]')
        self.assertEqual({c['aria-controls'] for c in controls}, {s['id'] for s in sections})
        for link in rights.select('a[href]'):
            url = urlparse(link['href'])
            self.assertIn(url.scheme, ('', 'https'))
            if url.netloc == 'github.com':
                self.assertTrue(url.path.startswith('/matt-ye/opengsa/blob/main/docs/'))
                local = ROOT / unquote(url.path.split('/blob/main/', 1)[1])
                self.assertTrue(local.is_file(), str(local))
        self.assertIn('支給上限', rights.select_one('#rights-pay-group').get_text())
        self.assertNotIn('29025/', str(rights))  # Removed official URL returns 410.


if __name__ == "__main__":
    unittest.main()
