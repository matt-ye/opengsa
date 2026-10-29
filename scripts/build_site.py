"""建立 GitHub Pages 公開預覽；只輸出明列的網站成品。"""
import argparse
from pathlib import Path
import shutil

from export_wireframes import ROOT, export

URL = "https://matt-ye.github.io/opengsa/"
FEEDBACK = "https://github.com/matt-ye/opengsa/issues/new?template=preview-feedback.yml"


def build(output):
    if output.exists() and any(output.iterdir()):
        raise ValueError("Output directory must be empty; existing files are preserved")
    export(output / "index.html")
    page = output / "index.html"
    html = page.read_text(encoding="utf-8")

    def replace_once(old, new):
        nonlocal html
        if html.count(old) != 1:
            raise ValueError("Preview template changed; review publication markers")
        html = html.replace(old, new, 1)

    replace_once("<title>OpenGSA｜四頁線框審閱稿</title>", "<title>OpenGSA｜公開預覽 · 獎助與研究生權益</title>")
    description = "把時間留給研究，把獎助檢索交給 OpenGSA。體驗獎助篩選、甘特圖與研討會規劃；資料為示範及待覆核草稿。"
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
    replace_once("設計審閱稿 · 四分頁互動線框 · 資料快照 2026.10.28 · 所有獎助資料待獨立覆核，非申請建議", f'公開預覽 · 合成示範與來源草稿，非即時申請清單 · 資料待獨立覆核 · <a href="{FEEDBACK}">提供回饋 ↗</a>')
    replace_once("互動原型 · 不進行個人資格核定", "公開預覽 · 不進行個人資格核定")
    replace_once("OpenGSA · MVP介面基礎審閱稿 0.8 · 無外部字型、無追蹤、無個資送出。<br>原創線框內容依專案授權；官方文件各保留原權利。自動擷取及正式發布尚待驗證。", f'''OpenGSA · 公開預覽 0.8 · 個人條件與研討會輸入只留本次瀏覽，無分析追蹤程式。<br>
GitHub Pages託管可能保留連線紀錄，詳見<a href="https://docs.github.com/en/site-policy/privacy-policies/github-general-privacy-statement">GitHub隱私聲明</a>。<br>
<a href="{FEEDBACK}">回報操作問題／建議</a>（需GitHub帳號，內容公開；請勿提交個資或私人申訴） · <a href="https://github.com/matt-ye/opengsa">原始碼與資料說明</a><br>
所有來源資料仍待獨立覆核，請以正式公告為準；來源變更須覆核後更新，Agent、RSS／ICS尚未啟用。原創內容依專案授權，官方文件保留原權利。''')
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
