# 🦪 ClamBakeSanta

> *One bot. One ocean. Infinite holidays.*

A fully automated daily haiku generator — and a demonstration of a reusable,
plugin-based automation framework built entirely on free infrastructure.

**Live site:** https://soylentaquamarine.github.io/clambakesanta/
**RSS feed:** https://soylentaquamarine.github.io/clambakesanta/feed.xml

---

## What It Does

Every morning at 8:00 AM Eastern, a GitHub Actions workflow:

1. Reads today's holidays and birthdays from curated data files
2. Calls a free AI model (GitHub Models / GPT-4o-mini) to write fresh haikus
3. Commits the generated HTML directly back to this repo
4. GitHub Pages serves the updated site within minutes
5. Optionally posts to Mastodon and/or Discord

The result is a self-updating website and RSS feed that requires zero
daily maintenance and costs exactly **$0.00** to operate.

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
│  │  plugin  │    │  plugin  │    │  github_pages            │   │
│  └──────────┘    └──────────┘    │  mastodon                │   │
│       │               │          │  discord                  │   │
│   Produces          Transforms   └──────────────────────────┘   │
│   an Event         Event into            │                        │
│                      a Result            ▼                        │
│                                   ┌──────────┐                   │
│                                   │  STATE   │                   │
│                                   │  store   │                   │
│                                   └──────────┘                   │
└──────────────────────────────────────────────────────────────────┘

Event → Engine → Result → Adapters → State
```

### The Four Layers

| Layer | Responsibility | Example |
|---|---|---|
| **Source** | Produces a standardized Event | `daily_holidays` reads today's data files |
| **Engine** | Transforms Event → Result (no I/O) | `clambakesanta` calls AI, returns haikus |
| **Adapters** | Publish Result to output channels | `github_pages`, `mastodon`, `discord` |
| **State** | Deduplication + audit trail | `state/run_log.json` committed to repo |

### Key Design Principles

- **No hardcoded dependencies between layers.** Each layer only knows about `Event` and `Result` models.
- **Plugin registry.** New plugins self-register via `@register()` decorator — no core changes needed.
- **Graceful degradation.** Missing credentials → adapter skips silently. One failed adapter never stops others.
- **Config-driven.** Swap engines, add adapters, change channels — all from `config.yml`, no code changes.

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
│       ├── github_pages.py     # Writes docs/ HTML + RSS
│       ├── mastodon_adapter.py # Posts toots to Mastodon
│       └── discord.py          # Posts to Discord webhook
│
├── data/                       # Your editorial control layer
│   ├── january_randomholiday.txt
│   ├── january_celebritybirthday.txt
│   └── ... (24 files total, one per month per type)
│
├── docs/                       # GitHub Pages root (auto-generated daily)
│   ├── index.html              # Today's haikus
│   ├── feed.xml                # RSS 2.0 feed
│   └── archives/               # One HTML file per day, forever
│
├── state/
│   └── run_log.json            # Dedup log + human-readable run history
│
├── .github/workflows/
│   └── daily.yml               # Cron job: runs every morning at 8 AM ET
│
├── config.yml                  # All configuration — no hardcoded values
├── run.py                      # Entry point (python run.py)
└── requirements.txt            # openai, requests, pyyaml
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
| Website hosting | GitHub Pages | **Free** |
| RSS feed | Static file served by Pages | **Free** |
| Mastodon posting | Mastodon API (public instance) | **Free** |
| Discord posting | Discord webhook | **Free** |
| **Total** | | **$0.00 / month** |

GitHub Models uses the `GITHUB_TOKEN` that is automatically injected into
every Actions run. No API key to manage, no billing to set up.

---

## Setup Guide

### 1. Fork or create the repository

Create a new repo named `clambakesanta` on your GitHub account.

### 2. Enable GitHub Pages

`Settings → Pages → Source → Deploy from a branch → Branch: main → /docs`

### 3. Update config.yml

```yaml
site_base_url: "https://YOUR-USERNAME.github.io/clambakesanta"
```

### 4. Add optional secrets (Settings → Secrets and variables → Actions)

| Secret | Required for |
|---|---|
| `MASTODON_INSTANCE_URL` | Mastodon posting (e.g. `https://mastodon.social`) |
| `MASTODON_ACCESS_TOKEN` | Mastodon posting |
| `DISCORD_WEBHOOK_URL` | Discord posting |

> `GITHUB_TOKEN` is automatic — no setup needed.

### 5. Trigger your first run

`Actions → Daily Haiku Generation → Run workflow`

The site will update within 2 minutes of the workflow completing.

### 6. Customize your holidays

Edit any file in `data/` directly in the GitHub web UI.
Format: `MM-DD: Theme One, Theme Two`

---

## Extending the Framework

### Add a new output channel (e.g. Bluesky)

```python
# plugins/adapters/bluesky.py
from framework.registry import register
from framework.adapters.base import BaseAdapter
from framework.models import Result

@register("adapters", "bluesky")
class BlueskyAdapter(BaseAdapter):
    def publish(self, result: Result) -> bool:
        # your posting logic here
        return True
```

Then add `bluesky` to the `adapters` list in `config.yml` and
`plugins.adapters.bluesky` to `plugin_modules`. That's it —
no other files change.

### Add a new engine (e.g. system monitor)

```python
# plugins/engines/system_monitor.py
from framework.registry import register
from framework.engines.base import BaseEngine
from framework.models import Event, Result

@register("engines", "system_monitor")
class SystemMonitorEngine(BaseEngine):
    def process(self, event: Event) -> Result:
        # check CPU, disk, memory...
        return Result(event=event, engine_id="system_monitor", content="All systems OK")
```

Change `engine: system_monitor` in `config.yml`. Done.

---

## Tech Stack

- **Python 3.11** — framework and plugins
- **GitHub Actions** — scheduling and execution
- **GitHub Models** — free AI via `GITHUB_TOKEN` (GPT-4o-mini)
- **GitHub Pages** — static site hosting from `docs/`
- **Mastodon API** — free social posting
- **RSS 2.0** — feed for any RSS reader

---

## License

MIT — fork it, adapt it, build your own bot on top of it.

---

*Built by Stephen Pleasants · [@SoylentAquamarine](https://github.com/SoylentAquamarine)*
