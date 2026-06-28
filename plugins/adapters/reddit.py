"""
reddit — Adapter plugin.

Posts each daily haiku to r/haiku as a separate submission.

Reddit r/haiku title format (required by the subreddit rules):
  first line / second line / third line

Post body:
  Happy National Eggs Benedict Day from u/TheClamBakeSanta
  — or —
  Happy Birthday Charlie Chaplin from u/TheClamBakeSanta

Setup (one-time):
  1. Log in as u/TheClamBakeSanta at reddit.com
  2. Go to https://www.reddit.com/prefs/apps
  3. Click "create another app" at the bottom
     - Name:        ClamBakeSanta
     - Type:        script
     - Description: (anything)
     - redirect uri: http://localhost:8080
  4. Note the client ID (under the app name) and secret
  5. Add four GitHub Secrets:
       REDDIT_CLIENT_ID     = (client id, short string under app name)
       REDDIT_CLIENT_SECRET = (secret)
       REDDIT_USERNAME      = TheClamBakeSanta
       REDDIT_PASSWORD      = (account password)
  6. Add "reddit" to adapters in config.yml

If any secret is missing, this adapter skips silently.
"""
from __future__ import annotations
import os
import time

from framework.registry import register
from framework.adapters.base import BaseAdapter
from framework.models import Result

def _format_post(rec: dict, date_str: str, username: str) -> tuple[str, str]:
    """Return (title, body) for a Reddit profile post."""
    lines = rec["haiku"].split("\n")
    poem_lines = [ln.rstrip(",") for ln in lines[:-1]]

    # Title is the haiku: line one / line two / line three
    title = " / ".join(poem_lines)

    # Body is the announcement
    theme = rec.get("theme", "")
    if theme.lower().startswith("birthday "):
        announcement = f"Happy {theme}"
    else:
        announcement = f"Happy {theme}"

    body = (
        f"{announcement}\n\n"
        f"*Daily haiku by [Clam Bake Santa](https://soylentaquamarine.github.io/ClamBakeSanta)*"
    )

    return title, body


@register("adapters", "reddit")
class RedditAdapter(BaseAdapter):
    """
    Posts each haiku to r/haiku.
    Title = haiku lines joined by ' / '
    Body  = theme attribution line
    """

    def publish(self, result: Result) -> bool:
        client_id     = os.environ.get("REDDIT_CLIENT_ID", "").strip()
        client_secret = os.environ.get("REDDIT_CLIENT_SECRET", "").strip()
        username      = os.environ.get("REDDIT_USERNAME", "").strip()
        password      = os.environ.get("REDDIT_PASSWORD", "").strip()

        if not all([client_id, client_secret, username, password]):
            return False  # Not configured — skip silently

        try:
            import praw
        except ImportError:
            print("  Reddit: praw not installed — run: pip install praw")
            return False

        haiku_records = result.metadata.get("haikus", [])
        if not haiku_records:
            return True

        try:
            reddit = praw.Reddit(
                client_id=client_id,
                client_secret=client_secret,
                username=username,
                password=password,
                user_agent=f"ClamBakeSanta/1.0 (by u/{username})",
            )
            # Post to the user's own profile subreddit to build karma
            subreddit = reddit.subreddit(f"u_{username}")
        except Exception as exc:
            print(f"  Reddit auth error: {exc}")
            return False

        posted = 0
        errors = 0
        for i, rec in enumerate(haiku_records):
            if i > 0:
                time.sleep(60)   # Reddit rate limit: space posts out

            title, body = _format_post(rec, result.event.date_str, username)

            try:
                submission = subreddit.submit(title=title, selftext=body, nsfw=False)
                print(f"  Reddit posted: {submission.shortlink}  [{rec['theme']}]")
                # Save post ID/URL for engagement tracking
                try:
                    from framework.post_store import save_post_id
                    save_post_id(
                        self.config,
                        result.event.date_str,
                        rec.get("tag", ""),
                        "reddit",
                        {"id": submission.id, "url": submission.shortlink},
                    )
                except Exception:
                    pass
                posted += 1
            except Exception as exc:
                print(f"  Reddit post failed [{rec['theme']}]: {exc}")
                errors += 1

        print(f"  Reddit: {posted} posted, {errors} errors")
        return errors == 0 or posted > 0
