"""方案實體頁、方案索引、sitemap 與 robots.txt。

首頁的方案清單由 JS 從內嵌 JSON 畫出來，不執行 JS 的爬蟲讀不到任何一筆方案。
這裡替每個方案輸出一張實體 HTML，首頁另輸出一份純 HTML 索引連到它們。
頁面只呈現資料裡已有的內容，每頁都列出官方來源；未經來源查證的方案照樣上架，但要標示。
"""
from collections import Counter
from html import escape
import json
import re

CATEGORY_LABELS = {
    "living_tuition": "生活／學費",
    "living_emergency": "急難支持",
    "phd_research": "博士研究",
    "outcome_award": "成果獎",
    "international_conference": "國際會議",
    "overseas_research": "境外研究",
    "indirect_support": "聘任入口",
    "research_tools": "研究工具／算力",
}
DEGREE_LABELS = {"phd": "博士生", "master": "碩士生", "bachelor": "大學生", "k12": "中小學生"}
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def programme_slugs(opportunities):
    """方案網址代號。candidate_id 帶來源版本雜湊，來源一改版就會換，不能當網址；
    opportunity_id 是「方案＋年度梯次」的語意代號。少數重複的再加上首個來源 id 區分。"""
    counts = Counter(o["opportunity_id"] for o in opportunities)
    slugs = {}
    for o in opportunities:
        base = o["opportunity_id"].lower()
        if counts[o["opportunity_id"]] > 1:
            base = f"{base}--{first_source(o) or o['id']}".lower()
        slug = re.sub(r"[^a-z0-9-]+", "-", base).strip("-")
        if not SLUG_RE.match(slug):
            raise ValueError(f"Unusable programme slug: {o['id']}")
        slugs[o["id"]] = slug
    if len(set(slugs.values())) != len(slugs):
        raise ValueError("Programme slugs collide; review opportunity_id uniqueness")
    return slugs


def _refs(value):
    """Collects every {"source": ...} reference inside a record, in reading order."""
    found = []
    if isinstance(value, dict):
        if isinstance(value.get("source"), str):
            found.append(value["source"])
        for v in value.values():
            found.extend(_refs(v))
    elif isinstance(value, list):
        for v in value:
            found.extend(_refs(v))
    return found


def first_source(opportunity):
    refs = _refs(opportunity)
    return refs[0] if refs else None


def programme_sources(opportunity, sources_by_id):
    seen, out = set(), []
    for sid in _refs(opportunity):
        src = sources_by_id.get(sid)
        if sid in seen or not src or not str(src.get("url", "")).startswith(("https://", "http://")):
            continue
        seen.add(sid)
        out.append(src)
    return out


def _text(field):
    return (field or {}).get("text") if isinstance(field, dict) else None


def _row(label, value):
    return f"<dt>{escape(label)}</dt><dd>{escape(value)}</dd>" if value else ""


def page_description(o, title=None):
    category = CATEGORY_LABELS.get(o.get("category"), "獎助")
    who = _text(o.get("eligibility", {}).get("identity")) or ""
    text = f"{title or o['title']}（{category}）。{who}"
    suffix = "請以官方來源為準。"
    if len(text) + len(suffix) > 90:
        text = text[:89 - len(suffix)] + "…"
    return text + suffix


def page_titles(opportunities, sources_by_id):
    """同名方案（不同學校轉發、不同梯次）在標題後加上區分，避免多頁共用同一個 <title>。
    依序試公告單位、梯次、來源標題、來源網域，取第一個能讓同名方案彼此不同的。"""
    from urllib.parse import urlparse

    def source(o):
        return sources_by_id.get(first_source(o) or "") or {}

    hints = [
        lambda o: _text((o.get("organizations") or {}).get("announcer")),
        lambda o: (o.get("cycle") or {}).get("label"),
        lambda o: source(o).get("title"),
        lambda o: urlparse(source(o).get("url") or "").hostname,
    ]
    groups = {}
    for o in sorted(opportunities, key=lambda x: x["id"]):
        groups.setdefault(o["title"], []).append(o)
    titles = {}
    for title, group in groups.items():
        chosen = None
        if len(group) > 1:
            for hint in hints:
                values = [hint(o) for o in group]
                if all(values) and len(set(values)) == len(values) and not any(v in title for v in values):
                    chosen = values
                    break
        if len(group) > 1 and not chosen:
            # 同名、同網域又沒有其他欄位可分：多半是同一方案被收成兩張卡，資料端應合併。
            # 先編號讓標題不重複，網址代號本身不受影響。
            chosen = [f"公告 {i + 1}" for i in range(len(group))]
        for i, o in enumerate(sorted(group, key=lambda x: x["id"])):
            titles[o["id"]] = f"{title}（{chosen[i]}）" if chosen else title
    return titles


def render_programme(o, slug, sources, unverified, site_url, head_extra, footer_html, as_of, title=None):
    url = f"{site_url}p/{slug}/"
    title = title or o["title"]
    category = CATEGORY_LABELS.get(o.get("category"), "獎助")
    elig = o.get("eligibility") or {}
    degrees = "、".join(DEGREE_LABELS.get(d, d) for d in elig.get("degrees") or [])
    orgs = o.get("organizations") or {}
    app = o.get("application") or {}
    rows = "".join([
        _row("類別", category),
        _row("適用學歷", degrees),
        _row("身分資格", _text(elig.get("identity"))),
        _row("補助內容", _text(o.get("benefit"))),
        _row("出資單位", _text(orgs.get("funder"))),
        _row("公告單位", _text(orgs.get("announcer"))),
        _row("收件單位", _text(orgs.get("receiver"))),
        _row("受理狀態", app.get("reason")),
    ])
    steps = "".join(
        f"<li>{escape(s.get('action') or '')}"
        + (f"（{escape(s['deadline']['value'])}）" if (s.get("deadline") or {}).get("value") else "")
        + (f"<br><small>{escape(s['deadline']['note'])}</small>" if (s.get("deadline") or {}).get("note") else "")
        + "</li>"
        for s in o.get("steps") or [] if s.get("action")
    )
    questions = "".join(f"<li>{escape(q)}</li>" for q in o.get("open_questions") or [])
    source_items = "".join(
        f'<li><a href="{escape(s["url"])}" rel="noopener">{escape(s.get("title") or s["url"])}</a>'
        + (f"<br><small>最後核對 {escape(s['checked_on'])}</small>" if s.get("checked_on") else "")
        + "</li>"
        for s in sources
    )
    warning = (
        '<p class="warn">⚠ 未經來源查證：這筆資料不是由來源萃取流程產生，內容可能有誤，請以下方官方來源為準。</p>'
        if unverified else ""
    )
    description = page_description(o, title)
    ld = {
        "@context": "https://schema.org",
        "@graph": [
            {"@type": "WebPage", "@id": url, "url": url, "name": title, "description": description,
             "inLanguage": "zh-Hant", "isPartOf": {"@id": f"{site_url}#website"}},
            {"@type": "BreadcrumbList", "itemListElement": [
                {"@type": "ListItem", "position": 1, "name": "OpenGSA", "item": site_url},
                {"@type": "ListItem", "position": 2, "name": title, "item": url},
            ]},
        ],
    }
    return f"""<!doctype html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(title)}｜OpenGSA</title>
<meta name="description" content="{escape(description)}">
<link rel="canonical" href="{url}">
<meta property="og:type" content="article">
<meta property="og:locale" content="zh_TW">
<meta property="og:title" content="{escape(title)}｜OpenGSA">
<meta property="og:description" content="{escape(description)}">
<meta property="og:url" content="{url}">
<meta property="og:image" content="{site_url}assets/opengsa-social-preview.jpg">
<meta name="twitter:card" content="summary_large_image">
<script type="application/ld+json">{json.dumps(ld, ensure_ascii=False)}</script>
<style>
:root{{--bg:#faf8f3;--fg:#1f2a24;--muted:#5d6b63;--line:#d9d3c4;--accent:#1f5c45;--warn:#8a4b00}}
@media (prefers-color-scheme:dark){{:root{{--bg:#141a17;--fg:#e8eee9;--muted:#a6b3ab;--line:#33403a;--accent:#7fc4a6;--warn:#f0b35a}}}}
body{{margin:0;background:var(--bg);color:var(--fg);font:16px/1.7 system-ui,"Noto Sans TC",sans-serif}}
main,header,footer{{max-width:760px;margin:0 auto;padding:0 16px}}
header{{padding-top:20px}} a{{color:var(--accent)}}
h1{{font-size:1.6rem;line-height:1.35;margin:.4em 0}}
dl{{display:grid;grid-template-columns:7em 1fr;gap:6px 12px;margin:0}} dt{{color:var(--muted)}} dd{{margin:0}}
section{{border-top:1px solid var(--line);margin-top:20px;padding-top:12px}}
.warn{{color:var(--warn);font-weight:600}} small{{color:var(--muted)}}
footer{{color:var(--muted);font-size:.85rem;padding-bottom:32px;margin-top:28px}}
@media (max-width:520px){{dl{{grid-template-columns:1fr}}dt{{margin-top:8px}}}}
</style>
{head_extra}
</head>
<body>
<header><a href="{site_url}">← OpenGSA 臺灣碩博士獎助與研究生權益</a></header>
<main>
<h1>{escape(title)}</h1>
{warning}
<p>OpenGSA 整理的來源摘要，非資格核定；申請前請以官方來源為準。資料快照 {escape(as_of)}。</p>
<section><h2>重點</h2><dl>{rows}</dl></section>
{f'<section><h2>申請步驟</h2><ol>{steps}</ol></section>' if steps else ''}
<section><h2>官方來源</h2>{f'<ul>{source_items}</ul>' if source_items else '<p>尚無可公開的來源連結。</p>'}</section>
{f'<section><h2>尚待確認</h2><ul>{questions}</ul></section>' if questions else ''}
<section><h2>在 OpenGSA 中比較與安排</h2><p><a href="{site_url}?tab=detail&amp;id={escape(o['id'])}">開啟互動詳情</a>：與其他方案並排比較、加入我的時間軸。</p></section>
</main>
<footer>{footer_html}</footer>
</body>
</html>
"""


def index_section(opportunities, slugs, unverified_ids):
    """首頁的純 HTML 方案索引：不執行 JS 也讀得到每一筆方案。"""
    groups = {}
    for o in sorted(opportunities, key=lambda x: x["title"]):
        groups.setdefault(o.get("category"), []).append(o)
    blocks = []
    for cat in CATEGORY_LABELS:
        items = groups.get(cat)
        if not items:
            continue
        lis = "".join(
            f'<li><a href="p/{slugs[o["id"]]}/">{escape(o["title"])}</a>'
            + (" <small>⚠ 未經來源查證</small>" if o["id"] in unverified_ids else "") + "</li>"
            for o in items
        )
        blocks.append(f"<h3>{escape(CATEGORY_LABELS[cat])}（{len(items)}）</h3><ul>{lis}</ul>")
    return (
        '<section id="programme-index" class="programme-index" aria-labelledby="programme-index-title">'
        f'<h2 id="programme-index-title">收錄方案一覽（{len(opportunities)} 筆）</h2>'
        "<p>每筆方案都有獨立頁面，附官方來源連結。</p>"
        f'<details><summary>展開全部方案</summary>{"".join(blocks)}</details></section>'
    )


def sitemap_xml(site_url, slugs):
    urls = [site_url] + [f"{site_url}p/{s}/" for s in sorted(slugs.values())]
    body = "".join(f"<url><loc>{escape(u)}</loc></url>" for u in urls)
    return f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{body}</urlset>\n'


def robots_txt(site_url):
    # 線上的 robots.txt 由 Cloudflare 代管規則產生（屬 mattye.dev 整個 zone）；這份只補 Sitemap 位置。
    return f"User-agent: *\nAllow: /\n\nSitemap: {site_url}sitemap.xml\n"


def website_jsonld(site_url, description):
    return json.dumps({
        "@context": "https://schema.org",
        "@type": "WebSite",
        "@id": f"{site_url}#website",
        "url": site_url,
        "name": "OpenGSA",
        "alternateName": "OpenGSA 臺灣碩博士獎助與研究生權益",
        "description": description,
        "inLanguage": "zh-Hant",
        "publisher": {"@type": "Person", "name": "Matt Ye", "url": "https://mattye.dev/"},
    }, ensure_ascii=False)
