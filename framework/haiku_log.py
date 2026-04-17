"""
Persistent haiku log.

Every newly generated haiku is appended to state/haiku_log.json.
The log is the long-term memory of the system — used for:
  - Anti-repetition:  engine reads last 7 days before generating
  - Weekly reporting: report compiles scores over rolling 7-day window
  - Archive:          permanent record of every haiku ever posted

File format: JSON array, oldest entry first.
Each entry:
  {
    "date":      "2026-04-17",
    "theme":     "National Haiku Day",
    "haiku":     "line1\nline2\nline3\nhashtag line",
    "tag":       "NationalHaikuDay",
    "logged_at": "2026-04-17T05:01:23+00:00"
  }
"""
from __future__ import annotations

import json
import pathlib
from datetime import date, datetime, timedelta, timezone


# ── Internal helpers ──────────────────────────────────────────────────────────

def _log_path(config: dict) -> pathlib.Path:
    state_dir = pathlib.Path(config.get("state_dir", "state"))
    state_dir.mkdir(parents=True, exist_ok=True)
    return state_dir / "haiku_log.json"


def _parse_date(date_str: str) -> date:
    try:
        return date.fromisoformat(date_str)
    except (ValueError, TypeError):
        return date.min


# ── Public API ────────────────────────────────────────────────────────────────

def load_log(config: dict) -> list[dict]:
    """Return the full haiku log (oldest first)."""
    path = _log_path(config)
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def save_log(config: dict, records: list[dict]) -> None:
    """Overwrite the haiku log file."""
    _log_path(config).write_text(
        json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def append_haikus(config: dict, date_str: str, haiku_records: list[dict]) -> None:
    """
    Append today's freshly generated haikus to the log.
    If entries for today already exist (e.g. --regenerate), they are replaced.
    """
    log = load_log(config)
    # Drop any existing entries for this date (handles --regenerate)
    log = [e for e in log if e.get("date") != date_str]
    now = datetime.now(timezone.utc).isoformat()
    for rec in haiku_records:
        log.append({
            "date":      date_str,
            "theme":     rec.get("theme", ""),
            "haiku":     rec.get("haiku", ""),
            "tag":       rec.get("tag", ""),
            "logged_at": now,
        })
    save_log(config, log)


def recent_haikus(config: dict, days: int = 7) -> list[dict]:
    """
    Return all log entries from the last `days` days, excluding today.
    Used by the engine to build the anti-repetition context.
    """
    today = date.today()
    cutoff = today - timedelta(days=days)
    return [
        e for e in load_log(config)
        if cutoff <= _parse_date(e.get("date", "")) < today
    ]


def opening_phrases(config: dict, days: int = 7) -> list[str]:
    """
    Return the first line of each haiku from the last `days` days.
    Used to build the 'avoid these' list for the AI prompt.
    """
    phrases = []
    for entry in recent_haikus(config, days):
        lines = entry.get("haiku", "").split("\n")
        if lines and lines[0].strip():
            phrases.append(lines[0].strip().rstrip(","))
    return phrases


def entries_for_date(config: dict, date_str: str) -> list[dict]:
    """Return all log entries for a specific date."""
    return [e for e in load_log(config) if e.get("date") == date_str]
