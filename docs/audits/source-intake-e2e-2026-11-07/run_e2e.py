"""從 repo 副本跑合成來源的端到端流程；只動副本，傳輸換成本機假頁。"""
import json, os, shutil, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = Path(sys.argv[1])
RUN = HERE / "run"
if RUN.exists():
    shutil.rmtree(RUN)
REPO, FIX = RUN / "repo", RUN / "fixtures"
shutil.copytree(SRC, REPO, ignore=shutil.ignore_patterns(".git", "work", "dist", "__pycache__"))
shutil.copy(HERE / "mock_http_get.cjs", REPO / "scripts/http_get.cjs")
FIX.mkdir()
HOST = "scholarship.opengsa-synthetic.example"
MAIN = f"https://{HOST}/news/phd-2026"
POLICY = f"https://{HOST}/policy/rules"
SID = "synthetic-foundation-2026"


def page(title, deadline="115年4月15日", extra=""):
    return f"""<!doctype html><html lang="zh-Hant"><head><title>{title}</title></head><body><nav>首頁</nav>
<article class="post"><h1>{title}</h1>
<p>公告日期：115年2月10日</p>
<p>一、申請資格：國內公私立大學校院碩士班、博士班在學學生，前一學年學業成績平均達八十分以上者。</p>
<p>二、獎助金額：每名新臺幣五萬元整（NT$50,000），名額十名。</p>
<p>三、申請期間：自115年3月1日起至{deadline}止，逾期不予受理。</p>
<p>四、應備文件：申請表、歷年成績單、研究計畫書、指導教授推薦函。</p>
<p>五、兼領限制：同一學年度不得同時領取本基金會其他獎學金。</p>
<p>六、申請方式：由學生本人以電子郵件寄送至基金會。</p>
<p>七、結果公告：115年6月30日前公告於本基金會網站。</p>
{extra}
<p><a href="/policy/rules">合成基金會研究生獎學金設置辦法</a></p>
</article><footer>合成測試頁，非真實機構</footer></body></html>"""


POLICY_HTML = """<!doctype html><html lang="zh-Hant"><head><title>合成基金會研究生獎學金設置辦法</title></head><body>
<article class="post"><h1>合成基金會研究生獎學金設置辦法</h1>
<p>第一條 本辦法依本基金會章程訂定，適用於國內公私立大學校院碩士班、博士班在學學生。</p>
<p>第二條 申請資格：前一學年學業成績平均達八十分以上者，得申請本獎學金。</p>
<p>第三條 本辦法經董事會通過後施行，修正時亦同。</p></article></body></html>"""


def fixtures(main_html):
    (FIX / "main.html").write_text(main_html, encoding="utf-8")
    (FIX / "policy.html").write_text(POLICY_HTML, encoding="utf-8")
    (FIX / "map.json").write_text(json.dumps({
        MAIN: {"file": "main.html", "type": "text/html; charset=utf-8"},
        POLICY: {"file": "policy.html", "type": "text/html; charset=utf-8"},
    }), encoding="utf-8")


fixtures(page("合成基金會115學年度研究生獎學金"))
ENV = {**os.environ, "OPENGSA_FIXTURES": str(FIX), "PYTHONUTF8": "1", "OPENGSA_MODEL_MODE": "off"}
LOG = []


def sh(step, *cmd, tail=700):
    r = subprocess.run([str(c) for c in cmd], cwd=REPO, env=ENV, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=900)
    out = (r.stdout + "\n" + r.stderr).strip()
    LOG.append({"step": step, "cmd": " ".join(str(c).replace(str(REPO), "<repo>") for c in cmd[1:]), "exit": r.returncode, "tail": out[-tail:]})
    print(f"\n### {step} exit={r.returncode}\n{out[-tail:]}", flush=True)
    return r


def read(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def save(p, v):
    Path(p).parent.mkdir(parents=True, exist_ok=True)
    Path(p).write_text(json.dumps(v, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def note(step, **kw):
    LOG.append({"step": step, **kw})
    print(f"\n### {step}\n{json.dumps(kw, ensure_ascii=False, indent=1)[:1800]}", flush=True)


PY = sys.executable
PROFILE = {"id": SID, "title": "合成基金會115學年度研究生獎學金", "url": MAIN, "body_selector": "article", "required_markers": ["申請資格"],
           "pdf_include": [], "max_pdfs": 0, "review_note": "合成來源，端到端實測用。", "evidence_mode": "short_excerpt",
           "category": "phd_research", "resource_kind": "scholarship", "scope": "nationwide"}

# ===== 第 3 步：沒有指令可把 issue 轉成來源，只能手改；這裡代替維護者手改副本。
cfg = read(REPO / "data/scan-sources.json")
cfg["sources"].append(PROFILE)
cfg["allowed_hosts"] = sorted(set(cfg["allowed_hosts"]) | {HOST})
save(REPO / "data/scan-sources.json", cfg)
sh("3 新來源輸入：scan --check-config", PY, "scripts/scan_sources.py", "--check-config")
only = {**cfg, "sources": [PROFILE]}
save(RUN / "only.json", only)

# ===== 第 6-9 步：scan，等同 workflow 的 scan job，但只掃合成來源（游標輪轉另外測）。
sh("6-8 scan（等同 scan job）", PY, "scripts/scan_sources.py", "--config", RUN / "only.json", "--state", "work/a/state.json", "--output", "work/a/report", tail=500)
rep = REPO / "work/a/report"
sc = read(rep / "structured-candidates.json") if (rep / "structured-candidates.json").exists() else {"candidates": []}
c0 = sc["candidates"][0] if sc["candidates"] else {}
note("8 萃取結果", files=sorted(p.name for p in rep.glob("*")), candidates=len(sc["candidates"]), verification=c0.get("verification", {}).get("status"),
     errors=c0.get("verification", {}).get("errors"), warnings=c0.get("verification", {}).get("warnings"), title=c0.get("title"), benefit=c0.get("benefit"),
     cycle=c0.get("cycle"), eligibility=str(c0.get("eligibility"))[:400], timing=str(c0.get("application") or c0.get("timing"))[:400], missing=c0.get("gaps_and_conflicts", {}).get("missing_fields"))

# ===== 第 9 步：提案，等同 workflow 下一步。
sh("9 propose_radar_update（等同 scan job 下一步）", PY, "scripts/propose_radar_update.py", "--candidates", "work/a/report/structured-candidates.json", "--output", "work/a/proposal", tail=900)
prop = REPO / "work/a/proposal"
note("9 提案產物", exists=prop.exists(), files=sorted(str(p.relative_to(prop)) for p in prop.rglob("*") if p.is_file() and "preview" not in str(p))[:30])

# ===== 第 11 步前：沒有套用指令；手動把 repo/ 蓋回去（PR-DRAFT.md 指示的做法），看 CI 閘門。
before = len(read(REPO / "data/candidates/source-review.json")["candidates"])
if (prop / "repo").exists():
    shutil.copytree(prop / "repo", REPO, dirs_exist_ok=True)
after = len(read(REPO / "data/candidates/source-review.json")["candidates"])
note("10-11 手動套用提案", source_review_before=before, source_review_after=after)
sh("11 CI 閘門 check_data", PY, "scripts/check_data.py")
sh("11 CI 閘門 check_provenance", PY, "scripts/check_provenance.py")
sh("11 CI 閘門 scan --check-config", PY, "scripts/scan_sources.py", "--check-config")
ut = sh("11 CI 閘門 unittest", PY, "-m", "unittest", "discover", "-s", "tests", tail=2600)
sh("11 build_site（未經任何人工審核）", PY, "scripts/build_site.py", RUN / "site1", tail=300)


def site_state(d):
    p = Path(d) / "index.html"
    if not p.exists():
        return {"built": False}
    h = p.read_text(encoding="utf-8")
    feed = (Path(d) / "feed.xml").read_text(encoding="utf-8") if (Path(d) / "feed.xml").exists() else ""
    return {"built": True, "title_in_page": h.count("合成基金會115學年度研究生獎學金"), "host_in_page": h.count(HOST), "title_in_feed": feed.count("合成基金會115學年度研究生獎學金"), "feed_items": feed.count("<item>")}


note("11 上架結果（無人工審核）", **site_state(RUN / "site1"))

# ===== 第 10 步：審核工作台與台帳。
cands = read(REPO / "data/candidates/source-review.json")["candidates"]
mine = [c for c in cands if c["source_metadata"]["source_id"] == SID]
if mine:
    sys.path.insert(0, str(REPO))
    os.environ.update(ENV)
    os.chdir(REPO)
    from scripts.review_candidates import candidate_fingerprint
    c = mine[0]
    sh("10 審核工作台（離線）", PY, "scripts/build_review_workspace.py", "--source-id", SID, "--output", "work/rv1", tail=400)
    for action, name in (("dismissed", "駁回"), ("applied", "核准")):
        dec = {"schema_version": "1.1.0", "reviews": [{"revision_id": c["source_metadata"]["revision_id"], "source_id": SID, "candidate_id": c["candidate_id"],
               "candidate_sha256": candidate_fingerprint(c), "action": action, "reviewer": "synthetic-reviewer", "reviewed_on": "2026-11-07", "reason": "端到端實測"}]}
        save(RUN / f"dec-{action}.json", dec)
        sh(f"10 工作台 {name} --refresh --export-draft", PY, "scripts/build_review_workspace.py", "--source-id", SID, "--decisions", RUN / f"dec-{action}.json",
           "--refresh", "--export-draft", "--output", f"work/rv-{action}", tail=500)
        out = REPO / f"work/rv-{action}"
        note(f"10 {name}產物", files=sorted(p.name for p in out.glob("*")) if out.exists() else None)
    # 駁回寫進台帳後，網站是否下架？
    led = REPO / "data/scan-reviews.json"
    orig = led.read_text(encoding="utf-8")
    save(led, read(RUN / "dec-dismissed.json"))
    sh("10 駁回寫入台帳後 build_site", PY, "scripts/build_site.py", RUN / "site2", tail=200)
    note("10 駁回後網站", **site_state(RUN / "site2"))
    led.write_text(orig, encoding="utf-8")

# ===== 時間軌：temporal_replay，看結果回不回得了網站。
sh("7-8 temporal_replay（model off，等同手動 job）", PY, "scripts/run_temporal_action.py", "--source-ids", SID, "--output", "work/t1", tail=500)
t1 = REPO / "work/t1"
note("8 temporal 產物", files=sorted(str(p.relative_to(t1)) for p in t1.rglob("*") if p.is_file())[:20] if t1.exists() else None)
if (t1 / "rules/temporal-observations.json").exists():
    tobs = read(t1 / "rules/temporal-observations.json")
    recs = tobs.get("records", {})
    note("8 temporal 記錄", record_count=len(recs), sample=json.dumps(next(iter(recs.values()), {}), ensure_ascii=False)[:900])
obs_data = read(REPO / "data/temporal-observations.json")["records"]
note("9 temporal 是否進 data", synthetic_in_data=any(SID in json.dumps(v, ensure_ascii=False) for v in obs_data.values()) if isinstance(obs_data, dict) else None)
sh("9 CI check_data（有候選、無 temporal 記錄）", PY, "scripts/check_data.py", tail=300)

# ===== 第 4-5 步 路徑一：source_chains。
reg = read(REPO / "data/source-chain-sources.json")
entry = {"url": MAIN, "program_key": c0.get("program_key", "synthetic"), "scope": "general", "cycle": "115", "application_year": 2026, "phase": "annual",
         "role": "local_announcement", "evidence_mode": "hash_only", "body_selector": "article", "required_markers": ["申請資格"], "parent_urls": [], "historical_baseline_allowed": False}
save(RUN / "chain.json", {**reg, "allowed_hosts": [HOST], "sources": [entry]})
sh("4 source_chains（等同 source_chains job）", PY, "scripts/source_chains.py", "--config", RUN / "chain.json", "--output", "work/chain/out.json", tail=700)
if (REPO / "work/chain/out.json").exists():
    ch = read(REPO / "work/chain/out.json")
    note("4 資訊鏈產物", documents=[{k: d.get(k) for k in ("url", "status", "role")} for d in ch["documents"]][:6], relations=ch.get("relations", [])[:4],
         links=[l for d in ch["documents"] for l in d.get("links", [])][:4], events=sum(len(d.get("events", [])) for d in ch["documents"]))
    note("5 列舉是否回到來源設定", policy_child_in_scan_sources=POLICY in json.dumps(read(REPO / "data/scan-sources.json"), ensure_ascii=False))

# ===== 第 4-5 步 路徑二：expand_sources（全庫擴展用，無 workflow）。
inv = {"as_of": "2026-11-07", "rows": [{"id": "SYN1", "url": MAIN, "title": "合成來源", "batch": "B1", "category": "foundation", "kind": "公告", "restrictions": [], "access_gate": "fresh_policy_and_profile_check_required"}]}
save(RUN / "inv.json", inv)
sh("4-5 expand_sources --batch B1", PY, "scripts/expand_sources.py", "--inventory", RUN / "inv.json", "--batch", "B1", "--state", "work/x/state.json", "--output", "work/x/report", tail=800)
xr = REPO / "work/x/report"
if (xr / "structured-candidates.json").exists():
    xs = read(xr / "structured-candidates.json")
    res = read(xr / "source-results.json")
    note("5 expand 列舉與萃取", candidates=[{"id": c["candidate_id"], "title": c["title"], "status": c["verification"]["status"]} for c in xs["candidates"]],
         discovered=[r["url"] for r in res["discovered_sources"]], records=[{k: r.get(k) for k in ("url", "status", "disposition")} for r in res["records"]])
    sh("9 expand 結果接提案", PY, "scripts/propose_radar_update.py", "--candidates", "work/x/report/structured-candidates.json", "--config", "work/x/report/source-profiles.json", "--output", "work/x/proposal", "--no-preview", tail=700)

# ===== 來源更新：改截止日再掃一次，舊卡是否被取代。
fixtures(page("合成基金會115學年度研究生獎學金", deadline="115年5月20日"))
sh("更新 第二次 scan（截止日改變）", PY, "scripts/scan_sources.py", "--config", RUN / "only.json", "--state", "work/a/state.json", "--output", "work/a/report2", tail=300)
if (REPO / "work/a/report2/structured-candidates.json").exists():
    s2 = read(REPO / "work/a/report2/structured-candidates.json")
    note("更新 待審佇列", pending=len(s2["candidates"]), revisions=[c["source_metadata"]["revision_id"][:10] for c in s2["candidates"]], statuses=[c["verification"]["status"] for c in s2["candidates"]])
    sh("更新 提案", PY, "scripts/propose_radar_update.py", "--candidates", "work/a/report2/structured-candidates.json", "--output", "work/a/proposal2", "--no-preview", tail=600)
    if (REPO / "work/a/proposal2/summary.json").exists():
        note("更新 提案摘要", **{k: v for k, v in read(REPO / "work/a/proposal2/summary.json").items() if k in ("incoming", "accepted_for_radar_proposal", "withheld_failed_checks", "retained_old_candidates", "proposed_candidates", "replaced_urls")})

save(RUN / "log.json", LOG)
reqs = (FIX / "requests.log").read_text(encoding="utf-8").splitlines() if (FIX / "requests.log").exists() else []
print("\nmock requests:", len(reqs), sorted(set(reqs)))
