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
