"""
bluesky — Adapter plugin.

Posts each haiku as a separate Bluesky post.
Bluesky is a decentralized social network with a free public API.

Setup (one-time, ~5 minutes):
  1. Create a free account at bsky.app
  2. Go to: Settings → Privacy and Security → App Passwords
     - Name: ClamBakeSanta
     - Click Create App Password and copy it
  3. Add two GitHub Secrets:
       BLUESKY_HANDLE       = yourhandle.bsky.social
       BLUESKY_APP_PASSWORD = the app password you copied
  4. Add "bluesky" to adapters in config.yml

If either secret is missing, this adapter skips silently.

Rate limits: very generous — we post a few haikus per day, nowhere near limits.
"""
from __future__ import annotations
import os
import time
import json
import re

import requests

from framework.registry import register
from framework.adapters.base import BaseAdapter
from framework.models import Result

MAX_POST_LENGTH = 300   # Bluesky character limit
POST_DELAY_SECONDS = 60  # 1 minute between posts, same as Mastodon

BLUESKY_API = "https://bsky.social/xrpc"


def _format_post(rec: dict, date_str: str) -> str:
    """Format a single haiku record as a Bluesky post."""
    lines = rec["haiku"].split("\n")
    poem = "\n".join(lines[:-1])
    hashtag_line = lines[-1] if lines else ""
    tag = rec.get("tag", "")
    event_tag = tag if tag.lower().startswith("happybirthday") else f"Happy{tag}"
    post = f"{poem}\n\n{hashtag_line}\n\n#{date_str.replace('-', '')} #{event_tag} #ClamBakeSanta"
    return post[:MAX_POST_LENGTH]


def _create_session(handle: str, app_password: str) -> dict:
    """Authenticate with Bluesky and return session tokens."""
    resp = requests.post(
        f"{BLUESKY_API}/com.atproto.server.createSession",
        json={"identifier": handle, "password": app_password},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def _extract_facets(text: str) -> list[dict]:
    """
    Detect hashtags in the post text and return Bluesky facet annotations.
    Bluesky needs facets to render hashtags as clickable links.
    """
    facets = []
    encoded = text.encode("utf-8")
    for m in re.finditer(r"#(\w+)", text):
        tag = m.group(1)
        # Find byte positions (Bluesky uses UTF-8 byte offsets)
        start_byte = len(text[:m.start()].encode("utf-8"))
        end_byte = len(text[:m.end()].encode("utf-8"))
        facets.append({
            "index": {"byteStart": start_byte, "byteEnd": end_byte},
            "features": [{"$type": "app.bsky.richtext.facet#tag", "tag": tag}],
        })
    return facets


def _post_record(session: dict, text: str) -> dict:
    """Create a single Bluesky post (record)."""
    resp = requests.post(
        f"{BLUESKY_API}/com.atproto.repo.createRecord",
        headers={"Authorization": f"Bearer {session['accessJwt']}"},
        json={
            "repo": session["did"],
            "collection": "app.bsky.feed.post",
            "record": {
                "$type": "app.bsky.feed.post",
                "text": text,
                "facets": _extract_facets(text),
                "createdAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            },
        },
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


@register("adapters", "bluesky")
class BlueskyAdapter(BaseAdapter):
    """
    Posts each haiku as an individual Bluesky post.
    Skips gracefully if credentials are not configured.
    """

    def publish(self, result: Result) -> bool:
        handle = os.environ.get("BLUESKY_HANDLE", "").strip()
        app_password = os.environ.get("BLUESKY_APP_PASSWORD", "").strip()

        if not handle or not app_password:
            return False  # Not configured — skip silently

        haiku_records = result.metadata.get("haikus", [])
        if not haiku_records:
            return False

        session = _create_session(handle, app_password)
        posted = 0

        for rec in haiku_records:
            text = _format_post(rec, result.event.date_str)
            _post_record(session, text)
            posted += 1
            if posted < len(haiku_records):
                time.sleep(POST_DELAY_SECONDS)

        return True
