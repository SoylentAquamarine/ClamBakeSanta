"""
telegram — Adapter plugin.

Posts each haiku as a separate message to a public Telegram channel.
Uses the Telegram Bot API — free, no rate limits for small bots.

Setup (one-time):
  1. Message @BotFather on Telegram → /newbot
     - Bot name: ClamBakeSanta
     - Username: ClamBakeSantaBot
     - Copy the API token
  2. Create a public Telegram channel
  3. Add ClamBakeSantaBot as Administrator of the channel
  4. Add two GitHub Secrets:
       TELEGRAM_BOT_TOKEN   = (token from BotFather)
       TELEGRAM_CHANNEL     = @clambakesanta  (your channel username)
  5. Add "telegram" to adapters in config.yml

If either secret is missing, this adapter skips silently.
"""
from __future__ import annotations
import os
import time

import requests

from framework.registry import register
from framework.adapters.base import BaseAdapter
from framework.models import Result

POST_DELAY_SECONDS = 60   # 1 minute between posts
TELEGRAM_API = "https://api.telegram.org"


def _format_message(rec: dict, date_str: str) -> str:
    """Format a single haiku as a Telegram message with MarkdownV2."""
    lines = rec["haiku"].split("\n")
    poem_lines = lines[:-1]
    hashtag_line = lines[-1] if lines else ""

    theme = rec.get("theme", "")
    display_theme = (
        f"Happy {theme}" if theme.lower().startswith("birthday") else theme
    )

    tag = rec.get("tag", "")
    event_tag = tag if tag.lower().startswith("happybirthday") else f"Happy{tag}"

    # Telegram MarkdownV2 requires escaping special chars
    def esc(text: str) -> str:
        for ch in r"\_*[]()~`>#+-=|{}.!":
            text = text.replace(ch, f"\\{ch}")
        return text

    poem = "\n".join(esc(l) for l in poem_lines)
    footer = f"\\#{date_str.replace('-', '')} \\#{event_tag} \\#ClamBakeSanta"

    return (
        f"*{esc(display_theme.upper())}*\n\n"
        f"{poem}\n\n"
        f"_{esc(hashtag_line)}_\n\n"
        f"{footer}"
    )


def _send_message(token: str, channel: str, text: str) -> dict:
    """Send a message to a Telegram channel."""
    resp = requests.post(
        f"{TELEGRAM_API}/bot{token}/sendMessage",
        json={
            "chat_id": channel,
            "text": text,
            "parse_mode": "MarkdownV2",
        },
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


@register("adapters", "telegram")
class TelegramAdapter(BaseAdapter):
    """
    Posts each haiku as an individual Telegram channel message.
    Skips gracefully if credentials are not configured.
    """

    def publish(self, result: Result) -> bool:
        token   = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
        channel = os.environ.get("TELEGRAM_CHANNEL", "").strip()

        if not token or not channel:
            return False  # Not configured — skip silently

        haiku_records = result.metadata.get("haikus", [])
        if not haiku_records:
            return False

        posted = 0
        for rec in haiku_records:
            text = _format_message(rec, result.event.date_str)
            _send_message(token, channel, text)
            posted += 1
            if posted < len(haiku_records):
                time.sleep(POST_DELAY_SECONDS)

        return True
