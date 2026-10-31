"""匯出可離線開啟的單檔互動線框；不建立或部署產品網站。"""
import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def export(output, pilot_data=None, review_preview=False):
    source = ROOT / "docs/design/wireframes.html"
    html = source.read_text(encoding="utf-8")
    for block, filename in [("pilot-data", "pilot.json"), ("conference-data", "conference-programs.json")]:
        data = pilot_data if block=="pilot-data" and pilot_data is not None else json.loads((ROOT / "data" / filename).read_text(encoding="utf-8"))
        encoded = json.dumps(data, ensure_ascii=False).replace("<", "\\u003c")
        html, count = re.subn(
            rf'(<script id="{block}" type="application/json">).*?(</script>)',
            lambda match: match[1] + encoded + match[2], html, flags=re.S,
        )
        if count != 1:
            raise ValueError(f"Expected one {block} block")
    code = (ROOT / "docs/design/prototype.js").read_text(encoding="utf-8")
    if "</script" in code.lower():
        raise ValueError("Inline script delimiter must be escaped")
    html = html.replace('<script src="prototype.js"></script>', "<script>\n" + code + "\n</script>")
    if review_preview:
        html=html.replace("<body>",'<body data-review-preview="true">',1)
        html=html.replace("設計審閱稿 · 四分頁互動線框 · 資料快照 2026.10.28 · 所有獎助資料待獨立覆核，非申請建議","候選審查預覽 · 未核准／未發布 · 僅顯示本批候選，非正式可申請清單",1)
        html=html.replace("OpenGSA｜四頁線框審閱稿","OpenGSA｜候選審查預覽",1)
        html=html.replace("收錄臺大與全國代表性獎助草稿及會議補助制度；申請前請以主辦單位當期公告為準。","本頁僅預覽本批待審候選；尚未更新公開網站，申請前請核對官方當期公告。",1)
    if output.resolve() == source.resolve():
        raise ValueError("Keep the source HTML and JavaScript separate; choose an export path")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(html, encoding="utf-8")
    print(f"Exported: {output.name}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    export(parser.parse_args().output)
