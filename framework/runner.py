"""
Main execution loop — the only place that wires all four layers together.

Pipeline
--------
  Source  ──► validate_event ──► Engine (or cache) ──► validate_result ──► Adapters ──► State
       produces Event                 transforms                  publishes

The runner contains ZERO business logic.  It knows:
  - how to load plugins
  - how to call each layer in the right order
  - how to validate the hand-off between layers
  - how to record the outcome in state

Everything else lives in plugins.

Haiku caching
-------------
After the engine runs, today's haikus are saved to state/haiku_cache.json.
On any subsequent run for the same date (re-runs, --force, adapter tests)
the engine is skipped and the cached haikus are used instead.
This ensures every adapter always uses the same poems for a given day.
Use --regenerate (run.py) to force fresh AI generation and overwrite the cache.

Schema validation
-----------------
validate_event()  is called right after the source produces an Event.
validate_result() is called right after the engine produces a Result,
                  and again as a guard immediately before each adapter runs.
A ValidationError from either check is treated as a hard failure — the run
stops rather than posting corrupt or incomplete content to any platform.
"""
from __future__ import annotations
import importlib
import json
import logging
import pathlib
from datetime import datetime, timezone

from .registry import get_plugin
from .state.json_store import JsonStateStore
from .models import Event, Result
from .haiku_log import append_haikus
from .validation import validate_event, validate_result, ValidationError
from . import run_log

log = logging.getLogger(__name__)

# Default plugin modules to import on startup.
# Adding a new plugin = add its module path here (or in config.yml plugin_modules).
DEFAULT_PLUGIN_MODULES = [
    "plugins.sources.daily_holidays",
    "plugins.engines.clambakesanta",
    "plugins.adapters.github_pages",
    "plugins.adapters.discord",
    "plugins.adapters.mastodon_adapter",
]


def _load_plugins(config: dict) -> None:
    """
    Import all plugin modules so their @register decorators fire.
    Safe to call multiple times — importlib caches modules.
    """
    modules = config.get("plugin_modules", DEFAULT_PLUGIN_MODULES)
    for module_path in modules:
        try:
            importlib.import_module(module_path)
            log.debug("Loaded plugin: %s", module_path)
        except ImportError as exc:
            log.warning("Could not load plugin module '%s': %s", module_path, exc)


def _cache_path(config: dict) -> pathlib.Path:
    state_dir = pathlib.Path(config.get("state_dir", "state"))
    state_dir.mkdir(parents=True, exist_ok=True)
    return state_dir / "haiku_cache.json"


def _load_cache(config: dict, date_str: str) -> dict | None:
    """Return cached haiku data for date_str, or None if not available."""
    path = _cache_path(config)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("date") == date_str:
            return data
    except (json.JSONDecodeError, OSError):
        pass
    return None


def _save_cache(config: dict, result: Result) -> None:
    """Persist today's haiku result to cache file."""
    path = _cache_path(config)
    data = {
        "date":    result.event.date_str,
        "haikus":  result.metadata.get("haikus", []),
        "themes":  result.metadata.get("themes", []),
        "content": result.content,
        "saved_at": datetime.now(timezone.utc).isoformat(),
    }
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    log.info("Haiku cache saved → %s", path)


def _result_from_cache(event: Event, engine_id: str, cache: dict) -> Result:
    """Reconstruct a Result object from cached data."""
    return Result(
        event=event,
        engine_id=engine_id,
        content=cache.get("content", ""),
        metadata={
            "haikus": cache.get("haikus", []),
            "themes": cache.get("themes", []),
            "date":   cache.get("date", event.date_str),
        },
    )


def run(config: dict, force: bool = False, regenerate: bool = False) -> dict:
    """
    Execute one full run of the framework pipeline.

    Parameters
    ----------
    config     : parsed config.yml as a dict
    force      : if True, skip the deduplication check (run even if already ran today)
    regenerate : if True, call the AI engine even if a cache exists for today

    Returns
    -------
    dict with keys: date, engine, adapters_ok, adapters_failed, skipped
    """
    _load_plugins(config)

    state = JsonStateStore(config.get("state_dir", "state"))

    # ── 1. SOURCE ─────────────────────────────────────────────────────────────
    # Ask the source plugin "what is happening today?"
    # It reads data files and returns a standardized Event object.
    source_id = config["source"]
    source    = get_plugin("sources", source_id)(config)
    event     = source.produce()

    # Guard: make sure the source gave us a well-formed Event before we proceed.
    # A bad Event (missing date, wrong type, etc.) means nothing downstream works.
    try:
        validate_event(event)
    except ValidationError as exc:
        raise RuntimeError(str(exc)) from exc

    # Deduplication: if we already ran successfully for this date, bail out early
    # unless --force was passed.  This prevents double-posting on re-runs.
    if not force and state.already_ran_today(event.date_str):
        log.info("Already ran for %s — skipping. Pass --force to override.", event.date_str)
        return {"date": event.date_str, "skipped": True, "engine": config.get("engine", "")}

    themes_found = event.payload.get("themes", [])
    log.info("Run starting | date=%s source=%s", event.date_str, source_id)
    log.info("Themes found (%d): %s", len(themes_found), themes_found)

    # ── 2. ENGINE (or cache) ──────────────────────────────────────────────────
    engine_id = config["engine"]
    cache     = None if regenerate else _load_cache(config, event.date_str)

    if cache:
        result = _result_from_cache(event, engine_id, cache)
        haiku_count = len(result.metadata.get("haikus", []))
        log.info("Using cached haikus for %s (%d haiku(s)) — skipping AI call",
                 event.date_str, haiku_count)
    else:
        engine = get_plugin("engines", engine_id)(config)
        result = engine.process(event)

        haikus          = result.metadata.get("haikus", [])
        writers_block   = result.metadata.get("writers_block", [])
        haiku_count     = len(haikus)

        log.info("Engine '%s': %d/%d haiku(s) generated — %d writer's block",
                 engine_id, haiku_count, len(themes_found), len(writers_block))

        if writers_block:
            for wb in writers_block:
                log.warning("Writer's block: skipped theme=%r after %d attempt(s)",
                            wb["theme"], wb["attempts"])

        if not haikus:
            log.error("No haikus generated — writer's block on all themes. "
                      "Run will be marked complete to prevent re-posting attempts.")

        # Save cache and haiku log (even if empty — marks the run as attempted).
        _save_cache(config, result)
        if haikus:
            append_haikus(config, event.date_str, haikus)

    # Guard: make sure the engine (or cache restore) gave us a valid Result.
    # An invalid Result here means we'd post garbage to every platform — stop now.
    try:
        validate_result(result)
    except ValidationError as exc:
        raise RuntimeError(str(exc)) from exc

    # ── 3. ADAPTERS ───────────────────────────────────────────────────────────
    # Run each output channel in the order listed in config.yml.
    # Adapters are independent — one failure never stops the others.
    # Missing credentials → the adapter returns False (skipped silently).
    adapters_ok: list[str] = []
    adapters_failed: list[tuple[str, str]] = []

    for adapter_id in config.get("adapters", []):
        # Paranoia check: validate the result hasn't been accidentally mutated
        # between adapters.  This should never fail, but if it does, we want
        # a clear error rather than a silent bad post.
        try:
            validate_result(result)
        except ValidationError as exc:
            msg = f"Result corrupted before adapter '{adapter_id}': {exc}"
            adapters_failed.append((adapter_id, msg))
            log.error(msg)
            continue

        try:
            adapter = get_plugin("adapters", adapter_id)(config)
            success = adapter.publish(result)
            if success:
                adapters_ok.append(adapter_id)
                log.info("Adapter '%s': OK", adapter_id)
            else:
                log.info("Adapter '%s': SKIPPED (returned False — likely missing credentials)",
                         adapter_id)
        except Exception as exc:
            adapters_failed.append((adapter_id, str(exc)))
            log.error("Adapter '%s' FAILED: %s", adapter_id, exc)

    # ── 4. STATE ──────────────────────────────────────────────────────────────
    state.record_run(result)

    haiku_log_entries = [
        {
            "theme":           r.get("theme"),
            "tag":             r.get("tag"),
            "valid_syllables": r.get("valid_syllables", True),
            "counts":          r.get("syllable_counts", []),
        }
        for r in result.metadata.get("haikus", [])
    ]

    summary = {
        "date":           event.date_str,
        "engine":         engine_id,
        "adapters_ok":    adapters_ok,
        "adapters_failed": adapters_failed,
        "skipped":        False,
    }

    run_log.append(config, {
        "timestamp":       datetime.now(timezone.utc).isoformat(),
        "date":            event.date_str,
        "themes_found":    themes_found,
        "haikus_posted":   haiku_log_entries,
        "writers_block":   result.metadata.get("writers_block", []),
        "adapters_ok":     adapters_ok,
        "adapters_failed": [(a, e) for a, e in adapters_failed],
        "skipped":         False,
    })

    if adapters_failed:
        log.warning("Some adapters failed: %s", [a for a, _ in adapters_failed])
    log.info("Run complete | date=%s haikus=%d writers_block=%d adapters_ok=%s",
             event.date_str,
             len(result.metadata.get("haikus", [])),
             len(result.metadata.get("writers_block", [])),
             adapters_ok)

    return summary
