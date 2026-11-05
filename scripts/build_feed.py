#!/usr/bin/env python3
"""Build RSS 2.0 and Atom feeds for OpenGSA public scholarship radar.

Generates:
1. feed.xml: Comprehensive feed of all 236 schemes and recent revisions.
2. feed-deadlines.xml: Focused feed of schemes with confirmed/impending deadlines.
"""
from datetime import datetime, timezone, timedelta
from email.utils import format_datetime
from html import escape
from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
SITE_URL = "https://matt-ye.github.io/opengsa/"
FEED_URL = f"{SITE_URL}feed.xml"
DEADLINES_FEED_URL = f"{SITE_URL}feed-deadlines.xml"
TAIPEI_TZ = timezone(timedelta(hours=8))


def format_rfc822(dt: datetime) -> str:
    """Format datetime as RFC 822 / 2822 for RSS 2.0."""
    return format_datetime(dt)


def generate_rss_xml(title: str, feed_link: str, description: str, items: list[dict], build_time: datetime) -> str:
    """Generate valid RSS 2.0 XML string."""
    xml_items = []
    for item in items:
        cat_tag = f"      <category>{escape(item['category'])}</category>\n" if item.get("category") else ""
        xml_items.append(
            f"""    <item>
      <title>{escape(item['title'])}</title>
      <link>{escape(item['link'])}</link>
      <description>{escape(item['description'])}</description>
{cat_tag}      <guid isPermaLink="false">{escape(item['guid'])}</guid>
      <pubDate>{format_rfc822(item['pubDate'])}</pubDate>
    </item>"""
        )

    items_block = "\n".join(xml_items)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>{escape(title)}</title>
    <link>{escape(SITE_URL)}</link>
    <description>{escape(description)}</description>
    <language>zh-TW</language>
    <lastBuildDate>{format_rfc822(build_time)}</lastBuildDate>
    <atom:link href="{escape(feed_link)}" rel="self" type="application/rss+xml"/>
{items_block}
  </channel>
</rss>
"""


def build_feeds(output_dir: Path, candidates: list[dict], observations: dict) -> tuple[Path, Path]:
    """Build and save feed.xml and feed-deadlines.xml in output_dir."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.now(TAIPEI_TZ)

    records = observations.get("records", {})
    all_feed_items = []
    deadlines_feed_items = []

    for cand in candidates:
        cid = cand.get("candidate_id") or cand.get("id")
        title = cand.get("title", "未命名獎助方案")
        cat = cand.get("category", "other")
        opp_id = cand.get("opportunity_id") or cand.get("program_key") or cid
        item_link = f"{SITE_URL}?id={opp_id}"

        # Benefit and eligibility summary
        benefit_text = cand.get("benefit", {}).get("text", "獎助內容詳見官方簡章")
        ident = cand.get("eligibility", {}).get("identity", {}).get("text", "資格條件請見來源公告")
        desc = f"【身分資格】{ident} ｜ 【獎助內容】{benefit_text}"

        rec = records.get(cid, {})
        obs_time_str = rec.get("observed_at") or cand.get("source_metadata", {}).get("observed_at")
        if obs_time_str:
            try:
                item_date = datetime.fromisoformat(obs_time_str.replace("Z", "+00:00")).astimezone(TAIPEI_TZ)
            except Exception:
                item_date = now
        else:
            item_date = now

        item_dict = {
            "title": title,
            "link": item_link,
            "description": desc,
            "category": cat,
            "guid": cid,
            "pubDate": item_date,
        }
        all_feed_items.append(item_dict)

        # Check for confirmed student deadlines
        steps = cand.get("schedule", {}).get("steps", [])
        student_deadline = None
        for step in steps:
            if step.get("actor") == "student" and step.get("deadline", {}).get("kind") in ("date", "datetime"):
                val = step.get("deadline", {}).get("value")
                if val:
                    student_deadline = val
                    break

        # Also check time policy or radar record
        if not student_deadline and rec.get("time_dates", {}).get("end", {}).get("kind") in ("date", "datetime"):
            student_deadline = rec["time_dates"]["end"].get("value")

        if student_deadline:
            deadline_desc = f"【申請截止提醒：{student_deadline}】{desc}"
            deadlines_feed_items.append({
                "title": f"⏱️ [即將截止] {title}（截止日：{student_deadline}）",
                "link": item_link,
                "description": deadline_desc,
                "category": cat,
                "guid": f"{cid}-deadline",
                "pubDate": item_date,
            })

    # Sort feeds: latest publication/observation first
    all_feed_items.sort(key=lambda x: x["pubDate"], reverse=True)
    deadlines_feed_items.sort(key=lambda x: x["pubDate"], reverse=True)

    # 1. Main Feed
    main_xml = generate_rss_xml(
        title="OpenGSA 獎助雷達最新動態 (All Scholarships)",
        feed_link=FEED_URL,
        description="OpenGSA 全庫跨部會、各大專院校與民間企業獎助學金最新公告與觀測紀錄",
        items=all_feed_items,
        build_time=now,
    )
    main_file = output_dir / "feed.xml"
    main_file.write_text(main_xml, encoding="utf-8")

    # 2. Deadlines Feed
    deadlines_xml = generate_rss_xml(
        title="OpenGSA 獎助截止倒數提醒 (Scholarship Deadlines)",
        feed_link=DEADLINES_FEED_URL,
        description="OpenGSA 獎助學金與研究補助時程截止提醒通知",
        items=deadlines_feed_items,
        build_time=now,
    )
    deadlines_file = output_dir / "feed-deadlines.xml"
    deadlines_file.write_text(deadlines_xml, encoding="utf-8")

    return main_file, deadlines_file


if __name__ == "__main__":
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from scripts.build_site import load_full_library
    cands, obs = load_full_library(ROOT)
    out = ROOT / "dist/test-feed" if len(sys.argv) < 2 else Path(sys.argv[1])
    m, d = build_feeds(out, cands["candidates"], obs)
    print(f"Generated RSS Feeds:\n- {m}\n- {d}")
