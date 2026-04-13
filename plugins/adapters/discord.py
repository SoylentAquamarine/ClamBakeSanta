"""
discord — Adapter plugin.

Posts today's haikus to a Discord channel via webhook.
No Discord account required for the bot — just a webhook URL.

Setup:
  1. In your Discord server: Edit Channel → Integrations → Webhooks → New Webhook
  2. Copy the webhook URL
  3. Add it as a GitHub Secret named DISCORD_WEBHOOK_URL
  4. Add "discord" to the adapters list in config.yml

If DISCORD_WEBHOOK_URL is not set, this adapter silently skips (returns False).
This means Discord is opt-in — the rest of the system keeps running without it.
"""
from __future__ import annotations
import os
import json

import requests

from framework.registry import register
from framework.adapters.base import BaseAdapter
from framework.models import Result

MAX_MESSAGE_LENGTH = 2000  # Discord hard limit


def _format_message(result: Result, site_url: str) -> str:
    """Format haiku records into a Discord message."""
    haiku_records = result.metadata.get("haikus", [])
    date_str = result.event.date_str

    if not haiku_records:
        return f"🌊 **Clam Bake Santa** — {date_str}\nNo holidays today. The tide is quiet."

    lines = [f"🦪 **Clam Bake Santa** — {date_str}\n"]
    for rec in haiku_records:
        lines.append(f"**{rec['theme']}**")
        lines.append(rec["haiku"])
        lines.append("")

    if site_url:
        lines.append(f"📖 Full archive: {site_url}/archives/")

    return "\n".join(lines)[:MAX_MESSAGE_LENGTH]


@register("adapters", "discord")
class DiscordAdapter(BaseAdapter):
    """
    Sends a formatted haiku message to a Discord channel webhook.
    Skips gracefully if DISCORD_WEBHOOK_URL is not configured.
    """

    def publish(self, result: Result) -> bool:
        webhook_url = os.environ.get("DISCORD_WEBHOOK_URL", "").strip()
        if not webhook_url:
            return False  # Not configured — skip silently

        site_url = self.config.get("site_base_url", "").rstrip("/")
        message = _format_message(result, site_url)

        payload = {"content": message, "username": "ClamBakeSanta 🦪"}
        resp = requests.post(
            webhook_url,
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"},
            timeout=15,
        )
        resp.raise_for_status()
        return True
