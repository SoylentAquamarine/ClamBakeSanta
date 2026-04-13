"""Base class for all Adapter plugins."""
from __future__ import annotations
from abc import ABC, abstractmethod
from ..models import Result


class BaseAdapter(ABC):
    """
    An Adapter publishes a Result to an output channel. It contains
    formatting and delivery logic only — no business logic.

    Every Adapter plugin must:
      1. Inherit from BaseAdapter
      2. Implement publish(result) returning True on success, False if skipped
      3. Register itself: @register("adapters", "my_adapter_name")

    Adapters are independent. Adding a new channel (Telegram, Slack, etc.)
    requires zero changes to the framework or other adapters.
    """

    def __init__(self, config: dict):
        self.config = config

    @abstractmethod
    def publish(self, result: Result) -> bool:
        """
        Publish result to this adapter's channel.

        Returns
        -------
        True  — published successfully
        False — skipped (e.g. missing credentials, nothing to publish)
        """
        ...
