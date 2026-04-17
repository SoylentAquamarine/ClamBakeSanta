"""
Shared config loader for standalone scripts (check_engagement.py, weekly_report.py).

Reads config.yml from the current working directory and returns it as a dict.
Scripts that run inside GitHub Actions always execute from the repo root, so
the relative path "config.yml" resolves correctly without any special handling.

The runner (run.py) has its own loader that accepts a --config argument; this
version is for scripts that always use the default file.
"""
from __future__ import annotations

import pathlib

import yaml


def load_config(path: str = "config.yml") -> dict:
    """
    Parse config.yml and return it as a plain dict.
    Returns an empty dict if the file doesn't exist rather than crashing,
    so scripts can still run with sensible defaults when config is missing.
    """
    cfg_path = pathlib.Path(path)
    if not cfg_path.exists():
        return {}
    return yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
