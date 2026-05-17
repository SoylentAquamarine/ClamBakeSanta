#!/usr/bin/env python3
"""
Standalone haiku syllable validator.

Usage:
  python scripts/validate_haiku.py              # validate state/haiku_cache.json
  python scripts/validate_haiku.py --test       # run built-in test cases
  python scripts/validate_haiku.py --help       # show this help

Exit codes: 0 = all valid, 1 = validation failed.
"""
from __future__ import annotations
import json
import pathlib
import sys

# Allow running from repo root or from scripts/
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from framework.haiku_validator import (
    validate_haiku,
    count_line_syllables,
    TEST_CASES,
)


def run_tests() -> bool:
    print("Running built-in syllable test cases...")
    passed = 0
    for line, expected in TEST_CASES:
        actual = count_line_syllables(line)
        status = "PASS" if actual == expected else "FAIL"
        print(f"  [{status}] '{line}' → {actual} syllables (expected {expected})")
        if actual == expected:
            passed += 1
    total = len(TEST_CASES)
    print(f"\n{passed}/{total} tests passed.")
    return passed == total


def validate_cache(cache_path: pathlib.Path) -> bool:
    if not cache_path.exists():
        print(f"ERROR: Cache file not found: {cache_path}", file=sys.stderr)
        return False

    try:
        data = json.loads(cache_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        print(f"ERROR: Could not read {cache_path}: {exc}", file=sys.stderr)
        return False

    haikus = data.get("haikus", [])
    if not haikus:
        print(f"WARNING: No haikus found in {cache_path}")
        return True

    date = data.get("date", "unknown")
    print(f"Validating {len(haikus)} haiku(s) for {date} ({cache_path})...")
    all_valid = True

    for rec in haikus:
        theme = rec.get("theme", "(unknown)")
        haiku_text = rec.get("haiku", "")
        valid, counts = validate_haiku(haiku_text)
        got = "-".join(str(c) for c in counts) if counts else "unknown"

        if valid:
            print(f"  [PASS] {theme!r} → {got}")
        else:
            print(f"  [FAIL] {theme!r} → expected 5-7-5, got {got}")
            all_valid = False

    return all_valid


def main() -> None:
    args = sys.argv[1:]

    if "--help" in args or "-h" in args:
        print(__doc__)
        sys.exit(0)

    if "--test" in args:
        ok = run_tests()
        sys.exit(0 if ok else 1)

    cache_path = pathlib.Path("state/haiku_cache.json")
    ok = validate_cache(cache_path)

    if ok:
        print("\nValidation PASSED — all haikus are 5-7-5.")
        sys.exit(0)
    else:
        print("\nValidation FAILED — syllable counts do not match 5-7-5.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
