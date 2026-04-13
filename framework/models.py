"""
Shared data models.

Event  — standardized object produced by any Source plugin.
Result — standardized object produced by any Engine plugin.

These two contracts are the only interfaces between layers.
No layer imports from another layer directly — only through these models.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class Event:
    """
    A source-agnostic event. Every Source must produce one of these.

    Fields
    ------
    source_id   : which source plugin produced this (e.g. "daily_holidays")
    timestamp   : when the event was produced (timezone-aware)
    date_str    : YYYY-MM-DD string for the run date
    mm_dd       : MM-DD string used by data file lookups
    payload     : arbitrary source-specific data (e.g. {"themes": [...]})
    """
    source_id: str
    timestamp: datetime
    date_str: str
    mm_dd: str
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class Result:
    """
    An engine-agnostic result. Every Engine must return one of these.

    Fields
    ------
    event       : the Event that triggered this run (full context preserved)
    engine_id   : which engine plugin produced this (e.g. "clambakesanta")
    content     : human-readable summary string (adapters can use this directly)
    metadata    : arbitrary engine-specific data (e.g. {"haikus": [...], "themes": [...]})
    """
    event: Event
    engine_id: str
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)
