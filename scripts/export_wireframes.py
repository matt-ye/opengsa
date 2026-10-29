"""匯出可離線開啟的單檔互動線框；不建立或部署產品網站。"""
import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def export(output):
    source = ROOT / "docs/design/wireframes.html"
    html = source.read_text(encoding="utf-8")
    data = json.loads((ROOT / "data/pilot.json").read_text(encoding="utf-8"))
    encoded = json.dumps(data, ensure_ascii=False).replace("<", "\\u003c")
    html, count = re.subn(
        r'(<script id="pilot-data" type="application/json">).*?(</script>)',
        lambda match: match[1] + encoded + match[2],
        html, flags=re.S,
    )
    if count != 1:
        raise ValueError("Expected one pilot-data block")
    code = (ROOT / "docs/design/prototype.js").read_text(encoding="utf-8")
    if "</script" in code.lower():
        raise ValueError("Inline script delimiter must be escaped")
    html = html.replace('<script src="prototype.js"></script>', "<script>\n" + code + "\n</script>")
    if output.resolve() == source.resolve():
        raise ValueError("Keep the source HTML and JavaScript separate; choose an export path")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(html, encoding="utf-8")
    print(f"Exported: {output.name}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    export(parser.parse_args().output)
