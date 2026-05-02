# Data Pipeline — ClamBakeSanta

## Pipeline Overview

The framework executes a strict linear pipeline with validation gates between every layer. The runner (`framework/runner.py`) contains zero business logic — it only knows how to wire the layers together and validate hand-offs.

```
Source
  │
  ▼
validate_event()          ← hard stop if invalid
  │
  ▼
Deduplication check       ← skip if already ran today (unless --force)
  │
  ▼
Haiku cache check         ← load cache if exists for today date (unless --regenerate)
  │              │
  │              └── Cache hit → _result_from_cache()
  │
  ▼ Cache miss
Engine.process(event)     ← calls AI; returns Result
  │
  ├── _save_cache()       ← write haiku_cache.json
  └── append_haikus()     ← append to long-term haiku_log/
  │
  ▼
validate_result()         ← hard stop if invalid
  │
  ▼ (for each adapter in config order)
┌─────────────────────────────────────────┐
│  validate_result() [paranoia check]     │
│  adapter.publish(result)                │
│  → True  : adapters_ok.append()        │
│  → False : skipped (no credentials)    │
│  → raise : adapters_failed.append()    │
│  (continues to next adapter regardless)│
└─────────────────────────────────────────┘
  │
  ▼
state.record_run(result)  ← mark today as done in run_log.json
  │
  ▼
Return summary dict
```

---

## Step 1: Source — `daily_holidays` Plugin

**File**: `plugins/sources/daily_holidays.py`

The source reads two text files for the current month:
- `data/{month}_randomholiday.txt` — quirky/observational holidays
- `data/{month}_celebritybirthday.txt` — celebrity birthdays

It finds entries matching today's date and assembles a `themes` list (strings). Returns an `Event` object.

**`Event` schema** (`framework/models.py`):
```python
@dataclass
class Event:
    date_str: str          # ISO format: "YYYY-MM-DD"
    payload: dict          # { "themes": ["National Cookie Day", "Sammy Davis Jr birthday"] }
```

---

## Step 2: `validate_event()`

**File**: `framework/validation.py`

Checks the `Event` before anything downstream runs. Raises `ValidationError` on:
- Missing or empty `date_str`
- Wrong type for `payload`
- Missing `themes` key

A `ValidationError` from this check is a **hard failure** — the run stops immediately. The runner raises a `RuntimeError`, the GitHub Action fails, and no adapter is called.

---

## Step 3: Deduplication Check

```python
if not force and state.already_ran_today(event.date_str):
    return {"date": ..., "skipped": True}
```

`JsonStateStore.already_ran_today()` reads `state/run_log.json` and checks for a successful run on `date_str`. If found, the run returns early with `skipped: True`.

Override with `--force` (CLI) or `force=True` (programmatic). Used by adapter test workflows that need to run outside the daily deduplication window.

---

## Step 4a: Haiku Cache Check

Before calling the AI engine, the runner checks `state/haiku_cache.json`:

```python
cache = None if regenerate else _load_cache(config, event.date_str)
```

**Cache hit**: `haiku_cache.json` exists AND its `"date"` field matches `event.date_str`. The engine is skipped entirely — `_result_from_cache()` reconstructs a `Result` from the cached data.

**Cache miss**: No cache file, wrong date, or `--regenerate` flag passed. Engine runs normally.

**Why cache exists**: All adapters for a given day must use the same haikus. If the pipeline reruns (e.g., an adapter failed and the workflow was re-triggered), the cache ensures every platform gets identical poems rather than AI-regenerated ones that would differ.

**Haiku cache schema** (`state/haiku_cache.json`):
```json
{
  "date": "2026-05-02",
  "haikus": ["5-7-5 poem...", "5-7-5 poem...", "5-7-5 poem..."],
  "themes": ["National Cookie Day", "Sammy Davis Jr birthday"],
  "content": "Full formatted text of all haikus",
  "saved_at": "2026-05-02T13:00:00Z"
}
```

---

## Step 4b: Engine — `clambakesanta` Plugin (Fresh Run)

**File**: `plugins/engines/clambakesanta.py`

On a cache miss, the engine:
1. Takes `event.payload["themes"]` from the `Event`.
2. Constructs a prompt instructing `gpt-4o-mini` to write 3 haikus, one per theme, in 5-7-5 syllable structure.
3. Calls GitHub Models API (`GITHUB_TOKEN` injected automatically by Actions).
4. Parses the response into individual haikus.
5. Returns a `Result` object.

**`Result` schema** (`framework/models.py`):
```python
@dataclass
class Result:
    event: Event
    engine_id: str          # "clambakesanta"
    content: str            # Full formatted output (all haikus combined)
    metadata: dict          # { "haikus": [...], "themes": [...], "date": "YYYY-MM-DD" }
```

After the engine returns:
- `_save_cache(config, result)` writes `state/haiku_cache.json`.
- `append_haikus(config, date_str, haikus)` appends to the long-term `state/haiku_log/` directory for anti-repetition and weekly reporting.

---

## Step 5: `validate_result()`

**File**: `framework/validation.py`

Checks the `Result` before any adapter runs. Raises `ValidationError` on:
- Empty or missing `content`
- Missing or malformed `metadata`
- Missing `haikus` list in metadata

Called **once** after the engine/cache step (hard stop if invalid), then called **again** at the start of each adapter loop iteration (paranoia check — catches accidental mutation between adapter calls).

---

## Step 6: Adapter Loop

For each `adapter_id` in `config["adapters"]` (in order):

```python
# 1. Paranoia validate
validate_result(result)

# 2. Instantiate adapter
adapter = get_plugin("adapters", adapter_id)(config)

# 3. Publish
success = adapter.publish(result)
```

**`adapter.publish(result)` return contract**:
| Return value | Meaning |
|---|---|
| `True` | Posted successfully → `adapters_ok` |
| `False` | Skipped (missing credentials or env vars) |
| `raise Exception` | Adapter failed → `adapters_failed` with error string |

**Isolation**: Each adapter is fully independent. An exception from one adapter is caught, logged, and added to `adapters_failed`. The loop continues to the next adapter. A failing Discord adapter never stops the Mastodon or GitHub Pages adapters.

**Missing credentials**: Each adapter checks for its required environment variables (`MASTODON_ACCESS_TOKEN`, `BLUESKY_APP_PASSWORD`, etc.) and returns `False` immediately if any are absent. The runner logs this as "SKIPPED" — not an error.

---

## Step 7: State Recording

```python
state.record_run(result)
```

`JsonStateStore.record_run()` appends the run record to `state/run_log.json`. Future runs on the same date will see `already_ran_today()` return `True`, preventing double-posting.

---

## Run Summary

The `run()` function returns:
```python
{
    "date": "2026-05-02",
    "engine": "clambakesanta",
    "adapters_ok": ["mastodon", "bluesky", "github_pages"],
    "adapters_failed": [("discord", "Webhook 403 Forbidden")],
    "skipped": False,
}
```

---

## CLI Flags (`run.py`)

| Flag | Effect |
|---|---|
| `--force` | Skip deduplication check; run even if already ran today |
| `--regenerate` | Bypass haiku cache; force fresh AI generation |
| `--adapter NAME` | Run only the specified adapter (still uses cache if available) |

These flags are passed through to `runner.run(config, force=..., regenerate=...)`.

---

## Schema Invariants

| Contract | Enforced by |
|---|---|
| `Event.date_str` is non-empty ISO date | `validate_event()` |
| `Event.payload["themes"]` is a non-empty list | `validate_event()` |
| `Result.content` is non-empty string | `validate_result()` |
| `Result.metadata["haikus"]` is a list | `validate_result()` |
| All adapters for a date use the same haikus | `haiku_cache.json` keyed by date |
| No double-posting on the same date | `run_log.json` + `already_ran_today()` |
| `state/` files never manually edited | `.gitignore` + documentation |
