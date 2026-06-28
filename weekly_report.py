#!/usr/bin/env python3
"""
weekly_report.py
"""

from __future__ import annotations

import json
import os
import smtplib
import subprocess
from datetime import date, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import List, Dict

from framework.config import load_config

SUBSCRIBERS_FILE = Path("state/subscribers.json")


# ── Subscribers ───────────────────────────────────────────────────────────────

def load_subscribers() -> list[str]:
    if not SUBSCRIBERS_FILE.exists():
        return []
    try:
        data = json.loads(SUBSCRIBERS_FILE.read_text(encoding="utf-8"))
        return sorted(data.get("subscribers", []))
    except Exception:
        return []


def _git_file_at(path: str, ref: str) -> str | None:
    """Return the contents of a file at a given git ref, or None if not found."""
    try:
        result = subprocess.run(
            ["git", "show", f"{ref}:{path}"],
            capture_output=True, text=True, check=True,
        )
        return result.stdout
    except subprocess.CalledProcessError:
        return None


def subscriber_changes(start: date) -> tuple[list[str], list[str]]:
    """Return (added, removed) since start date by diffing git history."""
    # Find the oldest commit on or before the start date
    result = subprocess.run(
        ["git", "log", "--format=%H", f"--before={start.isoformat()}", "-1", "--", str(SUBSCRIBERS_FILE)],
        capture_output=True, text=True,
    )
    old_ref = result.stdout.strip()

    if not old_ref:
        # No prior commit — everything current is "new"
        current = set(load_subscribers())
        return sorted(current), []

    old_contents = _git_file_at(str(SUBSCRIBERS_FILE), old_ref)
    if not old_contents:
        return [], []

    try:
        old_subs = set(json.loads(old_contents).get("subscribers", []))
    except Exception:
        return [], []

    current_subs = set(load_subscribers())
    added = sorted(current_subs - old_subs)
    removed = sorted(old_subs - current_subs)
    return added, removed


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


def subscribers_section_html(subscribers: list[str], added: list[str], removed: list[str]) -> str:
    total = len(subscribers)

    rows = "".join(f"<li>{s}</li>" for s in subscribers) if subscribers else "<li><em>None</em></li>"

    changes = ""
    if added:
        changes += "<p>➕ <b>Added:</b> " + ", ".join(added) + "</p>"
    if removed:
        changes += "<p>➖ <b>Removed:</b> " + ", ".join(removed) + "</p>"
    if not added and not removed:
        changes = "<p><em>No changes this week.</em></p>"

    return section("Email Subscribers", f"""
<p><b>Total:</b> {total}</p>
{changes}
<ul style="font-size:0.9rem;color:{_PALETTE['muted']};">{rows}</ul>
""")


# ── Report builder ────────────────────────────────────────────────────────────

def build_html_report(week_records, week_start, week_end, prior_total, site_url, title="Weekly Report",
                      subscribers=None, added=None, removed=None):

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
    for plat in ["mastodon", "bluesky", "tumblr"]:
        lead = platform_leader(week_records, plat)
        if lead:
            plat_data = lead["platforms"].get(plat, {})
            score = plat_data.get("score", 0)
            leaders += f"<div><b>{plat.title()}</b>: {lead['theme']} — ⭐ {score}</div>"

    # WordPress is one aggregate post per day — show its best week day by views
    wp_records = [r for r in week_records if r.get("tag") == "_wp_daily" or "_wp_daily" in str(r.get("tag",""))]
    if not wp_records:
        # fall back: any record that has a wordpress platform entry
        wp_records = [r for r in week_records if "wordpress" in r.get("platforms", {})]
    if wp_records:
        best_wp = max(wp_records, key=lambda r: r.get("platforms", {}).get("wordpress", {}).get("views", 0))
        wp = best_wp.get("platforms", {}).get("wordpress", {})
        views = wp.get("views", 0)
        likes = wp.get("likes", 0)
        leaders += f"<div><b>WordPress</b>: {best_wp['date']} — {views} views, {likes} likes</div>"

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
    subs_section = subscribers_section_html(subscribers or [], added or [], removed or [])

    return f"""
<html>
<body style="font-family:system-ui;max-width:700px;margin:auto;">

<h1>{title}</h1>

{stats_section}

{subs_section}

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

    subscribers = load_subscribers()
    added, removed = subscriber_changes(start)

    html = build_html_report(
        records,
        start,
        today,
        0,
        config.get("site_base_url", ""),
        title=title,
        subscribers=subscribers,
        added=added,
        removed=removed,
    )

    send_email(subject, html)


if __name__ == "__main__":
    main()
