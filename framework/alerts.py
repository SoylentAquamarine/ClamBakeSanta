"""
alerts.py — Email notification for hard run failures.

Separate from the weekly/daily engagement reports: this fires immediately,
same-day, only when something actually needs attention (e.g. zero haikus
posted). Uses the same Gmail SMTP + secrets as weekly_report.py.
"""
from __future__ import annotations

import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

log = logging.getLogger(__name__)


def send_failure_alert(subject: str, body_lines: list[str]) -> None:
    """
    Send a plain-text alert email. Silently no-ops (with a log warning) if
    the Gmail/report env vars aren't configured — this must never raise and
    break the run it's reporting on.
    """
    gmail = os.environ.get("GMAIL_ADDRESS")
    pw    = os.environ.get("GMAIL_APP_PASSWORD")
    to    = os.environ.get("REPORT_EMAIL")

    if not gmail or not pw or not to:
        log.warning(
            "Skipping failure alert email — GMAIL_ADDRESS/GMAIL_APP_PASSWORD/"
            "REPORT_EMAIL not all set."
        )
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = gmail
    msg["To"] = to
    msg.attach(MIMEText("\n".join(body_lines), "plain"))

    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as s:
            s.starttls()
            s.login(gmail, pw)
            s.sendmail(gmail, to, msg.as_string())
        log.info("Failure alert email sent to %s", to)
    except Exception as exc:
        log.error("Failed to send failure alert email: %s", exc)
