"""Gemini conversation collector (stub)."""
import logging
from src.collectors.base import BaseCollector
from src.ingest.normalize import RawConversation

logger = logging.getLogger("sj_home_agent.collectors.gemini")

SELECTORS = [
    'a[href*="/app/"]',
    'div[role="listitem"] a',
    'mat-list-item a',
]

class GeminiCollector(BaseCollector):
    platform = "gemini"

    def get_url(self) -> str:
        return "https://gemini.google.com/app"

    async def check_login(self, page) -> bool:
        try:
            await page.wait_for_load_state("networkidle", timeout=10000)
            if "/signin" in page.url or "accounts.google" in page.url:
                return False
            return True
        except Exception as e:
            logger.error("Login check failed: %s", e)
            return False

    async def get_conversation_list(self, page) -> list[RawConversation]:
        conversations: list[RawConversation] = []
        await page.wait_for_load_state("networkidle", timeout=15000)
        await page.wait_for_timeout(3000)

        # Try to open sidebar if needed
        try:
            sidebar_btn = page.locator('button[aria-label*="menu"], button[aria-label*="Menu"]')
            if await sidebar_btn.count() > 0:
                await sidebar_btn.first.click()
                await page.wait_for_timeout(1000)
        except Exception:
            pass

        found_selector = None
        for selector in SELECTORS:
            if await page.locator(selector).count() > 0:
                found_selector = selector
                break

        if not found_selector:
            logger.warning("No Gemini conversation elements found")
            return conversations

        elements = await page.locator(found_selector).all()
        for el in elements:
            try:
                href = await el.get_attribute("href")
                if not href:
                    continue
                title_text = await el.inner_text()
                title = title_text.strip() if title_text else "Untitled"
                url = href if href.startswith("http") else f"https://gemini.google.com{href}"
                conversations.append(RawConversation(
                    platform="gemini", title=title, url=url,
                ))
            except Exception as e:
                logger.error("Error extracting Gemini element: %s", e)
        logger.info("Collected %d conversations from Gemini", len(conversations))
        return conversations
