#!/usr/bin/env python3
"""
check_engagement.py

Fetches current engagement metrics for every tracked post and writes them
to partitioned day files under state/engagement/.

State layout:
  state/post_ids/YYYY-MM-DD.json    ← written by adapters after each post
  state/post_ids/summary.json       ← rolling 7-day index (auto-rebuilt)
  state/engagement/YYYY-MM-DD.json  ← engagement metrics per day
  state/engagement/summary.json     ← rolling 7-day summary (auto-rebuilt)

Engagement score formula:
    score = likes
          + (2 × shares / boosts / reposts)
          + (3 × replies / comments)

Platforms checked:
  - Mastodon   — favourites_count, reblogs_count, replies_count
  - Bluesky    — likeCount, repostCount, replyCount
  - Reddit     — score (upvotes − downvotes), num_comments

Skips any platform whose credentials are not configured.

Usage:
    python check_engagement.py [--days N]   # default: check last 3 days
"""
from __future__ import annotations

import argparse
import os
import pathlib
import sys
from datetime import date, datetime, timedelta, timezone

import requests
import yaml


# ── Config ────────────────────────────────────────────────────────────────────

def load_config() -> dict:
    cfg_path = pathlib.Path("config.yml")
    if cfg_path.exists():
        return yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    return {}


# ── Engagement score ──────────────────────────────────────────────────────────

def compute_score(likes: int = 0, shares: int = 0, replies: int = 0) -> int:
    """
    score = likes + (2 × shares) + (3 × replies)

    Shares extend reach → ×2.
    Replies signal real conversation → ×3.
    """
    return int(likes) + (2 * int(shares)) + (3 * int(replies))


# ── Mastodon ──────────────────────────────────────────────────────────────────

def check_mastodon(post_info: dict) -> dict | None:
    instance_url = os.environ.get("MASTODON_INSTANCE_URL", "").rstrip("/")
    access_token = os.environ.get("MASTODON_ACCESS_TOKEN", "").strip()
    post_id      = post_info.get("id", "")

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
        upvotes  = sub.score
        comments = sub.num_comments
        return {
            "id":       post_id,
            "url":      post_info.get("url", ""),
            "upvotes":  upvotes,
            "comments": comments,
            "score":    compute_score(upvotes, 0, comments),
        }
    except Exception as exc:
        print(f"  Reddit check failed ({post_id}): {exc}", file=sys.stderr)
        return None


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Fetch engagement metrics for tracked posts"
    )
    parser.add_argument(
        "--days", type=int, default=3,
        help="How many days back to check (default: 3)"
    )
    args = parser.parse_args()

    config = load_config()

    # Import stores after config is known (they need config for paths)
    from framework.post_store      import load_summary as load_post_ids
    from framework.engagement_store import load_day, save_day
    from framework.haiku_log        import build_index

    post_ids    = load_post_ids(config)
    haiku_index = build_index(config)

    if not post_ids:
        print("No post IDs found — run the daily workflow first.")
        return

    # Authenticate platform clients once
    bsky_session  = _bluesky_session()
    reddit_client = _reddit_client()

    now = datetime.now(timezone.utc).isoformat()

    # Determine which dates to check
    today      = date.today()
    check_from = today - timedelta(days=args.days)
    dates_to_check = sorted(
        d for d in post_ids
        if check_from <= date.fromisoformat(d) <= today
    )

    if not dates_to_check:
        print(f"No posts found in the last {args.days} day(s).")
        return

    print(f"Checking engagement for {len(dates_to_check)} date(s): "
          f"{', '.join(dates_to_check)}")

    for date_str in dates_to_check:
        day_posts   = post_ids[date_str]          # { tag: { platform: {...} } }
        day_data    = load_day(config, date_str)  # existing engagement (may be empty)
        changed     = False

        for tag, platforms in day_posts.items():
            meta  = haiku_index.get(tag, {})
            entry = day_data.setdefault(tag, {
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
                    changed = True
                    print(f"  {date_str} [{tag}] mastodon  "
                          f"score={result['score']}  "
                          f"❤️{result['likes']} 🔁{result['boosts']} "
                          f"💬{result['replies']}")

            # --- Bluesky ---
            if "bluesky" in platforms and bsky_session:
                result = check_bluesky(platforms["bluesky"], bsky_session)
                if result:
                    plat_results["bluesky"] = result
                    changed = True
                    print(f"  {date_str} [{tag}] bluesky   "
                          f"score={result['score']}  "
                          f"❤️{result['likes']} 🔁{result['reposts']} "
                          f"💬{result['replies']}")

            # --- Reddit ---
            if "reddit" in platforms and reddit_client:
                result = check_reddit(platforms["reddit"], reddit_client)
                if result:
                    plat_results["reddit"] = result
                    changed = True
                    print(f"  {date_str} [{tag}] reddit    "
                          f"score={result['score']}  "
                          f"⬆️{result['upvotes']} 💬{result['comments']}")

            # Recompute total across all platforms
            entry["total_score"]  = sum(
                p.get("score", 0) for p in plat_results.values()
            )
            entry["last_checked"] = now

        if changed:
            # Write day file + rebuild summary.json atomically
            save_day(config, date_str, day_data)
            print(f"  → state/engagement/{date_str}.json updated")

    print("\nDone.")


if __name__ == "__main__":
    main()
