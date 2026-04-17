"""
Schema validation for Event and Result objects.

Validation runs at every stage boundary inside the runner:
  Source  → validate_event()   → Engine
  Engine  → validate_result()  → Adapters
  Result  → validate_result()  → (guard before each adapter)

Design principles:
  - Fail loudly at the boundary, not silently downstream
  - Collect ALL errors before raising (one exception = complete picture)
  - Engine plugins can register a custom metadata validator for deeper checks
  - All validators are pure functions — no side effects, no logging

Custom metadata validation
--------------------------
Engines that produce a structured metadata dict can register a validator:

    from framework.validation import register_metadata_validator

    @register_metadata_validator("clambakesanta")
    def _validate(metadata: dict) -> list[str]:
        errors = []
        ...
        return errors

The runner calls any registered validator automatically after the engine runs.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Callable

from .models import Event, Result

# ── Exception ─────────────────────────────────────────────────────────────────

class ValidationError(ValueError):
    """Raised when an Event or Result fails schema validation."""
    pass


# ── Patterns ──────────────────────────────────────────────────────────────────

_DATE_RE  = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_MM_DD_RE = re.compile(r"^\d{2}-\d{2}$")


# ── Metadata validator registry ───────────────────────────────────────────────

_metadata_validators: dict[str, Callable[[dict], list[str]]] = {}


def register_metadata_validator(engine_id: str):
    """
    Decorator — registers a metadata validator for a specific engine.

    The decorated function receives `metadata: dict` and returns a list of
    error strings (empty list = valid).

    Usage:
        @register_metadata_validator("my_engine")
        def _validate(metadata: dict) -> list[str]:
            errors = []
            if "required_key" not in metadata:
                errors.append("missing required_key")
            return errors
    """
    def decorator(fn: Callable[[dict], list[str]]):
        _metadata_validators[engine_id] = fn
        return fn
    return decorator


# ── Core validators ───────────────────────────────────────────────────────────

def validate_event(event: Event) -> None:
    """
    Validate a Source-produced Event against the framework contract.
    Raises ValidationError with all problems listed if invalid.
    """
    errors: list[str] = []

    if not isinstance(getattr(event, "source_id", None), str) or not event.source_id:
        errors.append("source_id must be a non-empty string")

    if not isinstance(getattr(event, "timestamp", None), datetime):
        errors.append("timestamp must be a datetime instance")

    date_str = getattr(event, "date_str", None)
    if not date_str or not _DATE_RE.match(str(date_str)):
        errors.append(f"date_str must match YYYY-MM-DD, got {date_str!r}")

    mm_dd = getattr(event, "mm_dd", None)
    if not mm_dd or not _MM_DD_RE.match(str(mm_dd)):
        errors.append(f"mm_dd must match MM-DD, got {mm_dd!r}")

    if not isinstance(getattr(event, "payload", None), dict):
        errors.append("payload must be a dict")

    if errors:
        raise ValidationError(
            f"Source '{getattr(event, 'source_id', '?')}' produced an invalid Event — "
            + "; ".join(errors)
        )


def validate_result(result: Result) -> None:
    """
    Validate an Engine-produced Result against the framework contract.
    Also runs any registered engine-specific metadata validator.
    Raises ValidationError with all problems listed if invalid.
    """
    errors: list[str] = []

    if not isinstance(getattr(result, "event", None), Event):
        errors.append("event must be an Event instance")

    engine_id = getattr(result, "engine_id", None)
    if not isinstance(engine_id, str) or not engine_id:
        errors.append("engine_id must be a non-empty string")

    if not isinstance(getattr(result, "content", None), str):
        errors.append("content must be a string")

    metadata = getattr(result, "metadata", None)
    if not isinstance(metadata, dict):
        errors.append("metadata must be a dict")

    # Run engine-specific metadata validator if registered
    if not errors and isinstance(engine_id, str) and engine_id in _metadata_validators:
        extra = _metadata_validators[engine_id](result.metadata)
        errors.extend(extra)

    if errors:
        raise ValidationError(
            f"Engine '{engine_id or '?'}' produced an invalid Result — "
            + "; ".join(errors)
        )
