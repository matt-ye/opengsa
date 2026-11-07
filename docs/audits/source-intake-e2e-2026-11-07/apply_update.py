"""套用「來源更新」提案（舊卡被新版取代），看 CI 閘門。只動 run/repo 副本。"""
import json, os, re, shutil, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE / "run/repo"
ENV = {**os.environ, "PYTHONUTF8": "1", "OPENGSA_FIXTURES": str(HERE / "run/fixtures"), "PYTHONDONTWRITEBYTECODE": "1"}
shutil.copytree(REPO / "work/a/proposal2/repo", REPO, dirs_exist_ok=True)
rows = json.loads((REPO / "data/candidates/source-review.json").read_text(encoding="utf-8"))["candidates"]
print("source-review", len(rows), [c["candidate_id"] for c in rows if "synthetic" in c["candidate_id"]])
for name, cmd in (("check_data", ["scripts/check_data.py"]), ("check_provenance", ["scripts/check_provenance.py"]), ("unittest", ["-m", "unittest", "discover", "-s", "tests"]), ("build_site", ["scripts/build_site.py", str(HERE / "run/site-update")])):
    r = subprocess.run([sys.executable, *cmd], cwd=REPO, env=ENV, capture_output=True, text=True, encoding="utf-8", errors="replace")
    out = r.stdout + r.stderr
    print(f"### {name} exit={r.returncode}")
    if name == "unittest":
        print(re.findall(r"^(?:FAIL|ERROR): .*$", out, re.M), out.strip().splitlines()[-1])
    else:
        print(out.strip()[-200:])
feed = (HERE / "run/site-update/feed.xml").read_text(encoding="utf-8")
print("feed items", feed.count("<item>"), "synthetic", feed.count("合成基金會115學年度研究生獎學金"))
