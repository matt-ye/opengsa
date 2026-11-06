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
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.build_site import load_full_library


class SiteBuildTests(unittest.TestCase):
    def test_all_254_temporal_projections_render_without_fabricated_coordinates(self):
        soup=BeautifulSoup(self.html,'html.parser')
        payload={key:json.loads(soup.select_one('#'+tag).string) for key,tag in
            [('pilot','pilot-data'),('radar','radar-data')]}
        code=r'''
const fs=require('node:fs'), assert=require('node:assert/strict');
const core=require('./docs/design/prototype.js');
const data=JSON.parse(fs.readFileSync(0,'utf8'));
const items=core.makeDrafts(data.pilot,'2026-11-03',data.radar);
assert.equal(items.length,254);
for(const item of items){
 const mode=core.timePresentation(item);
 assert.ok(mode.label && !mode.label.includes('undefined'),item.id);
 if(item.timePolicy?.gaps.includes('multiple_cycles_need_split')){
  assert.equal(item.start.value,null);assert.equal(item.end.value,null);assert.equal(item.milestones.length,0);
 }
 if(['event_relative','recurring','continuous','unit_announced','review_only','reference','undetermined'].includes(mode.mode)){
  assert.equal(item.start.value,null,item.id);assert.equal(item.end.value,null,item.id);
 }
 if(item.start.value&&item.end.value)assert.ok(item.start.value<=item.end.value,item.id);
 const range=core.domain([item],'2026-11-03','fit'),g=core.geometry(item,range);
 if(g.bar){assert.ok(Number.isFinite(g.bar.left)&&Number.isFinite(g.bar.width),item.id);assert.ok(g.bar.width>=0,item.id);}
 assert.notEqual(item.rawState,'open',item.id); // no unreviewed replay auto-opens intake
}
for(const state of ['open','closed','upcoming','unknown','not_applicable']){
 const actual=state==='upcoming'?'not_yet_open':state;
 assert.ok(core.filterItems(items,{application:state}).every(i=>i.rawState===actual));
}
console.log('254 items: temporal labels, geometry, ambiguous years, intake filters PASS');
'''
        result=subprocess.run(['node','-e',code],cwd=ROOT,input=json.dumps(payload,ensure_ascii=False),
            text=True,encoding='utf-8',capture_output=True)
        self.assertEqual(result.returncode,0,result.stderr)

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
        self.assertEqual(files, {"index.html", "assets/opengsa-social-preview.jpg", ".nojekyll", "feed.xml", "feed-deadlines.xml"})
        self.assertEqual((self.output / "assets/opengsa-social-preview.jpg").read_bytes(), (ROOT / "docs/assets/opengsa-social-preview.jpg").read_bytes())

    def test_preview_is_self_contained_and_uses_named_radar_snapshot(self):
        self.assertNotIn('<script src=', self.html)
        embedded = re.search(r'<script id="pilot-data" type="application/json">(.*?)</script>', self.html, re.S)
        snapshot=json.loads(embedded[1])
        full_bundle, _ = load_full_library(ROOT)
        candidates = full_bundle['candidates']
        self.assertEqual({o['id'] for o in snapshot['opportunities']},{c['candidate_id'] for c in candidates})
        self.assertEqual(len(snapshot['opportunities']), 254)
        self.assertEqual(len(snapshot['opportunities']),len(candidates))
        self.assertTrue(all(o['review']['status']=='draft' for o in snapshot['opportunities']))
        self.assertIn('data-radar-view="true"',self.html)
        metadata=re.search(r'<script id="radar-data" type="application/json">(.*?)</script>',self.html,re.S)
        self.assertEqual(set(json.loads(metadata[1])['records']),{c['candidate_id'] for c in candidates})
        self.assertEqual(len(json.loads(metadata[1])['records']), 254)
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
        self.assertEqual([a.get_text(strip=True) for a in links],['提供回饋 ↗','提供獎助來源 ↗','⭐ GitHub Star ↗'])
        for link,template in zip(links[:2],['preview-feedback.yml','resource-source.yml']):
            self.assertEqual(link['href'],'https://github.com/matt-ye/opengsa/issues/new?template='+template)
            self.assertTrue((ROOT/'.github/ISSUE_TEMPLATE'/template).is_file())
            self.assertIsNone(link.find_parent(attrs={'role':'tablist'}))
            self.assertEqual(link['target'],'_blank');self.assertIn('noopener',link['rel'])
        self.assertEqual(links[2]['href'],'https://github.com/matt-ye/opengsa')
        self.assertEqual(links[2]['target'],'_blank');self.assertIn('noopener',links[2]['rel'])
        rss_btn = header.select_one('.header-actions #rss-subscribe-btn')
        self.assertIsNotNone(rss_btn)
        self.assertEqual(rss_btn.get_text(strip=True), '📡 訂閱推播')
        self.assertIsNone(rss_btn.find_parent(attrs={'role': 'tablist'}))
        self.assertIsNone(soup.select_one('.review-strip a'))

    def test_mobile_header_and_compare_select_cannot_widen_page(self):
        css=(ROOT/'docs/design/wireframes.html').read_text(encoding='utf-8')
        breakpoint_at=css.index('@media(max-width:1160px){.nav{flex-wrap:wrap')
        self.assertLess(css.rindex('flex-wrap:nowrap;flex-shrink:0}'),breakpoint_at,'不可在斷點之後以基底規則蓋回 nowrap')
        self.assertIn('.compare-controls select{flex:1;min-width:0;',css)

    def test_rss_modal_and_followit_integration(self):
        soup = BeautifulSoup(self.html, 'html.parser')
        dialog = soup.select_one('#rss-dialog')
        self.assertIsNotNone(dialog)
        self.assertEqual(dialog.name, 'dialog')

        form = dialog.select_one('form[action="https://api.follow.it/subscribe"]')
        self.assertIsNotNone(form)
        self.assertEqual(form['method'].lower(), 'post')
        self.assertEqual(form['target'], '_blank')
        self.assertIn('noopener', form.get('rel', ''))
        resource = form.select_one('input[name="resource"]')
        self.assertIsNotNone(resource)
        self.assertEqual(resource['value'], 'https://matt-ye.github.io/opengsa/feed.xml')
        self.assertIsNotNone(form.select_one('input[name="email"][type="email"]'))

        followit_link = dialog.select_one('a[href="https://follow.it/now"]')
        self.assertIsNotNone(followit_link)
        self.assertEqual(followit_link['target'], '_blank')

        main_input = dialog.select_one('#feed-main-url')
        self.assertIsNotNone(main_input)
        self.assertEqual(main_input['value'], 'https://matt-ye.github.io/opengsa/feed.xml')
        copy_main = dialog.select_one('#copy-feed-main')
        self.assertIsNotNone(copy_main)
        self.assertEqual(copy_main['data-copy'], 'https://matt-ye.github.io/opengsa/feed.xml')

        deadlines_input = dialog.select_one('#feed-deadlines-url')
        self.assertIsNotNone(deadlines_input)
        self.assertEqual(deadlines_input['value'], 'https://matt-ye.github.io/opengsa/feed-deadlines.xml')
        copy_deadlines = dialog.select_one('#copy-feed-deadlines')
        self.assertIsNotNone(copy_deadlines)
        self.assertEqual(copy_deadlines['data-copy'], 'https://matt-ye.github.io/opengsa/feed-deadlines.xml')

        self.assertIsNotNone(dialog.select_one('#rss-dialog-close'))
        self.assertIsNotNone(dialog.select_one('#rss-dialog-dismiss'))

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

    def test_page_heading_and_timing_table_remain_semantic_in_the_build(self):
        soup = BeautifulSoup(self.html, 'html.parser')
        self.assertEqual(len(soup.select('main h1')), 1)
        table = soup.select_one('#dates-table table')
        self.assertEqual(len(table.select('thead th[scope="col"]')), 6)
        self.assertIn('時間類型／規則', table.get_text())
        self.assertIsNotNone(table.caption)


if __name__ == "__main__":
    unittest.main()
