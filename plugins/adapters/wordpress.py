"""
wordpress — Adapter plugin.

Posts the daily haiku collection as a single blog entry on WordPress.com.

Each day becomes one post titled "Clam Bake Santa — YYYY-MM-DD" with
all haikus formatted as sections, mirroring the GitHub Pages layout.

Setup (one-time):
  1. Create a free WordPress.com account and site (e.g. clambakesanta.wordpress.com)
  2. Register an app at https://developer.wordpress.com/apps/
     - Type: Web, Redirect URL: http://localhost
  3. Run the OAuth2 flow to get an access token (see README)
  4. Add two GitHub Secrets:
       WORDPRESS_TOKEN   = (OAuth2 access token)
       WORDPRESS_BLOG_ID = (numeric blog ID returned during OAuth)
  5. Add "wordpress" to adapters in config.yml

If either secret is missing, this adapter skips silently.
"""
from __future__ import annotations
import os

import requests

from framework.registry import register
from framework.adapters.base import BaseAdapter
from framework.models import Result

API_BASE = "https://public-api.wordpress.com/rest/v1.1"


def _build_post(haiku_records: list[dict], date_str: str, base_url: str) -> tuple[str, str, str]:
    """Return (title, html_content, excerpt) for the WordPress post."""
    title = f"Clam Bake Santa — {date_str}"

    sections = ""
    for rec in haiku_records:
        theme = rec.get("theme", "")
        display_theme = (
            f"Happy {theme}" if theme.lower().startswith("birthday") else theme
        )
        lines = rec["haiku"].split("\n")
        poem_lines = [ln.rstrip(",") for ln in lines[:-1]]
        hashtag_line = lines[-1] if lines else ""

        poem_html = "<br>\n".join(poem_lines)
        sections += f"""
<div style="margin:2rem 0;padding:1.5rem;background:#fdfaf5;border-left:4px solid #2c6e49;border-radius:4px;">
  <h3 style="margin:0 0 0.8rem;color:#2c6e49;font-size:1rem;text-transform:uppercase;
             letter-spacing:0.05em;">{display_theme}</h3>
  <p style="margin:0 0 0.5rem;font-family:Georgia,serif;font-size:1.1rem;line-height:1.9;">
    {poem_html}
  </p>
  <p style="margin:0;color:#666;font-size:0.85rem;">{hashtag_line}</p>
</div>"""

    footer = (
        f'<hr style="margin:2rem 0;border:none;border-top:1px solid #e0d9cc;">'
        f'<p style="color:#666;font-size:0.85rem;text-align:center;">'
        f'View the full archive at <a href="{base_url}">{base_url}</a><br>'
        f'Subscribe to the email list: send SUBSCRIBE to clambakesanta@gmail.com</p>'
    )

    # Clean plain-text excerpt for the WordPress blog index page
    excerpt_lines = []
    for rec in haiku_records:
        theme = rec.get("theme", "")
        display_theme = (
            f"Happy {theme}" if theme.lower().startswith("birthday") else theme
        )
        lines = rec["haiku"].split("\n")
        poem_lines = [ln.rstrip(",") for ln in lines[:3]]
        excerpt_lines.append(f"{display_theme}: {' / '.join(poem_lines)}")
    excerpt = "\n".join(excerpt_lines)

    return title, sections + footer, excerpt


@register("adapters", "wordpress")
class WordPressAdapter(BaseAdapter):
    """
    Posts today's haiku collection as a single WordPress.com blog entry.
    Skips silently if WORDPRESS_TOKEN or WORDPRESS_BLOG_ID are not set.
    """

    def publish(self, result: Result) -> bool:
        token   = os.environ.get("WORDPRESS_TOKEN", "").strip()
        blog_id = os.environ.get("WORDPRESS_BLOG_ID", "").strip()

        if not token or not blog_id:
            return False  # Not configured — skip silently

        haiku_records = result.metadata.get("haikus", [])
        if not haiku_records:
            return True

        base_url = self.config.get("site_base_url", "").rstrip("/")
        title, content, excerpt = _build_post(haiku_records, result.event.date_str, base_url)

        try:
            resp = requests.post(
                f"{API_BASE}/sites/{blog_id}/posts/new",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                json={
                    "title":   title,
                    "content": content,
                    "excerpt": excerpt,
                    "status":  "publish",
                    "tags":    ["haiku", "poetry", "daily", "ClamBakeSanta"],
                    "format":  "standard",
                },
                timeout=30,
            )
            resp.raise_for_status()
            post_url = resp.json().get("URL", "")
            print(f"  WordPress: published → {post_url}")
            return True
        except Exception as exc:
            print(f"  WordPress error: {exc}")
            return False
