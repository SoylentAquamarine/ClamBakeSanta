#!/usr/bin/env python3
"""
generate_monthly_data.py

Generates two data files for a target month:
  data/ephemeral/YYYY-MM.txt  — variable-date holidays from ephemeral_rules.txt
  data/celestial/YYYY-MM.txt  — moon phases, meteor showers, zodiac ingress,
                                 equinoxes/solstices (calculated via ephem)

Usage:
  python scripts/generate_monthly_data.py              # generates next month
  python scripts/generate_monthly_data.py --month 2026-08   # specific month
  python scripts/generate_monthly_data.py --bootstrap  # current + next month
"""
from __future__ import annotations

import argparse
import calendar
import math
import pathlib
import re
import sys
from datetime import date, timedelta

# ── Ephem ─────────────────────────────────────────────────────────────────────

try:
    import ephem
except ImportError:
    print("ERROR: ephem not installed — run: pip install ephem", file=sys.stderr)
    sys.exit(1)

# ── Constants ─────────────────────────────────────────────────────────────────

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent

WEEKDAY_MAP = {
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
    "friday": 4, "saturday": 5, "sunday": 6,
}
ORDINAL_MAP = {
    "1st": 1, "first": 1,
    "2nd": 2, "second": 2,
    "3rd": 3, "third": 3,
    "4th": 4, "fourth": 4,
    "5th": 5, "fifth": 5,
    "last": -1,
}
MONTH_MAP = {
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
}
ZODIAC_SIGNS = [
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
]

# Major annual meteor showers: (peak_month, peak_day, display_name)
# Dates accurate to ±2 days across decades.
METEOR_SHOWERS = [
    (1,  3,  "Quadrantid Meteor Shower"),
    (4,  22, "Lyrid Meteor Shower"),
    (5,  6,  "Eta Aquariid Meteor Shower"),
    (8,  12, "Perseid Meteor Shower"),
    (10, 21, "Orionid Meteor Shower"),
    (11, 17, "Leonid Meteor Shower"),
    (12, 14, "Geminid Meteor Shower"),
    (12, 22, "Ursid Meteor Shower"),
]


# ── Ephemeral holiday helpers ─────────────────────────────────────────────────

def _parse_rule(rule_str: str) -> tuple[int, int, int] | None:
    """
    Parse '4th Thursday of November' → (ordinal, weekday_index, month_number).
    Returns None on parse failure.
    """
    m = re.match(r"(\w+)\s+(\w+)\s+of\s+(\w+)", rule_str.strip(), re.IGNORECASE)
    if not m:
        return None
    ordinal = ORDINAL_MAP.get(m.group(1).lower())
    weekday = WEEKDAY_MAP.get(m.group(2).lower())
    month   = MONTH_MAP.get(m.group(3).lower())
    if ordinal is None or weekday is None or month is None:
        return None
    return ordinal, weekday, month


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date | None:
    """
    Return the date of the nth occurrence of weekday (0=Mon…6=Sun) in year/month.
    n=-1 returns the last occurrence.
    """
    cal  = calendar.monthcalendar(year, month)
    days = [week[weekday] for week in cal if week[weekday] != 0]
    if not days:
        return None
    idx = -1 if n == -1 else n - 1
    if idx >= len(days) or idx < -len(days):
        return None
    return date(year, month, days[idx])


def generate_ephemeral(year: int, month: int) -> list[tuple[date, str]]:
    """
    Read ephemeral_rules.txt and return (date, name) pairs that fall in year/month.
    """
    rules_path = REPO_ROOT / "data" / "ephemeral_rules.txt"
    if not rules_path.exists():
        print(f"  WARNING: {rules_path} not found — skipping ephemeral holidays")
        return []

    results: list[tuple[date, str]] = []
    for raw in rules_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            continue
        rule_part, _, name = line.partition(":")
        parsed = _parse_rule(rule_part.strip())
        if parsed is None:
            print(f"  WARNING: could not parse rule: {line!r}")
            continue
        ordinal, weekday, rule_month = parsed
        if rule_month != month:
            continue
        d = _nth_weekday(year, month, weekday, ordinal)
        if d:
            results.append((d, name.strip()))

    return sorted(results)


# ── Celestial helpers ─────────────────────────────────────────────────────────

def _ephem_to_date(ephem_date) -> date:
    return ephem.Date(ephem_date).datetime().date()


def _zodiac_sign(ephem_date) -> str:
    sun = ephem.Sun(ephem_date)
    # Convert to ecliptic coordinates to get the Sun's apparent ecliptic longitude.
    # ephem.Ecliptic gives the geocentric ecliptic lon/lat directly.
    ecl = ephem.Ecliptic(sun, epoch=ephem_date)
    lon = math.degrees(ecl.lon) % 360
    return ZODIAC_SIGNS[int(lon / 30)]


def generate_celestial(year: int, month: int) -> list[tuple[date, str]]:
    """
    Return (date, name) pairs for celestial events in year/month:
      - Moon phases (New, First Quarter, Full, Last Quarter)
      - Zodiac sign ingress
      - Meteor shower peaks
      - Equinoxes and solstices
    """
    _, days_in_month = calendar.monthrange(year, month)
    month_start = date(year, month, 1)
    month_end   = date(year, month, days_in_month)

    results: list[tuple[date, str]] = []

    # ── Moon phases ───────────────────────────────────────────────────────────
    phase_funcs = [
        (ephem.next_new_moon,            "New Moon"),
        (ephem.next_first_quarter_moon,  "First Quarter Moon"),
        (ephem.next_full_moon,           "Full Moon"),
        (ephem.next_last_quarter_moon,   "Last Quarter Moon"),
    ]
    # Search from two weeks before month start to catch phases right at the edge
    for phase_func, name in phase_funcs:
        search = ephem.Date(f"{year}/{month}/1") - 14
        for _ in range(4):  # at most ~4 occurrences of any phase per month
            next_d = phase_func(search)
            d = _ephem_to_date(next_d)
            if d > month_end:
                break
            if month_start <= d <= month_end:
                results.append((d, name))
            search = next_d + 1

    # ── Zodiac ingress ────────────────────────────────────────────────────────
    prev_sign = _zodiac_sign(ephem.Date(f"{year}/{month}/1") - 1)
    for day in range(1, days_in_month + 1):
        sign = _zodiac_sign(ephem.Date(f"{year}/{month}/{day}"))
        if sign != prev_sign:
            results.append((date(year, month, day), f"Welcome to {sign} Season"))
        prev_sign = sign

    # ── Meteor showers ────────────────────────────────────────────────────────
    for shower_month, shower_day, name in METEOR_SHOWERS:
        if shower_month == month:
            results.append((date(year, month, shower_day), name))

    # ── Equinoxes and solstices ───────────────────────────────────────────────
    season_funcs = [
        (ephem.next_vernal_equinox,   "Spring Equinox"),
        (ephem.next_summer_solstice,  "Summer Solstice"),
        (ephem.next_autumnal_equinox, "Autumn Equinox"),
        (ephem.next_winter_solstice,  "Winter Solstice"),
    ]
    search_start = ephem.Date(f"{year}/{month}/1") - 100
    for season_func, name in season_funcs:
        d = _ephem_to_date(season_func(search_start))
        if month_start <= d <= month_end:
            results.append((d, name))

    return sorted(results)


# ── File writers ──────────────────────────────────────────────────────────────

def _write_file(path: pathlib.Path, header: str, entries: list[tuple[date, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"# {header}", ""]
    for d, name in entries:
        lines.append(f"{d.strftime('%m-%d')}: {name}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"  Wrote {path} ({len(entries)} entries)")


def generate_month(year: int, month: int, force: bool = False) -> None:
    tag = f"{year}-{month:02d}"
    generated_on = date.today().isoformat()

    ephemeral_path = REPO_ROOT / "data" / "ephemeral" / f"{tag}.txt"
    celestial_path = REPO_ROOT / "data" / "celestial" / f"{tag}.txt"

    print(f"\nGenerating data for {tag}:")

    if ephemeral_path.exists() and not force:
        print(f"  {ephemeral_path.name} already exists — skipping (use --force to overwrite)")
    else:
        entries = generate_ephemeral(year, month)
        _write_file(
            ephemeral_path,
            f"Ephemeral holidays for {tag} — auto-generated {generated_on}",
            entries,
        )

    if celestial_path.exists() and not force:
        print(f"  {celestial_path.name} already exists — skipping (use --force to overwrite)")
    else:
        entries = generate_celestial(year, month)
        _write_file(
            celestial_path,
            f"Celestial events for {tag} — auto-generated {generated_on}",
            entries,
        )


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Generate ephemeral and celestial data files")
    parser.add_argument(
        "--month", default=None,
        help="Target month as YYYY-MM (default: next month)",
    )
    parser.add_argument(
        "--bootstrap", action="store_true",
        help="Generate current month AND next month (for first deploy)",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Overwrite existing files",
    )
    args = parser.parse_args()

    today = date.today()

    if args.month:
        try:
            year, month = map(int, args.month.split("-"))
        except ValueError:
            print("ERROR: --month must be YYYY-MM", file=sys.stderr)
            sys.exit(1)
        generate_month(year, month, force=args.force)
    elif args.bootstrap:
        # Current month
        generate_month(today.year, today.month, force=args.force)
        # Next month
        next_month = (today.replace(day=1) + timedelta(days=32)).replace(day=1)
        generate_month(next_month.year, next_month.month, force=args.force)
    else:
        # Default: next month
        next_month = (today.replace(day=1) + timedelta(days=32)).replace(day=1)
        generate_month(next_month.year, next_month.month, force=args.force)


if __name__ == "__main__":
    main()
