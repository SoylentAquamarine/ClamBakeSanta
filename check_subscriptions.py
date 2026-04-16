#!/usr/bin/env python3
"""
check_subscriptions.py

Standalone subscription processor — runs independently of the main
haiku pipeline. Checks Gmail inbox for SUBSCRIBE/UNSUBSCRIBE emails,
updates state/subscribers.json, and sends confirmation replies.

Called by the check_subscriptions.yml workflow one hour before the
main daily run so the freshest subscriber list is ready.

Usage:
    python check_subscriptions.py
"""
from __future__ import annotations
import imaplib
import json
import os
import smtplib
import email as email_lib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

SUBSCRIBERS_FILE = Path("state/subscribers.json")
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587
IMAP_HOST = "imap.gmail.com"


def load_subscribers() -> dict:
    if SUBSCRIBERS_FILE.exists():
        return json.loads(SUBSCRIBERS_FILE.read_text(encoding="utf-8"))
    return {"subscribers": []}


def save_subscribers(data: dict) -> None:
    SUBSCRIBERS_FILE.parent.mkdir(parents=True, exist_ok=True)
    SUBSCRIBERS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def send_email(smtp, from_addr, to_addr, subject, html, text):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = f"Clam Bake Santa <{from_addr}>"
    msg["To"]      = to_addr
    msg.attach(MIMEText(text, "plain"))
    msg.attach(MIMEText(html, "html"))
    smtp.sendmail(from_addr, to_addr, msg.as_string())


def main():
    gmail_address = os.environ.get("GMAIL_ADDRESS", "").strip()
    app_password  = os.environ.get("GMAIL_APP_PASSWORD", "").strip()

    if not gmail_address or not app_password:
        print("GMAIL_ADDRESS or GMAIL_APP_PASSWORD not set — skipping.")
        return

    data        = load_subscribers()
    subscribers = set(data.get("subscribers", []))
    new_subs    = 0
    new_unsubs  = 0

    # ── Verify SMTP credentials first ────────────────────────────────────────
    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.ehlo()
            smtp.login(gmail_address, app_password)
        print("SMTP credentials: OK")
    except Exception as exc:
        print(f"SMTP credentials: FAILED — {exc}")
        raise

    try:
        # ── IMAP: read inbox ──────────────────────────────────────────────────
        mail = imaplib.IMAP4_SSL(IMAP_HOST)
        mail.login(gmail_address, app_password)

        all_msg_ids = []
        for folder in ("inbox", "[Gmail]/Spam"):
            try:
                mail.select(folder)
                _, msg_ids = mail.search(None, "UNSEEN")
                all_msg_ids.extend(msg_ids[0].split())
            except Exception:
                pass

        mail.select("inbox")

        # ── SMTP: send confirmation replies ──────────────────────────────────
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.ehlo()
            smtp.login(gmail_address, app_password)

            for msg_id in all_msg_ids:
                _, msg_data = mail.fetch(msg_id, "(RFC822)")
                raw    = msg_data[0][1]
                parsed = email_lib.message_from_bytes(raw)
                subject = parsed.get("Subject", "").upper()
                sender  = email_lib.utils.parseaddr(parsed.get("From", ""))[1].lower()

                if not sender:
                    continue

                if "SUBSCRIBE" in subject and "UNSUBSCRIBE" not in subject:
                    if sender not in subscribers:
                        subscribers.add(sender)
                        new_subs += 1
                        send_email(
                            smtp, gmail_address, sender,
                            "You're subscribed to Clam Bake Santa 🦪",
                            f"<p>You're subscribed! Daily haikus will arrive each morning.</p>"
                            f"<p>To unsubscribe, reply with UNSUBSCRIBE in the subject.</p>",
                            "You're subscribed to Clam Bake Santa!\n\n"
                            "Daily haikus will arrive each morning.\n\n"
                            "To unsubscribe, reply with UNSUBSCRIBE in the subject.",
                        )
                        print(f"  + Subscribed: {sender}")

                elif "UNSUBSCRIBE" in subject:
                    if sender in subscribers:
                        subscribers.discard(sender)
                        new_unsubs += 1
                        send_email(
                            smtp, gmail_address, sender,
                            "You've unsubscribed from Clam Bake Santa",
                            "<p>You've been unsubscribed. The clams will miss you.</p>"
                            "<p>To resubscribe, email with SUBSCRIBE in the subject.</p>",
                            "You've been unsubscribed from Clam Bake Santa.\n\n"
                            "The clams will miss you.\n\n"
                            "To resubscribe, email with SUBSCRIBE in the subject.",
                        )
                        print(f"  - Unsubscribed: {sender}")

                mail.store(msg_id, "+FLAGS", "\\Seen")

        mail.logout()

    except Exception as exc:
        print(f"  IMAP error: {exc}")
        print("  Subscription inbox check skipped — SMTP sending will still work.")

    data["subscribers"] = sorted(subscribers)
    save_subscribers(data)

    print(f"Done: +{new_subs} subscribed, -{new_unsubs} unsubscribed, "
          f"{len(subscribers)} total subscribers")


if __name__ == "__main__":
    main()
