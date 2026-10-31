"""建立 GitHub Pages 公開預覽；只輸出明列的網站成品。"""
import argparse
from pathlib import Path
import shutil
import json
import sys

from export_wireframes import ROOT, export
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from scripts.build_review_workspace import candidate_preview_data
from scripts.check_data import validate_candidate_snapshot
from scripts.radar_metadata import radar_metadata

URL = "https://matt-ye.github.io/opengsa/"
FEEDBACK = "https://github.com/matt-ye/opengsa/issues/new?template=preview-feedback.yml"


def build(output):
    if output.exists() and any(output.iterdir()):
        raise ValueError("Output directory must be empty; existing files are preserved")
    read=lambda name:json.loads((ROOT/'data'/name).read_text(encoding='utf-8'))
    candidates,pilot,config=read('candidates/source-review.json'),read('pilot.json'),read('scan-sources.json')
    errors=validate_candidate_snapshot(candidates,config)
    if errors:raise ValueError('Invalid radar source snapshot: '+str(errors))
    # Read-only discovery view. This does not confer human approval or modify
    # the complete-data pilot/ledger; unknown fields remain explicit in the UI.
    export(output / "index.html",pilot_data=candidate_preview_data(candidates,pilot,config),radar_view=True,
           radar_data=radar_metadata(candidates))
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
</head>''')
    replace_once("設計審閱稿 · 四分頁互動線框 · 資料快照 2026.10.28 · 所有獎助資料待獨立覆核，非申請建議", f'獎助雷達預覽 · 來源摘要，非即時資格核定 · ⚠ 不明，請見來源 · <a href="{FEEDBACK}">提供回饋 ↗</a>')
    replace_once("互動原型 · 不進行個人資格核定", "公開預覽 · 不進行個人資格核定")
    replace_once("OpenGSA · MVP介面基礎審閱稿 0.8 · 無外部字型、無追蹤、無個資送出。<br/>原創線框內容依專案授權；官方文件各保留原權利。自動擷取及正式發布尚待驗證。", f'''OpenGSA · 公開預覽 0.9 · 個人條件與研討會輸入只留本次瀏覽，無分析追蹤程式。<br>
GitHub Pages託管可能保留連線紀錄，詳見<a href="https://docs.github.com/en/site-policy/privacy-policies/github-general-privacy-statement">GitHub隱私聲明</a>。<br>
<a href="{FEEDBACK}">回報操作問題／建議</a>（需GitHub帳號，內容公開；請勿提交個資或私人申訴） · <a href="https://github.com/matt-ye/opengsa">原始碼與資料說明</a><br>
雷達為自動整理的來源摘要，未知資訊導流原文，非人工資格核定。完整資料發布仍須獨立覆核；模型僅手動啟用，RSS／ICS尚未啟用。原創內容依專案授權，官方文件保留原權利。''')
    page.write_text(html, encoding="utf-8")
    (output / "assets").mkdir()
    shutil.copyfile(ROOT / "docs/assets/opengsa-social-preview.jpg", output / "assets/opengsa-social-preview.jpg")
    (output / ".nojekyll").write_text("", encoding="utf-8")
    print("Built public preview: index.html, assets/opengsa-social-preview.jpg, .nojekyll")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    try:
        build(args.output)
    except ValueError as error:
        parser.error(str(error))
