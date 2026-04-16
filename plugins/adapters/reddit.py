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

SUBREDDIT = "haiku"
USER_AGENT = "ClamBakeSanta/1.0 (by u/TheClamBakeSanta)"


def _haiku_title(haiku_text: str) -> str:
    """
    Build the r/haiku title from a haiku.

    r/haiku requires the title to be the haiku itself in the format:
        first line / second line / third line

    The haiku_text has 4 lines: 3 poem lines + 1 hashtag line.
    We only use the first 3.
    """
    lines = [ln.strip() for ln in haiku_text.strip().splitlines() if ln.strip()]
    poem_lines = lines[:3]   # drop the hashtag line
    return " / ".join(poem_lines)


def _post_body(theme: str) -> str:
    """
    Build the post body.

    Birthdays  → "Happy Birthday Charlie Chaplin from u/TheClamBakeSanta"
    Holidays   → "Happy National Eggs Benedict Day from u/TheClamBakeSanta"
    """
    theme = theme.strip()
    if theme.lower().startswith("birthday "):
        display = f"Happy {theme}"          # "Happy Birthday Charlie Chaplin"
    else:
        display = f"Happy {theme}"          # "Happy National Eggs Benedict Day"
    return f"{display} from u/TheClamBakeSanta"


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
                user_agent=USER_AGENT,
            )
            subreddit = reddit.subreddit(SUBREDDIT)
        except Exception as exc:
            print(f"  Reddit auth error: {exc}")
            return False

        posted = 0
        errors = 0
        for i, rec in enumerate(haiku_records):
            if i > 0:
                time.sleep(60)   # Reddit rate limit: 1 post/minute for new accounts

            title = _haiku_title(rec["haiku"])
            body  = _post_body(rec["theme"])

            try:
                submission = subreddit.submit(title=title, selftext=body)
                print(f"  Reddit posted: {submission.shortlink}  [{rec['theme']}]")
                posted += 1
            except Exception as exc:
                print(f"  Reddit post failed [{rec['theme']}]: {exc}")
                errors += 1

        print(f"  Reddit: {posted} posted, {errors} errors")
        return errors == 0 or posted > 0
