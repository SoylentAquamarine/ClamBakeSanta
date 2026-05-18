"""
daily_themes — Combined source plugin for ClamBakeSanta.

Replaces daily_holidays.  Reads four data sources and applies
priority/cap logic to produce the final theme list for the day.

Priority order (fills up to max_haikus_per_day = 6):
  1. Fixed holidays        data/MONTH_randomholiday.txt
  2. Ephemeral holidays    data/ephemeral/YYYY-MM.txt   (auto-generated)
  3. Celebrity birthdays   data/MONTH_celebritybirthday.txt
  4. Celestial events      data/celestial/YYYY-MM.txt   (auto-generated)
     └─ celestial backfill only when total < max_haikus_per_day
        and capped at max_celestial_per_day = 4

If a generated file is missing for the current month the category is
skipped silently — the daily run never fails because of a missing file.
"""
from __future__ import annotations

import pathlib
import re
from datetime import datetime
from zoneinfo import ZoneInfo

from framework.registry import register
from framework.sources.base import BaseSource
from framework.models import Event

MONTHS = [
    "january", "february", "march", "april", "may", "june",
    "july", "august", "september", "october", "november", "december",
]


def _read_monthly_txt(path: pathlib.Path, mm_dd: str) -> list[str]:
    """
    Read a monthly text file (fixed or generated) and return themes for mm_dd.

    Fixed format:   MM-DD: Theme One, Theme Two
    Generated format: MM-DD: Theme Name   (one per line)
    Both formats are handled identically.
    """
    if not path.exists():
        return []
    themes: list[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        m = re.match(r"^(\d{2}-\d{2}):\s*(.+)$", line)
        if m and m.group(1) == mm_dd:
            for part in m.group(2).split(","):
                t = part.strip()
                if t:
                    themes.append(t)
    return themes


@register("sources", "daily_themes")
class DailyThemesSource(BaseSource):
    """
    Produces an Event with today's themes, applying priority and cap logic.

    Config keys (all optional, with defaults shown):
      max_haikus_per_day:   6   hard cap on total themes
      max_celestial_per_day: 4  celestial backfill cap (even on an empty day)
      data_dir:             data
      timezone:             America/New_York
    """

    def produce(self) -> Event:
        cfg          = self.config
        max_total    = cfg.get("max_haikus_per_day", 6)
        max_celestial = cfg.get("max_celestial_per_day", 4)

        tz       = ZoneInfo(cfg.get("timezone", "America/New_York"))
        now      = datetime.now(tz)
        date_str = now.strftime("%Y-%m-%d")
        mm_dd    = now.strftime("%m-%d")
        yyyy_mm  = now.strftime("%Y-%m")
        month_name = MONTHS[now.month - 1]

        data_dir = pathlib.Path(cfg.get("data_dir", "data"))
        themes: list[str] = []

        # ── 1. Fixed holidays ─────────────────────────────────────────────────
        fixed = _read_monthly_txt(
            data_dir / f"{month_name}_randomholiday.txt", mm_dd
        )
        themes.extend(fixed[: max_total - len(themes)])

        # ── 2. Ephemeral holidays ─────────────────────────────────────────────
        if len(themes) < max_total:
            ephemeral = _read_monthly_txt(
                data_dir / "ephemeral" / f"{yyyy_mm}.txt", mm_dd
            )
            themes.extend(ephemeral[: max_total - len(themes)])

        # ── 3. Celebrity birthdays ────────────────────────────────────────────
        if len(themes) < max_total:
            birthdays = _read_monthly_txt(
                data_dir / f"{month_name}_celebritybirthday.txt", mm_dd
            )
            themes.extend(birthdays[: max_total - len(themes)])

        # ── 4. Celestial backfill ─────────────────────────────────────────────
        if len(themes) < max_total:
            celestial_all = _read_monthly_txt(
                data_dir / "celestial" / f"{yyyy_mm}.txt", mm_dd
            )
            slots = min(max_total - len(themes), max_celestial)
            themes.extend(celestial_all[:slots])

        return Event(
            source_id="daily_themes",
            timestamp=now,
            date_str=date_str,
            mm_dd=mm_dd,
            payload={"themes": themes, "month": month_name},
        )
