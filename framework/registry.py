"""
Plugin registry.

Plugins register themselves via @register() decorators when their modules are imported.
The runner imports all plugin modules at startup, causing decorators to fire.

Usage
-----
  # In a plugin file:
  from framework.registry import register
  from framework.engines.base import BaseEngine

  @register("engines", "my_engine")
  class MyEngine(BaseEngine):
      ...

  # In runner.py:
  EngineClass = get_plugin("engines", "my_engine")
  engine = EngineClass(config)
"""
from __future__ import annotations

_registry: dict[str, dict[str, type]] = {
    "sources": {},
    "engines": {},
    "adapters": {},
}

VALID_KINDS = set(_registry.keys())


def register(kind: str, name: str):
    """
    Class decorator. Registers a plugin under (kind, name).

    Parameters
    ----------
    kind : "sources" | "engines" | "adapters"
    name : unique identifier string (used in config.yml)
    """
    def decorator(cls: type) -> type:
        if kind not in VALID_KINDS:
            raise ValueError(
                f"Unknown plugin kind '{kind}'. Must be one of: {sorted(VALID_KINDS)}"
            )
        _registry[kind][name] = cls
        return cls
    return decorator


def get_plugin(kind: str, name: str) -> type:
    """Retrieve a registered plugin class. Raises ValueError if not found."""
    try:
        return _registry[kind][name]
    except KeyError:
        available = sorted(_registry.get(kind, {}).keys())
        raise ValueError(
            f"Plugin '{name}' not registered under '{kind}'. "
            f"Available: {available or ['(none loaded yet)']}"
        )


def list_plugins(kind: str) -> list[str]:
    """Return names of all registered plugins of a given kind."""
    return sorted(_registry.get(kind, {}).keys())
