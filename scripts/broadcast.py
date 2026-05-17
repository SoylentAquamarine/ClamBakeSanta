#!/usr/bin/env python3
"""
Broadcast a custom message to all configured ClamBakeSanta platforms.

Each platform is skipped silently if its credentials are not set.

Usage:
  python scripts/broadcast.py --title "Title" --message "Your text here"

Or read message from a file:
  python scripts/broadcast.py --title "Title" --message-file msg.txt
"""
from __future__ import annotations
import argparse
import json
import os
import pathlib
import smtplib
import sys
import time
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import requests

# ── Mastodon ──────────────────────────────────────────────────────────────────

def post_mastodon(title: str, message: str) -> bool:
    instance = os.environ.get("MASTODON_INSTANCE_URL", "").rstrip("/")
    token    = os.environ.get("MASTODON_ACCESS_TOKEN", "").strip()
    if not instance or not token:
        print("  [mastodon] skipped — credentials not set")
        return False
    text = f"{title}\n\n{message}" if title else message
    text = text[:500]
    resp = requests.post(
        f"{instance}/api/v1/statuses",
        headers={"Authorization": f"Bearer {token}"},
        json={"status": text, "visibility": "public"},
        timeout=15,
    )
    resp.raise_for_status()
    url = resp.json().get("url", "")
    print(f"  [mastodon] posted → {url}")
    return True


# ── Bluesky ───────────────────────────────────────────────────────────────────

BLUESKY_API = "https://bsky.social/xrpc"


def post_bluesky(title: str, message: str) -> bool:
    handle   = os.environ.get("BLUESKY_HANDLE", "").strip()
    password = os.environ.get("BLUESKY_APP_PASSWORD", "").strip()
    if not handle or not password:
        print("  [bluesky] skipped — credentials not set")
        return False
    session = requests.post(
        f"{BLUESKY_API}/com.atproto.server.createSession",
        json={"identifier": handle, "password": password},
        timeout=15,
    )
    session.raise_for_status()
    sess = session.json()
    text = f"{title}\n\n{message}" if title else message
    text = text[:300]
    now  = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    resp = requests.post(
        f"{BLUESKY_API}/com.atproto.repo.createRecord",
        headers={"Authorization": f"Bearer {sess['accessJwt']}"},
        json={
            "repo":       sess["did"],
            "collection": "app.bsky.feed.post",
            "record":     {"$type": "app.bsky.feed.post", "text": text, "createdAt": now},
        },
        timeout=15,
    )
    resp.raise_for_status()
    print(f"  [bluesky] posted → {resp.json().get('uri', '')}")
    return True


# ── Reddit ────────────────────────────────────────────────────────────────────

def post_reddit(title: str, message: str, subreddit: str = "ClamBakeSanta") -> bool:
    client_id     = os.environ.get("REDDIT_CLIENT_ID", "").strip()
    client_secret = os.environ.get("REDDIT_CLIENT_SECRET", "").strip()
    username      = os.environ.get("REDDIT_USERNAME", "").strip()
    password      = os.environ.get("REDDIT_PASSWORD", "").strip()
    if not all([client_id, client_secret, username, password]):
        print("  [reddit] skipped — credentials not set")
        return False
    try:
        import praw
    except ImportError:
        print("  [reddit] skipped — praw not installed")
        return False
    reddit = praw.Reddit(
        client_id=client_id,
        client_secret=client_secret,
        username=username,
        password=password,
        user_agent="ClamBakeSanta/1.0 (broadcast)",
    )
    sub  = reddit.subreddit(subreddit)
    post = sub.submit(title=title or "ClamBakeSanta Update", selftext=message)
    print(f"  [reddit] posted → {post.url}")
    return True


# ── Tumblr ────────────────────────────────────────────────────────────────────

TUMBLR_API = "https://api.tumblr.com/v2"


def post_tumblr(title: str, message: str) -> bool:
    consumer_key    = os.environ.get("TUMBLR_CONSUMER_KEY", "").strip()
    consumer_secret = os.environ.get("TUMBLR_CONSUMER_SECRET", "").strip()
    oauth_token     = os.environ.get("TUMBLR_OAUTH_TOKEN", "").strip()
    oauth_secret    = os.environ.get("TUMBLR_OAUTH_SECRET", "").strip()
    if not all([consumer_key, consumer_secret, oauth_token, oauth_secret]):
        print("  [tumblr] skipped — credentials not set")
        return False
    from requests_oauthlib import OAuth1
    auth = OAuth1(consumer_key, consumer_secret, oauth_token, oauth_secret)
    info = requests.get(f"{TUMBLR_API}/user/info", auth=auth, timeout=15)
    info.raise_for_status()
    blog_name = info.json()["response"]["user"]["blogs"][0]["name"]
    body = f"<p>{message.replace(chr(10), '<br>')}</p>"
    resp = requests.post(
        f"{TUMBLR_API}/blog/{blog_name}/post",
        auth=auth,
        json={"type": "text", "title": title or "", "body": body,
              "tags": "ClamBakeSanta,announcement"},
        timeout=15,
    )
    resp.raise_for_status()
    post_id = resp.json().get("response", {}).get("id", "")
    print(f"  [tumblr] posted → post ID {post_id}")
    return True


# ── Telegram ──────────────────────────────────────────────────────────────────

def post_telegram(title: str, message: str) -> bool:
    token   = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    channel = os.environ.get("TELEGRAM_CHANNEL", "").strip()
    if not token or not channel:
        print("  [telegram] skipped — credentials not set")
        return False

    def esc(t: str) -> str:
        for ch in r"\_*[]()~`>#+-=|{}.!":
            t = t.replace(ch, f"\\{ch}")
        return t

    text = f"*{esc(title)}*\n\n{esc(message)}" if title else esc(message)
    resp = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": channel, "text": text, "parse_mode": "MarkdownV2"},
        timeout=15,
    )
    resp.raise_for_status()
    print(f"  [telegram] posted → message_id {resp.json()['result']['message_id']}")
    return True


# ── WordPress ─────────────────────────────────────────────────────────────────

WP_API = "https://public-api.wordpress.com/rest/v1.1"


def post_wordpress(title: str, message: str) -> bool:
    token   = os.environ.get("WORDPRESS_TOKEN", "").strip()
    blog_id = os.environ.get("WORDPRESS_BLOG_ID", "").strip()
    if not token or not blog_id:
        print("  [wordpress] skipped — credentials not set")
        return False
    content = f"<p>{message.replace(chr(10), '<br>')}</p>"
    resp = requests.post(
        f"{WP_API}/sites/{blog_id}/posts/new",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"title": title or "ClamBakeSanta Update", "content": content,
              "status": "publish", "tags": ["ClamBakeSanta", "announcement"]},
        timeout=30,
    )
    resp.raise_for_status()
    url = resp.json().get("URL", "")
    print(f"  [wordpress] posted → {url}")
    return True


# ── Email subscribers ─────────────────────────────────────────────────────────

def post_email(title: str, message: str) -> bool:
    gmail = os.environ.get("GMAIL_ADDRESS", "").strip()
    pw    = os.environ.get("GMAIL_APP_PASSWORD", "").strip()
    if not gmail or not pw:
        print("  [email] skipped — credentials not set")
        return False
    subscribers_path = pathlib.Path("state/subscribers.json")
    if not subscribers_path.exists():
        print("  [email] skipped — no subscribers file found")
        return False
    data        = json.loads(subscribers_path.read_text(encoding="utf-8"))
    subscribers = [s for s in data.get("subscribers", []) if s.get("confirmed")]
    if not subscribers:
        print("  [email] skipped — no confirmed subscribers")
        return False
    subject  = title or "Update from ClamBakeSanta"
    html     = f"<p>{message.replace(chr(10), '<br>')}</p>"
    plain    = message
    sent = 0
    with smtplib.SMTP("smtp.gmail.com", 587) as smtp:
        smtp.starttls()
        smtp.login(gmail, pw)
        for sub in subscribers:
            addr = sub.get("email", "")
            if not addr:
                continue
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"]    = f"Clam Bake Santa <{gmail}>"
            msg["To"]      = addr
            msg.attach(MIMEText(plain, "plain"))
            msg.attach(MIMEText(html, "html"))
            smtp.sendmail(gmail, addr, msg.as_string())
            sent += 1
    print(f"  [email] sent to {sent} subscriber(s)")
    return sent > 0


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Broadcast a message to all ClamBakeSanta platforms")
    parser.add_argument("--title",        default="", help="Post title (used by WordPress, Reddit, Email subject)")
    parser.add_argument("--message",      default="", help="Message body text")
    parser.add_argument("--message-file", default="", help="Read message body from this file instead")
    parser.add_argument("--subreddit",    default="ClamBakeSanta", help="Reddit subreddit (default: ClamBakeSanta)")
    args = parser.parse_args()

    if args.message_file:
        message = pathlib.Path(args.message_file).read_text(encoding="utf-8").strip()
    else:
        message = args.message.strip()

    if not message:
        print("ERROR: --message or --message-file is required.", file=sys.stderr)
        sys.exit(1)

    title = args.title.strip()

    print(f"Broadcasting to all platforms...")
    print(f"  Title:   {title or '(none)'}")
    print(f"  Message: {message[:80]}{'...' if len(message) > 80 else ''}\n")

    results = {}
    platforms = [
        ("mastodon",  lambda: post_mastodon(title, message)),
        ("bluesky",   lambda: post_bluesky(title, message)),
        ("reddit",    lambda: post_reddit(title, message, args.subreddit)),
        ("tumblr",    lambda: post_tumblr(title, message)),
        ("telegram",  lambda: post_telegram(title, message)),
        ("wordpress", lambda: post_wordpress(title, message)),
        ("email",     lambda: post_email(title, message)),
    ]

    for name, fn in platforms:
        try:
            results[name] = fn()
        except Exception as exc:
            print(f"  [{name}] FAILED: {exc}", file=sys.stderr)
            results[name] = False
        time.sleep(2)

    print("\nSummary:")
    for name, ok in results.items():
        print(f"  {name:12} {'OK' if ok else 'skipped/failed'}")


if __name__ == "__main__":
    main()
