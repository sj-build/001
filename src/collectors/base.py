"""Base collector interface with shared SPA helpers."""
import logging
import re
from abc import ABC, abstractmethod
from datetime import date, datetime, timedelta
from typing import Optional

from src.ingest.normalize import RawConversation

logger = logging.getLogger("sj_home_agent.collectors.base")


class BaseCollector(ABC):
    """Abstract base for all platform collectors.

    Provides shared SPA helpers that all collectors can use to avoid
    networkidle waits and reliably scrape dynamic content.
    """

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

    # ── Shared SPA helpers ─────────────────────────────────────────

    async def _wait_for_content(
        self,
        page,
        selectors: list[str],
        max_attempts: int = 6,
        poll_interval: int = 2000,
    ) -> Optional[str]:
        """Poll for any selector match. Returns first matching selector or None.

        Replaces networkidle pattern for SPAs that never settle.
        """
        for attempt in range(max_attempts):
            for selector in selectors:
                try:
                    count = await page.locator(selector).count()
                    if count > 0:
                        logger.info(
                            "Content found via %s (%d elements, attempt %d)",
                            selector, count, attempt + 1,
                        )
                        return selector
                except Exception:
                    continue
            logger.info("Waiting for content, attempt %d/%d", attempt + 1, max_attempts)
            await page.wait_for_timeout(poll_interval)
        return None

    async def _scroll_to_load_all(
        self,
        page,
        selector: str,
        max_scrolls: int = 5,
        scroll_delay: int = 2000,
    ) -> int:
        """Scroll page to bottom to trigger lazy loading.

        Returns final element count. Stops when no new elements appear.
        """
        prev_count = await page.locator(selector).count()
        for scroll_num in range(max_scrolls):
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_timeout(scroll_delay)
            new_count = await page.locator(selector).count()
            if new_count == prev_count:
                logger.info("Scroll %d: no new elements (%d total)", scroll_num + 1, new_count)
                break
            logger.info("Scroll %d: %d → %d elements", scroll_num + 1, prev_count, new_count)
            prev_count = new_count
        return prev_count

    async def _find_working_selector(
        self,
        page,
        selectors: list[str],
    ) -> Optional[str]:
        """Try each selector, return first with count > 0."""
        for selector in selectors:
            try:
                count = await page.locator(selector).count()
                if count > 0:
                    logger.info("Working selector: %s (%d elements)", selector, count)
                    return selector
            except Exception:
                continue
        return None

    @staticmethod
    def _extract_date_from_text(text: str) -> Optional[str]:
        """Parse date strings commonly found in chat UIs.

        Handles: "Today", "Yesterday", "N days ago", ISO dates, MM/DD/YYYY.
        Returns ISO date string (YYYY-MM-DD) or None.
        """
        if not text:
            return None

        cleaned = text.strip().lower()
        today = date.today()

        if cleaned == "today":
            return today.isoformat()

        if cleaned == "yesterday":
            return (today - timedelta(days=1)).isoformat()

        # "N days ago", "N day ago"
        days_ago_match = re.search(r"(\d+)\s*days?\s*ago", cleaned)
        if days_ago_match:
            n = int(days_ago_match.group(1))
            return (today - timedelta(days=n)).isoformat()

        # "N weeks ago"
        weeks_ago_match = re.search(r"(\d+)\s*weeks?\s*ago", cleaned)
        if weeks_ago_match:
            n = int(weeks_ago_match.group(1))
            return (today - timedelta(weeks=n)).isoformat()

        # ISO date: 2025-01-15 or 2025-01-15T10:00:00
        iso_match = re.search(r"\d{4}-\d{2}-\d{2}", cleaned)
        if iso_match:
            return iso_match.group(0)

        # MM/DD/YYYY
        mdy_match = re.search(r"(\d{1,2})/(\d{1,2})/(\d{4})", cleaned)
        if mdy_match:
            try:
                m, d, y = int(mdy_match.group(1)), int(mdy_match.group(2)), int(mdy_match.group(3))
                return date(y, m, d).isoformat()
            except ValueError:
                return None

        return None
