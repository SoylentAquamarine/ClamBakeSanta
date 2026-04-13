"""
daily_holidays — Source plugin for ClamBakeSanta.

Reads monthly data files from data/ and produces an Event containing
all holidays and birthdays for today's date.

Data file format (one file per month per type):
  data/january_randomholiday.txt
  data/january_celebritybirthday.txt

Each line:
  MM-DD: Theme One, Theme Two
  # lines starting with # are comments

To add a new holiday or birthday, edit the appropriate data file
directly in the GitHub web UI — no code change needed.
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


@register("sources", "daily_holidays")
class DailyHolidaysSource(BaseSource):
    """
    Produces an Event with today's themes pulled from the approved data files.

    The data files are your editorial control layer — only what you put
    in these files will ever become a haiku subject.
    """

    def produce(self) -> Event:
        tz = ZoneInfo(self.config.get("timezone", "America/New_York"))
        now = datetime.now(tz)
        date_str = now.strftime("%Y-%m-%d")
        mm_dd = now.strftime("%m-%d")
        month_name = MONTHS[now.month - 1]

        data_dir = pathlib.Path(self.config.get("data_dir", "data"))
        themes: list[str] = []

        for suffix in ("randomholiday", "celebritybirthday"):
            fpath = data_dir / f"{month_name}_{suffix}.txt"
            if not fpath.exists():
                continue
            for raw_line in fpath.read_text(encoding="utf-8").splitlines():
                line = raw_line.strip()
                if not line or line.startswith("#"):
                    continue
                m = re.match(r"^(\d{2}-\d{2}):\s*(.+)$", line)
                if m and m.group(1) == mm_dd:
                    for part in m.group(2).split(","):
                        t = part.strip()
                        if t:
                            themes.append(t)

        return Event(
            source_id="daily_holidays",
            timestamp=now,
            date_str=date_str,
            mm_dd=mm_dd,
            payload={"themes": themes, "month": month_name},
        )
