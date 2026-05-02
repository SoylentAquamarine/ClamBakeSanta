# System Overview — ClamBakeSanta

## Purpose

ClamBakeSanta is a fully automated daily haiku bot that operates without human intervention. Every morning it reads today's holidays and celebrity birthdays from curated data files, calls a free AI model to write three haikus, then publishes them to nine social platforms and a static website. The system is built entirely on free infrastructure: GitHub Actions, GitHub Models, and GitHub Pages. Zero cost. Zero manual steps.

Beyond the haiku output, the project is a demonstration of a reusable, plugin-based automation framework — the AI engine, output channels, and input sources are all independently swappable via `config.yml`.

## Tech Stack

| Component | Technology |
|---|---|
| Language | Python 3 |
| Configuration | PyYAML (`config.yml`) |
| Scheduling | GitHub Actions (cron, daily at 8 AM ET) |
| AI Engine | GitHub Models API (`gpt-4o-mini`), free tier, authenticated via `GITHUB_TOKEN` |
| Static site | GitHub Pages (serves `docs/` directory) |
| State storage | JSON files in `state/` directory (machine-managed) |

## Core Architecture (4-Layer Plugin Pipeline)

The entire system is driven by `config.yml`. No business logic is hardcoded in the framework. Each layer is swappable by changing the config — you can replace the AI engine, add output channels, or change the input source without modifying framework code.

```
Source → validate_event → Engine (or cache) → validate_result → Adapters (×N) → State
```

### Layer 1: Source
Produces an `Event` object describing what is happening today. The active source is set by `config.yml: source: daily_holidays`.

- **`daily_holidays`** plugin (`plugins/sources/daily_holidays.py`): Reads `data/{month}_randomholiday.txt` and `data/{month}_celebritybirthday.txt`. Returns an `Event` with `date_str` and `payload.themes` (list of strings).

### Layer 2: Engine
Transforms the `Event` into a `Result`. The active engine is set by `config.yml: engine: clambakesanta`.

- **`clambakesanta`** plugin (`plugins/engines/clambakesanta.py`): Calls GitHub Models (`gpt-4o-mini`) with a structured prompt that includes today's themes. Generates 3 haikus. Returns a `Result` with formatted `content` and `metadata.haikus` + `metadata.themes`.

### Layer 3: Adapters (9 output channels)
Each adapter independently publishes the `Result` to a platform. One adapter failing never stops the others. Missing credentials cause a silent skip (returns `False`). Active adapters listed in `config.yml: adapters:`.

| Adapter | Platform | Notes |
|---|---|---|
| `mastodon` | Mastodon | 1 post per haiku, 1 minute apart |
| `bluesky` | Bluesky | 1 post per haiku, 1 minute apart |
| `tumblr` | Tumblr | 1 post per haiku, 1 minute apart |
| `telegram` | Telegram | 1 post per haiku, 1 minute apart |
| `email_list` | Gmail subscribers | Daily digest email |
| `reddit` | r/haiku | One post per day |
| `wordpress` | WordPress.com | Daily digest post |
| `github_pages` | GitHub Pages | Updates `docs/` static site |
| `discord` | Discord | Summary message after site updates |

### Layer 4: State
After all adapters run, `state.record_run(result)` marks today as complete. Prevents double-posting on re-runs.

## Plugin System

Plugins self-register via `@register()` decorators when their modules are imported. The framework imports all plugin modules listed in `config.yml: plugin_modules:` at startup. Adding a new plugin = add its module path to `plugin_modules`. The framework's `get_plugin('adapters', 'my_adapter')` looks up the registered class.

Core plugin interfaces (`framework/`):
- `framework/adapters/base.py` — `BaseAdapter` with `publish(result) → bool`
- `framework/engines/base.py` — `BaseEngine` with `process(event) → Result`
- `framework/sources/base.py` — `BaseSource` with `produce() → Event`

## State Management

The `state/` directory is entirely machine-managed. **Never manually edit these files.**

| File/Dir | Contents | Purpose |
|---|---|---|
| `haiku_cache.json` | `{ date, haikus, themes, content, saved_at }` | Today's haikus — prevents AI re-call on reruns |
| `run_log.json` | Array of completed run records | Deduplication — `already_ran_today()` check |
| `haiku_log/` | Long-term haiku history files | Anti-repetition; weekly report source |
| `engagement/` | Per-platform engagement metrics | Tracked by `check_engagement.py` |
| `post_ids/` | Per-platform post IDs | Deduplication and future reference |
| `subscribers.json` | Email subscriber list | Managed by `email_list` adapter |

The `.gitattributes` file configures a union merge driver for `state/**/*.json` — on any git merge conflict, both sides are appended rather than one side overwriting the other. This protects automated bot commits from being lost during developer pushes.

## GitHub Workflows

| Workflow file | Schedule | Purpose |
|---|---|---|
| `daily.yml` | Cron: 8 AM ET daily | Main pipeline run |
| `check_engagement.yml` | Scheduled | Monitor platform engagement |
| `check_subscriptions.yml` | Scheduled | Validate email subscriptions |
| `update_about_pages.yml` | Triggered | Rebuild static about pages |
| `weekly_report.yml` | Cron: weekly | Generate weekly summary |
| `test_adapter.yml` | Manual | Generic adapter test |
| `test_mastodon.yml` | Manual | Individual adapter tests |
| `test_bluesky.yml` | Manual | |
| `test_discord.yml` | Manual | |
| `test_email_list.yml` | Manual | |
| `test_github_pages.yml` | Manual | |
| `test_reddit.yml` | Manual | |
| `test_telegram.yml` | Manual | |
| `test_tumblr.yml` | Manual | |
| `test_wordpress.yml` | Manual | |

## Data Files

All subjects the AI writes about are controlled by curated text files in `data/`:

- `data/{month}_randomholiday.txt` — Random/quirky holidays for each month
- `data/{month}_celebritybirthday.txt` — Celebrity birthdays for each month

24 files total (2 per month × 12 months). The curated data is the safety layer — the AI never writes about anything not in these files.

## Output Channels

The `docs/` directory is served by GitHub Pages:

| File | Contents |
|---|---|
| `docs/index.html` | Today's haiku (updated daily) |
| `docs/archives/` | Past daily haiku HTML pages |
| `docs/archives/index.html` | Archive index |
| `docs/feed.xml` | RSS feed |
| `docs/ClamBakeSanta.jpg` | Site logo |
| `docs/santa_clambake.png` | Alternate logo |

## Ancillary Scripts

| Script | Purpose |
|---|---|
| `run.py` | CLI entrypoint: `--force`, `--regenerate`, `--adapter` flags |
| `check_engagement.py` | Standalone engagement tracker |
| `check_subscriptions.py` | Standalone subscription checker |
| `update_about.py` | Rebuild about/profile pages |
| `weekly_report.py` | Generate and post weekly report |
