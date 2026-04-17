"""
Engagement store — partitioned by date.

Directory layout:
  state/engagement/
    2026-04-17.json   ← one file per day: { tag: { theme, haiku, platforms, total_score, ... } }
    2026-04-16.json
    ...
    summary.json      ← rolling 7-day merged view rebuilt after every write
                        (fast-access file used by weekly_report.py)

Day-file format:
  {
    "NationalHaikuDay": {
      "theme":   "National Haiku Day",
      "haiku":   "...",
      "platforms": {
        "mastodon": {"id": "...", "url": "...", "likes": 4,
                     "boosts": 1, "replies": 0, "score": 6},
        "bluesky":  {"uri": "...", "likes": 2, "reposts": 0,
                     "replies": 1, "score": 5},
        "reddit":   {"id": "...", "url": "...", "upvotes": 3,
                     "comments": 2, "score": 9}
      },
      "total_score":  20,
      "last_checked": "2026-04-18T06:00:00+00:00"
    }
  }

Migration:  if the old flat state/engagement.json exists, it is split into
            per-day files automatically on the first call, then renamed to
            engagement.json.migrated so the migration never runs twice.
"""
from __future__ import annotations

import json
import pathlib
from datetime import date, timedelta

SUMMARY_DAYS = 7

_migrated: set[str] = set()


# ── Internal helpers ──────────────────────────────────────────────────────────

def _store_dir(config: dict) -> pathlib.Path:
    d = pathlib.Path(config.get("state_dir", "state")) / "engagement"
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
    One-time migration: split state/engagement.json into per-day files.
    Renames the old file to .json.migrated so this runs only once.
    Uses a per-process in-memory cache so the filesystem check only happens
    once per process, not on every read/write call.
    """
    state_key = config.get("state_dir", "state")
    if state_key in _migrated:
        return

    old = pathlib.Path(state_key) / "engagement.json"
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
        print(f"[engagement_store] Migrated {count} day(s) of engagement → engagement/")
    except Exception as exc:
        print(f"[engagement_store] Migration warning: {exc}")


def _rebuild_summary(config: dict, days: int = SUMMARY_DAYS) -> dict:
    """
    Rebuild summary.json from the last `days` day files.
    Returns { date_str: { tag: {...} } }.
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

def load_day(config: dict, date_str: str) -> dict:
    """Return { tag: {...} } for a specific date."""
    _migrate_flat(config)
    return _read(_day_file(config, date_str), {})


def save_day(config: dict, date_str: str, data: dict) -> None:
    """
    Overwrite the engagement data for a specific date, then rebuild
    summary.json so the weekly report always reads fresh data.
    """
    _migrate_flat(config)
    _write(_day_file(config, date_str), data)
    _rebuild_summary(config)


def load_summary(config: dict, days: int = SUMMARY_DAYS) -> dict:
    """
    Return { date_str: { tag: {...} } } for the last `days` days — fast path.
    Rebuilds from day files if summary.json doesn't exist yet.
    """
    _migrate_flat(config)
    data = _read(_summary_file(config), None)
    if data is None:
        return _rebuild_summary(config, days)
    return data


def load_range(config: dict, start: date, end: date) -> dict:
    """
    Return engagement data for all dates in [start, end).
    Reads individual day files — used by weekly_report when --weeks > 1.
    """
    _migrate_flat(config)
    result: dict = {}
    store_dir = _store_dir(config)
    for p in sorted(store_dir.glob("????-??-??.json"), key=lambda x: x.stem):
        d = _parse_date(p.stem)
        if d < start:
            continue
        if d >= end:
            break
        data = _read(p, {})
        if isinstance(data, dict):
            result[p.stem] = data
    return result
