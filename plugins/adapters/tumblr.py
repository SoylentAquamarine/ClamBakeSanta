"""
tumblr — Adapter plugin.

Posts each haiku as a styled text post on Tumblr.
Tumblr's free API uses OAuth1 — credentials are one-time setup.

Setup (one-time):
  1. Go to tumblr.com/oauth/apps → Register application
     - Name: ClamBakeSanta
     - Callback URL: https://localhost
  2. Copy Consumer Key + Consumer Secret
  3. Run the auth script to get OAuth Token + Secret
  4. Add four GitHub Secrets:
       TUMBLR_CONSUMER_KEY    = (from app registration)
       TUMBLR_CONSUMER_SECRET = (from app registration)
       TUMBLR_OAUTH_TOKEN     = (from auth script)
       TUMBLR_OAUTH_SECRET    = (from auth script)
  5. Add "tumblr" to adapters in config.yml

If any secret is missing, this adapter skips silently.
"""
from __future__ import annotations
import os
import time

import requests
from requests_oauthlib import OAuth1

from framework.registry import register
from framework.adapters.base import BaseAdapter
from framework.models import Result

POST_DELAY_SECONDS = 60  # 1 minute between posts

TUMBLR_API = "https://api.tumblr.com/v2"


def _get_blog_name(auth: OAuth1) -> str:
    """Fetch the primary blog name for the authenticated user."""
    resp = requests.get(f"{TUMBLR_API}/user/info", auth=auth, timeout=15)
    resp.raise_for_status()
    return resp.json()["response"]["user"]["blogs"][0]["name"]


def _format_post(rec: dict, date_str: str) -> dict:
    """Format a haiku record as Tumblr post fields."""
    lines = rec["haiku"].split("\n")
    poem_lines = lines[:-1]
    hashtag_line = lines[-1] if lines else ""

    tag = rec.get("tag", "")
    event_tag = tag if tag.lower().startswith("happybirthday") else f"Happy{tag}"
    theme = rec.get("theme", "")

    # Title: "Happy Birthday Thomas Jefferson" or "National Peach Cobbler Day"
    if theme.lower().startswith("birthday "):
        title = f"Happy {theme}"
    else:
        title = theme

    # Body: poem lines as HTML, then the attribution line
    poem_html = "<br>".join(line for line in poem_lines)
    body = f"<p>{poem_html}</p><p><small>{hashtag_line}</small></p>"

    # Tags: date, event tag, generic haiku tags
    tags = [
        date_str,
        event_tag,
        "ClamBakeSanta",
        "haiku",
        "poetry",
        "dailyhaiku",
    ]

    return {"title": title, "body": body, "tags": ",".join(tags)}


@register("adapters", "tumblr")
class TumblrAdapter(BaseAdapter):
    """
    Posts each haiku as an individual Tumblr text post.
    Skips gracefully if credentials are not configured.
    """

    def publish(self, result: Result) -> bool:
        consumer_key    = os.environ.get("TUMBLR_CONSUMER_KEY", "").strip()
        consumer_secret = os.environ.get("TUMBLR_CONSUMER_SECRET", "").strip()
        oauth_token     = os.environ.get("TUMBLR_OAUTH_TOKEN", "").strip()
        oauth_secret    = os.environ.get("TUMBLR_OAUTH_SECRET", "").strip()

        if not all([consumer_key, consumer_secret, oauth_token, oauth_secret]):
            return False  # Not configured — skip silently

        haiku_records = result.metadata.get("haikus", [])
        if not haiku_records:
            return False

        auth = OAuth1(consumer_key, consumer_secret, oauth_token, oauth_secret)
        blog_name = _get_blog_name(auth)
        posted = 0

        for rec in haiku_records:
            fields = _format_post(rec, result.event.date_str)
            resp = requests.post(
                f"{TUMBLR_API}/blog/{blog_name}/post",
                auth=auth,
                json={
                    "type": "text",
                    "title": fields["title"],
                    "body": fields["body"],
                    "tags": fields["tags"],
                    "native_inline_images": True,
                },
                timeout=15,
            )
            resp.raise_for_status()
            posted += 1
            if posted < len(haiku_records):
                time.sleep(POST_DELAY_SECONDS)

        return True
