#!/usr/bin/env python3
"""
ClamBakeSanta — entry point.

Usage
-----
  # Normal daily run (skips if already ran today)
  python run.py

  # Force run even if already ran today (useful for testing)
  python run.py --force

  # Use a different config file
  python run.py --config my_config.yml

  # Run for a specific date (overrides system clock — for backfill/testing)
  python run.py --date 2025-12-25

The GitHub Actions workflow calls: python run.py
"""
from __future__ import annotations
import argparse
import logging
import sys
import yaml

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


def load_config(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def main() -> int:
    parser = argparse.ArgumentParser(description="ClamBakeSanta automation runner")
    parser.add_argument("--config", default="config.yml", help="Path to config file")
    parser.add_argument("--force", action="store_true", help="Run even if already ran today")
    parser.add_argument("--date", default=None, help="Override date (YYYY-MM-DD) for testing")
    parser.add_argument("--adapter", default=None, help="Test a single adapter only (skips all others)")
    args = parser.parse_args()

    config = load_config(args.config)

    # Optional date override for testing or backfill
    if args.date:
        config["_date_override"] = args.date
        log.info("Date override: %s", args.date)

    # Single-adapter test mode — override the adapters list in config
    if args.adapter:
        log.info("TEST MODE — running only adapter: %s", args.adapter)
        config["adapters"] = [args.adapter]

    from framework.runner import run
    summary = run(config, force=args.force)

    if summary.get("skipped"):
        log.info("Skipped — already ran for %s. Use --force to override.", summary["date"])
        return 0

    failed = summary.get("adapters_failed", [])
    ok = summary.get("adapters_ok", [])

    if failed:
        log.warning("Some adapters failed (content was still generated): %s", failed)

    log.info("Done — %s | OK: %s | Failed: %s", summary["date"], ok, [f[0] for f in failed])

    # Only fail the workflow if NO adapters succeeded at all
    if failed and not ok:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
