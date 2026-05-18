"""
Writer's block log — records every haiku attempt that failed 5-7-5 validation.

Layout:  state/writers_block/YYYY-MM-DD.json
         One file per day, each is a list of block records.

Block record format:
  {
    "theme":     "No Dirty Dishes Day",
    "tag":       "NoDirtyDishesDay",
    "timestamp": "2026-05-18T12:35:44+00:00",
    "attempts":  [
      {"text": "Plates piled to the sky,\\n...", "counts": [5, 8, 5]},
      {"text": "Dishes wait for you,\\n...",     "counts": [5, 6, 6]},
      ...
    ]
  }

Rolling: files older than keep_days (default 30) are pruned automatically
on every write, so the directory never grows unbounded.
"""
from __future__ import annotations

import json
import pathlib
from datetime import date, datetime, timedelta, timezone

_DEFAULT_KEEP_DAYS = 30


def _store_dir(config: dict) -> pathlib.Path:
    d = pathlib.Path(config.get("state_dir", "state")) / "writers_block"
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


def append(
    config: dict,
    date_str: str,
    theme: str,
    tag: str,
    attempts: list[dict],
    keep_days: int = _DEFAULT_KEEP_DAYS,
) -> None:
    """
    Append a writer's block record for one theme.

    Parameters
    ----------
    date_str : run date, e.g. "2026-05-18"
    theme    : human-readable theme name
    tag      : CamelCase hashtag key
    attempts : list of {"text": str, "counts": list[int]} — one per retry
    """
    path = _day_file(config, date_str)
    entries = _read(path, [])
    entries.append({
        "theme":     theme,
        "tag":       tag,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "attempts":  attempts,
    })
    path.write_text(json.dumps(entries, indent=2, ensure_ascii=False), encoding="utf-8")
    _cleanup_old(config, keep_days)


def load_day(config: dict, date_str: str) -> list[dict]:
    """Return all writer's block records for a given date."""
    return _read(_day_file(config, date_str), [])


def load_recent(config: dict, days: int = _DEFAULT_KEEP_DAYS) -> list[dict]:
    """Return all records from the last `days` days, oldest first."""
    cutoff = date.today() - timedelta(days=days)
    records: list[dict] = []
    for p in sorted(_store_dir(config).glob("????-??-??.json"), key=lambda x: x.stem):
        try:
            if date.fromisoformat(p.stem) >= cutoff:
                records.extend(_read(p, []))
        except ValueError:
            pass
    return records
