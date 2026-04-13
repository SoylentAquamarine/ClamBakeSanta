"""Base class for all Source plugins."""
from __future__ import annotations
from abc import ABC, abstractmethod
from ..models import Event


class BaseSource(ABC):
    """
    A Source produces Events. It knows nothing about engines or adapters.

    Every Source plugin must:
      1. Inherit from BaseSource
      2. Implement produce() returning a valid Event
      3. Register itself: @register("sources", "my_source_name")

    The config dict is the parsed contents of config.yml, passed in full
    so sources can read any setting they need.
    """

    def __init__(self, config: dict):
        self.config = config

    @abstractmethod
    def produce(self) -> Event:
        """Generate and return a standardized Event object."""
        ...
