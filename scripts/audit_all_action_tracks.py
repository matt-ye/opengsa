# encoding: utf-8
"""Sequential Action Track Execution and Audit for all 202 Schemes."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.build_site import load_full_library
from scripts.temporal_tracks import classify_source_track, evaluate_incremental_diff, parser_fingerprint
from scripts.time_policy import validate_temporal_snapshot
from scripts.radar_metadata import radar_metadata

bundle, obs = load_full_library(ROOT)
candidates = bundle['candidates']
observations = obs['records']

print(f"============================================================")
print(f"OpenGSA Action Sequence: All {len(candidates)} Candidate Schemes Audit")
print(f"============================================================")

tracks = {'gov': [], 'other': [], 'enterprise': []}
for c in candidates:
    t = classify_source_track(c)
    tracks[t].append(c)

parser_fp = parser_fingerprint(ROOT)
print(f"Parser Fingerprint: {parser_fp[:16]}...")

for tname, tlist in [
    ('gov (公部門與教育法規軌 · 週二/週五)', tracks['gov']),
    ('other (學生福利與AI工具軌 · 週三/週六)', tracks['other']),
    ('enterprise (企業與學會獎助軌 · 週一/週四)', tracks['enterprise']),
]:
    print(f"\n--- [Action Track] {tname}: {len(tlist)} 方案 ---")
    decisions = [evaluate_incremental_diff(c, observations=obs, current_parser_sha256=parser_fp) for c in tlist]
    run_c = sum(1 for d in decisions if d['should_run'])
    skip_c = sum(1 for d in decisions if not d['should_run'])
    print(f"  > Incremental Gate: {skip_c} SKIP_UNCHANGED (0 HTTP / 0 Token), {run_c} NEED_RUN")
    
    # Verify policy completeness
    modes = {}
    for c in tlist:
        cid = c['candidate_id']
        mode = observations[cid]['policy']['submission_mode']
        modes[mode] = modes.get(mode, 0) + 1
    
    print(f"  > Policy Modes: {modes}")
    assert modes.get('undetermined', 0) == 0, f"Undetermined found in {tname}"

print(f"\n--- [Action Track 4] 全庫整併與時程契約驗證 ---")
val_errors = validate_temporal_snapshot(bundle, obs)
print(f"  > Contract Validation Errors: {len(val_errors)}")
assert len(val_errors) == 0, f"Validation errors: {val_errors}"

meta = radar_metadata(bundle, obs)
print(f"  > Radar Metadata Records Built: {len(meta['records'])} / {len(candidates)}")
assert len(meta['records']) == len(candidates)

print(f"\n[SUCCESS] All 3 Tracks + Consolidation PASS 100%! Ready for publication.")
