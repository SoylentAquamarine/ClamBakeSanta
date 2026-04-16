#!/usr/bin/env python3
"""
check_subscriptions.py

Standalone subscription processor — runs independently of the main
haiku pipeline. Checks Gmail inbox for SUBSCRIBE/UNSUBSCRIBE emails,
updates state/subscribers.json, and sends confirmation replies via
Brevo (transactional email API — free tier, no IP blocking).

Called by the check_subscriptions.yml workflow one hour before the
main daily run so the freshest subscriber list is ready.

Usage:
    python check_subscriptions.py

Required env vars:
    GMAIL_ADDRESS         — clamsbakesanta@gmail.com  (IMAP read only)
    GMAIL_APP_PASSWORD    — 16-char Gmail app password  (IMAP read only)
    BREVO_API_KEY         — Brevo transactional API key  (sending only)
"""
from __future__ import annotations
import imaplib
import json
import os
import email as email_lib
from pathlib import Path

import requests

SUBSCRIBERS_FILE = Path("state/subscribers.json")
IMAP_HOST = "imap.gmail.com"
BREVO_SEND_URL = "https://api.brevo.com/v3/smtp/email"


def load_subscribers() -> dict:
    if SUBSCRIBERS_FILE.exists():
        return json.loads(SUBSCRIBERS_FILE.read_text(encoding="utf-8"))
    return {"subscribers": []}


def save_subscribers(data: dict) -> None:
    SUBSCRIBERS_FILE.parent.mkdir(parents=True, exist_ok=True)
    SUBSCRIBERS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def send_email(brevo_key: str, from_addr: str, to_addr: str,
               subject: str, html: str, text: str) -> None:
    """Send a single email via Brevo transactional API."""
    resp = requests.post(
        BREVO_SEND_URL,
        headers={"api-key": brevo_key, "Content-Type": "application/json"},
        json={
            "sender":      {"name": "Clam Bake Santa", "email": from_addr},
            "to":          [{"email": to_addr}],
            "subject":     subject,
            "htmlContent": html,
            "textContent": text,
        },
        timeout=30,
    )
    resp.raise_for_status()


def main():
    gmail_address = os.environ.get("GMAIL_ADDRESS", "").strip()
    app_password  = os.environ.get("GMAIL_APP_PASSWORD", "").strip()
    brevo_key     = os.environ.get("BREVO_API_KEY", "").strip()

    if not gmail_address or not app_password:
        print("GMAIL_ADDRESS or GMAIL_APP_PASSWORD not set — skipping.")
        return

    if not brevo_key:
        print("BREVO_API_KEY not set — subscriptions will be processed "
              "but confirmation emails will not be sent.")

    data        = load_subscribers()
    subscribers = set(data.get("subscribers", []))
    new_subs    = 0
    new_unsubs  = 0

    try:
        # ── IMAP: read Gmail inbox for SUBSCRIBE / UNSUBSCRIBE emails ─────────
        mail = imaplib.IMAP4_SSL(IMAP_HOST)
        mail.login(gmail_address, app_password)

        all_msg_ids = []
        for folder in ("inbox", "[Gmail]/Spam"):
            try:
                mail.select(folder)
                _, msg_ids = mail.search(None, "UNSEEN")
                all_msg_ids.extend(msg_ids[0].split())
            except Exception:
                pass  # folder may not exist, skip

        mail.select("inbox")

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
                    if brevo_key:
                        try:
                            send_email(
                                brevo_key, gmail_address, sender,
                                "You're subscribed to Clam Bake Santa 🦪",
                                f"<p>You're subscribed! Daily haikus will arrive each morning.</p>"
                                f"<p>To unsubscribe, reply with UNSUBSCRIBE in the subject.</p>",
                                "You're subscribed to Clam Bake Santa!\n\n"
                                "Daily haikus will arrive each morning.\n\n"
                                "To unsubscribe, reply with UNSUBSCRIBE in the subject.",
                            )
                            print(f"  ✉  Confirmation sent to {sender}")
                        except Exception as e:
                            print(f"  ⚠  Confirmation send failed for {sender}: {e}")
                    print(f"  + Subscribed: {sender}")

            elif "UNSUBSCRIBE" in subject:
                if sender in subscribers:
                    subscribers.discard(sender)
                    new_unsubs += 1
                    if brevo_key:
                        try:
                            send_email(
                                brevo_key, gmail_address, sender,
                                "You've unsubscribed from Clam Bake Santa",
                                "<p>You've been unsubscribed. The clams will miss you.</p>"
                                "<p>To resubscribe, email with SUBSCRIBE in the subject.</p>",
                                "You've been unsubscribed from Clam Bake Santa.\n\n"
                                "The clams will miss you.\n\n"
                                "To resubscribe, email with SUBSCRIBE in the subject.",
                            )
                            print(f"  ✉  Farewell sent to {sender}")
                        except Exception as e:
                            print(f"  ⚠  Farewell send failed for {sender}: {e}")
                    print(f"  - Unsubscribed: {sender}")

            mail.store(msg_id, "+FLAGS", "\\Seen")

        mail.logout()
        print(f"IMAP: processed {len(all_msg_ids)} unseen message(s)")

    except Exception as exc:
        print(f"  IMAP error: {exc}")
        print("  Subscription inbox check skipped — list unchanged.")

    data["subscribers"] = sorted(subscribers)
    save_subscribers(data)

    print(f"Done: +{new_subs} subscribed, -{new_unsubs} unsubscribed, "
          f"{len(subscribers)} total subscriber(s)")


if __name__ == "__main__":
    main()
