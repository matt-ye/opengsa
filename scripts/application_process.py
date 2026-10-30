"""Conservative delivery-method and applicability rules; missing text never means N/A."""
import re


def infer_process(blocks):
    method = {"mode":"unknown", "channels":[], "paper_delivery":"unknown",
              "handwritten_signature":"unknown", "deadline_basis":"unknown",
              "note":"須核對申請、補件與核銷各步驟；線上報名不等於全程免紙本", "refs":[]}
    applicability, evidence = {}, {}
    for index, block in enumerate(blocks):
        text = re.sub(r"\s+", "", block["text"])
        paper = bool(re.search(r"紙本.{0,12}(?:郵寄|送達|遞交|繳交)|(?:郵寄|遞交|繳交).{0,5}紙本|書面方式提出|掛號郵寄|親送|親自送達", text))
        if re.search(r"(?:不需|不須|無須|免).{0,5}(?:遞交|郵寄|寄送|繳交)紙本",text):paper=False
        online = bool(re.search(r"線上(?:申請|申辦|報名)|上傳.{0,12}(?:平台|系統)|(?:平台|系統).{0,8}上傳|電子郵件申請", text))
        if paper or online:
            evidence[f"application_method/{index}"] = block
        for channel, matched in [("post", "郵寄" in text),("in_person",bool(re.search(r"親送|親自送達",text))),
                                 ("portal", online and "電子郵件申請" not in text),("email","電子郵件申請" in text),
                                 ("paper",paper)]:
            if matched and channel not in method["channels"]:method["channels"].append(channel)
        if paper and not re.search(r"免.{0,5}紙本|不(?:需|須).{0,5}紙本|無(?:需|須).{0,5}紙本", text):
            method["paper_delivery"] = "required"
        if re.search(r"全程線上|免.{0,5}(?:寄送|遞交|繳交)紙本|(?:不需|不須|無須).{0,5}(?:寄送|遞交|繳交)紙本", text):
            method["paper_delivery"] = "not_required" if method["paper_delivery"] != "required" else "unknown"
            evidence[f"application_method/{index}"] = block
        if "親筆簽名" in text or "親簽" in text:
            method["handwritten_signature"] = "required"
            evidence[f"application_method/{index}"] = block
        basis = "received" if re.search(r"送達.{0,12}為準|收到.{0,8}為準",text) else "postmark" if re.search(r"郵戳為憑|郵戳為準",text) and not re.search(r"不以郵戳|非以郵戳|非郵戳",text) else None
        if basis:
            method["deadline_basis"] = basis
            evidence[f"application_method/{index}"] = block
        no_application = bool(re.search(r"(?:免(?:另行|額外)?申請|(?:無須|不需|不須)(?:另行|額外)?申請)(?!核銷|補件|展延|變更)",text))
        if no_application:
            for key in ("application_start","student_deadline"):
                applicability[key] = {"status":"not_applicable","reason":"來源明示無須提出申請","refs":[]}
                evidence["field_applicability."+key] = block
            method.update(mode="automatic",paper_delivery="not_applicable")
            evidence[f"application_method/{index}"] = block
        if re.search(r"不另公告(?:審查)?結果|無審查結果|無審查程序",text):
            applicability["result_date"]={"status":"not_applicable","reason":"來源明示無審查結果／不另公告結果","refs":[]}
            evidence["field_applicability.result_date"] = block
        if re.search(r"不限學生身分|無須學生身分|不限學籍|regardlessofwheretheyareintheireducation|noinstitutionalenrollmentrequirement",text,re.I):
            for key in ("candidate_qualification","year_limit"):
                applicability[key]={"status":"not_applicable","reason":"來源明示不以學生學籍為申請條件","refs":[]}
                evidence["field_applicability."+key] = block
    if method["mode"] != "automatic":
        has_paper = "paper" in method["channels"]
        has_online = any(c in method["channels"] for c in ("portal","email"))
        method["mode"] = "hybrid" if has_paper and has_online else "paper" if has_paper else "electronic" if has_online else "unknown"
        if method["mode"] == "hybrid":
            method["note"]="同時出現紙本與電子途徑；須核對是擇一或各階段皆必須，不推定全程免紙本"
    return method, applicability, evidence


def process_errors(record):
    """N/A must have evidence and must not conceal an existing concrete value."""
    errors=[]
    schedule=record.get("schedule",{})
    values={"application_start":schedule.get("application_start",record.get("start",{})),
            "result_date":schedule.get("result_date",record.get("result",{}))}
    for key,entry in record.get("field_applicability",{}).items():
        if entry.get("status") != "not_applicable":continue
        if not entry.get("refs") or not entry.get("reason"):errors.append("na_requires_evidence:"+key)
        concrete=values.get(key) or {}
        if key=="student_deadline":
            concrete=next((s.get("deadline",{}) for s in schedule.get("steps",record.get("steps",[])) if s.get("actor") in ("student","student_or_representative") and s.get("deadline",{}).get("value")),{})
        if concrete.get("value"):errors.append("na_conflicts_with_value:"+key)
        elig=record.get("eligibility",{})
        if key=="candidate_qualification" and elig.get("candidate",{}).get("mode")=="required":errors.append("na_conflicts_with_value:"+key)
        if key=="year_limit" and elig.get("year_limit",{}).get("mode") in ("range","freshman","graduating"):errors.append("na_conflicts_with_value:"+key)
    return errors
