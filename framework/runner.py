"""
Main execution loop.

Flow:
  Source → Engine (or cache) → Adapters → State

The runner is the only place that knows about all four layers.
It wires them together but contains zero business logic itself.

Haiku caching
-------------
After the engine runs, today's haikus are saved to state/haiku_cache.json.
On any subsequent run for the same date (re-runs, --force, adapter tests)
the engine is skipped and the cached haikus are used instead.
This ensures every adapter always uses the same poems for a given day.
Use --regenerate (run.py) to force fresh AI generation and overwrite the cache.
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
    source_id = config["source"]
    source = get_plugin("sources", source_id)(config)
    event = source.produce()

    # Deduplication: skip if already ran for this date
    if not force and state.already_ran_today(event.date_str):
        log.info("Already ran for %s — skipping. Pass --force to override.", event.date_str)
        return {"date": event.date_str, "skipped": True}

    log.info("Run starting | date=%s source=%s", event.date_str, source_id)
    log.info("Themes found: %s", event.payload.get("themes", []))

    # ── 2. ENGINE (or cache) ──────────────────────────────────────────────────
    engine_id = config["engine"]
    cache = None if regenerate else _load_cache(config, event.date_str)

    if cache:
        result = _result_from_cache(event, engine_id, cache)
        log.info("Using cached haikus for %s (%d item(s)) — skipping AI call",
                 event.date_str, len(result.metadata.get("haikus", [])))
    else:
        engine = get_plugin("engines", engine_id)(config)
        result = engine.process(event)
        haiku_count = len(result.metadata.get("haikus", []))
        log.info("Engine '%s' produced %d item(s)", engine_id, haiku_count)
        _save_cache(config, result)
        # Persist to long-term haiku log (used for anti-repetition + reporting)
        append_haikus(config, event.date_str, result.metadata.get("haikus", []))

    # ── 3. ADAPTERS ───────────────────────────────────────────────────────────
    adapters_ok: list[str] = []
    adapters_failed: list[tuple[str, str]] = []

    for adapter_id in config.get("adapters", []):
        try:
            adapter = get_plugin("adapters", adapter_id)(config)
            success = adapter.publish(result)
            if success:
                adapters_ok.append(adapter_id)
                log.info("Adapter '%s': OK", adapter_id)
            else:
                log.info("Adapter '%s': SKIPPED (returned False)", adapter_id)
        except Exception as exc:
            adapters_failed.append((adapter_id, str(exc)))
            log.error("Adapter '%s' FAILED: %s", adapter_id, exc)

    # ── 4. STATE ──────────────────────────────────────────────────────────────
    state.record_run(result)

    summary = {
        "date": event.date_str,
        "engine": engine_id,
        "adapters_ok": adapters_ok,
        "adapters_failed": adapters_failed,
        "skipped": False,
    }
    log.info("Run complete: %s", summary)
    return summary
