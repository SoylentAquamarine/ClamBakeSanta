#!/usr/bin/env python3
"""
One-time backfill: finds all past ClamBakeSanta WordPress.com posts and writes
their IDs into state/post_ids/ so check_engagement can track likes going forward.

Matches posts by title prefix "Clam Bake Santa — YYYY-MM-DD".
Skips any date that already has a WordPress post ID saved.

Usage:
  python scripts/backfill_wordpress_posts.py
"""
from __future__ import annotations
import os
import pathlib
import sys
from datetime import date

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import requests
from framework.config import load_config
from framework.post_store import save_post_id, load_day

WP_API           = "https://public-api.wordpress.com/rest/v1.1"
TITLE_PREFIX     = "Clam Bake Santa — "   # em-dash matches the adapter


def _fetch_all_posts(token: str, blog_id: str) -> list[dict]:
    headers   = {"Authorization": f"Bearer {token}"}
    posts     = []
    page_size = 100
    offset    = 0

    while True:
        resp = requests.get(
            f"{WP_API}/sites/{blog_id}/posts",
            headers=headers,
            params={
                "number": page_size,
                "offset": offset,
                "fields": "ID,URL,title",
                "status": "publish",
            },
            timeout=30,
        )
        resp.raise_for_status()
        page = resp.json().get("posts", [])
        posts.extend(page)
        if len(page) < page_size:
            break
        offset += page_size

    return posts


def main() -> None:
    config  = load_config()
    token   = os.environ.get("WORDPRESS_TOKEN", "").strip()
    blog_id = os.environ.get("WORDPRESS_BLOG_ID", "").strip()

    if not token or not blog_id:
        print("ERROR: WORDPRESS_TOKEN and WORDPRESS_BLOG_ID must be set.", file=sys.stderr)
        sys.exit(1)

    print("Fetching all WordPress posts...")
    posts = _fetch_all_posts(token, blog_id)
    print(f"Found {len(posts)} total posts.")

    saved = skipped = 0

    for post in posts:
        title = post.get("title", "")
        if not title.startswith(TITLE_PREFIX):
            skipped += 1
            continue

        date_str = title[len(TITLE_PREFIX):].strip()
        try:
            date.fromisoformat(date_str)
        except ValueError:
            skipped += 1
            continue

        post_id  = str(post.get("ID", ""))
        post_url = post.get("URL", "")
        if not post_id:
            skipped += 1
            continue

        # Skip if already present
        existing = load_day(config, date_str)
        if existing.get("_wp_daily", {}).get("wordpress", {}).get("id") == post_id:
            print(f"  [{date_str}] already saved — skipping")
            skipped += 1
            continue

        save_post_id(config, date_str, "_wp_daily", "wordpress",
                     {"id": post_id, "url": post_url})
        print(f"  [{date_str}] saved ID={post_id}  {post_url}")
        saved += 1

    print(f"\nDone: {saved} backfilled, {skipped} skipped.")


if __name__ == "__main__":
    main()
