"""Outer-layer 3-track schedule router and 3-stage incremental diff gate.

Note: the scheduled scan (Mon-Sat 09:17 Taipei) does NOT use tracks; the weekday
mapping below is only used by the manual `temporal_replay` operation (auto track).

Tracks (weekday used only by manual temporal_replay):
- gov (Tue/Fri, 週二/五): 公部門與政府機關獎助
- enterprise (Mon/Thu, 週一/四): 企業、基金會與學會獎助
- other (Wed/Sat, 週三/六): AI工具、研討會、校內院系與其他補助
- all: 全軌道來源

Incremental Diff Gate (3 Stages):
1. Gate 1 (Candidate & Binding State): Run if candidate is new or fingerprint changed.
2. Gate 2 (Content Hash & Mode Completion): Skip if raw_sha256 is unchanged and
   submission_mode is already resolved (0 HTTP / 0 model tokens). Run only on
   NEW, CHANGED, or BACKFILL (undetermined / blocked / pending refinement).
3. Gate 3 (Chunk-level Cache Diff): Within a document, skip chunks whose
   chunk_id +revision already have verified claims in the checkpoint cache.
"""
from datetime import date, datetime
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.evaluate_deadlines import taipei_today
from scripts.review_candidates import candidate_fingerprint

TRACKS = ("gov", "enterprise", "other", "all")

PARSER_FILES = (
    "scripts/temporal_reextract.py",
    "scripts/extract_candidates.py",
    "scripts/semantic_facts.py",
)


def parser_fingerprint(root=ROOT):
    """Line-ending-normalised parser hash so Windows and Actions checkouts agree.

    Used by the undetermined cooldown: a cooled record re-runs as soon as any
    parser file changes, never because of CRLF/LF checkout differences.
    """
    import hashlib
    import json

    parts = [
        hashlib.sha256((Path(root) / name).read_bytes().replace(b"\r\n", b"\n")).hexdigest()
        for name in PARSER_FILES
    ]
    return hashlib.sha256(json.dumps(parts).encode()).hexdigest()

TRACK_METADATA = {
    "gov": {
        "track": "gov",
        "label": "公部門與政府機關獎助",
        "weekdays": (1, 4),  # Tuesday, Friday
        "weekday_names": ("週二", "週五"),
    },
    "enterprise": {
        "track": "enterprise",
        "label": "企業、基金會與學會獎助",
        "weekdays": (0, 3),  # Monday, Thursday
        "weekday_names": ("週一", "週四"),
    },
    "other": {
        "track": "other",
        "label": "AI工具、校內院系與其他補助",
        "weekdays": (2, 5),  # Wednesday, Saturday
        "weekday_names": ("週三", "週六"),
    },
    "all": {
        "track": "all",
        "label": "全軌道來源",
        "weekdays": (0, 1, 2, 3, 4, 5, 6),
        "weekday_names": ("全部",),
    },
}

_AI_AND_TOOL_MARKERS = (
    "ai-tools",
    "copilot",
    "aws",
    "google-student",
    "cloud-credits",
    "perks",
    "perk",
    "jetbrains",
    "github",
    "notion",
    "figma",
    "student-pack",
)

_ENTERPRISE_MARKERS = (
    "基金會",
    "台積電",
    "tsmc",
    "鴻海",
    "foxconn",
    "聯發科",
    "mediatek",
    "行天宮",
    "宗倬章",
    "中技社",
    "ctci",
    "富邦",
    "國泰",
    "學會",
    "faos",
    "協會",
    "企業",
    "nvidia",
    "research.google",
    "慈濟",
    "普仁",
    "家扶",
    "罕見疾病",
    "auo",
    "realtek",
    "innolux",
    "compal",
    "asus",
    "trendmicro",
    "spil",
    "psmc",
    "delta-foundation",
    "chtf",
    "esun",
    "taishin",
    "megabank",
    "scsb",
    "qinlao",
    "taiwanbio",
    "gfc",
    "microsoft research",
    "聯盟",
)

_GOV_MARKERS = (
    ".gov.tw",
    "gov.taipei",
    "sinica.edu.tw",
    "教育部",
    "國科會",
    "國家科學及技術委員會",
    "nstc",
    "moe",
    "中央研究院",
    "中研院",
    "勞動部",
    "市政府",
    "縣政府",
    "青年局",
    "農業部",
    "退輔會",
    "原住民族委員會",
    "原住民族",
    "原民會",
    "原民",
    "國教署",
    "k12ea",
    "移民署",
    "衛生福利部",
    "學產基金",
    "學產",
)

RESOLVED_SUBMISSION_MODES = frozenset({
    "fixed_window",
    "deadline_only",
    "start_only",
    "event_relative",
    "recurring",
    "conditional_deadline",
    "automatic",
    "reference",
    "continuous",
    "unit_announced",
    "review_only",
})

REFINEMENT_SUBMISSION_MODES = frozenset({
    "procedure_only",
    "rule_text",
    "mixed",
})


def classify_source_track(item, profile=None):
    """Deterministically assign a candidate or source profile to 'gov', 'enterprise', or 'other'."""
    if profile and profile.get("schedule_track") in ("gov", "enterprise", "other"):
        return profile["schedule_track"]
    if item.get("schedule_track") in ("gov", "enterprise", "other"):
        return item["schedule_track"]

    meta = item.get("source_metadata") or {}
    sid = (meta.get("source_id") or item.get("id") or "").lower()
    url = (meta.get("url") or item.get("url") or "").lower()
    title = (item.get("title") or (profile or {}).get("title") or "").lower()
    rk = item.get("resource_kind") or (profile or {}).get("resource_kind") or ""

    if rk == "tool_subscription" or any(m in sid for m in _AI_AND_TOOL_MARKERS):
        return "other"

    haystack = f"{sid} {url} {title}"
    if sid.startswith("ent-") or any(m in haystack for m in _ENTERPRISE_MARKERS):
        return "enterprise"

    if any(m in haystack for m in _GOV_MARKERS):
        return "gov"

    return "other"


def track_for_weekday(value=None):
    """Map weekday (0=Mon..6=Sun) or ISO date string to its scheduled track."""
    if value is None:
        value = taipei_today()
    if isinstance(value, int):
        if not 0 <= value <= 6:
            raise ValueError("invalid_weekday")
        wd = value
    elif isinstance(value, datetime):
        wd = value.date().weekday()
    elif isinstance(value, date):
        wd = value.weekday()
    elif isinstance(value, str):
        wd = date.fromisoformat(value[:10]).weekday()
    else:
        raise ValueError("invalid_weekday_input")

    for name in ("enterprise", "gov", "other"):
        if wd in TRACK_METADATA[name]["weekdays"]:
            return name
    return "all"


def evaluate_incremental_diff(
    candidate,
    observations=None,
    observed_raw_sha256=None,
    observed_attachment_hashes=None,
    include_refinement=False,
    force_recheck=False,
    current_parser_sha256=None,
):
    """3-Stage Incremental Diff Gate for a single candidate.

    Returns a dict:
    {
        'candidate_id': str,
        'source_id': str,
        'url': str,
        'track': str,
        'should_run': bool,
        'decision': 'RUN_NEW' | 'RUN_CHANGED' | 'RUN_BACKFILL' | 'RUN_FORCED' | 'SKIP_UNCHANGED',
        'reason': str,
    }
    """
    cid = candidate["candidate_id"]
    meta = candidate["source_metadata"]
    sid = meta["source_id"]
    url = meta["url"]
    track = classify_source_track(candidate)
    base = {
        "candidate_id": cid,
        "source_id": sid,
        "url": url,
        "track": track,
    }

    if force_recheck:
        return {**base, "should_run": True, "decision": "RUN_FORCED", "reason": "explicit_force_recheck"}

    records = (observations or {}).get("records") or {}
    record = records.get(cid)
    current_fp = candidate_fingerprint(candidate)

    # Gate 1: Candidate existence and binding integrity
    if not record:
        return {**base, "should_run": True, "decision": "RUN_NEW", "reason": "no_prior_observation"}
    if record.get("candidate_sha256") != current_fp or record.get("url") != url:
        return {**base, "should_run": True, "decision": "RUN_NEW", "reason": "candidate_fingerprint_or_url_changed"}

    # Gate 2a: Remote content or attachment hash change
    if observed_raw_sha256 and record.get("raw_sha256") and observed_raw_sha256 != record.get("raw_sha256"):
        return {**base, "should_run": True, "decision": "RUN_CHANGED", "reason": "source_content_hash_changed"}

    if observed_attachment_hashes is not None:
        recorded_docs = {d.get("url"): d.get("raw_sha256") for d in record.get("documents", []) if d.get("url")}
        if dict(observed_attachment_hashes) != recorded_docs:
            return {**base, "should_run": True, "decision": "RUN_CHANGED", "reason": "attachment_hash_changed"}

    # Gate 2b: Completion & Backfill status check
    if record.get("status") != "replayed":
        return {
            **base,
            "should_run": True,
            "decision": "RUN_BACKFILL",
            "reason": f"prior_status_{record.get('status', 'unknown')}",
        }

    policy = record.get("policy") or {}
    mode = policy.get("submission_mode", "undetermined")
    if mode == "undetermined":
        subkind = record.get("undetermined_subkind")
        if (
            subkind in ("regulation_without_schedule", "no_schedule_in_document")
            and current_parser_sha256
            and record.get("parser_sha256") == current_parser_sha256
        ):
            return {
                **base,
                "should_run": False,
                "decision": "SKIP_UNCHANGED",
                "reason": f"cooldown_{subkind}",
            }
        return {
            **base,
            "should_run": True,
            "decision": "RUN_BACKFILL",
            "reason": f"submission_mode_undetermined_{subkind}" if subkind else "submission_mode_undetermined",
        }

    if include_refinement and mode in REFINEMENT_SUBMISSION_MODES:
        if not record.get("model_refined"):
            return {
                **base,
                "should_run": True,
                "decision": "RUN_BACKFILL",
                "reason": f"refinement_needed_{mode}",
            }

    return {
        **base,
        "should_run": False,
        "decision": "SKIP_UNCHANGED",
        "reason": f"already_resolved_{mode}",
    }


def diff_document_chunks(chunks, cached_chunks_by_id=None, source_revision=None):
    """Gate 3: Chunk-level incremental diff.

    Splits prepared chunks into (`pending_chunks`, `reused_chunks`) so unchanged
    chunks within a partially updated or resumed multi-page source consume 0 tokens.
    """
    cache = cached_chunks_by_id or {}
    pending = []
    reused = []
    for chunk in chunks:
        cid = chunk["chunk_id"]
        entry = cache.get(cid)
        if entry and entry.get("complete") is True:
            if source_revision is None or entry.get("source_revision") == source_revision:
                reused.append({"chunk": chunk, "cached": entry})
                continue
        pending.append(chunk)
    return pending, reused


def plan_track_execution(
    candidates,
    observations=None,
    track="auto",
    include_refinement=False,
    observed_hashes=None,
    force_recheck=False,
    max_sources=None,
    as_of=None,
):
    """Outer-layer planner combining 3-track schedule routing and 3-stage incremental diff."""
    resolved_track = track_for_weekday(as_of) if track == "auto" else track
    if resolved_track not in TRACKS:
        raise ValueError(f"invalid_schedule_track:{resolved_track}")

    observed_hashes = observed_hashes or {}
    current_parser = parser_fingerprint()
    track_candidates = [
        c for c in candidates
        if resolved_track == "all" or classify_source_track(c) == resolved_track
    ]

    decisions = []
    run_candidates = []
    skip_candidates = []
    selected_source_ids = []
    seen_sids = set()

    for c in track_candidates:
        url = c["source_metadata"]["url"]
        sid = c["source_metadata"]["source_id"]
        decision = evaluate_incremental_diff(
            c,
            observations=observations,
            observed_raw_sha256=observed_hashes.get(url),
            include_refinement=include_refinement,
            force_recheck=force_recheck,
            current_parser_sha256=current_parser,
        )
        decisions.append(decision)
        if decision["should_run"]:
            run_candidates.append(c)
            if sid not in seen_sids:
                if max_sources is None or len(selected_source_ids) < max_sources:
                    selected_source_ids.append(sid)
                    seen_sids.add(sid)
        else:
            skip_candidates.append(c)

    meta = TRACK_METADATA[resolved_track]
    return {
        "track": resolved_track,
        "track_label": meta["label"],
        "weekday_names": list(meta["weekday_names"]),
        "total_in_track": len(track_candidates),
        "run_candidate_count": len(run_candidates),
        "skip_candidate_count": len(skip_candidates),
        "selected_source_ids": selected_source_ids,
        "decisions": decisions,
    }
