"""離線檢查資料形狀與引用；不判定個人資格或外站正確性。"""
import argparse
import json
import sys
from collections import Counter
from datetime import date
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))
from scripts.application_process import process_errors


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def validate(data):
    schema = read_json(ROOT / "schema/pilot.schema.json")
    Draft202012Validator.check_schema(schema)
    candidate_schema_path = ROOT / "schema/candidate.schema.json"
    if candidate_schema_path.exists():
        Draft202012Validator.check_schema(read_json(candidate_schema_path))
    errors = [
        f"{'/'.join(map(str, error.absolute_path))}: {error.message}"
        for error in Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(data)
    ]
    if errors:
        return errors
    as_of = date.fromisoformat(data["as_of"])
    source_ids = [source["id"] for source in data["sources"]]
    opportunity_ids = [item["id"] for item in data["opportunities"]]
    policy_ids = [item["id"] for item in data["policy_versions"]]
    for kind, ids in [("source", source_ids), ("opportunity", opportunity_ids), ("policy", policy_ids)]:
        if len(ids) != len(set(ids)):
            errors.append(f"duplicate {kind} id")

    def references(value, path=""):
        if isinstance(value, dict):
            if "source" in value and value["source"] not in source_ids:
                errors.append(f"{path}: unknown source {value['source']}")
            for key, child in value.items():
                references(child, f"{path}/{key}")
        elif isinstance(value, list):
            for index, child in enumerate(value):
                references(child, f"{path}/{index}")

    references(data)
    for source in data["sources"]:
        if date.fromisoformat(source["checked_on"]) > as_of:
            errors.append(f"{source['id']}: checked_on is after snapshot")
        if source["ownership_status"] == "assigned" and not source["owner"]:
            errors.append(f"{source['id']}: assigned source needs owner")
    source_map = {source["id"]: source for source in data["sources"]}
    for item in data["opportunities"]:
        key = item["id"]
        errors.extend(f"{key}: {e}" for e in process_errors(item))
        review = item["review"]
        if review["status"] == "reviewed":
            if review["editor"] == review["independent_reviewer"]:
                errors.append(f"{key}: review must be independent")
            if date.fromisoformat(review["reviewed_on"]) > as_of:
                errors.append(f"{key}: review date is after snapshot")
        if item["application"]["as_of"] != data["as_of"]:
            errors.append(f"{key}: application snapshot differs from dataset")
        if item["application"]["state"] != "unknown" and not item["application"]["refs"]:
            errors.append(f"{key}: known application state needs evidence")
        if item.get("start") and item["start"].get("value"):
            s_val = item["start"]["value"][:10]
            for step in item.get("steps", []):
                if step.get("actor") == "student" and step.get("deadline", {}).get("value"):
                    d_val = step["deadline"]["value"][:10]
                    if s_val > d_val:
                        errors.append(f"{key}: inverted start and deadline ({s_val} > {d_val})")
        year = item["eligibility"]["year_limit"]
        if year["mode"] == "range" and year["min"] > year["max"]:
            errors.append(f"{key}: inverted year range")
        refs = []
        def collect(value):
            if isinstance(value, dict):
                if "source" in value and "locator" in value:
                    refs.append(value["source"])
                for child in value.values():
                    collect(child)
            elif isinstance(value, list):
                for child in value:
                    collect(child)
        collect(item)
        has_excerpt = any(source_map.get(s, {}).get("authority") == "official_search_excerpt" for s in refs)
        if has_excerpt and (item["evidence_status"] != "incomplete" or review["status"] != "draft"):
            errors.append(f"{key}: search excerpt cannot pass completeness/review")
        if item["resource_kind"] == "employment_support" and item["participants"]["applicant"] == "student":
            errors.append(f"{key}: this pilot employment entry is unit/institution applied")
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", nargs="?", type=Path, default=ROOT / "data/pilot.json")
    args = parser.parse_args()
    data = read_json(args.path)
    errors = validate(data)
    if errors:
        for error in errors:
            print(error)
        raise SystemExit(1)
    counts = Counter(item["review"]["status"] for item in data["opportunities"])
    print(f"PASS: {len(data['opportunities'])} samples, {len(data['sources'])} sources; reviews={dict(counts)}")
    print("Shape/reference checks only. No eligibility engine, external-link check, or publication approval.")


if __name__ == "__main__":
    main()
