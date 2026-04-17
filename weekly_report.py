#!/usr/bin/env python3
"""
weekly_report.py

Compiles the last 7 days of engagement data and emails a summary report
to the address in REPORT_EMAIL.

Engagement score formula (same as check_engagement.py):
    score = likes + (2 × shares/boosts/reposts) + (3 × comments/replies)

Report includes:
  - Overall stats for the week (posts, platforms active, total engagement)
  - Top 5 haikus by total cross-platform score
  - Per-platform leaders (best on Mastodon, Bluesky, Reddit)
  - Full ranked table of all haikus posted this week
  - How the score compares to prior weeks (trend arrow)

Run every Sunday morning via GitHub Actions (weekly_report.yml).
Requires: GMAIL_ADDRESS, GMAIL_APP_PASSWORD, REPORT_EMAIL

Usage:
    python weekly_report.py [--weeks N]   # default: 1 (last 7 days)
"""
from __future__ import annotations

import argparse
import os
import smtplib
import sys
from datetime import date, datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from framework.config import load_config


# ── Data compilation ──────────────────────────────────────────────────────────

def collect_week(engagement: dict, start: date, end: date) -> list[dict]:
    """
    Return a flat list of haiku records for dates in [start, end).
    Each record:  { date, tag, theme, haiku, platforms, total_score }
    """
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
                "date":        date_str,
                "tag":         tag,
                "theme":       entry.get("theme", tag),
                "haiku":       entry.get("haiku", ""),
                "platforms":   entry.get("platforms", {}),
                "total_score": entry.get("total_score", 0),
            })
    return sorted(records, key=lambda r: r["total_score"], reverse=True)


def platform_leader(records: list[dict], platform: str) -> dict | None:
    """Return the haiku with the highest score on a specific platform."""
    candidates = [
        r for r in records
        if platform in r.get("platforms", {}) and r["platforms"][platform].get("score", 0) > 0
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda r: r["platforms"][platform]["score"])


# ── HTML email builder ────────────────────────────────────────────────────────

_PALETTE = {
    "green":     "#2c6e49",
    "light_bg":  "#fdfaf5",
    "border":    "#e0d9cc",
    "text":      "#333",
    "muted":     "#666",
    "gold":      "#d4a017",
    "silver":    "#888",
    "bronze":    "#a05c34",
}

_MEDAL = ["🥇", "🥈", "🥉", "4.", "5.", "6.", "7.", "8.", "9.", "10."]

_PLATFORM_EMOJI = {
    "mastodon": "🐘",
    "bluesky":  "🦋",
    "reddit":   "🤖",
}


def _haiku_card(rec: dict, rank: int, show_date: bool = True) -> str:
    medal   = _MEDAL[rank] if rank < len(_MEDAL) else f"{rank + 1}."
    theme   = rec["theme"]
    haiku_lines = rec["haiku"].split("\n")
    poem    = "<br>".join(
        ln.rstrip(",") for ln in haiku_lines[:3] if ln.strip()
    )
    plat_details = []
    for plat, pdata in rec.get("platforms", {}).items():
        emoji = _PLATFORM_EMOJI.get(plat, "📊")
        score = pdata.get("score", 0)
        if plat == "mastodon":
            detail = (f"❤️{pdata.get('likes',0)} "
                      f"🔁{pdata.get('boosts',0)} "
                      f"💬{pdata.get('replies',0)}")
        elif plat == "bluesky":
            detail = (f"❤️{pdata.get('likes',0)} "
                      f"🔁{pdata.get('reposts',0)} "
                      f"💬{pdata.get('replies',0)}")
        elif plat == "reddit":
            detail = (f"⬆️{pdata.get('upvotes',0)} "
                      f"💬{pdata.get('comments',0)}")
        else:
            detail = f"score {score}"
        plat_details.append(f"{emoji} {detail} (score {score})")

    plat_html = "  ·  ".join(plat_details) if plat_details else "no data yet"
    date_line = f'<div style="color:{_PALETTE["muted"]};font-size:0.8rem;">{rec["date"]}</div>' if show_date else ""

    return f"""
<div style="margin:1.2rem 0;padding:1.2rem 1.5rem;background:{_PALETTE["light_bg"]};
            border-left:4px solid {_PALETTE["green"]};border-radius:4px;">
  <div style="display:flex;align-items:baseline;gap:0.5rem;margin-bottom:0.4rem;">
    <span style="font-size:1.1rem;">{medal}</span>
    <strong style="color:{_PALETTE["green"]};">{theme}</strong>
    <span style="margin-left:auto;font-weight:bold;font-size:1.1rem;">⭐ {rec["total_score"]}</span>
  </div>
  {date_line}
  <p style="margin:0.5rem 0;font-family:Georgia,serif;font-size:1rem;line-height:1.9;color:{_PALETTE["text"]};">
    {poem}
  </p>
  <div style="font-size:0.82rem;color:{_PALETTE["muted"]};">{plat_html}</div>
</div>"""


def _section(title: str, content: str) -> str:
    return f"""
<h2 style="color:{_PALETTE["green"]};border-bottom:2px solid {_PALETTE["border"]};
           padding-bottom:0.3rem;margin-top:2rem;">{title}</h2>
{content}"""


def build_html_report(
    week_records: list[dict],
    week_start:   date,
    week_end:     date,
    prior_total:  int,
    site_url:     str,
) -> str:
    total_posts    = len(week_records)
    total_score    = sum(r["total_score"] for r in week_records)
    active_plats   = set(p for r in week_records for p in r.get("platforms", {}))

    # Trend indicator vs prior week
    if prior_total > 0:
        pct = ((total_score - prior_total) / prior_total) * 100
        trend = f"{'↑' if pct >= 0 else '↓'} {abs(pct):.0f}% vs prior week"
        trend_color = _PALETTE["green"] if pct >= 0 else "#c0392b"
    else:
        trend = "First week with data"
        trend_color = _PALETTE["muted"]

    # Top 5
    top5_html = "".join(_haiku_card(r, i) for i, r in enumerate(week_records[:5]))

    # Per-platform leaders
    plat_leader_html = ""
    for plat, emoji in _PLATFORM_EMOJI.items():
        leader = platform_leader(week_records, plat)
        if leader:
            pdata = leader["platforms"][plat]
            plat_leader_html += f"""
<div style="margin:0.8rem 0;">
  <strong>{emoji} {plat.capitalize()}:</strong>
  <em>{leader["theme"]}</em> — score {pdata.get("score", 0)}
</div>"""

    # Full ranked table (all haikus this week)
    table_rows = ""
    for i, r in enumerate(week_records):
        table_rows += f"""
<tr style="{'background:#f5f0e8' if i % 2 == 0 else ''}">
  <td style="padding:0.4rem 0.8rem;">{_MEDAL[i] if i < len(_MEDAL) else i+1}</td>
  <td style="padding:0.4rem 0.8rem;">{r["date"]}</td>
  <td style="padding:0.4rem 0.8rem;">{r["theme"]}</td>
  <td style="padding:0.4rem 0.8rem;text-align:center;font-weight:bold;">{r["total_score"]}</td>
  <td style="padding:0.4rem 0.8rem;font-size:0.85rem;color:{_PALETTE["muted"]};">
    {"  ·  ".join(
        f'{_PLATFORM_EMOJI.get(p,"")}{r["platforms"][p].get("score",0)}'
        for p in r["platforms"]
    )}
  </td>
</tr>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>ClamBakeSanta Weekly Report</title>
</head>
<body style="font-family:system-ui,sans-serif;max-width:680px;margin:0 auto;
             padding:1.5rem;color:{_PALETTE["text"]};">

<div style="text-align:center;margin-bottom:1.5rem;">
  <img src="https://clambakesanta.files.wordpress.com/2026/04/santa_clambake.jpg"
       alt="ClamBakeSanta" style="width:80px;height:80px;border-radius:50%;object-fit:cover;">
  <h1 style="color:{_PALETTE["green"]};margin:0.5rem 0 0;">ClamBakeSanta Weekly Report</h1>
  <p style="color:{_PALETTE["muted"]};margin:0.2rem 0;">
    {week_start.strftime('%B %d')} – {(week_end - timedelta(days=1)).strftime('%B %d, %Y')}
  </p>
</div>

{_section("📊 Week at a Glance", f"""
<div style="display:flex;flex-wrap:wrap;gap:1rem;margin:1rem 0;">
  <div style="flex:1;min-width:130px;padding:1rem;background:{_PALETTE["light_bg"]};
              border-radius:8px;text-align:center;border:1px solid {_PALETTE["border"]};">
    <div style="font-size:1.8rem;font-weight:bold;color:{_PALETTE["green"]};">{total_posts}</div>
    <div style="font-size:0.85rem;color:{_PALETTE["muted"]};">haikus posted</div>
  </div>
  <div style="flex:1;min-width:130px;padding:1rem;background:{_PALETTE["light_bg"]};
              border-radius:8px;text-align:center;border:1px solid {_PALETTE["border"]};">
    <div style="font-size:1.8rem;font-weight:bold;color:{_PALETTE["green"]};">{total_score}</div>
    <div style="font-size:0.85rem;color:{_PALETTE["muted"]};">total engagement</div>
  </div>
  <div style="flex:1;min-width:130px;padding:1rem;background:{_PALETTE["light_bg"]};
              border-radius:8px;text-align:center;border:1px solid {_PALETTE["border"]};">
    <div style="font-size:1.8rem;font-weight:bold;color:{_PALETTE["green"]};">{len(active_plats)}</div>
    <div style="font-size:0.85rem;color:{_PALETTE["muted"]};">active platforms</div>
  </div>
  <div style="flex:1;min-width:130px;padding:1rem;background:{_PALETTE["light_bg"]};
              border-radius:8px;text-align:center;border:1px solid {_PALETTE["border"]};">
    <div style="font-size:1.2rem;font-weight:bold;color:{trend_color};">{trend}</div>
    <div style="font-size:0.85rem;color:{_PALETTE["muted"]};">engagement trend</div>
  </div>
</div>
<p style="font-size:0.82rem;color:{_PALETTE["muted"]};">
  Score formula: ❤️ likes&nbsp;+&nbsp;2×&nbsp;🔁 shares/boosts/reposts&nbsp;+&nbsp;3×&nbsp;💬 replies/comments
</p>""")}

{_section("🏆 Top 5 Haikus This Week", top5_html)}

{_section("🏅 Platform Leaders", plat_leader_html or "<p>Not enough data yet.</p>")}

{_section("📋 Full Rankings", f"""
<table style="width:100%;border-collapse:collapse;font-size:0.9rem;">
  <thead>
    <tr style="background:{_PALETTE["green"]};color:white;">
      <th style="padding:0.5rem 0.8rem;text-align:left;">#</th>
      <th style="padding:0.5rem 0.8rem;text-align:left;">Date</th>
      <th style="padding:0.5rem 0.8rem;text-align:left;">Theme</th>
      <th style="padding:0.5rem 0.8rem;text-align:center;">Score</th>
      <th style="padding:0.5rem 0.8rem;text-align:left;">By platform</th>
    </tr>
  </thead>
  <tbody>{table_rows}</tbody>
</table>""")}

<hr style="border:none;border-top:1px solid {_PALETTE["border"]};margin:2rem 0;">
<p style="text-align:center;color:{_PALETTE["muted"]};font-size:0.85rem;">
  <a href="{site_url}" style="color:{_PALETTE["green"]};">Visit ClamBakeSanta</a> ·
  Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}
</p>

</body></html>"""


# ── Email sender ──────────────────────────────────────────────────────────────

def send_email(subject: str, html_body: str) -> bool:
    gmail_address  = os.environ.get("GMAIL_ADDRESS", "").strip()
    gmail_password = os.environ.get("GMAIL_APP_PASSWORD", "").strip()
    report_email   = os.environ.get("REPORT_EMAIL", "").strip()

    if not gmail_address or not gmail_password:
        print("GMAIL_ADDRESS or GMAIL_APP_PASSWORD not set — cannot send report.")
        return False
    if not report_email:
        print("REPORT_EMAIL not set — cannot send report.")
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = f"ClamBakeSanta <{gmail_address}>"
    msg["To"]      = report_email
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(gmail_address, gmail_password)
            server.sendmail(gmail_address, [report_email], msg.as_string())
        print(f"Weekly report sent → {report_email}")
        return True
    except Exception as exc:
        print(f"Email failed: {exc}", file=sys.stderr)
        return False


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Send weekly ClamBakeSanta engagement report")
    parser.add_argument("--weeks", type=int, default=1,
                        help="How many weeks back to report on (default: 1)")
    args = parser.parse_args()

    config = load_config()

    from framework.engagement_store import load_summary, load_range

    today      = date.today()
    week_end   = today
    week_start = week_end - timedelta(weeks=args.weeks)

    # Prior week for trend comparison
    prior_end   = week_start
    prior_start = prior_end - timedelta(weeks=1)

    # Use the fast summary file for 1-week reports; scan day files for longer windows
    if args.weeks <= 1:
        engagement = load_summary(config)
    else:
        engagement = load_range(config, prior_start, week_end)

    if not engagement:
        print("No engagement data yet — run check_engagement.py first.")
        sys.exit(0)

    week_records  = collect_week(engagement, week_start, week_end)
    prior_records = collect_week(engagement, prior_start, prior_end)
    prior_total   = sum(r["total_score"] for r in prior_records)

    if not week_records:
        print(f"No engagement data for {week_start} – {week_end}.")
        sys.exit(0)

    print(f"Found {len(week_records)} haiku records for "
          f"{week_start} – {week_end} (total score: {sum(r['total_score'] for r in week_records)})")

    site_url = config.get("site_base_url", "https://soylentaquamarine.github.io/ClamBakeSanta")
    subject  = (
        f"🦀 ClamBakeSanta Weekly — "
        f"{week_start.strftime('%b %d')}–{(week_end - timedelta(days=1)).strftime('%b %d, %Y')}"
    )
    html = build_html_report(week_records, week_start, week_end, prior_total, site_url)
    send_email(subject, html)


if __name__ == "__main__":
    main()
