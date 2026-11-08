"""CI閘門：候選必須能通過獨立檢核；已知手寫候選列在基準清單，只減不增。

verify_candidate以現有欄位重算，不採信候選自帶的verification。規則偵測的是手寫資料的特徵，
不是出處證明：補齊欄位仍可能騙過，所以AGENTS.md另規定候選只能由萃取流程產生。
"""
import glob
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.verify_candidates import verify_candidate

BASELINE = ROOT / "data/known-hand-authored-candidates.json"
MAX_BASELINE = 33


def problems(candidate):
    """回傳候選的出處問題；空清單代表通過。"""
    found = list(verify_candidate(candidate)["verification"]["errors"])
    meta = candidate["source_metadata"]
    if meta.get("prepared_document_sha256") == meta.get("revision_id"):
        found.append("prepared_document_hash_equals_revision")
    return found


def check(candidates, known):
    """回傳未列入基準的問題候選{id: problems}。"""
    flagged = {}
    for candidate in candidates:
        cid = candidate["candidate_id"]
        if cid not in known:
            found = problems(candidate)
            if found:
                flagged[cid] = found
    return flagged


def all_candidates(root=ROOT):
    rows = []
    for path in sorted(glob.glob(str(Path(root) / "data/candidates/*.json"))):
        rows.extend(json.loads(Path(path).read_text(encoding="utf-8"))["candidates"])
    return rows


def main():
    known = set(json.loads(BASELINE.read_text(encoding="utf-8"))["candidate_ids"])
    if len(known) > MAX_BASELINE:
        raise SystemExit(f"FAIL: baseline may only shrink: {len(known)} > {MAX_BASELINE}")
    flagged = check(all_candidates(), known)
    for cid, found in flagged.items():
        print(f"FAIL: {cid}: {found[:3]}")
    if flagged:
        raise SystemExit("候選未通過獨立檢核；候選只能由萃取流程產生，不可手寫。")
    print(f"PASS: provenance gate; {len(known)} known hand-authored candidates remain")


if __name__ == "__main__":
    main()
