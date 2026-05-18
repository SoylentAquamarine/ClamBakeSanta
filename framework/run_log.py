"""
Rolling run log — one JSON file per day under state/run_log/.

Each day file is a list of run records (supports multiple runs per day,
e.g. forced re-runs or adapter tests).

Run record format:
  {
    "timestamp":      "2026-05-18T09:01:23+00:00",
    "date":           "2026-05-18",
    "themes_found":   ["National Cheese Souffle Day", "No Dirty Dishes Day", ...],
    "haikus_posted":  [
      {"theme": "National Cheese Souffle Day", "tag": "...", "valid_syllables": true,
       "counts": [5, 7, 5]}
    ],
    "writers_block":  [
      {"theme": "No Dirty Dishes Day", "tag": "...", "attempts": 5}
    ],
    "adapters_ok":    ["mastodon", "bluesky", ...],
    "adapters_failed": [["reddit", "error message"], ...],
    "skipped":        false
  }

Rolling: files older than keep_days (default 30) are pruned on every write.
"""
from __future__ import annotations

import json
import pathlib
from datetime import date, datetime, timedelta, timezone

_DEFAULT_KEEP_DAYS = 30


def _store_dir(config: dict) -> pathlib.Path:
    d = pathlib.Path(config.get("state_dir", "state")) / "run_log"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _day_file(config: dict, date_str: str) -> pathlib.Path:
    return _store_dir(config) / f"{date_str}.json"


def _read(path: pathlib.Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return default


def _cleanup_old(config: dict, keep_days: int) -> None:
    cutoff = date.today() - timedelta(days=keep_days)
    for p in _store_dir(config).glob("????-??-??.json"):
        try:
            if date.fromisoformat(p.stem) < cutoff:
                p.unlink()
        except (ValueError, OSError):
            pass


def append(config: dict, record: dict, keep_days: int = _DEFAULT_KEEP_DAYS) -> None:
    """
    Append a run record to today's log file.

    Expected keys in record: timestamp, date, themes_found, haikus_posted,
    writers_block, adapters_ok, adapters_failed, skipped.
    """
    date_str = record.get("date", date.today().isoformat())
    path = _day_file(config, date_str)
    entries = _read(path, [])
    entries.append(record)
    path.write_text(json.dumps(entries, indent=2, ensure_ascii=False), encoding="utf-8")
    _cleanup_old(config, keep_days)


def load_day(config: dict, date_str: str) -> list[dict]:
    """Return all run records for a given date."""
    return _read(_day_file(config, date_str), [])


def load_recent(config: dict, days: int = _DEFAULT_KEEP_DAYS) -> list[dict]:
    """Return all run records from the last `days` days, oldest first."""
    cutoff = date.today() - timedelta(days=days)
    records: list[dict] = []
    for p in sorted(_store_dir(config).glob("????-??-??.json"), key=lambda x: x.stem):
        try:
            if date.fromisoformat(p.stem) >= cutoff:
                records.extend(_read(p, []))
        except ValueError:
            pass
    return records
