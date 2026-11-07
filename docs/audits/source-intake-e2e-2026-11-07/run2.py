"""第二輪：沿用 run/repo 副本，追 build_site 失敗、上架閘門、時間軌回寫、索引頁列舉與通用 profile。"""
import json, os, re, shutil, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUN = HERE / "run"
REPO, FIX = RUN / "repo", RUN / "fixtures"
ENV = {**os.environ, "OPENGSA_FIXTURES": str(FIX), "PYTHONUTF8": "1", "OPENGSA_MODEL_MODE": "off", "PYTHONDONTWRITEBYTECODE": "1"}
PY = sys.executable
HOST = "scholarship.opengsa-synthetic.example"
SID = "synthetic-foundation-2026"
TITLE = "合成基金會115學年度研究生獎學金"


def sh(step, *cmd, tail=500):
    r = subprocess.run([str(c) for c in cmd], cwd=REPO, env=ENV, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=900)
    out = (r.stdout + "\n" + r.stderr).strip()
    print(f"\n### {step} exit={r.returncode}\n{out[-tail:]}", flush=True)
    return r, out


def read(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def save(p, v):
    Path(p).parent.mkdir(parents=True, exist_ok=True)
    Path(p).write_text(json.dumps(v, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def note(step, **kw):
    print(f"\n### {step}\n{json.dumps(kw, ensure_ascii=False, indent=1)[:2600]}", flush=True)


def site(d):
    p = Path(d) / "index.html"
    if not p.exists():
        return {"built": False}
    h = p.read_text(encoding="utf-8")
    f = (Path(d) / "feed.xml").read_text(encoding="utf-8")
    m = re.search(r'<script id="radar-data"[^>]*>(.*?)</script>', h, re.S)
    radar = json.loads(m.group(1))["records"] if m else {}
    rec = {k: v for k, v in radar.items() if SID in k}
    return {"built": True, "title_in_page": h.count(TITLE), "title_in_feed": f.count(TITLE), "feed_items": f.count("<item>"), "radar_records": len(radar),
            "synthetic_radar": json.dumps(rec, ensure_ascii=False)[:500]}


# A. 所有失敗測試名稱
r, out = sh("A 全部 unittest（套用提案後）", PY, "-m", "unittest", "discover", "-s", "tests", tail=120)
fails = re.findall(r"^(FAIL|ERROR): (\S+) \((\S+?)\.", out, re.M)
note("A 失敗清單", count=len(fails), items=[f"{a} {c}.{b}" for a, b, c in fails])
msgs = re.findall(r"^(?:AssertionError|\w*Error): (.{0,110})$", out, re.M)
note("A 失敗訊息", msgs=msgs)

# B. build_site 的 as_of 寫死。只在副本改這一行，繼續看後面的閘門。
bs = REPO / "scripts/build_site.py"
text = bs.read_text(encoding="utf-8")
note("B 寫死日期", lines=[l.strip() for l in text.splitlines() if "2026-11-06" in l])
bs.write_text(text.replace('"as_of": "2026-11-06"', '"as_of": "2026-11-07"'), encoding="utf-8")
sh("B build_site（副本改 as_of 後，未經人工審核）", PY, "scripts/build_site.py", RUN / "s1", tail=500)
note("B 上架結果（未審核）", **site(RUN / "s1"))

# C. 駁回不影響上架？
c = next(x for x in read(REPO / "data/candidates/source-review.json")["candidates"] if x["source_metadata"]["source_id"] == SID)
led = REPO / "data/scan-reviews.json"
orig = led.read_text(encoding="utf-8")
save(led, read(RUN / "dec-dismissed.json"))
sh("C 駁回寫入台帳後 build_site", PY, "scripts/build_site.py", RUN / "s2", tail=200)
note("C 駁回後網站", **site(RUN / "s2"))
led.write_text(orig, encoding="utf-8")
note("C 候選狀態", review=c["review"], verification=c["verification"]["status"])

# D. 時間軌回寫：沒有 importer，手動套用 temporal 提案。
prop = REPO / "work/t1/temporal-observations.proposed.json"
d0 = read(REPO / "data/temporal-observations.json")
pv = read(prop)
note("D 提案差異", base_records=len(d0["records"]), proposed_records=len(pv["records"]), new_has_synth=any(SID in k or (v.get("url", "") and HOST in v.get("url", "")) for k, v in pv["records"].items()))
shutil.copy(REPO / "data/temporal-observations.json", RUN / "tobs.bak")
save(REPO / "data/temporal-observations.json", pv)
sh("D 套用時間提案 check_data", PY, "scripts/check_data.py", tail=300)
sh("D 套用時間提案 build_site", PY, "scripts/build_site.py", RUN / "s3", tail=200)
note("D 網站（有時間記錄）", **site(RUN / "s3"))

# E. 提案對資訊鏈索引的影響
idx0 = json.loads(subprocess.run(["git", "show", "origin/main:data/source-chain-index.json"], cwd=sys.argv[1], capture_output=True, text=True, encoding="utf-8").stdout)
idx1 = read(REPO / "work/a/proposal/repo/data/source-chain-index.json")
sc0 = json.loads(subprocess.run(["git", "show", "origin/main:data/source-chains.json"], cwd=sys.argv[1], capture_output=True, text=True, encoding="utf-8").stdout)
sc1 = read(REPO / "work/a/proposal/repo/data/source-chains.json")
note("E 提案對資訊鏈", programs_before=len(idx0["programs"]), programs_after=len(idx1["programs"]),
     dropped=[p["key"] for p in idx0["programs"] if p["key"] not in {q["key"] for q in idx1["programs"]}][:10],
     rules_before=sum(len(p["rules"]) for p in idx0["programs"]), rules_after=sum(len(p["rules"]) for p in idx1["programs"]),
     bindings_before=len(sc0["candidate_bindings"]), bindings_after=len(sc1["candidate_bindings"]),
     synthetic_bound=any(b.get("program_key", "").startswith("synthetic") for b in sc1["candidate_bindings"]),
     status_before=sorted({d["status"] for d in sc0["documents"]}), recheck_before=sum(d["status"] == "newer_candidate_requires_chain_recheck" for d in sc0["documents"]))

# F. 使用者常交的索引頁（表單允許）：能否列舉出底下的資源？
index_html = f"""<!doctype html><html lang="zh-Hant"><head><title>合成大學生輔組獎學金公告</title></head><body><main>
<h1>獎學金公告</h1><ul>
<li><a href="/news/a">合成甲基金會115年度研究生獎學金</a> 2026-03-01</li>
<li><a href="/news/b">合成乙基金會115年度清寒獎助學金</a> 2026-03-05</li>
<li><a href="/news/c">合成丙基金會博士生論文獎</a> 2026-03-09</li>
</ul><p>本頁彙整校內外獎學金公告，詳細資格與期限請見各公告連結內容，如有疑問請洽生活輔導組。</p></main></body></html>"""
(FIX / "index.html").write_text(index_html, encoding="utf-8")
child = """<!doctype html><html lang="zh-Hant"><head><title>{t}</title></head><body><article><h1>{t}</h1>
<p>申請資格：國內大學研究所在學學生。</p><p>獎助金額：每名新臺幣三萬元。</p><p>申請期間：115年3月1日至115年4月1日止。</p></article></body></html>"""
m = read(FIX / "map.json")
m[f"https://{HOST}/scholarships"] = {"file": "index.html", "type": "text/html; charset=utf-8"}
for k, t in (("a", "合成甲基金會115年度研究生獎學金"), ("b", "合成乙基金會115年度清寒獎助學金"), ("c", "合成丙基金會博士生論文獎")):
    (FIX / f"c{k}.html").write_text(child.format(t=t), encoding="utf-8")
    m[f"https://{HOST}/news/{k}"] = {"file": f"c{k}.html", "type": "text/html; charset=utf-8"}
save(FIX / "map.json", m)
inv = {"as_of": "2026-11-07", "rows": [{"id": "IDX1", "url": f"https://{HOST}/scholarships", "title": "合成索引", "batch": "B2", "category": "campus", "kind": "索引", "restrictions": [], "access_gate": "fresh_policy_and_profile_check_required"}]}
save(RUN / "inv2.json", inv)
sh("F expand 索引頁", PY, "scripts/expand_sources.py", "--inventory", RUN / "inv2.json", "--batch", "B2", "--state", "work/x2/state.json", "--output", "work/x2/report", tail=500)
if (REPO / "work/x2/report/source-results.json").exists():
    res = read(REPO / "work/x2/report/source-results.json")
    note("F expand 列舉結果", records=[{k: r.get(k) for k in ("url", "status", "disposition")} for r in res["records"]], links=[{k: l.get(k) for k in ("url", "role", "label")} for r in res["records"] for l in r.get("links", [])],
         discovered=[r["url"] for r in res["discovered_sources"]], candidates=read(REPO / "work/x2/report/structured-candidates.json")["candidates"].__len__())
# G. 通用 profile（新來源沒有人調 selector 時）
gen = {"id": "synthetic-generic", "title": "合成索引", "url": f"https://{HOST}/scholarships", "body_selector": "body", "required_markers": [], "pdf_include": [], "max_pdfs": 0,
       "review_note": "通用 profile", "evidence_mode": "hash_only", "category": "phd_research", "resource_kind": "scholarship", "scope": "nationwide"}
cfg = read(RUN / "only.json")
save(RUN / "gen.json", {**cfg, "sources": [gen]})
sh("G scan 索引頁（通用 profile）", PY, "scripts/scan_sources.py", "--config", RUN / "gen.json", "--state", "work/g/state.json", "--output", "work/g/report", tail=300)
if (REPO / "work/g/report/structured-candidates.json").exists():
    g = read(REPO / "work/g/report/structured-candidates.json")
    note("G 索引頁被當成", count=len(g["candidates"]), rows=[{"title": x["title"], "status": x["verification"]["status"], "errors": x["verification"]["errors"][:3], "benefit": x["benefit"]["summary"], "state": x["application"]["state"]} for x in g["candidates"]])
