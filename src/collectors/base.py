"""Base collector interface."""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

from src.ingest.normalize import RawConversation


class BaseCollector(ABC):
    """Abstract base for all platform collectors."""

    platform: str

    @abstractmethod
    async def check_login(self, page) -> bool:
        """Check if user is logged in on the platform page."""
        ...

    @abstractmethod
    async def get_conversation_list(self, page) -> list[RawConversation]:
        """Scrape conversation list from the platform."""
        ...

    def get_url(self) -> str:
        """Return the platform URL to navigate to."""
        raise NotImplementedError
