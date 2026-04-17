<div align="center">
  <img src="docs/santa_clambake.png" alt="ClamBakeSanta" width="180" style="border-radius:50%">

# ClamBakeSanta

> *One bot. One ocean. Infinite holidays.*
</div>

A fully automated daily haiku generator — and a demonstration of a reusable,
plugin-based automation framework built entirely on free infrastructure.

---

## Find ClamBakeSanta Everywhere

<table>
<tr><th>Platform</th><th>Link</th></tr>
<tr><td>🌐 <strong>Website</strong></td><td><a href="https://soylentaquamarine.github.io/ClamBakeSanta">soylentaquamarine.github.io/ClamBakeSanta</a></td></tr>
<tr><td>📡 <strong>RSS Feed</strong></td><td><a href="https://soylentaquamarine.github.io/ClamBakeSanta/feed.xml">ClamBakeSanta/feed.xml</a></td></tr>
<tr><td>🐘 <strong>Mastodon</strong></td><td><a href="https://mastodon.social/@ClamBakeSanta">@ClamBakeSanta@mastodon.social</a></td></tr>
<tr><td>🦋 <strong>Bluesky</strong></td><td><a href="https://bsky.app/profile/clambakesanta.bsky.social">@clambakesanta.bsky.social</a></td></tr>
<tr><td>📝 <strong>Tumblr</strong></td><td><a href="https://www.tumblr.com/clambakesanta">tumblr.com/clambakesanta</a></td></tr>
<tr><td>✈️ <strong>Telegram</strong></td><td><a href="https://t.me/clambakesanta">t.me/clambakesanta</a></td></tr>
<tr><td>🤖 <strong>Reddit</strong></td><td><a href="https://reddit.com/u/TheClamBakeSanta">u/TheClamBakeSanta on r/haiku</a></td></tr>
<tr><td>📧 <strong>Email list</strong></td><td>Send SUBSCRIBE to <a href="mailto:clambakesanta@gmail.com">clambakesanta@gmail.com</a></td></tr>
</table>

---

## What It Does

Every morning at 5 AM ET, two GitHub Actions workflows run:

**4 AM ET — Check Subscriptions (`check_subscriptions.yml`)**
- Reads the Gmail inbox for SUBSCRIBE / UNSUBSCRIBE emails
- Updates the subscriber list (`state/subscribers.json`)
- Sends confirmation replies via Gmail SMTP
- Commits the updated list so the main run has the freshest data

**5 AM ET — Daily Haiku Generation (`daily.yml`)**
1. Reads today's holidays and birthdays from curated data files
2. Loads the last 7 days of `state/haiku_log.json` — passes recent opening phrases to the AI to avoid repetition
3. Calls a free AI model (GitHub Models / GPT-4o-mini) to write one haiku per theme
4. **Saves the haikus to `state/haiku_cache.json`** so every adapter uses the same poems; appends to `state/haiku_log.json`
5. Posts each haiku individually to **Mastodon, Bluesky, Tumblr, Telegram, and Reddit** (staggered 1 minute apart); **saves post IDs to `state/post_ids.json`** for engagement tracking
6. Sends the daily digest email to all subscribers
7. Updates the **GitHub Pages** website and **RSS feed**
8. Posts a summary to Discord
9. Commits all state back to the repo

**6 PM ET — Check Engagement (`check_engagement.yml`)**
- Reads `state/post_ids.json` and queries Mastodon, Bluesky, and Reddit APIs for current metrics
- Computes engagement score: **likes + 2× shares/boosts + 3× replies/comments**
- Saves results to `state/engagement.json`
- Commits the updated engagement data

**9 AM ET Sundays — Weekly Report (`weekly_report.yml`)**
- Compiles the last 7 days of `state/engagement.json`
- Ranks haikus by cross-platform engagement score
- Emails a formatted HTML report to `REPORT_EMAIL` with top performers, platform leaders, and trend vs. prior week

The result is a fully self-updating multi-platform content pipeline with a built-in
analytics feedback loop — zero daily maintenance, costs exactly **$0.00** to operate.

---

## Haiku Caching

After the AI generates haikus each morning, they are saved to `state/haiku_cache.json`.
Any subsequent run that same day — whether a re-run, a `--force` run, or a per-adapter
test — reads from the cache instead of calling the AI again.

This means **every adapter always posts the same poems on a given day**, no matter
how many times workflows are triggered. The cache is committed to the repo alongside
the run log.

To force fresh AI generation (overwrite today's cache):
```
python run.py --force --regenerate
```

---

## Analytics & Feedback Loop

ClamBakeSanta is a **self-improving content engine**. Every post is tracked, every
reaction counted, and the results feed back into future content generation.

### Anti-Repetition
Before the AI writes today's haikus, the engine loads the opening lines from the
**last 7 days** of `state/haiku_log.json` and adds them to the prompt:

> *"For variety, avoid starting with opening words or images similar to: 'Golden yolks glisten', 'Crisp autumn breezes', …"*

This keeps the imagery fresh week over week while maintaining the overall style.

### Engagement Tracking
Each time Mastodon, Bluesky, or Reddit publish a post, the API response is saved
to `state/post_ids.json`. Every evening at 6 PM ET, `check_engagement.py` queries
each platform and records:

| Metric | Weight in score |
|---|---|
| Likes / favourites / upvotes | × 1 |
| Shares / boosts / reposts | × 2 |
| Replies / comments | × 3 |

```
score = likes + (2 × shares) + (3 × replies)
```

Replies get the highest weight — they signal a genuine emotional response, not just
a passive tap.

### Weekly Report
Every Sunday morning a formatted HTML email lands in your inbox with:
- Total posts + total engagement score for the week
- Trend vs. the prior week (↑ / ↓ %)
- Top 5 haikus ranked by cross-platform score
- Per-platform leader (best Mastodon, Bluesky, Reddit post)
- Full ranked table of every haiku this week

Required secret: **`REPORT_EMAIL`** — the address to receive the report.

---

## Architecture

ClamBakeSanta is built as a **modular, plugin-based automation framework**.
The haiku bot is just one example implementation — the underlying system
can be repurposed for monitoring alerts, scheduled reports, AI newsletters,
or any other automated content pipeline.

```
┌──────────────────────────────────────────────────────────────────────┐
│                      FRAMEWORK (framework/)                           │
│                                                                       │
│  ┌──────────┐   ┌─────────────────┐   ┌──────────────────────────┐  │
│  │  SOURCE  │──▶│  ENGINE / CACHE │──▶│        ADAPTERS          │  │
│  │  plugin  │   │  plugin         │   │  mastodon ──────────────┐│  │
│  └──────────┘   └─────────────────┘   │  bluesky  ──────────────┤│  │
│       │                │              │  tumblr                  ││  │
│   Produces         Transforms or      │  telegram                ││  │
│   an Event         loads from cache   │  email_list              ││  │
│                    ↕ haiku_log.json   │  reddit   ──────────────┘│  │
│                    (anti-repetition)  │  wordpress               │  │
│                                       │  github_pages            │  │
│                                       │  discord                 │  │
│                                       └──────────────────────────┘  │
│                                                  │                    │
│                                                  ▼                    │
│                                    ┌─────────────────────┐           │
│                                    │        STATE        │           │
│                                    │  run_log.json       │           │
│                                    │  haiku_cache.json   │           │
│                                    │  haiku_log.json     │◀── long-term memory │
│                                    │  post_ids.json      │◀── per-post IDs     │
│                                    │  engagement.json    │◀── daily metrics    │
│                                    │  subscribers.json   │           │
│                                    └─────────────────────┘           │
│                                                  │                    │
│                                    ┌─────────────▼───────────┐       │
│                                    │   ANALYTICS LOOP        │       │
│                                    │  check_engagement.py    │       │
│                                    │  weekly_report.py       │       │
│                                    └─────────────────────────┘       │
└──────────────────────────────────────────────────────────────────────┘
```

### The Four Layers

| Layer | Responsibility | Example |
|---|---|---|
| **Source** | Produces a standardized Event | `daily_holidays` reads today's data files |
| **Engine** | Transforms Event → Result (or loads cache) | `clambakesanta` calls AI, caches haikus |
| **Adapters** | Publish Result to output channels | `mastodon`, `bluesky`, `github_pages`, etc. |
| **State** | Deduplication + audit trail + cache | `state/run_log.json`, `state/haiku_cache.json` |

### Key Design Principles

- **No hardcoded dependencies between layers.** Each layer only knows about `Event` and `Result` models.
- **Plugin registry.** New plugins self-register via `@register()` decorator — no core changes needed.
- **Graceful degradation.** Missing credentials → adapter skips silently. One failed adapter never stops others.
- **Config-driven.** Swap engines, add adapters, change channels — all from `config.yml`, no code changes.
- **Adapter ordering matters.** Social posts go out first, site updates last — controlled by order in `config.yml`.
- **Consistent daily content.** Haiku cache ensures all adapters use identical poems even across multiple runs.

---

## File Structure

```
clambakesanta/
│
├── framework/                  # Core framework — zero business logic
│   ├── models.py               # Event and Result dataclasses (the contracts)
│   ├── registry.py             # Plugin registry (@register decorator)
│   ├── runner.py               # Execution loop: source→engine/cache→adapters→state
│   ├── haiku_log.py            # Partitioned haiku history + anti-repetition helpers
│   ├── post_store.py           # Partitioned post IDs/URLs per platform
│   ├── engagement_store.py     # Partitioned engagement metrics + 7-day summary
│   ├── sources/base.py         # BaseSource abstract class
│   ├── engines/base.py         # BaseEngine abstract class
│   ├── adapters/base.py        # BaseAdapter abstract class
│   └── state/json_store.py     # Dedup + run log (JSON file backend)
│
├── plugins/                    # All business logic lives here
│   ├── sources/
│   │   └── daily_holidays.py   # Reads data files → produces Event
│   ├── engines/
│   │   └── clambakesanta.py    # Calls AI → produces haiku Result
│   └── adapters/
│       ├── mastodon_adapter.py # Posts each haiku to Mastodon
│       ├── bluesky.py          # Posts each haiku to Bluesky
│       ├── tumblr.py           # Posts each haiku to Tumblr
│       ├── telegram.py         # Posts each haiku to Telegram channel
│       ├── email_list.py       # Sends daily digest to subscribers
│       ├── reddit.py           # Posts each haiku to r/haiku
│       ├── github_pages.py     # Writes docs/ HTML + RSS
│       └── discord.py          # Posts summary to Discord webhook
│
├── data/                       # Your editorial control layer
│   ├── january_randomholiday.txt
│   ├── january_celebritybirthday.txt
│   └── ... (24 files total, one per month per type)
│
├── docs/                       # GitHub Pages root (auto-generated daily)
│   ├── index.html              # Today's haikus
│   ├── santa_clambake.png      # Site logo
│   ├── feed.xml                # RSS 2.0 feed
│   └── archives/               # One HTML file per day, forever
│
├── state/
│   ├── run_log.json            # Dedup log + human-readable run history
│   ├── haiku_cache.json        # Today's haikus — shared across all adapters
│   ├── subscribers.json        # Email mailing list
│   ├── haiku_log/
│   │   ├── 2026-04-17.json     # One file per day — every haiku ever generated
│   │   └── recent.json         # Rolling 7-day summary (auto-rebuilt, fast access)
│   ├── post_ids/
│   │   ├── 2026-04-17.json     # Per-platform post IDs/URLs for one day
│   │   └── summary.json        # Rolling 7-day index (auto-rebuilt)
│   └── engagement/
│       ├── 2026-04-17.json     # Engagement metrics for one day
│       └── summary.json        # Rolling 7-day summary (auto-rebuilt, fast access)
│
├── .github/workflows/
│   ├── daily.yml               # Main cron: 5 AM ET — generate + publish everywhere
│   ├── check_subscriptions.yml # Sub cron: 4 AM ET — process SUBSCRIBE/UNSUBSCRIBE emails
│   ├── test_mastodon.yml       # Manual: re-post today's cached haikus to Mastodon
│   ├── test_bluesky.yml        # Manual: re-post today's cached haikus to Bluesky
│   ├── test_tumblr.yml         # Manual: re-post today's cached haikus to Tumblr
│   ├── test_telegram.yml       # Manual: re-post today's cached haikus to Telegram
│   ├── test_email_list.yml     # Manual: re-send today's digest to email subscribers
│   ├── test_reddit.yml         # Manual: re-post today's cached haikus to Reddit
│   ├── test_discord.yml        # Manual: re-post today's cached haikus to Discord
│   ├── test_github_pages.yml   # Manual: rebuild site from today's cached haikus
│   ├── check_engagement.yml    # Daily 6 PM ET: fetch likes/boosts/replies per post
│   └── weekly_report.yml       # Sunday 9 AM ET: email weekly stats to REPORT_EMAIL
│
├── check_subscriptions.py      # Standalone SUBSCRIBE/UNSUBSCRIBE processor
├── check_engagement.py         # Fetches engagement metrics; saves state/engagement.json
├── weekly_report.py            # Emails weekly stats report to REPORT_EMAIL
├── config.yml                  # All configuration — no hardcoded values
├── run.py                      # Entry point (python run.py [--force] [--regenerate] [--adapter X])
└── requirements.txt            # openai, requests, pyyaml, requests-oauthlib, praw
```

---

## The Safety Layer: Editorial Control

The biggest design decision: **the AI does not choose its own subjects.**

Every haiku subject comes from curated data files that you control.
The data files are the editorial layer — nothing becomes a haiku topic
unless you approved it first.

Guidelines built into the data files:
- Food holidays, nature themes, whimsical observances: always safe
- Birthdays: only universally beloved figures (musicians, scientists, athletes)
- No living politicians, no controversy, no broad cultural generalizations
- Cultural heritage is celebrated through specific people on their actual birthdays

The AI prompt also includes an explicit safety instruction:
> *"Keep all content joyful, inclusive, and appropriate for all audiences.
> Never reference politics, religion, controversy, or anything divisive."*

---

## Zero-Cost Infrastructure

| Component | Service | Cost |
|---|---|---|
| AI haiku generation | GitHub Models (GPT-4o-mini via `GITHUB_TOKEN`) | **Free** |
| Daily scheduling | GitHub Actions (cron) | **Free** (public repo) |
| Website + archive | GitHub Pages | **Free** |
| RSS feed | Static file served by Pages | **Free** |
| Mastodon posting | Mastodon API | **Free** |
| Bluesky posting | AT Protocol API | **Free** |
| Tumblr posting | Tumblr OAuth API | **Free** |
| Telegram posting | Telegram Bot API | **Free** |
| Email mailing list | Gmail SMTP/IMAP | **Free** |
| Reddit posting | Reddit API (PRAW) | **Free** |
| Discord posting | Discord webhook | **Free** |
| **Total** | | **$0.00 / month** |

---

## Setup Guide

### 1. Fork or create the repository

Create a new repo named `ClamBakeSanta` on your GitHub account.

### 2. Enable GitHub Pages

`Settings → Pages → Source → Deploy from a branch → Branch: main → /docs`

### 3. Update config.yml

```yaml
site_base_url: "https://YOUR-USERNAME.github.io/ClamBakeSanta"
```

### 4. Add secrets (Settings → Secrets and variables → Actions)

| Secret | Required for |
|---|---|
| `MASTODON_INSTANCE_URL` | Mastodon (e.g. `https://mastodon.social`) |
| `MASTODON_ACCESS_TOKEN` | Mastodon |
| `BLUESKY_HANDLE` | Bluesky (e.g. `yourbot.bsky.social`) |
| `BLUESKY_APP_PASSWORD` | Bluesky |
| `TUMBLR_CONSUMER_KEY` | Tumblr |
| `TUMBLR_CONSUMER_SECRET` | Tumblr |
| `TUMBLR_OAUTH_TOKEN` | Tumblr |
| `TUMBLR_OAUTH_SECRET` | Tumblr |
| `TELEGRAM_BOT_TOKEN` | Telegram |
| `TELEGRAM_CHANNEL` | Telegram (e.g. `@yourchannel`) |
| `GMAIL_ADDRESS` | Email mailing list |
| `GMAIL_APP_PASSWORD` | Email mailing list |
| `REDDIT_CLIENT_ID` | Reddit |
| `REDDIT_CLIENT_SECRET` | Reddit |
| `REDDIT_USERNAME` | Reddit (e.g. `TheClamBakeSanta`) |
| `REDDIT_PASSWORD` | Reddit |
| `DISCORD_WEBHOOK_URL` | Discord |
| `REPORT_EMAIL` | Weekly stats report recipient (your email) |

> `GITHUB_TOKEN` is automatic — no setup needed.

### 5. Trigger your first run

`Actions → Daily Haiku Generation → Run workflow`

### 6. Subscribe to the email list

Send any email to the configured Gmail address with **SUBSCRIBE** in the subject.
Send **UNSUBSCRIBE** to stop.

---

## Per-Adapter Testing

Each adapter has its own manual workflow under **Actions**. These use the
day's cached haikus so you always get the same poems, never fresh AI generation:

| Workflow | What it does |
|---|---|
| `Test — Mastodon` | Re-posts today's haikus to Mastodon |
| `Test — Bluesky` | Re-posts today's haikus to Bluesky |
| `Test — Tumblr` | Re-posts today's haikus to Tumblr |
| `Test — Telegram` | Re-posts today's haikus to Telegram |
| `Test — Email List` | Re-sends today's digest to all subscribers |
| `Test — Reddit` | Re-posts today's haikus to r/haiku |
| `Test — Discord` | Re-posts today's summary to Discord |
| `Test — GitHub Pages` | Rebuilds site from today's cached haikus |
| `Check Engagement` | Fetches metrics for the last 3 days of posts |
| `Weekly Report` | Sends a report email immediately (manual test) |

---

## Adding a New Platform — Sync Checklist

When adding a new adapter or changing any platform links, update **all** of these:

| What to update | Where | How |
|---|---|---|
| Platform links table | `README.md` | Edit directly |
| Architecture diagram | `README.md` | Edit directly |
| Zero-cost table | `README.md` | Edit directly |
| Secrets table | `README.md` | Edit directly |
| About page content | `content/about.html` | Edit, then run workflow below |
| All about pages (WordPress etc.) | Auto-pushed | **Actions → Update About Pages** |
| `config.yml` adapters list | `config.yml` | Add adapter name + module |
| Per-adapter test workflow | `.github/workflows/test_X.yml` | Create new file |
| Daily workflow secrets | `.github/workflows/daily.yml` | Add env var |
| Engagement checker | `check_engagement.py` | Add platform-specific fetch function |
| Engagement workflow secrets | `.github/workflows/check_engagement.yml` | Add env var |

> **Quick rule:** Edit `content/about.html` for anything link/platform related,
> then trigger **Actions → Update About Pages** to push it everywhere at once.
> Edit `README.md` separately for the full technical detail.

---

## Extending the Framework

### Add a new output channel in 3 steps

```python
# plugins/adapters/newplatform.py
from framework.registry import register
from framework.adapters.base import BaseAdapter
from framework.models import Result

@register("adapters", "newplatform")
class NewPlatformAdapter(BaseAdapter):
    def publish(self, result: Result) -> bool:
        # your posting logic here
        return True
```

1. Create the file above
2. Add `newplatform` to `adapters:` in `config.yml`
3. Add `plugins.adapters.newplatform` to `plugin_modules:` in `config.yml`

No other files change. The framework discovers and runs it automatically.

---

## Tech Stack

### Infrastructure
| Component | Technology | Auth method |
|---|---|---|
| Scheduling & execution | GitHub Actions (cron + manual dispatch) | `GITHUB_TOKEN` — automatic |
| AI haiku generation | GitHub Models API (GPT-4o-mini) | `GITHUB_TOKEN` — automatic |
| Static site + archive | GitHub Pages (served from `docs/`) | `GITHUB_TOKEN` — automatic |
| Language | Python 3.11 | — |

### Publishing connectors

| Platform | API / Library | Auth method | What it posts |
|---|---|---|---|
| **Mastodon** | Mastodon REST API v1 (`/api/v1/statuses`) | Bearer token — OAuth 2.0 app password created in Mastodon Preferences → Development | One toot per haiku |
| **Bluesky** | AT Protocol (`com.atproto.repo.createRecord`) | App Password — created in Bluesky Settings → Privacy and Security | One post per haiku with rich-text facets for hashtags |
| **Tumblr** | Tumblr OAuth API v2 (`/v2/blog/{id}/posts`) | OAuth 1.0a — Consumer Key + Secret + OAuth Token + Secret from Tumblr Developer Portal | One post per haiku |
| **Telegram** | Telegram Bot API (`sendMessage`) | Bot token — created via @BotFather | One message per haiku to a channel |
| **Reddit** | PRAW (Python Reddit API Wrapper) | OAuth 2.0 script app — Client ID + Secret + Username + Password | One text post per haiku to r/haiku |
| **WordPress.com** | WordPress.com REST API v1.1 (`/sites/{id}/posts/new`) | OAuth 2.0 Bearer token — authorized via `developer.wordpress.com/apps` with `global` scope | One styled blog post per day (all haikus combined) |
| **Discord** | Discord Webhook (`POST webhook_url`) | Webhook URL — created in Discord channel settings | One summary message per day |
| **Email list** | Gmail SMTP (`smtp.gmail.com:587` + STARTTLS) | Gmail App Password — created in Google Account → Security → App Passwords | Daily digest to all subscribers |
| **RSS feed** | Static XML file served by GitHub Pages | None — file write only | Rolling 30-day feed rebuilt daily |

### Engagement tracking connectors

| Platform | API endpoint | Metrics fetched |
|---|---|---|
| **Mastodon** | `GET /api/v1/statuses/{id}` | `favourites_count`, `reblogs_count`, `replies_count` |
| **Bluesky** | `GET app.bsky.feed.getPosts?uris={uri}` | `likeCount`, `repostCount`, `replyCount` |
| **Reddit** | PRAW `reddit.submission(id=…)` | `score` (upvotes − downvotes), `num_comments` |

---

## License

MIT — fork it, adapt it, build your own bot on top of it.

---

*Built by Stephen Pleasants · [@SoylentAquamarine](https://github.com/SoylentAquamarine)*
