"""Audit saved resource URLs without enabling schedules, models or publishing data."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit, urlunsplit, quote, unquote

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from bs4 import BeautifulSoup
from scripts.scan_sources import Fetcher, ScanError, digest, pdf_document, normalized, SKIP
from scripts.evaluate_deadlines import taipei_today

DOCUMENTS=["TAXONOMY-AND-SOURCES.md","SOURCE-LANDSCAPE-AND-EXPANSION.md",
    "ACADEMIC-CAREER-AND-ASSISTANTSHIPS.md","RIGHTS-SOURCES.md","RIGHTS-AND-LEGAL-FRAMEWORK.md",
    "CONFERENCE-SOURCES.md","PR18-RESOURCE-REVIEW.md","reference/AI-TOOL-SUBSIDIES.md",
    "PILOT-REVIEW.md","reference/HANDOFF.md","INGESTION-POC.md"]
FOREIGN_DEGREE_HOSTS={"www.fulbright.org.tw","www.daad.de","www.chevening.org","erasmus-plus.ec.europa.eu"}
RESOURCE_WORDS=re.compile(r"獎學|獎助|補助|申請|辦法|要點|scholarship|fellowship|grant",re.I)
HOST_FAILURES={"robots_not_plain_rules","robots_unavailable","http_403_host_paused","http_429_host_paused"}
TECHNICAL_HOSTS={"creativecommons.org","opensource.org","www.rfc-editor.org","www.w3.org","docs.astro.build","data.gov.tw"}


def canonical_url(url):
    if "<" in url or ">" in url:raise ValueError("Malformed resource URL")
    # Bare query keys such as &LTPno must not be interpreted as the HTML entity &LT.
    value=urlsplit(url.replace("\\&","&").replace("&amp;","&"))
    if value.scheme not in ("http","https") or not value.hostname or value.username or value.password:
        raise ValueError("Not a public resource URL")
    return urlunsplit((value.scheme,value.netloc.lower(),quote(unquote(value.path or "/"),safe="/()-._~"),value.query,""))


def collect_inventory(root=ROOT):
    rows={}
    def add(url,title,origin):
        try:url=canonical_url(url)
        except ValueError:return
        if urlsplit(url).hostname=="github.com":return
        row=rows.setdefault(url,{"url":url,"title":title or url,"used_in":[]})
        if origin not in row["used_in"]:row["used_in"].append(origin)
    def walk(value,origin):
        if isinstance(value,dict):
            if isinstance(value.get("url"),str):add(value["url"],value.get("title",value.get("id","")),origin)
            for child in value.values():walk(child,origin)
        elif isinstance(value,list):
            for child in value:walk(child,origin)
    for name in ["data/scan-sources.json","data/pilot.json","data/conference-programs.json","docs/examples/ingestion-sources.proposed.json"]:
        walk(json.loads((root/name).read_text(encoding="utf-8")),name)
    for name in DOCUMENTS:
        path="docs/"+name
        for title,url in re.findall(r"\[([^\]\n]*)\]\((https?://[^)\s]+)\)",(root/path).read_text(encoding="utf-8")):
            add(url,title,path)
    path="docs/design/wireframes.html"
    for a in BeautifulSoup((root/path).read_text(encoding="utf-8"),"html.parser").select('a[href^="http"]'):
        add(a["href"],a.get_text(" ",strip=True),path)
    return sorted(rows.values(),key=lambda r:r["url"])


def existing_observations(directory):
    found={}
    if not directory:return found
    for path in sorted(Path(directory).glob("**/report/scan-report.json")):
        report=json.loads(path.read_text(encoding="utf-8"))
        bundle=json.loads((path.parent/"structured-candidates.json").read_text(encoding="utf-8"))
        for doc in report["documents"]:
            old=found.get(canonical_url(doc["url"]),{})
            if old.get("observed_at","")>report["observed_at"]:continue
            candidates=[c for c in bundle["candidates"] if c["source_metadata"]["url"]==doc["url"]]
            found[canonical_url(doc["url"])]=dict(scan_status=doc["status"],format=doc["kind"],
                observed_at=report["observed_at"],candidate_ids=[c["candidate_id"] for c in candidates],
                verification=[c["verification"]["status"] for c in candidates],
                application_states=[c["application"]["state"] for c in candidates],
                judgment="candidate_pending_review" if candidates else "unavailable")
    return found


def skip_reason(row):
    url=row["url"];parts=urlsplit(url)
    if parts.scheme!="https":return "http_seed_requires_verified_https_replacement"
    if parts.hostname=="my.ntu.edu.tw":return "login_only_manual"
    if parts.hostname in FOREIGN_DEGREE_HOSTS:return "overseas_degree_placeholder_deferred"
    if parts.hostname in TECHNICAL_HOSTS:return "supporting_documentation_reference"
    if SKIP.search(url) or SKIP.search(row["title"]):return "private_or_award_list_not_fetched"
    if url.endswith("robots.txt") or url.endswith("/Privacy"):return "crawl_policy_reference"
    return None


def probe(row,fetcher):
    url=row["url"]
    response=fetcher.get(url,{},10*1024*1024 if urlsplit(url).path.lower().endswith(".pdf") else 2*1024*1024)
    if response["status"]!=200:raise ScanError("http_"+str(response["status"]))
    content_type=response["headers"].get("content-type","").lower()
    result={"observed_at":datetime.now(timezone.utc).isoformat(timespec="seconds"),"raw_sha256":digest(response["body"]),"final_url":response["url"]}
    if response["body"].startswith(b"%PDF-") or "application/pdf" in content_type:
        blocks=pdf_document(response["body"])
        result.update(scan_status="parsed_pdf",format="pdf",text_blocks=len(blocks),judgment="needs_source_profile_and_field_review")
    elif "text/html" in content_type:
        soup=BeautifulSoup(response["body"],"html.parser")
        main=soup.select_one("main,[role=main],article")
        roots=main or soup.body
        if roots is None:raise ScanError("html_body_missing")
        for node in roots.select("script,style,nav,footer,form,noscript"):node.decompose()
        text=normalized(roots.get_text(" ",strip=True))
        if len(text)<80:raise ScanError("html_no_meaningful_body_or_dynamic_content")
        links=[]
        # Discovery is metadata only; link labels and page prose are not retained.
        from urllib.parse import urljoin
        for anchor in roots.select("a[href]"):
            label=anchor.get_text(" ",strip=True)
            if not RESOURCE_WORDS.search(label) or SKIP.search(label):continue
            target=urljoin(response["url"],anchor["href"])
            if not target.startswith("https://") or SKIP.search(unquote(target)):continue
            try:target=canonical_url(target)
            except ValueError:continue
            if target not in links:links.append(target)
        result.update(scan_status="parsed_html_discovery_only",format="html",body_characters=len(text),
            relevant_link_count=len(links),discovered_urls=links[:20],judgment="needs_source_profile_and_field_review")
    else:raise ScanError("unexpected_content_type")
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--observations",type=Path)
    parser.add_argument("--previous",type=Path,help="Resume observations from an earlier audit without overwriting it")
    parser.add_argument("--probe",action="store_true",help="Manual bounded public GET batches; no model or schedule")
    args=parser.parse_args()
    if args.output.exists():parser.error("Choose a new output file; previous audits are preserved")
    config=json.loads((ROOT/"data/scan-sources.json").read_text(encoding="utf-8"))
    rows=collect_inventory();observations=existing_observations(args.observations)
    prior=json.loads(args.previous.read_text(encoding="utf-8")) if args.previous else {}
    normalized_prior=[]
    for row in prior.get("rows",[]):
        try:row["url"]=canonical_url(row["url"])
        except ValueError:continue
        normalized_prior.append(row)
    prior["rows"]=normalized_prior
    existing={r["url"] for r in rows}
    for row in prior.get("rows",[]):
        if "<" in row["url"] or ">" in row["url"]:continue
        if row["url"] not in existing:
            rows.append({"url":row["url"],"title":row["title"],"used_in":row["used_in"],"retired_from_current_inventory":True})
            existing.add(row["url"])
    for row in prior.get("rows",[]):
        if row.get("scan_status") not in (None,"not_probed") and not (row.get("inherited_host_pause") and row["scan_status"]=="robots_denied"):
            old=observations.get(row["url"],{})
            if old.get("observed_at","")<=row.get("observed_at",""):observations[row["url"]]=row
    config["allowed_hosts"]=sorted({urlsplit(r["url"]).hostname for r in rows if urlsplit(r["url"]).scheme=="https"})
    profiles={canonical_url(s["url"]):s for s in config["sources"]}
    report={"as_of":taipei_today(),"scope":"saved_resource_urls_in_data_and_source_documents_including_retired_links",
        "request_count_scope":"Saved probe calls only; interrupted in-flight requests may be omitted. Scanner batches counted separately.",
        "http_requests":prior.get("http_requests",0),"model_calls":0,"official_data_modified":False,"rows":rows,"batches":prior.get("batches",[])}
    fetcher=None;documents=0
    paused={urlsplit(url).hostname:row["scan_status"] for url,row in observations.items()
        if row.get("scan_status") in HOST_FAILURES}
    def save():
        report["counts"]=dict(Counter(r.get("scan_status","not_probed") for r in rows))
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    for index,row in enumerate(rows):
        row["source_id"]=profiles.get(row["url"],{}).get("id")
        row["pipeline_role"]=("supporting_documentation" if urlsplit(row["url"]).hostname in TECHNICAL_HOSTS else
            "enabled_candidate_profile" if profiles.get(row["url"],{}).get("enabled",True) and row["source_id"] else
            "disabled_profile" if row["source_id"] else "discovery_or_reference")
        if row["url"] in observations:
            row.update({k:v for k,v in observations[row["url"]].items() if k not in ("source_id","pipeline_role","url","title","used_in","retired_from_current_inventory")})
            save();continue
        reason=skip_reason(row)
        if not reason and urlsplit(row["url"]).hostname in paused:
            reason=paused[urlsplit(row["url"]).hostname]
            row["inherited_host_pause"]=True
        row.update(scan_status=reason or "not_probed",judgment="not_evaluated")
        if args.probe and not reason:
            if fetcher is None or documents>=5:
                fetcher=Fetcher(config);documents=0;report["batches"].append({"http_requests":0})
            before=fetcher.count
            try:row.update(probe(row,fetcher))
            except Exception as error:
                row["scan_status"]=str(error) if isinstance(error,ScanError) else type(error).__name__
                if row["scan_status"] in HOST_FAILURES:
                    paused[urlsplit(row["url"]).hostname]=row["scan_status"]
            documents+=1
            report["http_requests"]+=fetcher.count-before
            report["batches"][-1]["http_requests"]=fetcher.count
        save()
        print(f"{index+1}/{len(rows)} {row['scan_status']} {row['url']}",flush=True)
    print(json.dumps({"counts":report["counts"],"http_requests":report["http_requests"],"model_calls":0},ensure_ascii=False))


if __name__=="__main__":main()
