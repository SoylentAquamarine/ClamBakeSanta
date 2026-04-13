"""Base class for all Engine plugins."""
from __future__ import annotations
from abc import ABC, abstractmethod
from ..models import Event, Result


class BaseEngine(ABC):
    """
    An Engine transforms an Event into a Result. It knows nothing about
    where the result goes (no Discord, no file writes, no FTP).

    Every Engine plugin must:
      1. Inherit from BaseEngine
      2. Implement process(event) returning a valid Result
      3. Register itself: @register("engines", "my_engine_name")

    Engines should be swappable. Replacing the haiku engine with a
    system monitoring summarizer requires zero changes to the framework.
    """

    def __init__(self, config: dict):
        self.config = config

    @abstractmethod
    def process(self, event: Event) -> Result:
        """Transform an Event into a Result. No side effects."""
        ...
