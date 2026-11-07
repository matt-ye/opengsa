"""真實 scan() + 真實設定 + 新來源排在最後：無人審時新來源多久被掃到？網路與頁面解析用替身。"""
import json, sys
from pathlib import Path

ROOT = Path(sys.argv[1])
sys.path.insert(0, str(ROOT))
import scripts.scan_sources as s

cfg = json.loads((ROOT / "data/scan-sources.json").read_text(encoding="utf-8"))
HOST = "scholarship.opengsa-synthetic.example"
URL = f"https://{HOST}/news/phd-2026"
cfg["sources"].append({"id": "synthetic", "title": "合成", "url": URL, "body_selector": "article", "required_markers": [], "pdf_include": [], "max_pdfs": 0,
                       "review_note": "x", "evidence_mode": "short_excerpt"})
cfg["allowed_hosts"] = sorted(set(cfg["allowed_hosts"]) | {HOST})
enabled = [x for x in cfg["sources"] if x.get("enabled", True)]
print("enabled", len(enabled), "total", len(cfg["sources"]), "new source position", len(enabled))


def transport(url, headers, limit):
    if url.endswith("/robots.txt"):
        return {"status": 404, "headers": {}, "body": b""}
    return {"status": 200, "headers": {"content-type": "text/html"}, "body": ("v1" + url).encode()}


s.html_document = lambda data, source, url, hosts: ([{"locator": "x", "text": "申請資格 " + url + " 內容" * 20}], [])
state = None
hit = None
for run in range(1, 12):
    f = s.Fetcher(cfg, transport=transport, sleeper=lambda _: None)
    state, report = s.scan(cfg, state, fetcher=f)
    st = {}
    for d in report["documents"]:
        st[d["status"]] = st.get(d["status"], 0) + 1
    syn = next(d["status"] for d in report["documents"] if d["source_id"] == "synthetic")
    print(f"run {run}: http={report['http_requests']} pending={report['pending_candidates']} cursor={state['next_source_index']} synthetic={syn} statuses={st}")
    if syn in ("changed", "unchanged") and hit is None:
        hit = run
print("first run that read the new source:", hit)
