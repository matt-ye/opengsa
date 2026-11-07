"""把維護者核可的來源提交 Issue 轉成待處理請求。不抓取、不寫正式資料。

Issue 內容是公開輸入：這裡只取驗證過的網址與固定選項，名稱和說明不會帶進後續流程或留言。
"""
import argparse
import ipaddress
import json
from pathlib import Path
import re
import socket
import sys
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.audit_sources import canonical_url
from scripts.scan_sources import ScanError, safe_url

APPROVAL_LABEL = "source-approved"
LOCAL_SUFFIXES = (".localhost", ".local", ".internal")
# 對應 expand_sources.profile_for 的路由分類；只是初步標籤，不代表資格判斷。
CATEGORIES = {
    "獎學金／研究獎助": "scholarship",
    "研究成果獎／學術獎項": "award",
    "國際會議／出國交流補助": "mobility",
    "境外研究／研修／實習": "mobility",
    "學費／生活／急難／住宿支持": "living",
    "RA／TA 聘任或權益資訊": "rights",
    "研究工具／AI／算力／學生優惠": "ai",
    "公告索引／其他／不確定": "scholarship",
}
REASONS = {
    "not_approved_by_owner": "只有 repo owner 加上標籤才會處理。",
    "missing_url": "表單裡找不到來源網址。",
    "invalid_url": "網址格式不正確，或不是公開的 https 網址。",
    "private_host": "網址指向內部位址，不處理。",
    "restricted_url": "網址含登入、名冊或個資相關字樣，不處理。",
}


class IntakeRejected(Exception):
    pass


def form_fields(body):
    """解析 GitHub Issue 表單：每個欄位是 `### 標題` 加內容，空值是 _No response_。"""
    fields, current = {}, None
    for line in (body or "").splitlines():
        heading = re.fullmatch(r"###\s+(.+?)\s*", line)
        if heading:
            current = heading[1]
            fields[current] = []
        elif current:
            fields[current].append(line)
    cleaned = {key: "\n".join(lines).strip() for key, lines in fields.items()}
    return {key: value for key, value in cleaned.items() if value and value != "_No response_"}


def looks_public(host):
    """擋內部位址。瀏覽器式解析會把 127.1、0x7f.1 當 IP，也會把全形數字與句點轉成半形，所以只收純 ASCII 網域。"""
    if not re.fullmatch(r"[a-z0-9-]+(\.[a-z0-9-]+)+", host):
        return False
    # 最後一段是數字或 0x 開頭，會被當成 IPv4。
    if re.fullmatch(r"\d+|0x[0-9a-f]*", host.rsplit(".", 1)[-1]) or host.endswith(LOCAL_SUFFIXES):
        return False
    return resolves_public(host)


def resolves_public(host):
    """解析得到內部位址就拒絕（例如 127.0.0.1.nip.io）。解析失敗不算內部，之後抓取自然會失敗。"""
    try:
        addresses = {info[4][0] for info in socket.getaddrinfo(host, 443)}
    except OSError:
        return True
    return all(ipaddress.ip_address(address.split("%")[0]).is_global for address in addresses)


def validated_url(raw):
    """回傳可抓取的網址；公開輸入一律先過這裡。"""
    raw = (raw or "").strip()
    if not raw:
        raise IntakeRejected("missing_url")
    if len(raw) > 2000 or re.search(r"\s", raw):
        raise IntakeRejected("invalid_url")
    try:
        parts = urlsplit(raw)
        host = (parts.hostname or "").lower()
    except ValueError as error:
        raise IntakeRejected("invalid_url") from error
    if not host:
        raise IntakeRejected("invalid_url")
    if not looks_public(host):
        raise IntakeRejected("private_host")
    if parts.scheme != "https" or parts.username or parts.password or parts.port not in (None, 443):
        raise IntakeRejected("invalid_url")
    try:
        return canonical_url(safe_url(raw, {host}))
    except ScanError as error:
        raise IntakeRejected("restricted_url") from error


def build_request(event, registered_urls=()):
    """從 issues 事件產生請求。不是 owner 核可的事件一律拒絕，即使 workflow 條件被改壞。"""
    sender = event.get("sender", {}).get("login")
    owner = event.get("repository", {}).get("owner", {}).get("login")
    label = event.get("label", {}).get("name")
    if event.get("action") != "labeled" or label != APPROVAL_LABEL or not owner or sender != owner:
        raise IntakeRejected("not_approved_by_owner")
    fields = form_fields(event.get("issue", {}).get("body"))
    url = validated_url(fields.get("公開來源網址"))
    return {"schema_version": "source-intake-1", "status": "accepted", "issue": int(event["issue"]["number"]),
            "url": url, "host": urlsplit(url).hostname, "category": CATEGORIES.get(fields.get("資源類型"), "scholarship"),
            "approved_by": sender, "already_registered": url in {canonical_url(u) for u in registered_urls},
            "official_data_modified": False, "published": False}


def comment(request=None, reason=None):
    if reason:
        return f"來源未處理：{REASONS[reason]}\n"
    note = "這個網址已登記過。" if request["already_registered"] else "這是新網址。"
    # 後續抓取若中斷，留言會停在這段，所以要說清楚沒有完成。
    return f"已收到核可，來源網址：`{request['url']}`。{note}\n\n抓取與萃取沒有完成，請看 Actions 紀錄。網站資料沒有改動。\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--event", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    event = json.loads(args.event.read_text(encoding="utf-8"))
    config = json.loads((ROOT / "data/scan-sources.json").read_text(encoding="utf-8"))
    args.output.mkdir(parents=True, exist_ok=True)
    try:
        request = build_request(event, [source["url"] for source in config["sources"]])
        text = comment(request)
    except IntakeRejected as error:
        request = {"schema_version": "source-intake-1", "status": "rejected", "reason": str(error)}
        text = comment(reason=str(error))
    (args.output / "request.json").write_text(json.dumps(request, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (args.output / "comment.md").write_text(text, encoding="utf-8")
    print(json.dumps({key: request.get(key) for key in ("status", "reason", "already_registered")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
