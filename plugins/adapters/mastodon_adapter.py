"""
mastodon_adapter — Adapter plugin.

Posts each haiku as a separate toot on Mastodon.
Mastodon is a free, open-source social network with a public API.
No paid tier required. The API has been stable for years.

Setup (one-time, ~5 minutes):
  1. Create a free account on any Mastodon instance
     Recommended: mastodon.social or fosstodon.org
  2. Go to: Preferences → Development → New Application
     - Name: ClamBakeSanta
     - Scopes: write:statuses, read:statuses
       (write to post; read to fetch engagement metrics)
  3. Click Submit, then copy "Your access token"
  4. Add two GitHub Secrets:
       MASTODON_INSTANCE_URL  = https://mastodon.social  (your instance)
       MASTODON_ACCESS_TOKEN  = (the token you copied)
  5. Add "mastodon" to adapters in config.yml

If either secret is missing, this adapter skips silently.

Rate limits: 300 posts per 5 minutes — we post a few haikus per day, nowhere near this.
"""
from __future__ import annotations
import os
import time

import requests

from framework.registry import register
from framework.adapters.base import BaseAdapter
from framework.models import Result

MAX_TOOT_LENGTH = 500  # Mastodon standard limit
POST_DELAY_SECONDS = 60  # 1 minute between toots — staggers posts throughout the morning


def _format_toot(rec: dict, date_str: str) -> str:
    """Format a single haiku record as a Mastodon toot."""
    lines = rec["haiku"].split("\n")
    # Last line is the hashtag line, rest is the poem
    poem = "\n".join(lines[:-1])
    hashtag_line = lines[-1] if lines else ""
    # Build an event-specific hashtag (e.g. #HappyScrabbleDay, #HappyBirthdayThomasJefferson)
    tag = rec.get("tag", "")
    event_tag = tag if tag.lower().startswith("happybirthday") else f"Happy{tag}"
    toot = f"{poem}\n\n{hashtag_line}\n\n#{date_str.replace('-', '')} #{event_tag} #ClamBakeSanta"
    return toot[:MAX_TOOT_LENGTH]


@register("adapters", "mastodon")
class MastodonAdapter(BaseAdapter):
    """
    Posts each haiku as an individual Mastodon status.
    Skips gracefully if credentials are not configured.
    """

    def publish(self, result: Result) -> bool:
        instance_url = os.environ.get("MASTODON_INSTANCE_URL", "").rstrip("/")
        access_token = os.environ.get("MASTODON_ACCESS_TOKEN", "").strip()

        if not instance_url or not access_token:
            return False  # Not configured — skip silently

        haiku_records = result.metadata.get("haikus", [])
        if not haiku_records:
            return False

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        endpoint = f"{instance_url}/api/v1/statuses"
        posted = 0

        for rec in haiku_records:
            toot = _format_toot(rec, result.event.date_str)
            resp = requests.post(
                endpoint,
                data={"status": toot, "visibility": "public"},
                headers=headers,
                timeout=15,
            )
            resp.raise_for_status()
            resp_data = resp.json()
            # Save post ID/URL for engagement tracking
            try:
                from framework.post_store import save_post_id
                save_post_id(
                    self.config,
                    result.event.date_str,
                    rec.get("tag", ""),
                    "mastodon",
                    {"id": resp_data.get("id", ""), "url": resp_data.get("url", "")},
                )
            except Exception:
                pass
            posted += 1
            if posted < len(haiku_records):
                time.sleep(POST_DELAY_SECONDS)  # Be polite to the instance

        return True
