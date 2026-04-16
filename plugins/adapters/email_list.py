"""
email_list — Adapter plugin.

Daily mailer — sends today's haikus to every confirmed subscriber
via Gmail SMTP.

SUBSCRIBE/UNSUBSCRIBE processing is handled by check_subscriptions.py,
which runs one hour before this workflow via check_subscriptions.yml.

Subscriber list lives in state/subscribers.json and is committed back
to the repo by the workflow after each run — no database needed.

Setup (one-time):
  1. Create a Gmail account for ClamBakeSanta
  2. Enable 2-Factor Authentication
  3. Generate an App Password (Google Account → Security → App Passwords)
  4. Add two GitHub Secrets:
       GMAIL_ADDRESS      = clambakesanta@gmail.com
       GMAIL_APP_PASSWORD = (16-char app password, no spaces)
  5. Add "email_list" to adapters in config.yml

If either secret is missing, this adapter skips silently.
"""
from __future__ import annotations
import json
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from framework.registry import register
from framework.adapters.base import BaseAdapter
from framework.models import Result

SUBSCRIBERS_FILE = Path("state/subscribers.json")
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587


def _load_subscribers() -> dict:
    """Load subscriber list from state file."""
    if SUBSCRIBERS_FILE.exists():
        return json.loads(SUBSCRIBERS_FILE.read_text(encoding="utf-8"))
    return {"subscribers": []}


def _send_email(
    smtp: smtplib.SMTP,
    from_addr: str,
    to_addr: str,
    subject: str,
    html_body: str,
    text_body: str,
) -> None:
    """Send a single email via Gmail SMTP."""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"Clam Bake Santa <{from_addr}>"
    msg["To"] = to_addr
    msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))
    smtp.sendmail(from_addr, to_addr, msg.as_string())


def _build_daily_email(haiku_records: list[dict], date_str: str,
                       base_url: str) -> tuple[str, str]:
    """Build HTML and plain text versions of the daily email."""

    # ── HTML ─────────────────────────────────────────────────────────────────
    cards = ""
    plain_cards = ""
    for rec in haiku_records:
        theme = rec.get("theme", "")
        display_theme = (
            f"Happy {theme}" if theme.lower().startswith("birthday") else theme
        )
        lines = rec["haiku"].split("\n")
        poem_lines = lines[:-1]
        hashtag_line = lines[-1] if lines else ""
        poem_html = "<br>".join(poem_lines)
        cards += f"""
        <div style="background:#fff;border:1px solid #e0d9cc;border-radius:10px;
                    padding:1.5rem;margin:1.5rem 0;">
          <h2 style="font-size:0.9rem;color:#666;font-family:Arial,sans-serif;
                     text-transform:uppercase;letter-spacing:0.05em;
                     margin-bottom:0.8rem;">{display_theme.upper()}</h2>
          <p style="font-size:1.1rem;line-height:2;font-family:Georgia,serif;">
            {poem_html}
          </p>
          <p style="color:#2c6e49;font-size:0.85rem;font-family:Arial,sans-serif;
                    margin-top:0.5rem;">{hashtag_line}</p>
        </div>"""
        plain_cards += f"\n{display_theme.upper()}\n"
        plain_cards += "\n".join(poem_lines) + "\n"
        plain_cards += hashtag_line + "\n"

    html = f"""<!doctype html>
<html><body style="background:#fdfaf5;font-family:Georgia,serif;
                   max-width:600px;margin:0 auto;padding:2rem;">
  <div style="text-align:center;border-bottom:2px solid #e0d9cc;
              padding-bottom:1rem;margin-bottom:2rem;">
    <img src="{base_url}/santa_clambake.png"
         style="width:120px;height:120px;border-radius:50%;object-fit:cover;">
    <h1 style="color:#2c6e49;margin:0.5rem 0;">Clam Bake Santa</h1>
    <p style="color:#666;font-style:italic;">
      Daily haikus for {date_str}
    </p>
  </div>
  {cards}
  <div style="text-align:center;margin-top:2rem;padding-top:1rem;
              border-top:1px solid #e0d9cc;color:#666;
              font-size:0.8rem;font-family:Arial,sans-serif;">
    <p>View the full archive at
      <a href="{base_url}" style="color:#2c6e49;">{base_url}</a>
    </p>
    <p style="margin-top:0.5rem;">
      To unsubscribe, reply with UNSUBSCRIBE in the subject line.
    </p>
  </div>
</body></html>"""

    plain = f"Clam Bake Santa — Daily Haikus for {date_str}\n"
    plain += "=" * 50 + "\n"
    plain += plain_cards
    plain += f"\nView archive: {base_url}\n"
    plain += "To unsubscribe, reply with UNSUBSCRIBE in the subject.\n"

    return html, plain


def _confirm_html(email: str) -> str:
    return f"""<!doctype html>
<html><body style="font-family:Georgia,serif;max-width:500px;margin:2rem auto;">
  <h1 style="color:#2c6e49;">You're subscribed! 🦪</h1>
  <p>Every morning, fresh haikus celebrating today's holidays and birthdays
     will arrive in your inbox.</p>
  <p>To unsubscribe at any time, just reply with <strong>UNSUBSCRIBE</strong>
     in the subject line.</p>
  <p style="color:#666;font-size:0.9rem;">— Clam Bake Santa</p>
</body></html>"""


def _confirm_text(email: str) -> str:
    return ("You're subscribed to Clam Bake Santa!\n\n"
            "Every morning, fresh haikus celebrating today's holidays and "
            "birthdays will arrive in your inbox.\n\n"
            "To unsubscribe, reply with UNSUBSCRIBE in the subject.\n\n"
            "— Clam Bake Santa")


def _farewell_html(email: str) -> str:
    return """<!doctype html>
<html><body style="font-family:Georgia,serif;max-width:500px;margin:2rem auto;">
  <h1 style="color:#2c6e49;">You've been unsubscribed</h1>
  <p>You won't receive any more daily haikus. The clams will miss you.</p>
  <p>If you ever want to come back, just email with
     <strong>SUBSCRIBE</strong> in the subject.</p>
  <p style="color:#666;font-size:0.9rem;">— Clam Bake Santa</p>
</body></html>"""


def _farewell_text(email: str) -> str:
    return ("You've been unsubscribed from Clam Bake Santa.\n\n"
            "The clams will miss you. To resubscribe anytime, "
            "email with SUBSCRIBE in the subject.\n\n"
            "— Clam Bake Santa")


@register("adapters", "email_list")
class EmailListAdapter(BaseAdapter):
    """
    Sends the daily haiku digest to all confirmed subscribers via Gmail SMTP.
    Skips gracefully if Gmail credentials are not configured.
    """

    def publish(self, result: Result) -> bool:
        gmail_address = os.environ.get("GMAIL_ADDRESS", "").strip()
        app_password  = os.environ.get("GMAIL_APP_PASSWORD", "").strip()

        if not gmail_address or not app_password:
            return False  # Not configured — skip silently

        # Subscriptions are managed by check_subscriptions.yml which runs
        # 1 hour before this workflow. This adapter only sends the daily digest.

        subscribers = _load_subscribers().get("subscribers", [])
        if not subscribers:
            print("  Email: no subscribers yet — skipping send")
            return True

        haiku_records = result.metadata.get("haikus", [])
        if not haiku_records:
            return True

        base_url = self.config.get("site_base_url", "").rstrip("/")
        html_body, text_body = _build_daily_email(
            haiku_records, result.event.date_str, base_url
        )
        subject = f"🦪 Clam Bake Santa — {result.event.date_str}"

        sent = 0
        errors = 0
        try:
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as smtp:
                smtp.ehlo()
                smtp.starttls()
                smtp.ehlo()
                smtp.login(gmail_address, app_password)
                for addr in subscribers:
                    try:
                        _send_email(smtp, gmail_address, addr,
                                    subject, html_body, text_body)
                        sent += 1
                    except Exception as exc:
                        print(f"  Failed to send to {addr}: {exc}")
                        errors += 1
        except Exception as exc:
            print(f"  Email send error: {exc}")
            return False

        print(f"  Email: sent to {sent} subscriber(s), {errors} error(s)")
        return True
