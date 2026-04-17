"""
Post ID / URL store — partitioned by date.

Directory layout:
  state/post_ids/
    2026-04-17.json   ← one file per day: { tag: { platform: {id, url, ...} } }
    2026-04-16.json
    ...
    summary.json      ← rolling 7-day merged view rebuilt after every write
                        (fast-access file used by check_engagement.py)

Day-file format:
  {
    "NationalHaikuDay": {
      "mastodon": {"id": "112345678", "url": "https://mastodon.social/..."},
      "bluesky":  {"uri": "at://did:plc:.../app.bsky.feed.post/...", "cid": "..."},
      "reddit":   {"id": "abc123", "url": "https://redd.it/abc123"}
    }
  }

Migration:  if the old flat state/post_ids.json exists, it is split into
            per-day files automatically on the first call, then renamed to
            post_ids.json.migrated so the migration never runs twice.
"""
from __future__ import annotations

import json
import pathlib
from datetime import date, timedelta

SUMMARY_DAYS = 7

_migrated: set[str] = set()


# ── Internal helpers ──────────────────────────────────────────────────────────

def _store_dir(config: dict) -> pathlib.Path:
    d = pathlib.Path(config.get("state_dir", "state")) / "post_ids"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _day_file(config: dict, date_str: str) -> pathlib.Path:
    return _store_dir(config) / f"{date_str}.json"


def _summary_file(config: dict) -> pathlib.Path:
    return _store_dir(config) / "summary.json"


def _read(path: pathlib.Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return default


def _write(path: pathlib.Path, data) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _parse_date(date_str: str) -> date:
    try:
        return date.fromisoformat(date_str)
    except (ValueError, TypeError):
        return date.min


def _migrate_flat(config: dict) -> None:
    """
    One-time migration: split state/post_ids.json into per-day files.
    Renames the old file to .json.migrated so this runs only once.
    Uses a per-process in-memory cache so the filesystem check only happens
    once per process, not on every read/write call.
    """
    state_key = config.get("state_dir", "state")
    if state_key in _migrated:
        return

    old = pathlib.Path(state_key) / "post_ids.json"
    if not old.exists():
        _migrated.add(state_key)
        return
    try:
        data = _read(old, {})
        if not isinstance(data, dict):
            return
        count = 0
        for date_str, day_data in data.items():
            if isinstance(day_data, dict):
                _write(_day_file(config, date_str), day_data)
                count += 1
        _rebuild_summary(config)
        old.rename(old.with_suffix(".json.migrated"))
        _migrated.add(state_key)
        print(f"[post_store] Migrated {count} day(s) of post IDs → post_ids/")
    except Exception as exc:
        print(f"[post_store] Migration warning: {exc}")


def _rebuild_summary(config: dict, days: int = SUMMARY_DAYS) -> dict:
    """
    Rebuild summary.json from the last `days` day files.
    Returns the rebuilt summary dict { date_str: { tag: { platform: {...} } } }.
    """
    store_dir = _store_dir(config)
    today     = date.today()
    cutoff    = today - timedelta(days=days)

    summary: dict = {}
    for p in sorted(store_dir.glob("????-??-??.json"), key=lambda x: x.stem, reverse=True):
        d = _parse_date(p.stem)
        if d < cutoff:
            break
        data = _read(p, {})
        if isinstance(data, dict):
            summary[p.stem] = data

    _write(_summary_file(config), summary)
    return summary


# ── Public API ────────────────────────────────────────────────────────────────

def save_post_id(
    config:   dict,
    date_str: str,
    tag:      str,
    platform: str,
    data:     dict,
) -> None:
    """
    Save a post identifier for one haiku on one platform, then rebuild
    summary.json.

    Parameters
    ----------
    date_str : run date, e.g. "2026-04-17"
    tag      : haiku tag key, e.g. "NationalHaikuDay"
    platform : "mastodon" | "bluesky" | "reddit" | ...
    data     : dict of platform-specific IDs/URLs returned by the API
    """
    _migrate_flat(config)
    day_data = _read(_day_file(config, date_str), {})
    day_data.setdefault(tag, {})[platform] = data
    _write(_day_file(config, date_str), day_data)
    _rebuild_summary(config)


def load_summary(config: dict, days: int = SUMMARY_DAYS) -> dict:
    """
    Return the rolling summary (last `days` days) — fast path.
    Rebuilds from day files if summary.json doesn't exist yet.
    """
    _migrate_flat(config)
    data = _read(_summary_file(config), None)
    if data is None:
        return _rebuild_summary(config, days)
    return data


def load_day(config: dict, date_str: str) -> dict:
    """Return { tag: { platform: {...} } } for a specific date."""
    _migrate_flat(config)
    return _read(_day_file(config, date_str), {})


# Backward-compat alias used by check_engagement.py
def load_post_ids(config: dict) -> dict:
    """Alias for load_summary — returns last 7 days."""
    return load_summary(config)


def get_posts_for_date(config: dict, date_str: str) -> dict:
    """Alias for load_day."""
    return load_day(config, date_str)
