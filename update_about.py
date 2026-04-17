#!/usr/bin/env python3
"""
update_about.py

Pushes content/about.html to all "about" / informational pages.
Run this whenever you add a new platform or change any links.

Usage:
    python update_about.py

Or trigger via GitHub Actions: Actions → Update About Pages

Platforms updated:
  - WordPress.com  (clambakesanta.wordpress.com/about)

To add a new platform's about page:
  1. Add its section to content/about.html
  2. Add a publisher function below and call it in main()
  3. Add its required secrets to the workflow
"""
from __future__ import annotations
import os
from pathlib import Path

import requests

ABOUT_FILE = Path("content/about.html")


def load_about() -> str:
    return ABOUT_FILE.read_text(encoding="utf-8")


def update_wordpress(content: str) -> bool:
    token   = os.environ.get("WORDPRESS_TOKEN", "").strip()
    blog_id = os.environ.get("WORDPRESS_BLOG_ID", "").strip()

    if not token or not blog_id:
        print("  WordPress: WORDPRESS_TOKEN or WORDPRESS_BLOG_ID not set — skipping")
        return False

    # Page ID 1 = About page (slug: about)
    resp = requests.post(
        f"https://public-api.wordpress.com/rest/v1.1/sites/{blog_id}/posts/1",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": "About", "content": content, "status": "publish"},
        timeout=30,
    )
    if resp.status_code == 200:
        url = resp.json().get("URL", "")
        print(f"  WordPress: updated → {url}")
        return True
    else:
        print(f"  WordPress: FAILED {resp.status_code} — {resp.text[:200]}")
        return False


# ── Add new platform publishers here ─────────────────────────────────────────
# def update_medium(content: str) -> bool: ...
# def update_ghost(content: str) -> bool: ...


def main():
    content = load_about()
    print(f"Loaded content/about.html ({len(content)} chars)")

    results = {}
    results["wordpress"] = update_wordpress(content)

    ok      = [k for k, v in results.items() if v]
    skipped = [k for k, v in results.items() if not v]

    print(f"\nDone — updated: {ok or 'none'}  |  skipped: {skipped or 'none'}")


if __name__ == "__main__":
    main()
