"""
Post ID / URL store.

After each adapter publishes a haiku, it saves the platform's returned
post ID and URL here.  The engagement checker then reads these to know
which posts to query for likes/boosts/replies.

File: state/post_ids.json
Structure:
  {
    "2026-04-17": {
      "NationalHaikuDay": {
        "mastodon": {"id": "112345678", "url": "https://mastodon.social/..."},
        "bluesky":  {"uri": "at://did:plc:.../app.bsky.feed.post/...", "cid": "..."},
        "reddit":   {"id": "abc123", "url": "https://redd.it/abc123"}
      }
    }
  }
"""
from __future__ import annotations

import json
import pathlib


def _store_path(config: dict) -> pathlib.Path:
    state_dir = pathlib.Path(config.get("state_dir", "state"))
    state_dir.mkdir(parents=True, exist_ok=True)
    return state_dir / "post_ids.json"


def load_post_ids(config: dict) -> dict:
    """Return the entire post ID store."""
    path = _store_path(config)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def save_post_id(
    config: dict,
    date_str: str,
    tag: str,
    platform: str,
    data: dict,
) -> None:
    """
    Save a post identifier for a single haiku on a specific platform.

    Parameters
    ----------
    date_str : run date, e.g. "2026-04-17"
    tag      : haiku tag key, e.g. "NationalHaikuDay"
    platform : "mastodon" | "bluesky" | "reddit" | ...
    data     : dict of platform-specific IDs/URLs returned by the API
    """
    store = load_post_ids(config)
    store.setdefault(date_str, {}).setdefault(tag, {})[platform] = data
    _store_path(config).write_text(
        json.dumps(store, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def get_posts_for_date(config: dict, date_str: str) -> dict:
    """Return { tag: { platform: {...} } } for a specific date."""
    return load_post_ids(config).get(date_str, {})
