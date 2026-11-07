"""建立公開預覽（GitHub Pages＋自訂網域）；只輸出明列的網站成品。"""
import argparse
from pathlib import Path
import shutil
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT, ROOT / "scripts"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from export_wireframes import export
from scripts.build_review_workspace import candidate_preview_data
from scripts.build_feed import SITE_URL, build_feeds
from scripts.check_data import validate_candidate_snapshot
from scripts.radar_metadata import radar_metadata
from scripts.source_chains import timeline_metadata

URL = SITE_URL
# Cloudflare Web Analytics 的公開 site token（本來就會出現在頁面原始碼，不是密鑰）。
CF_ANALYTICS_TOKEN = "842cdb275d8b43219c0c0a2a55063852"
FEEDBACK = "https://github.com/matt-ye/opengsa/issues/new?template=preview-feedback.yml"


def load_full_library(root=ROOT):
    """Loads all 254 candidates across the 8 candidate bundles and combined observations."""
    read = lambda name: json.loads((Path(root) / "data" / name).read_text(encoding="utf-8"))
    bundle_files = [
        "candidates/source-review.json",
        "candidates/k12-scholarships.json",
        "candidates/student-perks.json",
        "candidates/enterprise-scholarships.json",
        "candidates/medical-scholarships.json",
        "candidates/university-scholarships.json",
        "candidates/topology-discovered-scholarships.json",
        "candidates/emergency-relief-aid.json",
    ]
    obs_files = [
        "temporal-observations.json",
        "k12-temporal-observations.json",
        "perks-temporal-observations.json",
        "enterprise-temporal-observations.json",
        "medical-temporal-observations.json",
        "university-temporal-observations.json",
        "topology-discovered-temporal-observations.json",
        "emergency-relief-temporal-observations.json",
    ]
    all_cands = []
    for bf in bundle_files:
        all_cands.extend(read(bf)["candidates"])

    combined_records = {}
    combined_batches = []
    total_http = 0
    for of in obs_files:
        o_data = read(of)
        combined_records.update(o_data["records"])
        combined_batches.extend(o_data.get("batches", []))
        total_http += o_data.get("http_requests", 0)

    combined_bundle = {
        "schema_version": "1.1.0-candidate",
        "generated_at": "2026-11-06T00:00:00Z",
        "as_of": "2026-11-06",
        "timezone": "Asia/Taipei",
        "model_enabled": False,
        "model_calls": 0,
        "official_data_modified": False,
        "candidates": all_cands,
    }
    combined_obs = {
        "version": "temporal-replay-1",
        "observed_at": "2026-11-06T00:00:00Z",
        "http_requests": total_http,
        "model_calls": 0,
        "published": False,
        "batches": combined_batches,
        "records": combined_records,
    }
    return combined_bundle, combined_obs


def build(output):
    if output.exists() and any(output.iterdir()):
        raise ValueError("Output directory must be empty; existing files are preserved")
    read = lambda name: json.loads((ROOT / "data" / name).read_text(encoding="utf-8"))
    candidates, observations = load_full_library(ROOT)
    pilot, config = read("pilot.json"), read("scan-sources.json")
    errors = validate_candidate_snapshot(candidates, config)
    if errors:
        raise ValueError("Invalid radar source snapshot: " + str(errors))
    # Read-only discovery view. This does not confer human approval or modify
    # the complete-data pilot/ledger; unknown fields remain explicit in the UI.
    export(
        output / "index.html",
        pilot_data=candidate_preview_data(candidates, pilot, config),
        radar_view=True,
        radar_data=radar_metadata(candidates, observations),
        chain_data=timeline_metadata(read("source-chains.json"), candidates),
    )
    page = output / "index.html"
    html = page.read_text(encoding="utf-8")

    def replace_once(old, new):
        nonlocal html
        if html.count(old) != 1:
            raise ValueError("Preview template changed; review publication markers")
        html = html.replace(old, new, 1)

    replace_once("<title>OpenGSA｜四頁線框審閱稿</title>", "<title>OpenGSA｜公開預覽 · 獎助與研究生權益</title>")
    description = "把時間留給研究，把獎助檢索交給 OpenGSA。獎助雷達整理來源摘要；未明資訊請至官方來源確認，篩選不代表資格核定。"
    replace_once("</head>", f'''<meta name="description" content="{description}">
<meta name="robots" content="noindex, nofollow">
<link rel="canonical" href="{URL}">
<link rel="alternate" type="application/rss+xml" title="OpenGSA 獎助雷達最新動態" href="{URL}feed.xml">
<link rel="alternate" type="application/rss+xml" title="OpenGSA 獎助截止倒數提醒" href="{URL}feed-deadlines.xml">
<meta property="og:type" content="website">
<meta property="og:locale" content="zh_TW">
<meta property="og:title" content="OpenGSA｜公開預覽">
<meta property="og:description" content="{description}">
<meta property="og:url" content="{URL}">
<meta property="og:image" content="{URL}assets/opengsa-social-preview.jpg">
<meta property="og:image:width" content="1280">
<meta property="og:image:height" content="640">
<meta property="og:image:alt" content="OpenGSA：把時間留給研究，研究與安心生活">
<meta name="twitter:card" content="summary_large_image">
<script type="module" src="https://static.cloudflareinsights.com/beacon.min.js" data-cf-beacon='{{"token":"{CF_ANALYTICS_TOKEN}","spa":false}}'></script>
</head>''')
    replace_once("設計審閱稿 · 四分頁互動線框 · 資料快照 2026.10.28 · 所有獎助資料待獨立覆核，非申請建議", '獎助雷達預覽 · 來源摘要，非即時資格核定 · ⚠ 不明，請見來源')
    replace_once("互動原型 · 不進行個人資格核定", "公開預覽 · 不進行個人資格核定")
    replace_once("OpenGSA · MVP介面基礎審閱稿 0.8 · 無外部字型、無追蹤、無個資送出。<br/>原創線框內容依專案授權；官方文件各保留原權利。自動擷取及正式發布尚待驗證。", f'''<p class="footer-links"><span>作者 <a href="https://mattye.dev/">葉淨維 Matt Ye</a></span><a href="https://github.com/matt-ye">GitHub</a><a href="https://github.com/matt-ye/opengsa">原始碼與資料說明</a><a href="{FEEDBACK}">回報問題</a><a href="{URL}feed.xml">全庫 RSS</a><a href="{URL}feed-deadlines.xml">截止倒數 RSS</a></p>
<p>OpenGSA 公開預覽 0.9：自動整理的來源摘要，非資格核定，請以官方公告為準。</p>
<p>個人條件與研討會輸入只留本次瀏覽。以Cloudflare Web Analytics統計瀏覽量：不使用Cookie，不記錄網址查詢參數（搜尋與篩選條件）。GitHub Pages託管與Cloudflare可能保留連線紀錄（<a href="https://docs.github.com/en/site-policy/privacy-policies/github-general-privacy-statement">GitHub隱私聲明</a>、<a href="https://www.cloudflare.com/privacypolicy/">Cloudflare隱私政策</a>）。回報內容公開，請勿提交個資或私人申訴。原創內容依專案授權，官方文件保留原權利。</p>''')
    page.write_text(html, encoding="utf-8")
    assets = output / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "docs/assets/opengsa-social-preview.jpg", assets / "opengsa-social-preview.jpg")
    build_feeds(output, candidates["candidates"], observations)
    (output / ".nojekyll").touch()
    print("Built public preview: index.html, feed.xml, feed-deadlines.xml, assets/opengsa-social-preview.jpg, .nojekyll")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    build(parser.parse_args().output)
