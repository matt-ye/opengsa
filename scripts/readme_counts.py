"""README 的資料規模區塊由資料產生，不手改。

- 卡片數：網站實際讀的卡片檔（build_site.load_full_library 的清單），依卡片類別統計；類別名稱沿用前端的 labels.category。
- 手寫卡數：data/known-hand-authored-candidates.json。
- 巡檢中的來源：data/scan-sources.json 裡啟用的來源。
- 不放日期：內容只在資料變動時才變，不會每次都改到 README。

預設只檢查（不一致時結束碼 1，CI 用）；--write 改寫 README（資料 PR 套用提案後會執行）。
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

START, END = "<!-- data-counts:start -->", "<!-- data-counts:end -->"


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def category_labels(root=ROOT):
    line = re.search(r"category:\s*\{([^}]*)\}", (Path(root) / "docs/design/prototype.js").read_text(encoding="utf-8")).group(1)
    return dict(re.findall(r'(\w+):"([^"]+)"', line))


def site_cards(root=ROOT):
    from scripts.build_site import load_full_library
    return load_full_library(root)[0]["candidates"]


def block(root=ROOT):
    cards = site_cards(root)
    hand = set(read(Path(root) / "data/known-hand-authored-candidates.json")["candidate_ids"])
    scanned = sum(s.get("enabled", True) for s in read(Path(root) / "data/scan-sources.json")["sources"])
    labels = category_labels(root)
    counts = Counter(c["category"] for c in cards)
    lines = [START,
             f"> **全庫方案覆蓋規模**：**{len(cards)} 筆來源摘要**，其中 {len(cards) - len(hand & {c['candidate_id'] for c in cards})} 筆由萃取流程產生、"
             f"{len(hand & {c['candidate_id'] for c in cards})} 筆是尚未由流程取代的手寫卡；排程巡檢中的來源 {scanned} 個。來源沒載明時程的標示為未判定，不補值。  ",
             "",
             "| 類別 | 筆數 |",
             "|---|---|"]
    lines.extend(f"| {labels.get(key, key)} | {count} |" for key, count in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])))
    lines.append(END)
    return "\n".join(lines)


def render(text, root=ROOT):
    pattern = re.compile(re.escape(START) + r".*?" + re.escape(END), re.S)
    if not pattern.search(text):
        raise ValueError("README is missing the data-counts markers")
    return pattern.sub(lambda _: block(root), text)


def refresh(root=ROOT):
    """資料變動後重算 README 的資料規模區塊；沒有 README 或沒有標記（例如測試用的暫存資料）就略過。回傳是否有改。"""
    path = Path(root) / "README.md"
    if not path.exists() or START not in path.read_text(encoding="utf-8"):
        return False
    text = path.read_text(encoding="utf-8")
    updated = render(text, root)
    if updated != text:
        path.write_text(updated, encoding="utf-8")
    return updated != text


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    path = args.root / "README.md"
    text = path.read_text(encoding="utf-8")
    updated = render(text, args.root)
    if args.write:
        if updated != text:
            path.write_text(updated, encoding="utf-8")
        print("written" if updated != text else "unchanged")
        return
    if updated != text:
        sys.exit("README 的資料規模區塊和資料不一致：執行 python scripts/readme_counts.py --write")
    print("README counts match the data")


if __name__ == "__main__":
    main()
