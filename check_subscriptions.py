"""
Process ClamBakeSanta email subscription requests.

This script is intended to run from .github/workflows/check_subscriptions.yml.
It connects to Gmail over IMAP, finds unread messages whose subject line is
exactly SUBSCRIBE or UNSUBSCRIBE, updates state/subscribers.json, sends a short
reply, and marks processed command messages as read so they are not handled again.

Required environment variables:
  GMAIL_ADDRESS
  GMAIL_APP_PASSWORD
"""
from __future__ import annotations

import email
import imaplib
import json
import logging
import os
import smtplib
from dataclasses import dataclass
from email.header import decode_header, make_header
from email.message import EmailMessage
from email.utils import parseaddr
from pathlib import Path
from typing import Iterable

IMAP_HOST = "imap.gmail.com"
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587
SUBSCRIBERS_FILE = Path("state/subscribers.json")

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


@dataclass(frozen=True)
class SubscriptionCommand:
    message_id: bytes
    sender: str
    command: str


def _mask(addr: str) -> str:
    """Return a log-safe version of an email address."""
    local, _, domain = addr.partition("@")
    if not domain:
        return "***"
    return f"{local[:2]}***@{domain}"


def _decode_header(value: str | None) -> str:
    if not value:
        return ""
    try:
        return str(make_header(decode_header(value)))
    except Exception:
        return value


def _detect_command(subject: str) -> str | None:
    """Return command only when the subject is exactly SUBSCRIBE or UNSUBSCRIBE."""
    normalized = " ".join(subject.strip().split()).upper()
    if normalized == "UNSUBSCRIBE":
        return "unsubscribe"
    if normalized == "SUBSCRIBE":
        return "subscribe"
    return None


def _load_subscribers() -> set[str]:
    if not SUBSCRIBERS_FILE.exists():
        return set()

    try:
        data = json.loads(SUBSCRIBERS_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        logging.warning("Subscriber file was invalid JSON; starting with empty list")
        return set()

    return {str(addr).strip().lower() for addr in data.get("subscribers", []) if str(addr).strip()}


def _save_subscribers(subscribers: Iterable[str]) -> None:
    SUBSCRIBERS_FILE.parent.mkdir(parents=True, exist_ok=True)
    data = {"subscribers": sorted({addr.strip().lower() for addr in subscribers if addr.strip()})}
    SUBSCRIBERS_FILE.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _send_reply(gmail_address: str, app_password: str, recipient: str, subject: str, body: str) -> None:
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = f"Clam Bake Santa <{gmail_address}>"
    msg["To"] = recipient
    msg.set_content(body)

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as smtp:
        smtp.ehlo()
        smtp.starttls()
        smtp.ehlo()
        smtp.login(gmail_address, app_password)
        smtp.send_message(msg)


def _confirmation(command: str) -> tuple[str, str]:
    if command == "subscribe":
        return (
            "You're subscribed to Clam Bake Santa",
            "You're subscribed to Clam Bake Santa!\n\n"
            "Fresh daily haikus will arrive in your inbox.\n\n"
            "To unsubscribe, send a new email with exactly UNSUBSCRIBE in the subject line.\n\n"
            "— Clam Bake Santa",
        )

    return (
        "You've been unsubscribed from Clam Bake Santa",
        "You've been unsubscribed from Clam Bake Santa.\n\n"
        "The clams will miss you. To resubscribe, send a new email with exactly SUBSCRIBE in the subject line.\n\n"
        "— Clam Bake Santa",
    )


def _fetch_commands(gmail_address: str, app_password: str) -> list[SubscriptionCommand]:
    commands: list[SubscriptionCommand] = []

    with imaplib.IMAP4_SSL(IMAP_HOST) as imap:
        imap.login(gmail_address, app_password)
        imap.select("INBOX")

        status, data = imap.search(None, "UNSEEN")
        if status != "OK":
            raise RuntimeError("Failed to search Gmail inbox")

        message_ids = data[0].split()
        logging.info("Found %d unread message(s)", len(message_ids))

        for message_id in message_ids:
            status, msg_data = imap.fetch(message_id, "(BODY.PEEK[HEADER])")
            if status != "OK" or not msg_data or not isinstance(msg_data[0], tuple):
                logging.warning("Could not fetch message header id %s", message_id.decode(errors="ignore"))
                continue

            msg = email.message_from_bytes(msg_data[0][1])
            sender = parseaddr(_decode_header(msg.get("From")))[1].strip().lower()
            subject = _decode_header(msg.get("Subject"))
            command = _detect_command(subject)

            # Mark every scanned message as seen so it isn't re-processed on the next run.
            imap.store(message_id, "+FLAGS", "\\Seen")

            if not sender or not command:
                logging.info("Skipped non-command message (marked seen)")
                continue

            commands.append(SubscriptionCommand(message_id=message_id, sender=sender, command=command))
            logging.info("Queued %s request from %s", command, _mask(sender))

        imap.close()
        imap.logout()

    return commands


def main() -> int:
    gmail_address = os.environ.get("GMAIL_ADDRESS", "").strip()
    app_password = os.environ.get("GMAIL_APP_PASSWORD", "").strip()

    if not gmail_address or not app_password:
        logging.warning("GMAIL_ADDRESS or GMAIL_APP_PASSWORD is missing; nothing to do")
        return 0

    subscribers = _load_subscribers()
    before = set(subscribers)
    commands = _fetch_commands(gmail_address, app_password)

    for command in commands:
        if command.command == "subscribe":
            subscribers.add(command.sender)
        elif command.command == "unsubscribe":
            subscribers.discard(command.sender)

        subject, body = _confirmation(command.command)
        try:
            _send_reply(gmail_address, app_password, command.sender, subject, body)
            logging.info("Sent %s confirmation to %s", command.command, _mask(command.sender))
        except Exception as exc:
            logging.error("Failed to send confirmation to %s: %s", _mask(command.sender), exc)

    if subscribers != before:
        _save_subscribers(subscribers)
        logging.info("Updated %s with %d subscriber(s)", SUBSCRIBERS_FILE, len(subscribers))
    else:
        logging.info("No subscriber changes")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
