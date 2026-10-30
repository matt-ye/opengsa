"""申請時間視窗、研討會事件相對期限與合成資格比對判斷。

原則：
1. 分開處理學生、系所、學院、學校／單位與機關期限；僅以學生適用窗口判定受理狀態。
2. 狀態包含：open、not_yet_open、closed、unknown。
3. 時區固定 Asia/Taipei (+08:00)；日期僅有年月日 (date) 時，絕不自造 23:59 午夜截止。
4. 不把機關彙送日或學院推薦日當成學生截止日；不把法規修正日當生效日；不從歷年日期推算下一期。
5. 研討會分流：國科會／臺大（前月首日彙送、前一日17:00、四週前補送接受函、例假日待核）、
   醫學院國際事務（會前四週送件、無補送條款）、FAOS（會前兩個曆月學校提出、學生校內期限未知）。
6. 個人準備建議不是官方申請起日；論文接受通知不是補助結果日。
"""
import argparse
import calendar
from datetime import date, datetime, time, timedelta, timezone
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
TAIPEI_TZ = timezone(timedelta(hours=8), name="Asia/Taipei")

UPPER_LAYER_ACTORS = ("department", "college", "unit", "university", "institution")
STUDENT_ACTORS = ("student", "student_or_representative")


def parse_iso_date(value):
    """嚴格解析 YYYY-MM-DD，拒絕無效曆日（如 2026-02-30 或非閏年 02-29）或含時分字串。"""
    if not isinstance(value, str) or not re.match(r"^\d{4}-\d{2}-\d{2}$", value):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def parse_taipei_datetime(value):
    """嚴格解析帶 +08:00 時區的 ISO 8601 datetime。"""
    if not isinstance(value, str) or not value.endswith("+08:00") or "T" not in value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.utcoffset() != timedelta(hours=8):
        return None
    return parsed.astimezone(TAIPEI_TZ)


def parse_clock(now_taipei):
    """支援 'YYYY-MM-DD'、'YYYY-MM-DDTHH:MM:SS+08:00'、date 或 datetime。
    回傳 (date_obj, datetime_obj_or_None)。當輸入只有日期時，不捏造當日時間。
    """
    if isinstance(now_taipei, datetime):
        if now_taipei.tzinfo is None:
            dt = now_taipei.replace(tzinfo=TAIPEI_TZ)
        else:
            dt = now_taipei.astimezone(TAIPEI_TZ)
        return dt.date(), dt
    if isinstance(now_taipei, date):
        return now_taipei, None
    if isinstance(now_taipei, str):
        d = parse_iso_date(now_taipei)
        if d is not None:
            return d, None
        dt = parse_taipei_datetime(now_taipei)
        if dt is not None:
            return dt.date(), dt
    raise ValueError(f"Invalid Asia/Taipei date or datetime: {now_taipei!r}")


def taipei_today(now=None):
    if now is None:
        now = datetime.now(TAIPEI_TZ)
    elif isinstance(now, datetime):
        now = now.astimezone(TAIPEI_TZ) if now.tzinfo else now.replace(tzinfo=TAIPEI_TZ)
    else:
        raise ValueError("now must be a datetime or None")
    return now.date().isoformat()


def add_days(iso_date_str, amount):
    d = parse_iso_date(iso_date_str)
    if d is None or not isinstance(amount, int) or isinstance(amount, bool):
        return None
    return (d + timedelta(days=amount)).isoformat()


def months_before(iso_date_str, months):
    """以曆月往前推算，遇月底（如31日或閏2月29日）對齊目標月份末日；絕不換算為減 30*N 天。"""
    d = parse_iso_date(iso_date_str)
    if d is None or not isinstance(months, int) or isinstance(months, bool) or months < 1:
        return None
    total_months = (d.year * 12 + (d.month - 1)) - months
    target_year = total_months // 12
    target_month = (total_months % 12) + 1
    last_day = calendar.monthrange(target_year, target_month)[1]
    target_day = min(d.day, last_day)
    return date(target_year, target_month, target_day).isoformat()


def previous_month_first_day(iso_date_str):
    """會議首日所屬月份之前一個月首日（支援跨年，如 2027-01-15 -> 2026-12-01）。"""
    d = parse_iso_date(iso_date_str)
    if d is None:
        return None
    first_of_current = date(d.year, d.month, 1)
    prev_last = first_of_current - timedelta(days=1)
    return date(prev_last.year, prev_last.month, 1).isoformat()


def adjust_to_next_working_day(iso_date_str, holiday_calendar=None):
    """若提供官方假日表（含週末與國定假日集合），順延至次一上班日；未提供時不妄自猜測補假或調整放假。"""
    d = parse_iso_date(iso_date_str)
    if d is None:
        return None, "unverified"
    if holiday_calendar is None:
        return d.isoformat(), "unverified"
    holidays = {str(h) for h in holiday_calendar.get("holidays", [])}
    workdays_override = {str(w) for w in holiday_calendar.get("make_up_workdays", [])}
    current = d
    for _ in range(30):
        iso = current.isoformat()
        is_weekend = current.weekday() >= 5
        if iso in workdays_override:
            return iso, "verified"
        if not is_weekend and iso not in holidays:
            return iso, "verified"
        current += timedelta(days=1)
    return current.isoformat(), "unverified"


def evaluate_conference_schedule(
    program_id,
    conference_start,
    now_taipei=None,
    acceptance_notice_date=None,
    prepare_days=14,
    manual_deadline=None,
    holiday_calendar=None,
):
    """依研討會方案分流計算各層基準與受理狀態，不混用國科會、醫學院與 FAOS 規則。"""
    start_d = parse_iso_date(conference_start) if conference_start is not None else None
    if conference_start is not None and start_d is None:
        return None
    if acceptance_notice_date is not None and parse_iso_date(acceptance_notice_date) is None:
        return None
    if not isinstance(prepare_days, int) or isinstance(prepare_days, bool) or not (0 <= prepare_days <= 90):
        return None
    if manual_deadline is not None and parse_iso_date(manual_deadline) is None:
        return None

    now_d, now_dt = parse_clock(now_taipei) if now_taipei is not None else (None, None)

    if start_d is None:
        return {
            "program_id": program_id,
            "conference_start": None,
            "state": "unknown",
            "reason_code": "missing_conference_start",
            "reason": "未提供會議舉行首日，無法計算事件相對期限。",
            "agency_submit_base": None,
            "agency_submit": None,
            "student_submit": None,
            "student_submit_kind": "unknown",
            "acceptance_supplement": None,
            "personal_prepare_start": None,
            "is_personal_prepare_official_start": False,
            "is_acceptance_notice_official_result": False,
            "calendar_status": "unverified",
            "deadline_status": "unknown",
            "notice_risk": "unknown",
        }

    if program_id in ("nstc-ntu", "nstc_ntu"):
        agency_base = previous_month_first_day(conference_start)
        agency_submit, cal_status = adjust_to_next_working_day(agency_base, holiday_calendar)
        student_date = add_days(agency_submit, -1)
        student_dt_str = f"{student_date}T17:00:00+08:00"
        supplement_date = add_days(conference_start, -28)
        prepare_date = add_days(student_date, -prepare_days)

        if acceptance_notice_date is None:
            notice_risk = "unknown"
        elif acceptance_notice_date > supplement_date:
            notice_risk = "after_supplement"
        elif acceptance_notice_date > student_date:
            notice_risk = "after_submission"
        else:
            notice_risk = "before_submission"

        state = "unknown"
        reason_code = "missing_application_start_and_calendar_unverified"
        if now_d is not None:
            student_dt = parse_taipei_datetime(student_dt_str)
            if now_dt is not None and now_dt > student_dt:
                state = "closed" if cal_status == "verified" else "unknown"
                reason_code = "closed_after_student_deadline" if cal_status == "verified" else "past_unverified_student_base"
            elif now_d > parse_iso_date(student_date):
                state = "closed" if cal_status == "verified" else "unknown"
                reason_code = "closed_after_student_deadline" if cal_status == "verified" else "past_unverified_student_base"
            else:
                state = "unknown"
                reason_code = "estimate_pending_calendar_and_department_check"

        return {
            "program_id": "nstc-ntu",
            "conference_start": conference_start,
            "state": state,
            "reason_code": reason_code,
            "reason": "國科會／臺大路徑：機構前月首日彙送、臺大學生前一日17:00送出；接受函最遲會前四週補送。",
            "agency_submit_base": agency_base,
            "agency_submit": agency_submit,
            "student_submit": student_dt_str,
            "student_submit_date": student_date,
            "student_submit_time": "17:00",
            "student_submit_kind": "datetime",
            "acceptance_supplement": supplement_date,
            "personal_prepare_start": prepare_date,
            "is_personal_prepare_official_start": False,
            "is_acceptance_notice_official_result": False,
            "calendar_status": cal_status,
            "deadline_status": "calendar_adjusted" if cal_status == "verified" else "estimate_pending_calendar",
            "notice_risk": notice_risk,
        }

    if program_id in ("ntu-med-oia", "ntu_med_oia"):
        student_date = add_days(conference_start, -28)
        prepare_date = add_days(student_date, -prepare_days)
        if acceptance_notice_date is None:
            notice_risk = "unknown"
        elif acceptance_notice_date > student_date:
            notice_risk = "after_deadline"
        else:
            notice_risk = "before_submission"

        state = "unknown"
        reason_code = "missing_application_start"
        if now_d is not None:
            if now_d > parse_iso_date(student_date):
                state = "closed"
                reason_code = "closed_after_student_deadline"
            else:
                state = "unknown"
                reason_code = "student_target_known_official_start_unconfirmed"

        return {
            "program_id": "ntu-med-oia",
            "conference_start": conference_start,
            "state": state,
            "reason_code": reason_code,
            "reason": "臺大醫學院國際事務中心：會議前四週送達；無國科會接受函補送條款，不可套用國科會補送規則。",
            "agency_submit_base": None,
            "agency_submit": None,
            "student_submit": student_date,
            "student_submit_date": student_date,
            "student_submit_time": None,
            "student_submit_kind": "date",
            "acceptance_supplement": None,
            "personal_prepare_start": prepare_date,
            "is_personal_prepare_official_start": False,
            "is_acceptance_notice_official_result": False,
            "calendar_status": "unverified",
            "deadline_status": "estimate_pending_calendar",
            "notice_risk": notice_risk,
        }

    if program_id in ("faos-student", "faos_student", "faos-student-conference"):
        agency_submit = months_before(conference_start, 2)
        prepare_date = add_days(agency_submit, -prepare_days)
        if acceptance_notice_date is None:
            notice_risk = "unknown"
        elif acceptance_notice_date > agency_submit:
            notice_risk = "after_deadline"
        else:
            notice_risk = "before_submission"

        state = "unknown"
        reason_code = "institution_deadline_known_student_internal_deadline_unknown"
        if now_d is not None and now_d > parse_iso_date(agency_submit):
            state = "closed"
            reason_code = "closed_after_institution_deadline"

        return {
            "program_id": "faos-student",
            "conference_start": conference_start,
            "state": state,
            "reason_code": reason_code,
            "reason": "FAOS 由學校負責人於會前兩個曆月提出（非60天）；學生校內截止日未知，不可把機構期限當學生截止日。",
            "agency_submit_base": agency_submit,
            "agency_submit": agency_submit,
            "student_submit": None,
            "student_submit_date": None,
            "student_submit_time": None,
            "student_submit_kind": "unknown",
            "acceptance_supplement": None,
            "personal_prepare_start": prepare_date,
            "is_personal_prepare_official_start": False,
            "is_acceptance_notice_official_result": False,
            "calendar_status": "unverified",
            "deadline_status": "student_deadline_unknown",
            "notice_risk": notice_risk,
        }

    if program_id in ("custom-unit", "manual"):
        prepare_date = add_days(manual_deadline, -prepare_days) if manual_deadline else None
        if acceptance_notice_date is None or manual_deadline is None:
            notice_risk = "unknown"
        elif acceptance_notice_date > manual_deadline:
            notice_risk = "after_deadline"
        else:
            notice_risk = "before_submission"

        return {
            "program_id": "custom-unit",
            "conference_start": conference_start,
            "state": "unknown",
            "reason_code": "manual_unverified_deadline",
            "reason": "自填院系所方案未經官方來源核對，保持受理待確認。",
            "agency_submit_base": None,
            "agency_submit": None,
            "student_submit": manual_deadline,
            "student_submit_date": manual_deadline,
            "student_submit_time": None,
            "student_submit_kind": "date" if manual_deadline else "unknown",
            "acceptance_supplement": None,
            "personal_prepare_start": prepare_date,
            "is_personal_prepare_official_start": False,
            "is_acceptance_notice_official_result": False,
            "calendar_status": "unverified",
            "deadline_status": "manual_estimate" if manual_deadline else "student_deadline_unknown",
            "notice_risk": notice_risk,
        }

    return None


def _extract_start_deadline(item):
    """從 candidate.schedule.application_start 或 pilot step action 擷取結構化申請起日；未知時回傳 unknown。"""
    if "schedule" in item and isinstance(item["schedule"].get("application_start"), dict):
        return item["schedule"]["application_start"]
    if isinstance(item.get("start"), dict):
        return item["start"]
    steps = item.get("steps", [])
    for step in steps:
        if step.get("actor") in STUDENT_ACTORS:
            match = re.search(r"開始日(\d{4}-\d{2}-\d{2})", step.get("action", ""))
            if match and parse_iso_date(match.group(1)):
                return {
                    "kind": "date",
                    "value": match.group(1),
                    "timezone": "Asia/Taipei",
                    "note": "由學生程序說明提取之開始日",
                }
    return {"kind": "unknown", "value": None, "timezone": "Asia/Taipei", "note": "未記錄明確申請起日"}


def _extract_steps(item):
    if "schedule" in item and "steps" in item["schedule"]:
        return item["schedule"]["steps"]
    return item.get("steps", [])


def evaluate_application_window(
    item,
    now_taipei,
    event_context=None,
    holiday_calendar=None,
    sources_by_id=None,
    freshness_days=180,
):
    """判斷單筆獎助機會或候選在指定 Asia/Taipei 時間點的學生受理狀態。"""
    now_d, now_dt = parse_clock(now_taipei)
    steps = _extract_steps(item)
    start_dl = _extract_start_deadline(item)
    if start_dl.get("certainty") in ("inferred", "tentative", "unknown"):
        start_dl = {**start_dl, "kind":"unknown", "value":None, "note":"推定或暫定起日不可升級為已確認受理狀態"}

    student_steps = [s for s in steps if s.get("actor") in STUDENT_ACTORS]
    upper_steps = [s for s in steps if s.get("actor") in UPPER_LAYER_ACTORS]
    supplement_steps = [s for s in steps if s.get("actor") == "supplement"]

    # 檢查來源是否過期
    source_stale = False
    stale_sources = []
    if sources_by_id:
        ref_ids = set()
        for s in steps:
            for ref in s.get("refs", []):
                if ref.get("source"):
                    ref_ids.add(ref["source"])
        for sid in ref_ids:
            src = sources_by_id.get(sid)
            if src and src.get("checked_on"):
                checked_d = parse_iso_date(src["checked_on"])
                if checked_d and (now_d - checked_d).days > freshness_days:
                    source_stale = True
                    stale_sources.append(sid)

    upper_layer_deadlines = [
        {
            "actor": s["actor"],
            "action": s["action"],
            "kind": s["deadline"]["kind"],
            "value": s["deadline"]["value"],
            "note": s["deadline"]["note"],
        }
        for s in upper_steps
    ]

    if all(item.get("field_applicability",{}).get(k,{}).get("status")=="not_applicable" for k in ("application_start","student_deadline")):
        return {"state":"unknown","as_of":now_d.isoformat(),"reason_code":"application_not_applicable",
                "reason":"申請窗口 N/A 不適用：來源明示免另行申請；不代表資格已核准。",
                "student_deadline":None,"application_start":None,"upper_layer_deadlines":upper_layer_deadlines,
                "supplement_deadlines":supplement_steps,"same_day_time_unconfirmed":False,
                "source_stale":source_stale,"stale_sources":stale_sources,"next_cycle_inferred":False}

    # 1. 純單位／機構申請之聘任入口（如 TA 制度），學生不在該入口直接申請一筆獎學金
    if item.get("resource_kind") == "employment_support" and item.get("participants", {}).get("applicant") in ("unit", "institution"):
        return {
            "state": "unknown",
            "as_of": now_d.isoformat(),
            "reason_code": "unit_application_entry_not_direct_student_window",
            "reason": "此為單位申請／聘任制度入口，學生需查個別課程或單位招募時間，非單一獎學金收件窗口。",
            "student_deadline": None,
            "application_start": start_dl.get("value"),
            "upper_layer_deadlines": upper_layer_deadlines,
            "supplement_deadlines": supplement_steps,
            "same_day_time_unconfirmed": False,
            "source_stale": source_stale,
            "stale_sources": stale_sources,
            "next_cycle_inferred": False,
        }

    # 2. 事件相對期限（如國際研討會）
    cycle_kind = item.get("cycle", {}).get("kind")
    relative_rule = item.get("schedule", {}).get("relative_rule", {})
    if cycle_kind == "event_relative" or (relative_rule and relative_rule.get("rule_type") not in (None, "none")):
        conf_start = (event_context or {}).get("conference_start")
        rule_id = (
            relative_rule.get("rule_type")
            if relative_rule and relative_rule.get("rule_type") not in (None, "none")
            else ("faos-student" if "faos" in item.get("program_key", "") else "nstc-ntu")
        )
        conf_eval = evaluate_conference_schedule(
            rule_id,
            conf_start,
            now_taipei=now_taipei,
            acceptance_notice_date=(event_context or {}).get("acceptance_notice_date"),
            prepare_days=(event_context or {}).get("prepare_days", 14),
            holiday_calendar=holiday_calendar,
        )
        return {
            "state": conf_eval["state"],
            "as_of": now_d.isoformat(),
            "reason_code": conf_eval["reason_code"],
            "reason": conf_eval["reason"],
            "student_deadline": conf_eval["student_submit"],
            "application_start": None,
            "upper_layer_deadlines": upper_layer_deadlines,
            "supplement_deadlines": supplement_steps,
            "conference_evaluation": conf_eval,
            "same_day_time_unconfirmed": False,
            "source_stale": source_stale,
            "stale_sources": stale_sources,
            "next_cycle_inferred": False,
        }

    # 3. 檢查學生步驟是否有明確固定日期或日時
    if item.get("resource_kind")=="tool_subscription":
        caps=[parse_iso_date(s.get("deadline",{}).get("value")) for s in student_steps]
        caps=[d for d in caps if d is not None]
        if not caps or now_d<=min(caps):
            return {"state":"unknown","as_of":now_d.isoformat(),"reason_code":"purchase_relative_deadline_requires_context",
                    "reason":"年度期限是最晚上限；購買／達成條件後的相對期限及經費餘額仍須確認，不推定目前受理。",
                    "student_deadline":min(caps).isoformat() if caps else None,"application_start":start_dl.get("value"),
                    "upper_layer_deadlines":upper_layer_deadlines,"supplement_deadlines":supplement_steps,
                    "same_day_time_unconfirmed":bool(caps and now_d==min(caps)),"source_stale":source_stale,
                    "stale_sources":stale_sources,"next_cycle_inferred":False}

    known_student = [
        s for s in student_steps if s.get("deadline", {}).get("kind") in ("date", "datetime") and s["deadline"].get("value")
    ]

    if known_student:
        step = known_student[0]
        dl = step["deadline"]
        dl_kind = dl["kind"]
        dl_val = dl["value"]

        # 檢查起日（若有明確申請起日且現在早於起日 -> not_yet_open）
        start_kind = start_dl.get("kind")
        start_val = start_dl.get("value")
        if start_kind == "date" and start_val:
            s_d = parse_iso_date(start_val)
            if s_d and now_d < s_d:
                return {
                    "state": "not_yet_open",
                    "as_of": now_d.isoformat(),
                    "reason_code": "not_yet_open_before_start",
                    "reason": f"尚未開放：學生申請開始日為 {start_val}。",
                    "student_deadline": dl_val,
                    "application_start": start_val,
                    "upper_layer_deadlines": upper_layer_deadlines,
                    "supplement_deadlines": supplement_steps,
                    "same_day_time_unconfirmed": False,
                    "source_stale": source_stale,
                    "stale_sources": stale_sources,
                    "next_cycle_inferred": False,
                }
        elif start_kind == "datetime" and start_val:
            s_dt = parse_taipei_datetime(start_val)
            if s_dt:
                if now_dt is not None and now_dt < s_dt:
                    return {
                        "state": "not_yet_open",
                        "as_of": now_d.isoformat(),
                        "reason_code": "not_yet_open_before_start",
                        "reason": f"尚未開放：學生申請開始時間為 {start_val}。",
                        "student_deadline": dl_val,
                        "application_start": start_val,
                        "upper_layer_deadlines": upper_layer_deadlines,
                        "supplement_deadlines": supplement_steps,
                        "same_day_time_unconfirmed": False,
                        "source_stale": source_stale,
                        "stale_sources": stale_sources,
                        "next_cycle_inferred": False,
                    }
                if now_dt is None and now_d < s_dt.date():
                    return {
                        "state": "not_yet_open",
                        "as_of": now_d.isoformat(),
                        "reason_code": "not_yet_open_before_start",
                        "reason": f"尚未開放：學生申請開始時間為 {start_val}。",
                        "student_deadline": dl_val,
                        "application_start": start_val,
                        "upper_layer_deadlines": upper_layer_deadlines,
                        "supplement_deadlines": supplement_steps,
                        "same_day_time_unconfirmed": False,
                        "source_stale": source_stale,
                        "stale_sources": stale_sources,
                        "next_cycle_inferred": False,
                    }

        if dl_kind == "date":
            end_d = parse_iso_date(dl_val)
            if now_d > end_d:
                return {
                    "state": "closed",
                    "as_of": now_d.isoformat(),
                    "reason_code": "closed_after_student_deadline",
                    "reason": f"本期學生申請已於 {dl_val} 截止；不從本期日期自動推算下一期。",
                    "student_deadline": dl_val,
                    "application_start": start_val,
                    "upper_layer_deadlines": upper_layer_deadlines,
                    "supplement_deadlines": supplement_steps,
                    "same_day_time_unconfirmed": False,
                    "source_stale": source_stale,
                    "stale_sources": stale_sources,
                    "next_cycle_inferred": False,
                }
            if now_d == end_d:
                # 只有年月日，不可自造 23:59 午夜截止！
                return {
                    "state": "unknown" if now_dt is not None else ("open" if start_val else "unknown"),
                    "as_of": now_d.isoformat(),
                    "reason_code": "due_today_time_unconfirmed",
                    "reason": f"當日（{dl_val}）截止，來源僅載日期未載確切時分，不可推定開放至23:59午夜。",
                    "student_deadline": dl_val,
                    "application_start": start_val,
                    "upper_layer_deadlines": upper_layer_deadlines,
                    "supplement_deadlines": supplement_steps,
                    "same_day_time_unconfirmed": True,
                    "source_stale": source_stale,
                    "stale_sources": stale_sources,
                    "next_cycle_inferred": False,
                }
            # now_d < end_d
            if source_stale:
                return {
                    "state": "unknown",
                    "as_of": now_d.isoformat(),
                    "reason_code": "source_observation_stale",
                    "reason": "來源查核日期已過期，需重新核對當期公告。",
                    "student_deadline": dl_val,
                    "application_start": start_val,
                    "upper_layer_deadlines": upper_layer_deadlines,
                    "supplement_deadlines": supplement_steps,
                    "same_day_time_unconfirmed": False,
                    "source_stale": True,
                    "stale_sources": stale_sources,
                    "next_cycle_inferred": False,
                }
            if not start_val:
                # 缺起日：除非原紀錄已明示當日觀察為 open 且同日快照，否則不單憑未來截止日宣稱已開放
                recorded_app = item.get("application", {})
                if recorded_app.get("state") == "open" and recorded_app.get("as_of") == now_d.isoformat() and recorded_app.get("refs"):
                    return {
                        "state": "open",
                        "as_of": now_d.isoformat(),
                        "reason_code": "open_by_observed_announcement_start_unconfirmed",
                        "reason": recorded_app.get("reason", "依公告觀察顯示受理中；起日與完整附件仍待核。"),
                        "student_deadline": dl_val,
                        "application_start": None,
                        "upper_layer_deadlines": upper_layer_deadlines,
                        "supplement_deadlines": supplement_steps,
                        "same_day_time_unconfirmed": False,
                        "source_stale": source_stale,
                        "stale_sources": stale_sources,
                        "next_cycle_inferred": False,
                    }
                return {
                    "state": "unknown",
                    "as_of": now_d.isoformat(),
                    "reason_code": "missing_application_start",
                    "reason": f"已知學生截止日 {dl_val}，但缺少官方申請開始日，不從公告發布日臆測已開始受理。",
                    "student_deadline": dl_val,
                    "application_start": None,
                    "upper_layer_deadlines": upper_layer_deadlines,
                    "supplement_deadlines": supplement_steps,
                    "same_day_time_unconfirmed": False,
                    "source_stale": source_stale,
                    "stale_sources": stale_sources,
                    "next_cycle_inferred": False,
                }
            return {
                "state": "open",
                "as_of": now_d.isoformat(),
                "reason_code": "open_within_student_window",
                "reason": f"位於學生申請期間（{start_val} 至 {dl_val}）。",
                "student_deadline": dl_val,
                "application_start": start_val,
                "upper_layer_deadlines": upper_layer_deadlines,
                "supplement_deadlines": supplement_steps,
                "same_day_time_unconfirmed": False,
                "source_stale": source_stale,
                "stale_sources": stale_sources,
                "next_cycle_inferred": False,
            }

        if dl_kind == "datetime":
            end_dt = parse_taipei_datetime(dl_val)
            if now_dt is not None:
                is_after = now_dt > end_dt
            else:
                is_after = now_d > end_dt.date()
            if is_after:
                return {
                    "state": "closed",
                    "as_of": now_d.isoformat(),
                    "reason_code": "closed_after_student_deadline",
                    "reason": f"本期學生申請已於 {dl_val} 截止；不自動推算下一期。",
                    "student_deadline": dl_val,
                    "application_start": start_val,
                    "upper_layer_deadlines": upper_layer_deadlines,
                    "supplement_deadlines": supplement_steps,
                    "same_day_time_unconfirmed": False,
                    "source_stale": source_stale,
                    "stale_sources": stale_sources,
                    "next_cycle_inferred": False,
                }
            if source_stale:
                return {
                    "state": "unknown",
                    "as_of": now_d.isoformat(),
                    "reason_code": "source_observation_stale",
                    "reason": "來源查核日期已過期，需重新核對當期公告。",
                    "student_deadline": dl_val,
                    "application_start": start_val,
                    "upper_layer_deadlines": upper_layer_deadlines,
                    "supplement_deadlines": supplement_steps,
                    "same_day_time_unconfirmed": False,
                    "source_stale": True,
                    "stale_sources": stale_sources,
                    "next_cycle_inferred": False,
                }
            if not start_val:
                recorded_app = item.get("application", {})
                if recorded_app.get("state") == "open" and recorded_app.get("as_of") == now_d.isoformat() and recorded_app.get("refs"):
                    return {
                        "state": "open",
                        "as_of": now_d.isoformat(),
                        "reason_code": "open_by_observed_announcement_start_unconfirmed",
                        "reason": recorded_app.get("reason", "依公告摘要觀察顯示受理中；需與資料完整度一併呈現。"),
                        "student_deadline": dl_val,
                        "application_start": None,
                        "upper_layer_deadlines": upper_layer_deadlines,
                        "supplement_deadlines": supplement_steps,
                        "same_day_time_unconfirmed": False,
                        "source_stale": source_stale,
                        "stale_sources": stale_sources,
                        "next_cycle_inferred": False,
                    }
                return {
                    "state": "unknown",
                    "as_of": now_d.isoformat(),
                    "reason_code": "missing_application_start",
                    "reason": f"已知學生截止時間 {dl_val}，但缺少官方申請開始日，不臆測已開放。",
                    "student_deadline": dl_val,
                    "application_start": None,
                    "upper_layer_deadlines": upper_layer_deadlines,
                    "supplement_deadlines": supplement_steps,
                    "same_day_time_unconfirmed": False,
                    "source_stale": source_stale,
                    "stale_sources": stale_sources,
                    "next_cycle_inferred": False,
                }
            return {
                "state": "open",
                "as_of": now_d.isoformat(),
                "reason_code": "open_within_student_window",
                "reason": f"位於學生申請期間（{start_val} 至 {dl_val}）。",
                "student_deadline": dl_val,
                "application_start": start_val,
                "upper_layer_deadlines": upper_layer_deadlines,
                "supplement_deadlines": supplement_steps,
                "same_day_time_unconfirmed": False,
                "source_stale": source_stale,
                "stale_sources": stale_sources,
                "next_cycle_inferred": False,
            }

    # 4. 學生截止日為 unknown，但有學院／校級／機關期限
    known_upper = [
        s for s in upper_steps if s.get("deadline", {}).get("kind") in ("date", "datetime") and s["deadline"].get("value")
    ]
    if known_upper:
        all_passed = True
        for s in known_upper:
            u_dl = s["deadline"]
            if u_dl["kind"] == "date":
                u_d = parse_iso_date(u_dl["value"])
                if u_d and now_d <= u_d:
                    all_passed = False
            elif u_dl["kind"] == "datetime":
                u_dt = parse_taipei_datetime(u_dl["value"])
                if u_dt:
                    if now_dt is not None and now_dt <= u_dt:
                        all_passed = False
                    elif now_dt is None and now_d <= u_dt.date():
                        all_passed = False
        if all_passed:
            return {
                "state": "closed",
                "as_of": now_d.isoformat(),
                "reason_code": "cycle_upper_layer_window_passed",
                "reason": "本梯次校院／機關送件期限已過，本期已截止；保留歷史，不從歷年日期猜測下一期。",
                "student_deadline": None,
                "application_start": start_dl.get("value"),
                "upper_layer_deadlines": upper_layer_deadlines,
                "supplement_deadlines": supplement_steps,
                "same_day_time_unconfirmed": False,
                "source_stale": source_stale,
                "stale_sources": stale_sources,
                "next_cycle_inferred": False,
            }
        # 若學院／機關期限尚未過，絕不可把學院／機關截止日當成學生截止日判 open！
        return {
            "state": "unknown",
            "as_of": now_d.isoformat(),
            "reason_code": "student_deadline_unknown_only_upper_layer_known",
            "reason": "僅知學院／校級／機關送件期限，所屬院系所之學生實際收件截止日尚待確認，不可將機關或學院期限當成學生截止日。",
            "student_deadline": None,
            "application_start": start_dl.get("value"),
            "upper_layer_deadlines": upper_layer_deadlines,
            "supplement_deadlines": supplement_steps,
            "same_day_time_unconfirmed": False,
            "source_stale": source_stale,
            "stale_sources": stale_sources,
            "next_cycle_inferred": False,
        }

    return {
        "state": "unknown",
        "as_of": now_d.isoformat(),
        "reason_code": "student_deadline_unknown",
        "reason": "尚無足以確認學生收件窗口的資料。",
        "student_deadline": None,
        "application_start": start_dl.get("value"),
        "upper_layer_deadlines": upper_layer_deadlines,
        "supplement_deadlines": supplement_steps,
        "same_day_time_unconfirmed": False,
        "source_stale": source_stale,
        "stale_sources": stale_sources,
        "next_cycle_inferred": False,
    }


def make_p1_profile(**overrides):
    """建立 P1 基準合成情境：臺大職能治療所博士班五年級、已取得博士候選人資格。
    未提供之國籍、在職、畢業時間、先前補助、基準日年級／候選人取得日等一律保持 unknown，絕不補猜。
    """
    profile = {
        "profile_id": "SYNTH-NTU-OT-PHD5",
        "observed_on": "2026-10-28",
        "institution": "NTU",
        "college": "醫學院",
        "department": "職能治療學系",
        "degree": "phd",
        "current_year": 5,
        "year_at_date": {},  # 例如 {"2026-09-01": 5} 僅於 P1-A 明示時提供
        "is_candidate": True,
        "candidate_acquired_on": None,
        "candidate_acquired_after": None,  # 例如 "2026-01-30" 於 P1-B 明示時提供
        "nationality": "unknown",
        "admission_route": "unknown",
        "in_service": "unknown",
        "has_fulltime_pay": "unknown",
        "graduating_this_year": "unknown",
        "applied_degree_exam": "unknown",
        "prior_nstc_abroad_result": "unknown",
        "received_nstc_abroad_before": "unknown",
        "hardship_proof": "unknown",
        "financial_difficulty_informal": False,
        "emergency_incident": "unknown",
        "publication_details": "unknown",
        "conference_details": "unknown",
        "existing_grants": "unknown",
    }
    profile.update(overrides)
    return profile


def evaluate_eligibility(item, profile, as_of="2026-10-28"):
    """對單一機會或候選進行結構化資格比對。
    回傳 dict 包含 criteria (meets_recorded_rules / not_met / needs_information / needs_manual_review)、
    reasons、missing_information、official_qualification_approved (恆為 False)。
    """
    elig = item.get("eligibility", {})
    reasons = []
    missing = []

    # 1. 學位檢查
    allowed_degrees = elig.get("degrees", [])
    student_degree = profile.get("degree", "unknown")
    if student_degree != "unknown" and allowed_degrees and student_degree not in allowed_degrees:
        return {
            "opportunity_id": item.get("id") or item.get("opportunity_id") or item.get("candidate_id"),
            "program_key": item.get("program_key"),
            "criteria": "not_met",
            "reasons": [f"學位不符：方案要求 {allowed_degrees}，申請者為 {student_degree}。"],
            "missing_information": [],
            "official_qualification_approved": False,
        }
    if student_degree == "unknown":
        missing.append("degree")
    if not allowed_degrees:
        missing.append("scheme_degree_rule")

    # 2. 學校檢查
    req_inst = elig.get("institution", "unknown")
    student_inst = profile.get("institution", "unknown")
    if req_inst in ("NTU", "domestic_eligible_institution") and student_inst == "unknown":
        missing.append("institution")
    if req_inst == "unknown":
        missing.append("scheme_institution_rule")
    if req_inst == "NTU" and student_inst not in ("NTU", "unknown"):
        return {
            "opportunity_id": item.get("id") or item.get("opportunity_id") or item.get("candidate_id"),
            "program_key": item.get("program_key"),
            "criteria": "not_met",
            "reasons": ["學校不符：方案限國立臺灣大學在學學生。"],
            "missing_information": [],
            "official_qualification_approved": False,
        }

    # 3. 年級限制（嚴格區分觀察日年級與基準日 assessed_at 年級；教育部 1-3 年級不影響國科會 unlimited）
    year_limit = elig.get("year_limit", {"mode": "unknown"})
    ymode = year_limit.get("mode", "unknown")
    if ymode == "range":
        ymin = year_limit.get("min")
        ymax = year_limit.get("max")
        assessed_at = year_limit.get("assessed_at")
        year_at_date = profile.get("year_at_date") or {}
        if assessed_at:
            grade_at_anchor = year_at_date.get(assessed_at, "unknown")
            if grade_at_anchor == "unknown":
                missing.append(f"year_at_{assessed_at}")
                reasons.append(f"需要基準日 {assessed_at} 之在學年級，不以 {profile.get('observed_on')} 當日觀察直接代填。")
            elif not (ymin <= grade_at_anchor <= ymax):
                return {
                    "opportunity_id": item.get("id") or item.get("opportunity_id") or item.get("candidate_id"),
                    "program_key": item.get("program_key"),
                    "criteria": "not_met",
                    "reasons": [f"年級不符：基準日 {assessed_at} 為 {grade_at_anchor} 年級，超出 {ymin}–{ymax} 年級限制。"],
                    "missing_information": [],
                    "official_qualification_approved": False,
                }
        else:
            cur_year = profile.get("current_year", "unknown")
            if cur_year == "unknown":
                missing.append("current_year")
            elif not (ymin <= cur_year <= ymax):
                return {
                    "opportunity_id": item.get("id") or item.get("opportunity_id") or item.get("candidate_id"),
                    "program_key": item.get("program_key"),
                    "criteria": "not_met",
                    "reasons": [f"年級不符：目前為 {cur_year} 年級，超出 {ymin}–{ymax} 年級限制。"],
                    "missing_information": [],
                    "official_qualification_approved": False,
                }
    elif ymode == "unlimited":
        reasons.append("本方案明示博士班不限年級，不因高年級排除。")
    else:
        missing.append("scheme_year_limit_rule")

    # 4. 博士候選人資格與取得時點檢查（如遠學要求截止日前通過候選人資格）
    cand_rule = elig.get("candidate", {"mode": "unknown"})
    if cand_rule.get("mode") == "required":
        if profile.get("is_candidate") not in (True, False):
            missing.append("is_candidate")
        if profile.get("is_candidate") is False:
            return {
                "opportunity_id": item.get("id") or item.get("opportunity_id") or item.get("candidate_id"),
                "program_key": item.get("program_key"),
                "criteria": "not_met",
                "reasons": ["未具博士學位候選人資格。"],
                "missing_information": [],
                "official_qualification_approved": False,
            }
        # 檢查候選人取得日期是否晚於該梯次截止日
        steps = _extract_steps(item)
        cycle_deadlines = [
            s["deadline"]["value"][:10]
            for s in steps
            if s.get("deadline", {}).get("kind") in ("date", "datetime") and s["deadline"].get("value")
        ]
        cutoff_date = cand_rule.get("assessed_at") or (min(cycle_deadlines) if cycle_deadlines else None)
        acquired_after = profile.get("candidate_acquired_after")
        acquired_on = profile.get("candidate_acquired_on")
        if cutoff_date:
            if acquired_after and acquired_after >= cutoff_date:
                return {
                    "opportunity_id": item.get("id") or item.get("opportunity_id") or item.get("candidate_id"),
                    "program_key": item.get("program_key"),
                    "criteria": "not_met",
                    "reasons": [f"博士候選人資格於 {acquired_after} 之後才取得，晚於本梯次基準／截止日 {cutoff_date}。"],
                    "missing_information": [],
                    "official_qualification_approved": False,
                }
            if acquired_on and acquired_on > cutoff_date:
                return {
                    "opportunity_id": item.get("id") or item.get("opportunity_id") or item.get("candidate_id"),
                    "program_key": item.get("program_key"),
                    "criteria": "not_met",
                    "reasons": [f"博士候選人取得日 {acquired_on} 晚於本梯次基準／截止日 {cutoff_date}。"],
                    "missing_information": [],
                    "official_qualification_approved": False,
                }
            if not acquired_on:
                missing.append("candidate_acquired_on")
                reasons.append(f"需確認是否在截止日（{cutoff_date}）前已取得博士候選人資格，不把事後觀察回填至過去時點。")

    # 5. 國籍、在職與其他特定條件檢查（不補猜未知條件）
    identity_text = elig.get("identity", {}).get("text", "")
    nat_rule = elig.get("nationality", "unknown")
    if nat_rule == "international_only":
        if profile.get("nationality") == "roc":
            return {"criteria":"not_met", "reasons":["本方案限外籍身分，須核對申請管道。"], "missing_information":[], "official_qualification_approved":False}
        if profile.get("nationality", "unknown") == "unknown":
            missing.append("nationality")
    requires_roc = nat_rule == "roc_only" or any(k in identity_text for k in ("本國籍", "中華民國國民", "中華民國國籍"))
    if requires_roc:
        if profile.get("nationality") in ("non_roc", "international"):
            return {
                "opportunity_id": item.get("id") or item.get("opportunity_id") or item.get("candidate_id"),
                "program_key": item.get("program_key"),
                "criteria": "not_met",
                "reasons": ["國籍不符：本方案限本國籍／中華民國國民。"],
                "missing_information": [],
                "official_qualification_approved": False,
            }
        if profile.get("nationality", "unknown") == "unknown":
            missing.append("nationality")

    if "國際生" in identity_text and profile.get("nationality") in ("non_roc", "international"):
        if profile.get("admission_route", "unknown") == "unknown":
            missing.append("admission_route")
            reasons.append("外籍博士生需確認是否為逕博生或依國際處管道分流，不一律排除。")

    emp_rule = elig.get("employment_status", "unknown")
    if emp_rule == "unemployed_or_no_fulltime_pay":
        if profile.get("has_fulltime_pay") is True:
            return {"criteria":"not_met", "reasons":["不符未具專職全時有給工作條件。"], "missing_information":[], "official_qualification_approved":False}
        if profile.get("has_fulltime_pay", "unknown") == "unknown":
            missing.append("has_fulltime_pay")
    excludes_in_service = emp_rule in ("non_in_service_only", "unemployed_or_no_fulltime_pay") or any(
        k in identity_text for k in ("非在職", "不含在職", "在職、工作")
    )
    if excludes_in_service:
        if profile.get("in_service") is True:
            return {
                "opportunity_id": item.get("id") or item.get("opportunity_id") or item.get("candidate_id"),
                "program_key": item.get("program_key"),
                "criteria": "not_met",
                "reasons": ["在職狀態不符：本方案排除在職生或有專職工作者。"],
                "missing_information": [],
                "official_qualification_approved": False,
            }
        if profile.get("in_service", "unknown") == "unknown":
            missing.append("in_service_and_employment")

    if "畢業" in identity_text or elig.get("graduation_requirement") not in (None, "none_specified", "unknown"):
        if profile.get("graduating_this_year", "unknown") == "unknown" or profile.get("applied_degree_exam", "unknown") == "unknown":
            missing.append("graduation_and_degree_exam_status")

    if "曾申請" in identity_text or "未獲補助" in identity_text or elig.get("prior_funding_rule") == "must_have_applied_nstc_abroad_unfunded":
        if profile.get("prior_nstc_abroad_result", "unknown") == "unknown":
            missing.append("prior_nstc_abroad_result")

    if "曾領本補助者不得" in identity_text or elig.get("prior_funding_rule") == "never_received_this_grant":
        if profile.get("received_nstc_abroad_before", "unknown") == "unknown":
            missing.append("received_nstc_abroad_before")

    if "減免身分" in identity_text or item.get("resource_kind") == "tuition_remission":
        if profile.get("hardship_proof", "unknown") == "unknown":
            missing.append("tuition_remission_identity_category")

    if item.get("hardship", {}).get("mode") == "required":
        # 即使非正式表示經濟拮据 (financial_difficulty_informal=True)，沒有正式清寒證明仍不可自動通過！
        if profile.get("hardship_proof") is not True:
            missing.append("official_hardship_proof")
            reasons.append("清寒限定方案需核對正式證明文件，不因一般經濟困難描述自動判為通過。")

    if item.get("resource_kind") == "emergency_aid":
        if profile.get("emergency_incident", "unknown") == "unknown":
            missing.append("emergency_incident_and_category")

    if item.get("category") == "international_conference":
        if profile.get("conference_details", "unknown") == "unknown":
            missing.append("conference_date_acceptance_and_prior_subsidy")

    if item.get("resource_kind") == "employment_support":
        missing.append("course_recruitment_and_training_qualification")

    if item.get("compatibility", {}).get("mode") in ("conditional", "prohibited", "unknown"):
        if profile.get("existing_grants", "unknown") == "unknown":
            missing.append("existing_grants_for_compatibility")

    # 6. 若證據本身為 incomplete（如搜尋摘要），強制為 needs_manual_review
    if elig.get("other_conditions") or elig.get("negated_conditions"):
        missing.append("additional_conditions_manual_check")
    if item.get("evidence_status") == "incomplete":
        return {
            "opportunity_id": item.get("id") or item.get("opportunity_id") or item.get("candidate_id"),
            "program_key": item.get("program_key"),
            "criteria": "needs_manual_review",
            "reasons": ["來源僅有搜尋摘要或辦法未完整讀取，必須人工核對正式辦法與附件。"] + reasons,
            "missing_information": missing,
            "official_qualification_approved": False,
        }

    if missing:
        return {
            "opportunity_id": item.get("id") or item.get("opportunity_id") or item.get("candidate_id"),
            "program_key": item.get("program_key"),
            "criteria": "needs_information",
            "reasons": reasons or ["尚缺未提供之個人條件或待查欄位，不自動推定符合。"],
            "missing_information": missing,
            "official_qualification_approved": False,
        }

    return {
        "opportunity_id": item.get("id") or item.get("opportunity_id") or item.get("candidate_id"),
        "program_key": item.get("program_key"),
        "criteria": "meets_recorded_rules",
        "reasons": reasons,
        "missing_information": [],
        "official_qualification_approved": False,
    }


def evaluate_compatibility_pair(item_a, item_b):
    """雙邊兼領檢查：只要任一方為 prohibited、conditional 或 unknown，絕不回傳 allowed。"""
    comp_a = item_a.get("compatibility", {"mode": "unknown", "note": "", "refs": []})
    comp_b = item_b.get("compatibility", {"mode": "unknown", "note": "", "refs": []})
    modes = {comp_a.get("mode", "unknown"), comp_b.get("mode", "unknown")}
    refs = list(comp_a.get("refs", [])) + list(comp_b.get("refs", []))

    if "prohibited" in modes:
        mode = "prohibited"
    elif "conditional" in modes or "unknown" in modes:
        mode = "needs_clarification"
    else:
        mode = "allowed_within_recorded_scope"

    return {
        "mode": mode,
        "can_assume_compatible": False if mode != "allowed_within_recorded_scope" else True,
        "scheme_a_mode": comp_a.get("mode", "unknown"),
        "scheme_b_mode": comp_b.get("mode", "unknown"),
        "explanation": f"方案A（{comp_a.get('mode')}：{comp_a.get('note', '')}）與方案B（{comp_b.get('mode')}：{comp_b.get('note', '')}）須同時核對雙方限制與重疊支領期間。",
        "refs": refs,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=ROOT / "data/pilot.json")
    parser.add_argument("--as-of", default="2026-10-28")
    args = parser.parse_args()

    data = json.loads(args.data.read_text(encoding="utf-8"))
    sources_by_id = {s["id"]: s for s in data.get("sources", [])}
    p1 = make_p1_profile()
    results = []
    for item in data.get("opportunities", []):
        window = evaluate_application_window(item, args.as_of, sources_by_id=sources_by_id)
        elig = evaluate_eligibility(item, p1, as_of=args.as_of)
        results.append(
            {
                "id": item["id"],
                "application_state": window["state"],
                "reason_code": window["reason_code"],
                "p1_criteria": elig["criteria"],
                "missing_information": elig["missing_information"],
            }
        )
    print(json.dumps({"as_of": args.as_of, "evaluated": len(results), "results": results}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
