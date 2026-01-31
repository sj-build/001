"""Gemini conversation collector."""
import logging
from src.collectors.base import BaseCollector
from src.ingest.normalize import RawConversation

logger = logging.getLogger("sj_home_agent.collectors.gemini")

SELECTORS = [
    'a[href*="/app/"]',
    'div[role="listitem"] a',
    'mat-list-item a',
]

LOAD_WAIT_MS = 5000


class GeminiCollector(BaseCollector):
    platform = "gemini"

    def get_url(self) -> str:
        return "https://gemini.google.com/app"

    async def check_login(self, page) -> bool:
        """Check login via polling instead of networkidle."""
        try:
            await page.wait_for_timeout(LOAD_WAIT_MS)

            if "/signin" in page.url or "accounts.google" in page.url:
                return False

            found = await self._wait_for_content(page, SELECTORS)
            if found:
                return True

            # Gemini may load without sidebar visible
            current_url = page.url
            if "gemini.google.com" in current_url and "/signin" not in current_url:
                logger.info("Login assumed OK (on gemini.google.com, no redirect)")
                return True

            return False
        except Exception as e:
            logger.error("Login check failed: %s", e)
            return False

    async def get_conversation_list(self, page) -> list[RawConversation]:
        """Scrape conversation list from Gemini."""
        conversations: list[RawConversation] = []

        await page.wait_for_timeout(LOAD_WAIT_MS)

        # Try to open sidebar if needed
        try:
            sidebar_btn = page.locator('button[aria-label*="menu"], button[aria-label*="Menu"]')
            if await sidebar_btn.count() > 0:
                await sidebar_btn.first.click()
                await page.wait_for_timeout(1000)
        except Exception:
            pass

        found_selector = await self._find_working_selector(page, SELECTORS)

        if not found_selector:
            # Scroll once and retry
            logger.info("No elements found; scrolling to trigger lazy load")
            try:
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await page.wait_for_timeout(2000)
                found_selector = await self._find_working_selector(page, SELECTORS)
            except Exception:
                pass

        if not found_selector:
            logger.warning("No Gemini conversation elements found")
            return conversations

        # Scroll to load all lazy content
        await self._scroll_to_load_all(page, found_selector)

        elements = await page.locator(found_selector).all()
        for el in elements:
            try:
                href = await el.get_attribute("href")
                if not href:
                    continue

                title_text = await el.inner_text()
                title = title_text.strip() if title_text else "Untitled"
                url = href if href.startswith("http") else f"https://gemini.google.com{href}"

                # Extract preview and date from parent
                preview = None
                conv_date = None
                try:
                    parent = el.locator("..")
                    parent_text = await parent.inner_text()
                    if parent_text and len(parent_text) > len(title) + 5:
                        extra_text = parent_text.replace(title, "").strip()
                        preview = extra_text[:200] if extra_text else None
                        conv_date = self._extract_date_from_text(extra_text)
                except Exception:
                    pass

                conversations.append(RawConversation(
                    platform="gemini",
                    title=title,
                    url=url,
                    date=conv_date,
                    preview=preview,
                ))
            except Exception as e:
                logger.error("Error extracting Gemini element: %s", e)
        logger.info("Collected %d conversations from Gemini", len(conversations))
        return conversations
