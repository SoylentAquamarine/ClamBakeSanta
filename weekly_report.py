#!/usr/bin/env python3
"""
weekly_report.py
"""

from __future__ import annotations

import os
import smtplib
from datetime import date, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import List, Dict

from framework.config import load_config


# ── Data ──────────────────────────────────────────────────────────────────────

def collect_week(engagement: dict, start: date, end: date) -> List[Dict]:
    records = []

    for date_str, day_data in engagement.items():
        try:
            d = date.fromisoformat(date_str)
        except ValueError:
            continue

        if not (start <= d < end):
            continue

        for tag, entry in day_data.items():
            records.append({
                "date": date_str,
                "tag": tag,
                "theme": entry.get("theme", tag),
                "haiku": entry.get("haiku", ""),
                "platforms": entry.get("platforms", {}),
                "total_score": entry.get("total_score", 0),
            })

    return sorted(records, key=lambda r: r["total_score"], reverse=True)


def platform_leader(records, platform):
    candidates = [
        r for r in records
        if platform in r.get("platforms", {})
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda r: r["platforms"][platform].get("score", 0))


# ── Styling ───────────────────────────────────────────────────────────────────

_PALETTE = {
    "green": "#2c6e49",
    "light_bg": "#fdfaf5",
    "border": "#e0d9cc",
    "text": "#333",
    "muted": "#666",
}

_MEDAL = ["🥇", "🥈", "🥉", "4.", "5."]


# ── HTML blocks ───────────────────────────────────────────────────────────────

def haiku_card(r, i):
    medal = _MEDAL[i] if i < len(_MEDAL) else f"{i+1}."

    lines = r["haiku"].split("\n")
    poem = "<br>".join(lines[:3])

    return f"""
<div style="margin:1rem 0;padding:1rem;background:{_PALETTE['light_bg']};
border-left:4px solid {_PALETTE['green']};">

<b>{medal} {r['theme']}</b>
<span style="float:right;">⭐ {r['total_score']}</span>

<div style="margin-top:0.5rem;font-family:serif;line-height:1.6;">
{poem}
</div>

<div style="font-size:0.8rem;color:{_PALETTE['muted']};">
{r['date']}
</div>

</div>
"""


def section(title, body):
    return f"""
<h2 style="color:{_PALETTE['green']};border-bottom:1px solid {_PALETTE['border']};">
{title}
</h2>
{body}
"""


# ── Report builder ────────────────────────────────────────────────────────────

def build_html_report(week_records, week_start, week_end, prior_total, site_url, title="Weekly Report"):

    total_posts = len(week_records)
    total_score = sum(r["total_score"] for r in week_records)
    active_plats = set(p for r in week_records for p in r.get("platforms", {}))

    if prior_total:
        pct = ((total_score - prior_total) / prior_total) * 100
        trend = f"{'↑' if pct >= 0 else '↓'} {abs(pct):.0f}% vs prior week"
    else:
        trend = "First week" if total_posts else "No data"

    date_range = f"{week_start} → {week_end}"

    top5 = "".join(haiku_card(r, i) for i, r in enumerate(week_records[:5]))

    leaders = ""
    for plat in ["mastodon", "bluesky", "reddit", "tumblr", "wordpress"]:
        lead = platform_leader(week_records, plat)
        if lead:
            leaders += f"<div><b>{plat}</b>: {lead['theme']}</div>"

    table = ""
    for i, r in enumerate(week_records):
        table += f"<tr><td>{i+1}</td><td>{r['date']}</td><td>{r['theme']}</td><td>{r['total_score']}</td></tr>"

    stats_section = section("Stats", f"""
<p>Date range: {date_range}</p>
<p>Posts: {total_posts}</p>
<p>Score: {total_score}</p>
<p>Platforms: {len(active_plats)}</p>
<p>{trend}</p>
""")

    top5_section = section("Top 5", top5)
    leaders_section = section("Leaders", leaders)
    all_section = section("All", f"<table>{table}</table>")

    return f"""
<html>
<body style="font-family:system-ui;max-width:700px;margin:auto;">

<h1>{title}</h1>

{stats_section}

{top5_section}

{leaders_section}

{all_section}

<hr>
<p><a href="{site_url}">Site</a></p>

</body>
</html>
"""

# ── Email ─────────────────────────────────────────────────────────────────────

def send_email(subject, html):
    gmail = os.environ.get("GMAIL_ADDRESS")
    pw = os.environ.get("GMAIL_APP_PASSWORD")
    to = os.environ.get("REPORT_EMAIL")

    if not gmail or not pw or not to:
        raise ValueError("Missing email environment variables")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = gmail
    msg["To"] = to
    msg.attach(MIMEText(html, "html"))

    with smtplib.SMTP("smtp.gmail.com", 587) as s:
        s.starttls()
        s.login(gmail, pw)
        s.sendmail(gmail, to, msg.as_string())


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    import argparse

    parser = argparse.ArgumentParser(description="Generate and email haiku engagement report")
    parser.add_argument(
        "--all-time", action="store_true",
        help="Report on all available data instead of just the last 7 days",
    )
    parser.add_argument(
        "--days", type=int, default=7,
        help="Number of days to include (default: 7, ignored if --all-time)",
    )
    args = parser.parse_args()

    config = load_config()

    today = date.today()

    if args.all_time:
        from framework.engagement_store import load_range
        # Use a far-past start date to catch all available day files
        start = date(2020, 1, 1)
        engagement = load_range(config, start, today + timedelta(days=1))
        title   = f"All-Time Report (through {today})"
        subject = f"ClamBakeSanta All-Time Report — {today}"
    else:
        from framework.engagement_store import load_summary
        start = today - timedelta(days=args.days)
        engagement = load_summary(config, days=args.days)
        title   = f"{args.days}-Day Report ({start} → {today})"
        subject = f"ClamBakeSanta {args.days}-Day Report — {today}"

    records = collect_week(engagement, start, today + timedelta(days=1))

    html = build_html_report(
        records,
        start,
        today,
        0,
        config.get("site_base_url", ""),
        title=title,
    )

    send_email(subject, html)


if __name__ == "__main__":
    main()
