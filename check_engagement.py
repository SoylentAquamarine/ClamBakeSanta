#!/usr/bin/env python3
"""
check_engagement.py

Fetches current engagement metrics for every tracked post and saves them
to state/engagement.json.

Engagement score formula:
    score = (likes / favourites / upvotes)
          + (2 × shares / boosts / reblogs / reposts)
          + (3 × comments / replies)

This gives extra weight to shares (they extend reach) and even more to
replies (they indicate genuine conversation).

Platforms checked:
  - Mastodon   — via instance REST API (favourites, reblogs, replies)
  - Bluesky    — via AT Protocol app.bsky.feed.getPosts (likeCount, repostCount, replyCount)
  - Reddit     — via PRAW (score = upvotes−downvotes, num_comments)

Run daily via GitHub Actions (check_engagement.yml).
Skips any platform whose credentials are not configured.

Output: state/engagement.json
  {
    "2026-04-17": {
      "NationalHaikuDay": {
        "theme":   "National Haiku Day",
        "haiku":   "...",
        "platforms": {
          "mastodon": {"id": "...", "url": "...", "likes": 4, "boosts": 1,
                       "replies": 0, "score": 6},
          "bluesky":  {"uri": "...", "likes": 2, "reposts": 0,
                       "replies": 1, "score": 5},
          "reddit":   {"id": "...", "url": "...", "upvotes": 3,
                       "comments": 2, "score": 9}
        },
        "total_score":  20,
        "last_checked": "2026-04-18T06:00:00+00:00"
      }
    }
  }

Usage:
    python check_engagement.py [--days N]   # default: check last 3 days
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys
from datetime import datetime, timezone

import requests
import yaml

# ── Config ────────────────────────────────────────────────────────────────────

def load_config() -> dict:
    cfg_path = pathlib.Path("config.yml")
    if cfg_path.exists():
        return yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    return {}


def _state_dir(config: dict) -> pathlib.Path:
    d = pathlib.Path(config.get("state_dir", "state"))
    d.mkdir(parents=True, exist_ok=True)
    return d


def _load_json(path: pathlib.Path) -> dict | list:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _save_json(path: pathlib.Path, data) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


# ── Engagement score formula ──────────────────────────────────────────────────

def compute_score(likes: int = 0, shares: int = 0, replies: int = 0) -> int:
    """
    score = likes + (2 × shares) + (3 × replies)

    Shares extend reach → weight 2.
    Replies signal real conversation → weight 3.
    """
    return likes + (2 * shares) + (3 * replies)


# ── Mastodon ──────────────────────────────────────────────────────────────────

def check_mastodon(post_info: dict) -> dict | None:
    instance_url  = os.environ.get("MASTODON_INSTANCE_URL", "").rstrip("/")
    access_token  = os.environ.get("MASTODON_ACCESS_TOKEN", "").strip()
    post_id       = post_info.get("id", "")

    if not instance_url or not access_token or not post_id:
        return None

    try:
        resp = requests.get(
            f"{instance_url}/api/v1/statuses/{post_id}",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=15,
        )
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        data    = resp.json()
        likes   = data.get("favourites_count", 0)
        boosts  = data.get("reblogs_count", 0)
        replies = data.get("replies_count", 0)
        return {
            "id":      post_id,
            "url":     post_info.get("url", ""),
            "likes":   likes,
            "boosts":  boosts,
            "replies": replies,
            "score":   compute_score(likes, boosts, replies),
        }
    except Exception as exc:
        print(f"  Mastodon check failed ({post_id}): {exc}", file=sys.stderr)
        return None


# ── Bluesky ───────────────────────────────────────────────────────────────────

BLUESKY_API = "https://bsky.social/xrpc"

def _bluesky_session() -> dict | None:
    handle   = os.environ.get("BLUESKY_HANDLE", "").strip()
    password = os.environ.get("BLUESKY_APP_PASSWORD", "").strip()
    if not handle or not password:
        return None
    try:
        resp = requests.post(
            f"{BLUESKY_API}/com.atproto.server.createSession",
            json={"identifier": handle, "password": password},
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        print(f"  Bluesky auth failed: {exc}", file=sys.stderr)
        return None


def check_bluesky(post_info: dict, session: dict) -> dict | None:
    uri = post_info.get("uri", "")
    if not uri:
        return None

    try:
        resp = requests.get(
            f"{BLUESKY_API}/app.bsky.feed.getPosts",
            headers={"Authorization": f"Bearer {session['accessJwt']}"},
            params={"uris": uri},
            timeout=15,
        )
        resp.raise_for_status()
        posts = resp.json().get("posts", [])
        if not posts:
            return None
        post    = posts[0]
        likes   = post.get("likeCount", 0)
        reposts = post.get("repostCount", 0)
        replies = post.get("replyCount", 0)
        return {
            "uri":     uri,
            "likes":   likes,
            "reposts": reposts,
            "replies": replies,
            "score":   compute_score(likes, reposts, replies),
        }
    except Exception as exc:
        print(f"  Bluesky check failed ({uri}): {exc}", file=sys.stderr)
        return None


# ── Reddit ────────────────────────────────────────────────────────────────────

def _reddit_client():
    try:
        import praw
    except ImportError:
        return None
    client_id     = os.environ.get("REDDIT_CLIENT_ID", "").strip()
    client_secret = os.environ.get("REDDIT_CLIENT_SECRET", "").strip()
    username      = os.environ.get("REDDIT_USERNAME", "").strip()
    password      = os.environ.get("REDDIT_PASSWORD", "").strip()
    if not all([client_id, client_secret, username, password]):
        return None
    try:
        return praw.Reddit(
            client_id=client_id,
            client_secret=client_secret,
            username=username,
            password=password,
            user_agent="ClamBakeSanta/1.0 (engagement checker)",
        )
    except Exception as exc:
        print(f"  Reddit auth failed: {exc}", file=sys.stderr)
        return None


def check_reddit(post_info: dict, reddit) -> dict | None:
    post_id = post_info.get("id", "")
    if not post_id or not reddit:
        return None
    try:
        sub      = reddit.submission(id=post_id)
        upvotes  = sub.score          # net score (upvotes − downvotes)
        comments = sub.num_comments
        return {
            "id":       post_id,
            "url":      post_info.get("url", ""),
            "upvotes":  upvotes,
            "comments": comments,
            # Reddit has no shares; comments get ×3 weight
            "score":    compute_score(upvotes, 0, comments),
        }
    except Exception as exc:
        print(f"  Reddit check failed ({post_id}): {exc}", file=sys.stderr)
        return None


# ── Haiku metadata lookup ─────────────────────────────────────────────────────

def _build_haiku_index(config: dict) -> dict:
    """Return { tag: {"theme": ..., "haiku": ...} } from the haiku log."""
    from framework.haiku_log import load_log
    index = {}
    for entry in load_log(config):
        index[entry.get("tag", "")] = {
            "theme": entry.get("theme", ""),
            "haiku": entry.get("haiku", ""),
            "date":  entry.get("date", ""),
        }
    return index


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Fetch engagement metrics for tracked posts")
    parser.add_argument("--days", type=int, default=3,
                        help="How many days back to check (default: 3)")
    args = parser.parse_args()

    config      = load_config()
    state_dir   = _state_dir(config)
    post_ids    = _load_json(state_dir / "post_ids.json")
    engagement  = _load_json(state_dir / "engagement.json")
    haiku_index = _build_haiku_index(config)

    if not post_ids:
        print("No post IDs found in state/post_ids.json — nothing to check.")
        return

    # Authenticate platform clients once
    bsky_session  = _bluesky_session()
    reddit_client = _reddit_client()

    now = datetime.now(timezone.utc).isoformat()

    # Determine which dates to check
    from datetime import date, timedelta
    today      = date.today()
    check_from = today - timedelta(days=args.days)
    dates_to_check = [
        d for d in post_ids
        if check_from <= date.fromisoformat(d) <= today
    ]

    if not dates_to_check:
        print(f"No posts found in the last {args.days} day(s).")
        return

    print(f"Checking engagement for {len(dates_to_check)} date(s): {', '.join(sorted(dates_to_check))}")

    for date_str in sorted(dates_to_check):
        day_posts    = post_ids[date_str]           # { tag: { platform: {...} } }
        day_results  = engagement.setdefault(date_str, {})

        for tag, platforms in day_posts.items():
            meta    = haiku_index.get(tag, {})
            entry   = day_results.setdefault(tag, {
                "theme":        meta.get("theme", tag),
                "haiku":        meta.get("haiku", ""),
                "platforms":    {},
                "total_score":  0,
                "last_checked": now,
            })

            plat_results = entry.setdefault("platforms", {})

            # --- Mastodon ---
            if "mastodon" in platforms:
                result = check_mastodon(platforms["mastodon"])
                if result:
                    plat_results["mastodon"] = result
                    print(f"  {date_str} {tag} mastodon: score={result['score']} "
                          f"(❤️{result['likes']} 🔁{result['boosts']} 💬{result['replies']})")

            # --- Bluesky ---
            if "bluesky" in platforms and bsky_session:
                result = check_bluesky(platforms["bluesky"], bsky_session)
                if result:
                    plat_results["bluesky"] = result
                    print(f"  {date_str} {tag} bluesky: score={result['score']} "
                          f"(❤️{result['likes']} 🔁{result['reposts']} 💬{result['replies']})")

            # --- Reddit ---
            if "reddit" in platforms and reddit_client:
                result = check_reddit(platforms["reddit"], reddit_client)
                if result:
                    plat_results["reddit"] = result
                    print(f"  {date_str} {tag} reddit: score={result['score']} "
                          f"(⬆️{result['upvotes']} 💬{result['comments']})")

            # Recompute total score across all platforms
            entry["total_score"]  = sum(
                p.get("score", 0) for p in plat_results.values()
            )
            entry["last_checked"] = now

    _save_json(state_dir / "engagement.json", engagement)
    print(f"\nEngagement data saved → {state_dir / 'engagement.json'}")


if __name__ == "__main__":
    main()
