"""
Persistent haiku log — partitioned by date.

Directory layout:
  state/haiku_log/
    2026-04-17.json   ← one file per day, array of haiku records
    2026-04-16.json
    ...
    recent.json       ← rolling 7-day summary rebuilt after every write
                        (fast-access file used by anti-repetition + report)

Day-file format (array):
  [
    {
      "date":      "2026-04-17",
      "theme":     "National Haiku Day",
      "haiku":     "line1\nline2\nline3\nhashtag line",
      "tag":       "NationalHaikuDay",
      "logged_at": "2026-04-17T05:01:23+00:00"
    },
    ...
  ]

Migration:  if the old flat state/haiku_log.json exists, it is split into
            per-day files automatically on the first call, then renamed to
            haiku_log.json.migrated so the migration never runs twice.
"""
from __future__ import annotations

import json
import pathlib
from datetime import date, datetime, timedelta, timezone

SUMMARY_DAYS = 7   # how many days to include in recent.json


# ── Internal helpers ──────────────────────────────────────────────────────────

def _log_dir(config: dict) -> pathlib.Path:
    d = pathlib.Path(config.get("state_dir", "state")) / "haiku_log"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _day_file(config: dict, date_str: str) -> pathlib.Path:
    return _log_dir(config) / f"{date_str}.json"


def _recent_file(config: dict) -> pathlib.Path:
    return _log_dir(config) / "recent.json"


def _read(path: pathlib.Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
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
    One-time migration: split state/haiku_log.json into per-day files.
    Renames the old file to .json.migrated so this runs only once.
    """
    old = pathlib.Path(config.get("state_dir", "state")) / "haiku_log.json"
    if not old.exists():
        return
    try:
        entries = _read(old, [])
        if not isinstance(entries, list):
            return
        # Group by date
        by_date: dict[str, list] = {}
        for e in entries:
            by_date.setdefault(e.get("date", "unknown"), []).append(e)
        for date_str, day_entries in by_date.items():
            _write(_day_file(config, date_str), day_entries)
        _rebuild_recent(config)
        old.rename(old.with_suffix(".json.migrated"))
        print(f"[haiku_log] Migrated {len(entries)} entries across "
              f"{len(by_date)} day(s) → haiku_log/")
    except Exception as exc:
        print(f"[haiku_log] Migration warning: {exc}")


def _rebuild_recent(config: dict, days: int = SUMMARY_DAYS) -> list[dict]:
    """
    Rebuild recent.json from the last `days` day files (excluding today).
    Returns the rebuilt list (oldest first).
    """
    log_dir = _log_dir(config)
    today   = date.today()
    cutoff  = today - timedelta(days=days)

    recent: list[dict] = []
    # Iterate day files newest-first; stop once we go past the window
    for p in sorted(log_dir.glob("????-??-??.json"), key=lambda x: x.stem, reverse=True):
        d = _parse_date(p.stem)
        if d >= today:
            continue     # skip today's partial run
        if d < cutoff:
            break
        recent.extend(_read(p, []))

    # Sort oldest-first for readability
    recent.sort(key=lambda e: e.get("date", ""))
    _write(_recent_file(config), recent)
    return recent


# ── Public API ────────────────────────────────────────────────────────────────

def append_haikus(config: dict, date_str: str, haiku_records: list[dict]) -> None:
    """
    Write today's freshly generated haikus to their day file, then
    rebuild recent.json.  If entries for today already exist (e.g. from a
    --regenerate run), they are fully replaced.
    """
    _migrate_flat(config)
    now = datetime.now(timezone.utc).isoformat()
    entries = [
        {
            "date":      date_str,
            "theme":     rec.get("theme", ""),
            "haiku":     rec.get("haiku", ""),
            "tag":       rec.get("tag", ""),
            "logged_at": now,
        }
        for rec in haiku_records
    ]
    _write(_day_file(config, date_str), entries)
    _rebuild_recent(config)


def load_day(config: dict, date_str: str) -> list[dict]:
    """Return all log entries for a specific date."""
    _migrate_flat(config)
    return _read(_day_file(config, date_str), [])


def load_recent(config: dict, days: int = SUMMARY_DAYS) -> list[dict]:
    """
    Return entries from the last `days` days using the fast recent.json.
    Rebuilds recent.json if it doesn't exist yet.
    """
    _migrate_flat(config)
    data = _read(_recent_file(config), None)
    if data is None:
        return _rebuild_recent(config, days)
    return data


def load_all(config: dict) -> list[dict]:
    """Return complete history by reading every day file (oldest first)."""
    _migrate_flat(config)
    all_entries: list[dict] = []
    for p in sorted(_log_dir(config).glob("????-??-??.json"), key=lambda x: x.stem):
        all_entries.extend(_read(p, []))
    return all_entries


def opening_phrases(config: dict, days: int = SUMMARY_DAYS) -> list[str]:
    """
    Return the first line of each haiku from the last `days` days,
    excluding today.  Used by the engine's anti-repetition prompt.
    """
    today  = date.today()
    cutoff = today - timedelta(days=days)
    phrases = []
    for entry in load_recent(config, days):
        d = _parse_date(entry.get("date", ""))
        if d < cutoff or d >= today:
            continue
        lines = entry.get("haiku", "").split("\n")
        if lines and lines[0].strip():
            phrases.append(lines[0].strip().rstrip(","))
    return phrases


def entries_for_date(config: dict, date_str: str) -> list[dict]:
    """Convenience alias for load_day."""
    return load_day(config, date_str)


def build_index(config: dict) -> dict[str, dict]:
    """
    Return { tag: {"theme", "haiku", "date"} } from the full history.
    Used by check_engagement.py to look up haiku text for each tag.
    """
    index: dict[str, dict] = {}
    for entry in load_all(config):
        index[entry.get("tag", "")] = {
            "theme": entry.get("theme", ""),
            "haiku": entry.get("haiku", ""),
            "date":  entry.get("date", ""),
        }
    return index
