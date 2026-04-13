"""
Main execution loop.

Flow:
  Source → Engine → Adapters → State

The runner is the only place that knows about all four layers.
It wires them together but contains zero business logic itself.
"""
from __future__ import annotations
import importlib
import logging
from .registry import get_plugin
from .state.json_store import JsonStateStore

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


def run(config: dict, force: bool = False) -> dict:
    """
    Execute one full run of the framework pipeline.

    Parameters
    ----------
    config : parsed config.yml as a dict
    force  : if True, skip the deduplication check (run even if already ran today)

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

    # ── 2. ENGINE ─────────────────────────────────────────────────────────────
    engine_id = config["engine"]
    engine = get_plugin("engines", engine_id)(config)
    result = engine.process(event)

    haiku_count = len(result.metadata.get("haikus", []))
    log.info("Engine '%s' produced %d item(s)", engine_id, haiku_count)

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
