# CHANGELOG

This changelog is append-only: older entries are at the top and the newest changes are at the bottom.

## 2026-05 - Initial Public Release

- Published the first ClamBakeSanta repository structure.
- Added the core Python framework layout.
- Added GitHub Actions automation for scheduled runs.
- Added GitHub Pages output under `docs/`.
- Established the basic holiday-driven haiku bot concept.

## 2026-05 - Plugin Framework

- Added the framework/plugin model:
  - source plugins
  - engine plugins
  - adapter plugins
  - shared Event/Result contracts
- Added plugin registry behavior using decorators.
- Added configuration-driven source, engine, and adapter selection through `config.yml`.

## 2026-05 - Daily Haiku Generation

- Added `run.py` as the daily entry point.
- Added `framework.runner` for the source → engine/cache → adapter flow.
- Added the `daily_themes` source.
- Added the `clambakesanta` engine.
- Added AI-based haiku generation.
- Added 5-7-5 syllable validation and retry handling.
- Added writer's block logging and fallback generation.

## 2026-05 - Publishing Adapters

- Added publishing adapters for multiple channels, including:
  - Mastodon
  - Bluesky
  - Tumblr
  - Telegram
  - WordPress
  - GitHub Pages / RSS
  - Email digest delivery
- Added sequential adapter execution through `config.yml` order.
- Added graceful skipping behavior for adapters without configured credentials.

## 2026-05 - Theme and Data Expansion

- Added curated fixed holiday data files.
- Added celebrity birthday data files.
- Added ephemeral holiday rule support.
- Added generated ephemeral holiday files under `data/ephemeral/`.
- Added generated celestial event files under `data/celestial/`.
- Added monthly data generation script for variable-date holidays and celestial events.

## 2026-05 - State and Caching

- Added same-day haiku caching in `state/haiku_cache.json`.
- Added haiku history under `state/haiku_log/`.
- Added run logging under `state/run_log/`.
- Added writer's block state under `state/writers_block/`.
- Added per-platform post ID tracking under `state/post_ids/`.

## 2026-05 - Analytics and Reporting

- Added engagement tracking script.
- Added scheduled engagement workflow.
- Added engagement state under `state/engagement/`.
- Added engagement scoring formula:
  - likes × 1
  - shares / boosts / reposts × 2
  - replies / comments × 3
- Added weekly HTML email report generation.

## 2026-06-10 - Documentation Reconciliation Pass by ChatGPT

### Summary

ChatGPT audited the repository documentation against the current code, workflows, state files, and diagrams, then updated the documentation to reflect the implementation as it exists now.

### Files updated

- `README.md`
- `diagrams/architecture.md`
- `diagrams/daily-workflow-sequence.md`
- `diagrams/workflow-schedule.md`
- `diagrams/state-files.md`

### Files added

- `docs/subscription-status.md`
- `CHANGELOG.md`

### Corrections made

- Rewrote the README as a current-state implementation overview.
- Corrected adapter execution from implied parallel publishing to sequential execution in `config.yml` order.
- Clarified that GitHub Actions schedules are defined in `.github/workflows/*.yml`, not `config.yml`.
- Documented the actual daily execution path:
  - `daily.yml`
  - `run.py`
  - `framework.runner`
  - source plugin
  - engine/cache
  - sequential adapters
  - state and docs commit
- Updated the architecture diagram to include GitHub Actions, monthly data generation, analytics, reporting, and repository state.
- Updated the daily workflow sequence diagram to match the real runner flow.
- Updated the workflow schedule diagram and manual trigger notes.
- Updated the state file map and retention notes.
- Added explicit subscription-system status documentation.

### Subscription-system clarification

- Documented that daily email digest delivery exists through `plugins/adapters/email_list.py` when Gmail secrets and `state/subscribers.json` are configured.
- Documented that automated Gmail inbox polling for SUBSCRIBE/UNSUBSCRIBE is not yet implemented.
- Marked `check_subscriptions.py` as placeholder/demo code.
- Added a future implementation roadmap for subscription automation.

### Code impact

This was a documentation-only change. No production code, adapter logic, workflow logic, or haiku generation behavior was modified.

## 2026-08-10 - Multi-Provider AI Backend

GitHub Models (the original free AI backend) was fully retired 2026-07-30 with no warning, silently zeroing out haiku generation for 10 days — the runner marks a zero-haiku day as "complete" to avoid retry-spam, so no GitHub Actions failure notification ever fired.

- Diagnosed and fixed the outage: replaced the dead `models.inference.ai.azure.com` endpoint.
- Added `framework/alerts.py` — emails `REPORT_EMAIL` immediately if a run produces zero haikus, instead of only surfacing days later in the weekly report.
- Rebuilt the AI engine (`plugins/engines/clambakesanta.py`) around a multi-provider fallback chain instead of a single hardcoded backend: primary (Groq) cascades through `config.yml`'s `ai.fallback` list (Mistral, Cohere, Cerebras, OpenRouter, Pollinations, Gemini, Fireworks, HuggingFace) per theme, independently, until one produces a valid haiku or every provider is exhausted.
- Added `_is_permanent_failure()` to fail fast on config problems (bad key, wrong model, zero quota) instead of burning all 5 retries on a provider that can't succeed this run.
- Made `reasoning_effort` opt-in per provider (`config.yml`) after discovering it's required for reasoning models (Groq/Cerebras `gpt-oss-*`, which otherwise silently burn their token budget on hidden chain-of-thought and return empty content) but breaks others outright (Mistral/Cohere reject unsupported values with a 400/422).
- Added `optional_key` support for providers that work anonymously (Pollinations).
- Added `run.py --engine-only` and `.github/workflows/test_ai_backend.yml` — test any provider or the whole fallback chain via real repo secrets with zero public-posting side effects, instead of risking a live post to every channel and every email subscriber just to check if a provider works.
- Removed OpenAI, Together, DeepSeek, and SambaNova from the chain after testing — real account issues (no billing credits, exhausted free credits, no free tier, payment method required) rather than anything fixable in code.
- New reference doc: [diagrams/ai-backend.md](diagrams/ai-backend.md) — the full provider chain, current status per provider, testing rules, how to add a new provider, and the hard-won gotchas from this investigation (stale model IDs, misleading error text, per-provider reasoning_effort requirements).

### Code impact

Engine behavior change: haiku generation no longer depends on a single AI provider. Workflow change: `daily.yml` now passes through 9 provider secrets instead of 1; `permissions.models: read` removed (no longer calls GitHub Models). No adapter or publishing logic changed.
