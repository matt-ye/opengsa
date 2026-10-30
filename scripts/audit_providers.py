"""手動 API 盤點：不輸出 key、帳號識別或錯誤原文，不使用學生／來源資料。"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import sys
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.providers import PROVIDERS, provider_settings


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # Do not forward authentication to a redirect target.


def request_json(url, key, payload=None):
    headers = {"User-Agent":"OpenGSA/0.2 (+https://github.com/matt-ye/opengsa)"}
    if key:
        headers["Authorization"] = "Bearer " + key
    data = None if payload is None else json.dumps(payload).encode()
    if data is not None:
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers)
    try:
        with urllib.request.build_opener(NoRedirect()).open(request, timeout=25) as response:
            raw = response.read(8 * 1024 * 1024 + 1)
            if len(raw) > 8 * 1024 * 1024:
                return 0, {}, {}
            allowed = {"x-ratelimit-limit-requests","x-ratelimit-limit-tokens","x-ratelimit-remaining-requests","x-ratelimit-remaining-tokens","x-ratelimit-reset-requests","x-ratelimit-reset-tokens"}
            quotas = {k.lower():v[:80] for k,v in response.headers.items() if k.lower() in allowed and re.fullmatch(r"[0-9 .:smhdTZ+_-]+",v)}
            return response.status, json.loads(raw), quotas
    except urllib.error.HTTPError as error:
        return error.code, {}, {}
    except (OSError, ValueError):
        return 0, {}, {}


def model_catalog(body):
    rows = body.get("data", body.get("models", [])) if isinstance(body, dict) else []
    return [m for m in rows if isinstance(m, dict) and isinstance(m.get("id",m.get("name")),str)]


def zero_price(model):
    return model.get("id", "").endswith(":free") and all(str(model.get("pricing",{}).get(k)) in ("0","0.0") for k in ("prompt","completion"))


def audit_provider(name, environ, probe=False, requester=request_json):
    info = PROVIDERS[name]
    row = {"provider":name,"key_present":False,"catalog_status":"not_checked","model_present":False,
           "authentication_status":"not_proven_by_catalog",
           "inference_status":"not_requested","inference_calls":0,"usage":None,
           "quota":None,"cost_usd":None,"account_free_entitlement_verified":False,
           "key_expires_on":info["key_expires_on"],"expiry_note":info["expiry_note"]}
    row["key_present"] = any(environ.get(k, "").strip() for k in info["key_envs"])
    try:
        base, wanted, key_env = provider_settings(name,environ)
    except ValueError:
        row["catalog_status"] = "region_or_endpoint_unconfirmed"
        return row
    key = environ.get(key_env, "").strip()
    row.update(key_present=bool(key),base_url=base,configured_model=wanted)
    if not key:
        row["catalog_status"] = "missing_key"
        return row
    status, body, quotas = requester(base+"/models",key)
    models = model_catalog(body)
    if name == "gemini":
        models = [{**m,"id":m.get("id",m.get("name","")).removeprefix("models/")} for m in models]
    ids = sorted({m.get("id",m.get("name")) for m in models if re.fullmatch(r"[A-Za-z0-9_./:-]{1,200}",m.get("id",m.get("name",""))) and key not in m.get("id",m.get("name",""))})
    row.update(catalog_status="success" if status==200 and models else f"http_{status}_or_empty",model_present=wanted in ids,
               model_count=len(ids),model_ids=ids[:1000],rate_limit_headers=quotas)
    selected = wanted if wanted in ids else None
    if name == "openrouter" and status == 200:
        free = sorted(m["id"] for m in models if zero_price(m) and m["id"] in ids)
        selected = wanted if wanted in free else (free[0] if free else None)
        row["zero_price_models"] = free
        qstatus, qbody, _ = requester(base+"/key",key)
        q = qbody.get("data",{}) if isinstance(qbody,dict) else {}
        if qstatus == 200:
            row["authentication_status"] = "key_metadata_accepted"
            daily = q.get("free_model_daily_requests") or {}
            row["quota"] = {k:daily[k] for k in ("used","limit","remaining") if isinstance(daily.get(k),(int,float))}
            row["observed_usage_usd"] = {k:q[k] for k in ("usage","usage_daily","usage_monthly") if isinstance(q.get(k),(int,float))}
        row["zero_price_model_verified"] = bool(selected)
    row["selected_model"] = selected
    if not probe:
        return row
    if selected is None:
        row["inference_status"] = "skipped_model_unavailable"
        return row
    if info["inference_policy"] not in ("user_reported_free","zero_price_free_only"):
        row["inference_status"] = "skipped_billing_or_credits_unconfirmed"
        return row
    payload = {"model":selected,"messages":[{"role":"user","content":"Return only this JSON object: {\"ok\":true}"}],"max_tokens":160,"temperature":0}
    if name == "groq":
        payload["reasoning_effort"] = "none"
    elif name == "openrouter":
        payload["reasoning"] = {"effort":"none","exclude":True}
        payload["response_format"] = {"type":"json_object"}
    row["inference_calls"] = 1
    status, result, quotas = requester(base+"/chat/completions",key,payload)
    row["inference_status"] = f"http_{status}"
    if status == 200:
        row["inference_status"] = "http_200_json_not_validated"
    row["rate_limit_headers"].update(quotas)
    row["usage"] = {k:v if isinstance(v,(int,float)) else None for k in ("prompt_tokens","completion_tokens","total_tokens") for v in [result.get("usage",{}).get(k)]}
    try:
        content = result["choices"][0]["message"]["content"]
        if status == 200 and json.loads(content) == {"ok":True}:
            row["inference_status"] = "synthetic_json_passed"
            row["authentication_status"] = "inference_accepted"
    except (KeyError,IndexError,TypeError,ValueError):
        pass
    return row


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--probe",action="store_true",help="At most one synthetic call per eligible provider; no paid fallback")
    parser.add_argument("--provider",choices=list(PROVIDERS))
    parser.add_argument("--output",type=Path,default=Path("work/provider-audit/report.json"))
    args = parser.parse_args()
    names = [args.provider] if args.provider else list(PROVIDERS)
    rows = [audit_provider(n,os.environ,args.probe) for n in names]
    report = {"observed_at":datetime.now(timezone.utc).isoformat(),"scope":"manual_only","claims":"catalog != inference != free entitlement; null means unknown","providers":rows}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"providers":len(rows),"catalog_success":sum(r["catalog_status"]=="success" for r in rows),"inference_calls":sum(r["inference_calls"] for r in rows)}))


if __name__ == "__main__":
    main()
