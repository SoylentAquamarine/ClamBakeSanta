<div align="center">
  <img src="docs/santa_clambake.png" alt="ClamBakeSanta" width="180" style="border-radius:50%">

# ClamBakeSanta

> *One bot. One ocean. Infinite holidays.*
</div>

A fully automated daily haiku generator — and a demonstration of a reusable,
plugin-based automation framework built entirely on free infrastructure.

---

## Find ClamBakeSanta Everywhere

| Platform | Link |
|---|---|
| 🌐 **Website** | https://soylentaquamarine.github.io/ClamBakeSanta |
| 📡 **RSS Feed** | https://soylentaquamarine.github.io/ClamBakeSanta/feed.xml |
| 🐘 **Mastodon** | https://mastodon.social/@ClamBakeSanta |
| 🦋 **Bluesky** | https://bsky.app/profile/clambakesanta.bsky.social |
| 📝 **Tumblr** | https://www.tumblr.com/clambakesanta |
| ✈️ **Telegram** | https://t.me/clambakesanta |
| 🤖 **Reddit** | https://reddit.com/u/TheClamBakeSanta |
| 📧 **Email list** | Send SUBSCRIBE to clamsbakesanta@gmail.com |

---

## What It Does

Every morning, a GitHub Actions workflow:

1. Reads today's holidays and birthdays from curated data files
2. Calls a free AI model (GitHub Models / GPT-4o-mini) to write fresh haikus
3. Posts each haiku individually to **Mastodon, Bluesky, Tumblr, and Telegram** (staggered 1 minute apart)
4. Sends a daily digest email to all subscribers
5. Updates the **GitHub Pages** site and **RSS feed**
6. Commits everything back to the repo

The result is a fully self-updating multi-platform content pipeline that requires
zero daily maintenance and costs exactly **$0.00** to operate.

---

## Architecture

ClamBakeSanta is built as a **modular, plugin-based automation framework**.
The haiku bot is just one example implementation — the underlying system
can be repurposed for monitoring alerts, scheduled reports, AI newsletters,
or any other automated content pipeline.

```
┌──────────────────────────────────────────────────────────────────┐
│                     FRAMEWORK (framework/)                        │
│                                                                   │
│  ┌──────────┐    ┌──────────┐    ┌──────────────────────────┐   │
│  │  SOURCE  │───▶│  ENGINE  │───▶│        ADAPTERS          │   │
│  │  plugin  │    │  plugin  │    │  mastodon                │   │
│  └──────────┘    └──────────┘    │  bluesky                 │   │
│       │               │          │  tumblr                  │   │
│   Produces          Transforms   │  telegram                │   │
│   an Event         Event into    │  email_list              │   │
│                      a Result    │  github_pages            │   │
│                                  │  discord                 │   │
│                                  └──────────────────────────┘   │
│                                            │                      │
│                                            ▼                      │
│                                   ┌──────────────┐               │
│                                   │    STATE     │               │
│                                   │  run_log +   │               │
│                                   │ subscribers  │               │
│                                   └──────────────┘               │
└──────────────────────────────────────────────────────────────────┘

Event → Engine → Result → Adapters → State
```

### The Four Layers

| Layer | Responsibility | Example |
|---|---|---|
| **Source** | Produces a standardized Event | `daily_holidays` reads today's data files |
| **Engine** | Transforms Event → Result (no I/O) | `clambakesanta` calls AI, returns haikus |
| **Adapters** | Publish Result to output channels | `mastodon`, `bluesky`, `github_pages`, etc. |
| **State** | Deduplication + audit trail | `state/run_log.json` committed to repo |

### Key Design Principles

- **No hardcoded dependencies between layers.** Each layer only knows about `Event` and `Result` models.
- **Plugin registry.** New plugins self-register via `@register()` decorator — no core changes needed.
- **Graceful degradation.** Missing credentials → adapter skips silently. One failed adapter never stops others.
- **Config-driven.** Swap engines, add adapters, change channels — all from `config.yml`, no code changes.
- **Adapter ordering matters.** Social posts go out first, site updates last — controlled by order in `config.yml`.

---

## File Structure

```
clambakesanta/
│
├── framework/                  # Core framework — zero business logic
│   ├── models.py               # Event and Result dataclasses (the contracts)
│   ├── registry.py             # Plugin registry (@register decorator)
│   ├── runner.py               # Execution loop: source→engine→adapters→state
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
│       ├── mastodon_adapter.py # Posts to Mastodon
│       ├── bluesky.py          # Posts to Bluesky
│       ├── tumblr.py           # Posts to Tumblr
│       ├── telegram.py         # Posts to Telegram channel
│       ├── email_list.py       # SUBSCRIBE/UNSUBSCRIBE + daily digest
│       ├── github_pages.py     # Writes docs/ HTML + RSS
│       └── discord.py          # Posts to Discord webhook
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
│   └── subscribers.json        # Email mailing list
│
├── .github/workflows/
│   └── daily.yml               # Cron job: runs every morning at 5 AM ET
│
├── config.yml                  # All configuration — no hardcoded values
├── run.py                      # Entry point (python run.py)
└── requirements.txt            # openai, requests, pyyaml, requests-oauthlib
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
| `DISCORD_WEBHOOK_URL` | Discord |

> `GITHUB_TOKEN` is automatic — no setup needed.

### 5. Trigger your first run

`Actions → Daily Haiku Generation → Run workflow`

### 6. Subscribe to the email list

Send any email to the configured Gmail address with **SUBSCRIBE** in the subject.
Send **UNSUBSCRIBE** to stop.

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

- **Python 3.11** — framework and all plugins
- **GitHub Actions** — scheduling and execution (free, public repo)
- **GitHub Models** — free AI inference via `GITHUB_TOKEN` (GPT-4o-mini)
- **GitHub Pages** — static site hosting from `docs/`
- **Mastodon API** — ActivityPub social network
- **Bluesky AT Protocol** — decentralized social network
- **Tumblr OAuth API** — blogging platform
- **Telegram Bot API** — channel messaging
- **Gmail SMTP/IMAP** — email mailing list
- **RSS 2.0** — universal feed standard

---

## License

MIT — fork it, adapt it, build your own bot on top of it.

---

*Built by Stephen Pleasants · [@SoylentAquamarine](https://github.com/SoylentAquamarine)*
