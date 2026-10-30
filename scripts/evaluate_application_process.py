"""Manual, bounded process-only evaluation. No model, raw HTML/PDF retention or publication."""
import json
from datetime import datetime, timezone
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from bs4 import BeautifulSoup
from scripts.application_process import infer_process
from scripts.scan_sources import Fetcher, html_document


def evaluate():
    config=json.loads((ROOT/"data/scan-sources.json").read_text(encoding="utf-8"))
    additional=[
        {"id":"taipei-ai","url":"https://youth.gov.taipei/services/05eb79e5-46b5-41e5-b1fd-0519d782b04a/0ecc1836-dd0d-4085-a34f-003609f00796","marker":"計畫目的"},
        {"id":"hsinchu-ai","url":"https://dgservice.hccg.gov.tw/serviceNotice.do?id=1323&rule=guest","marker":"AI領航青年數位工具補助計畫申請"},
        {"id":"aws-educate","url":"https://aws.amazon.com/education/awseducate/","marker":"AWS Educate"},
    ]
    config["allowed_hosts"] += ["youth.gov.taipei","dgservice.hccg.gov.tw","aws.amazon.com"]
    targets=[s for s in config["sources"] if s["id"] in ("nstc-conference-rule","ntu-doctoral-funding")]+additional
    fetcher=Fetcher(config)
    rows=[]
    for source in targets:
        row={"source_id":source["id"],"url":source["url"],"status":"not_checked"}
        try:
            response=fetcher.get(source["url"],{},2*1024*1024)
            if response["status"] != 200:raise ValueError("http_"+str(response["status"]))
            if "body_selector" in source:
                blocks,_=html_document(response["body"],source,response["url"],config["allowed_hosts"])
            else:
                soup=BeautifulSoup(response["body"],"html.parser")
                for node in soup.select("nav,header,footer,script,style,form,noscript"):node.decompose()
                lines=soup.get_text("\n",strip=True).splitlines()
                start=next((i for i,t in enumerate(lines) if source["marker"] in t),None)
                if start is None:raise ValueError("required_marker_missing")
                blocks=[{"locator":f"body/text-block {i}","text":line} for i,line in enumerate(lines[start:],start)]
            method,applicability,evidence=infer_process(blocks)
            for path,block in evidence.items():
                ref={"source":source["id"],"locator":block["locator"]}
                if path.startswith("application_method"):method["refs"].append(ref)
                else:applicability[path.split(".")[1]]["refs"].append(ref)
            row.update(status="parsed_pending_review",application_method=method,field_applicability=applicability)
        except Exception as error:
            # Only controlled status codes; never raw remote responses or connection details.
            row["status"]=str(error) if str(error) in ("required_marker_missing","robots_denied","robots_not_plain_rules","run_budget_exhausted","transport_error") or str(error).startswith("http_") else type(error).__name__
        rows.append(row)
    result={"observed_at":datetime.now(timezone.utc).isoformat(),"http_requests":fetcher.count,"model_calls":0,
            "official_data_modified":False,"raw_documents_stored":False,"human_approved":False,"rows":rows}
    path=ROOT/"work/application-process/report.json";path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"http_requests":fetcher.count,"sources":[{"id":r["source_id"],"status":r["status"],"mode":r.get("application_method",{}).get("mode")} for r in rows]}))


if __name__=="__main__":evaluate()
