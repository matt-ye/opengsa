"""有限公開來源掃描；只產生待覆核證據，不改寫網站資料。"""
import argparse
import base64
from copy import deepcopy
import hashlib
import html
import json
from pathlib import Path
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from urllib.parse import quote, unquote, urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
VERSION = "scanner-1"
AGENT = "OpenGSA/0.1 (+https://github.com/matt-ye/opengsa)"
SKIP = re.compile(r"名冊|名單|獲獎|得獎|姓名|學號|身分證|jsessionid|password|token=|login|登入", re.I)
CONTACT = re.compile(r"@|電話|聯絡|承辦|傳真|住址|通訊地址|\b0\d{1,3}[- ]\d{6,}")
KINDS = {
    "deadline_text": r"截止|期限|四週|兩個月|申請時間|受理期間|送達|彙送",
    "eligibility_text": r"資格|年級|在學|候選人|國籍|不得|不含|僅限",
    "amount_text": r"[\d,]+\s*(?:元|萬元)|新[臺台]幣",
    "compatibility_text": r"兼領|重複|分攤|同年度|同性質",
    "version_text": r"修正|修訂|生效|施行|適用",
}


class ScanError(Exception):
    pass


def normalized(text):
    return re.sub(r"\s+", " ", text).strip()


def digest(value):
    if not isinstance(value, bytes):
        value = json.dumps(value, sort_keys=True, ensure_ascii=False).encode()
    return hashlib.sha256(value).hexdigest()


def safe_url(url, hosts):
    parts = urlsplit(url)
    if (parts.scheme != "https" or parts.hostname not in hosts or parts.username or parts.password
            or parts.port not in (None, 443) or SKIP.search(unquote(url))):
        raise ScanError("url_not_allowed")
    return urlunsplit((parts.scheme, parts.netloc, quote(unquote(parts.path), safe="/()-._~"),
                       quote(unquote(parts.query), safe="=&-._~"), ""))


def robots_policy(text, url):
    """保守子集：適用群組任何Disallow皆禁止，不自動採Allow例外。"""
    applies = False
    agents = []
    in_rules = False
    delay = 0
    target = unquote(urlsplit(url).path + ("?" + urlsplit(url).query if urlsplit(url).query else ""))
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if ":" not in line:
            continue
        key, value = (p.strip() for p in line.split(":", 1))
        key = key.lower()
        if key == "user-agent":
            if in_rules:
                agents = []
                in_rules = False
            agents.append(value.lower())
            applies = any(a == "*" or a in AGENT.lower().split("/", 1)[0] for a in agents if a)
        else:
            in_rules = True
            if not applies:
                continue
            if key == "disallow" and value:
                end = value.endswith("$")
                pattern = re.escape(unquote(value[:-1] if end else value)).replace(r"\*", ".*")
                if re.match(pattern + ("$" if end else ""), target):
                    return False, delay
            if key == "crawl-delay":
                try:
                    seconds = float(value)
                    if 0 <= seconds <= 86400:
                        delay = max(delay, seconds)
                except ValueError:
                    pass
    return True, delay


def node_get(url, headers, limit):
    result = subprocess.run(["node", str(ROOT / "scripts/http_get.cjs")],
                            input=json.dumps({"url": url, "headers": headers, "limit": limit}).encode(),
                            capture_output=True, timeout=23)
    if result.returncode:
        raise ScanError("transport_error")
    response = json.loads(result.stdout)
    response["body"] = base64.b64decode(response["body"], validate=True)
    return response


class Fetcher:
    def __init__(self, config, transport=node_get, clock=time.monotonic, sleeper=time.sleep):
        self.config, self.transport, self.clock, self.sleeper = config, transport, clock, sleeper
        self.started, self.count = clock(), 0
        self.last, self.robots, self.blocked, self.delays, self.robots_checks = {}, {}, {}, {}, {}
        self.in_memory_blocks = {}

    def request(self, url, headers, limit):
        url = safe_url(url, self.config["allowed_hosts"])
        host = urlsplit(url).hostname
        if host in self.blocked:
            raise ScanError(self.blocked[host])
        wait = max(0, self.last.get(host, -1000000) + max(self.config["minimum_host_interval_seconds"], self.delays.get(host, 0)) - self.clock())
        if self.count >= self.config["max_requests"] or self.clock() + wait - self.started >= self.config["max_run_seconds"]:
            raise ScanError("run_budget_exhausted")
        self.sleeper(wait)
        self.count += 1
        self.last[host] = self.clock()
        response = self.transport(url, {"User-Agent": AGENT, "Accept-Encoding": "identity", **headers}, limit)
        if len(response["body"]) > limit:
            raise ScanError("response_too_large")
        if response["status"] in (403, 429):
            reason = f"http_{response['status']}_host_paused"
            self.blocked[host] = reason
            raise ScanError(reason)
        return response

    def permitted(self, url):
        host = urlsplit(url).hostname
        if host not in self.robots:
            robots_url = f"https://{host}/robots.txt"
            response = self.follow(robots_url, {}, 512000, robots=True)
            self.robots_checks[host] = {"status": response["status"], "sha256": digest(response["body"])}
            if response["status"] == 404:
                self.robots[host] = ""  # 404無規則；不是授權重製全文。
            elif response["status"] == 200:
                content = response["body"].decode("utf-8-sig", errors="replace")
                if "<html" in content.lower() or "<!doctype" in content.lower():
                    raise ScanError("robots_not_plain_rules")
                self.robots[host] = content
            else:
                raise ScanError("robots_unavailable")
        allowed, delay = robots_policy(self.robots[host], url)
        self.delays[host] = max(self.delays.get(host, 0), delay)
        if not allowed:
            raise ScanError("robots_denied")

    def follow(self, url, headers, limit, robots=False):
        for _ in range(4):
            url = safe_url(url, self.config["allowed_hosts"])
            if not robots:
                self.permitted(url)
            response = self.request(url, headers, limit)
            if response["status"] in (301, 302, 303, 307, 308):
                url = urljoin(url, response["headers"].get("location", ""))
                continue
            response["url"] = url
            return response
        raise ScanError("redirect_limit")

    def get(self, url, previous, limit):
        headers = {}
        if previous.get("etag"):
            headers["If-None-Match"] = previous["etag"]
        if previous.get("last_modified"):
            headers["If-Modified-Since"] = previous["last_modified"]
        for attempt in range(2):
            response = self.follow(url, headers, limit)
            if response["status"] >= 500 and response["headers"].get("retry-after"):
                self.blocked[urlsplit(url).hostname] = "service_retry_after_deferred"
                raise ScanError("service_retry_after_deferred")
            if response["status"] < 500 or attempt:
                return response
        raise ScanError("unreachable")


def html_document(data, source, url, hosts):
    soup = BeautifulSoup(data, "html.parser")
    nodes = soup.select(source["body_selector"])
    roots = [node for node in nodes if not any(parent in nodes for parent in node.parents)]
    if not roots:
        raise ScanError("body_selector_changed")
    attachments = {}
    attachment_roots = roots + (soup.select(source["attachment_selector"]) if source.get("attachment_selector") else [])
    for root in attachment_roots:
        for anchor in root.select("a[href]"):
            href = urljoin(url, anchor["href"])
            label = normalized(anchor.get_text(" ", strip=True) + " " + unquote(urlsplit(href).path.rsplit("/", 1)[-1]))
            if SKIP.search(label + unquote(href)):
                anchor.decompose()
                continue
            if urlsplit(href).path.lower().endswith(".pdf") and any(term in label for term in source["pdf_include"]):
                try:
                    href = safe_url(href, hosts)
                except ScanError:
                    continue
                attachments[href] = {"url": href, "title": label[:100]}
    for root in roots:
        for node in root.select("script,style,nav,footer,form,noscript"):
            node.decompose()
    lines = []
    for root in roots:
        lines.extend(normalized(line) for line in root.get_text("\n", strip=True).splitlines())
    if source.get("start_marker"):
        marker = source["start_marker"]
        start = next((i for i, line in enumerate(lines) if marker in line), None)
        if start is None:
            raise ScanError("start_marker_changed")
        lines = lines[start:]
    text = normalized(" ".join(lines))
    compact = re.sub(r"\s+", "", text)
    if len(text) < 80 or any(re.sub(r"\s+", "", term) not in compact for term in source["required_markers"]):
        raise ScanError("required_marker_missing")
    # 序號是此版萃取正文的定位，非原HTML原始碼行號。
    blocks = [{"locator": f"{source['body_selector']} / text-block {i}", "text": line}
              for i, line in enumerate(lines, 1) if line]
    return blocks, list(attachments.values())[:source["max_pdfs"]]


def pdf_document(data):
    result = subprocess.run([sys.executable, str(ROOT / "scripts/pdf_extract.py")], input=data,
                            capture_output=True, timeout=20)
    if result.returncode:
        raise ScanError("pdf_requires_manual_review")
    pages = json.loads(result.stdout)
    return [{"locator": f"PDF page {page['page']}", "text": normalized(line)}
            for page in pages for line in page["text"].splitlines() if normalized(line)]


def evidence_mentions(blocks, mode="short_excerpt"):
    facts, remaining, seen = [], 120, set()
    for kind, pattern in KINDS.items():
        for block in blocks:
            text = normalized(block["text"])
            if not re.search(pattern, text) or SKIP.search(text) or CONTACT.search(text):
                continue
            match = re.search(pattern, text)
            excerpt = text[max(0, match.start() - 15):max(0, match.start() - 15) + min(50, remaining)]
            if len(excerpt) < 8 or (kind, excerpt) in seen:
                continue
            facts.append({"field": kind, "normalized_value": None, "evidence": excerpt if mode=="short_excerpt" else None,
                          "evidence_sha256": digest(excerpt),
                          "locator": block["locator"], "status": "candidate_requires_human_review"})
            remaining -= len(excerpt)
            seen.add((kind, excerpt))
            break
    return facts


def scan(config, previous=None, fetcher=None, resolved=None):
    previous = previous or {"documents": {}, "pending": {}}
    state = deepcopy(previous)
    state.update({"version": VERSION, "documents": state.get("documents", {}), "pending": state.get("pending", {})})
    fetcher = fetcher or Fetcher(config)
    resolved = resolved or set()
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    reports, changed = [], 0
    queue = [(source, source["url"], "html") for source in config["sources"]]
    while queue:
        source, original_url, kind = queue.pop(0)
        old = previous["documents"].get(original_url, {})
        profile = digest([VERSION, source])
        fetch_previous = old if old.get("profile_sha256") == profile else {}
        report = {"source_id": source["id"], "url": original_url, "kind": kind}
        try:
            if changed >= config["max_changed_documents"]:
                raise ScanError("changed_document_budget_deferred")
            if len(state["pending"]) >= config["max_pending_candidates"]:
                raise ScanError("review_backlog_full")
            response = fetcher.get(original_url, fetch_previous, 10 * 1024 * 1024 if kind == "pdf" else 2 * 1024 * 1024)
            status = response["status"]
            if status == 304:
                if not fetch_previous.get("semantic_sha256"):
                    raise ScanError("unexpected_304_without_baseline")
                document = {**old, "last_checked_at": now}
                report["status"] = "unchanged_304"
            elif status == 200:
                content_type = response["headers"].get("content-type", "").lower()
                if kind == "html" and "text/html" not in content_type:
                    raise ScanError("unexpected_content_type")
                if kind == "pdf":
                    blocks, attachments = pdf_document(response["body"]), []
                else:
                    blocks, attachments = html_document(response["body"], source, response["url"], config["allowed_hosts"])
                if hasattr(fetcher, "in_memory_blocks"):
                    fetcher.in_memory_blocks[original_url] = blocks
                semantic = digest([[normalized(b["text"]) for b in blocks], attachments])
                document = {"raw_sha256": digest(response["body"]), "semantic_sha256": semantic,
                            "etag": response["headers"].get("etag"), "last_modified": response["headers"].get("last-modified"),
                            "attachments": attachments, "last_checked_at": now, "final_url": response["url"], "profile_sha256": profile}
                report["status"] = "unchanged" if old.get("semantic_sha256") == semantic and old.get("profile_sha256") == profile else "changed"
                if report["status"] == "changed":
                    changed += 1
                    revision = digest([original_url, semantic, profile])
                    candidate = {"id": revision, "source_id": source["id"], "url": original_url,
                                 "revision": document, "observed_at": now, "parser": VERSION,
                                 "review_status": "pending", "facts": evidence_mentions(blocks, source.get("evidence_mode", "short_excerpt")),
                                 "extraction_scope": "keyword_evidence_only_not_complete_record",
                                 "evidence_mode": source.get("evidence_mode", "short_excerpt"),
                                 "review_note": source["review_note"]}
                    if revision not in resolved:
                        state["pending"][revision] = candidate
            else:
                raise ScanError(f"http_{status}")
            state["documents"][original_url] = document
            if kind == "html":
                queue.extend((source, item["url"], "pdf") for item in document.get("attachments", []))
        except (ScanError, subprocess.TimeoutExpired) as error:
            report["status"] = str(error) if isinstance(error, ScanError) else "parser_or_request_timeout"
            report["retained_previous"] = bool(old)
        except Exception as error:
            report["status"] = "unexpected_" + type(error).__name__
            report["retained_previous"] = bool(old)
        reports.append(report)
    state["last_run_at"] = now
    report = {"version": VERSION, "observed_at": now, "baseline_missing": not bool(previous["documents"]),
              "http_requests": fetcher.count, "changed_documents": changed, "documents": reports,
              "pending_candidates": len(state["pending"]), "model_calls": 0, "official_data_modified": False,
              "robots_checks": getattr(fetcher, "robots_checks", {})}
    return state, report


def markdown_report(state, report):
    def cell(value):
        return html.escape(str(value)).replace("|", "&#124;").replace("`", "&#96;").replace("[", "&#91;").replace("]", "&#93;").replace("\n", " ")
    lines = ["# OpenGSA來源掃描候選報告", "", "僅為待覆核線索；不直接更新正式資料、資格或通知。", "",
             f"HTTP {report['http_requests']}次；變更{report['changed_documents']}份；待覆核{report['pending_candidates']}筆；模型呼叫0次。",
             "", "| 來源 | 類型 | 狀態 |", "|---|---|---|"]
    lines.extend(f"| {cell(d['source_id'])} | {d['kind']} | {cell(d['status'])} |" for d in report["documents"])
    lines.extend(["", "## 待覆核欄位線索", "", "| 來源URL | 欄位 | 原文短證據 | 定位 |", "|---|---|---|---|"])
    for candidate in state["pending"].values():
        for fact in candidate["facts"]:
            lines.append(f"| {cell(candidate['url'])} | {fact['field']} | {cell(fact['evidence'] or '版權限制：僅保留雜湊，請至來源核對')} | {cell(fact['locator'])} |")
    return "\n".join(lines) + "\n"


def run():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "data/scan-sources.json")
    parser.add_argument("--state", type=Path, default=ROOT / "work/scanner/state.json")
    parser.add_argument("--output", type=Path, default=ROOT / "work/scanner/report")
    parser.add_argument("--reviews", type=Path, default=ROOT / "data/scan-reviews.json")
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    if not (0 < config["max_requests"] <= 20 and 0 < config["max_changed_documents"] <= 5
            and 0 < config["max_pending_candidates"] <= 24 and config["minimum_host_interval_seconds"] >= 3
            and 0 < config["max_run_seconds"] <= 180):
        parser.error("Configuration exceeds the bounded scan policy")
    old = json.loads(args.state.read_text(encoding="utf-8")) if args.state.exists() else None
    if old and old.get("version") != VERSION:
        parser.error("State version differs; preserve it and select a new state path")
    resolved = set()
    reviews_payload = json.loads(args.reviews.read_text(encoding="utf-8"))
    for review in reviews_payload["reviews"]:
        if not all(review.get(key) for key in ["revision_id", "reviewer", "reason", "reviewed_on"]) or review.get("action") not in ["noted", "applied", "dismissed"]:
            parser.error("Incomplete review ledger entry")
        resolved.add(review["revision_id"])
        if old:
            old.get("pending", {}).pop(review["revision_id"], None)
    fetcher = Fetcher(config)
    state, report = scan(config, old, fetcher=fetcher, resolved=resolved)
    args.state.parent.mkdir(parents=True, exist_ok=True)
    temp = args.state.with_suffix(".new.json")
    temp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(args.state)
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "scan-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (args.output / "candidates.json").write_text(json.dumps(list(state["pending"].values()), ensure_ascii=False, indent=2), encoding="utf-8")
    (args.output / "summary.md").write_text(markdown_report(state, report), encoding="utf-8")
    from scripts.extract_candidates import refetch_and_extract_candidates
    from scripts.review_candidates import build_review_report
    pilot_data = json.loads((ROOT / "data/pilot.json").read_text(encoding="utf-8"))
    bundle, refetch_statuses = refetch_and_extract_candidates(
        list(state["pending"].values()),
        config,
        fetcher=fetcher,
        as_of=report["observed_at"][:10],
        in_memory_blocks_by_url=fetcher.in_memory_blocks,
        allow_network_refetch=False,
    )
    verified_bundle, review_summary, review_md = build_review_report(
        bundle,
        pilot_data,
        scan_report=report,
        reviews_data=reviews_payload,
        refetch_statuses=refetch_statuses,
    )
    (args.output / "structured-candidates.json").write_text(json.dumps(verified_bundle, ensure_ascii=False, indent=2), encoding="utf-8")
    (args.output / "review-diff.json").write_text(json.dumps(review_summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (args.output / "review-summary.md").write_text(review_md, encoding="utf-8")
    print(json.dumps({key: report[key] for key in ["http_requests", "changed_documents", "pending_candidates", "model_calls", "official_data_modified"]}))
    return report


if __name__ == "__main__":
    report = run()
    if not any(d["status"] in ["changed", "unchanged", "unchanged_304"] for d in report["documents"]):
        sys.exit(1)
