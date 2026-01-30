"""ChatGPT conversation collector (stub)."""
import logging
from src.collectors.base import BaseCollector
from src.ingest.normalize import RawConversation

logger = logging.getLogger("sj_home_agent.collectors.chatgpt")

SELECTORS = [
    'a[href*="/c/"]',
    'nav a[href*="/c/"]',
    'a[href*="/chat/"]',
    'li a[data-testid]',
]

class ChatGPTCollector(BaseCollector):
    platform = "chatgpt"

    def get_url(self) -> str:
        return "https://chatgpt.com"

    async def check_login(self, page) -> bool:
        try:
            await page.wait_for_load_state("networkidle", timeout=10000)
            if "/auth" in page.url or "/login" in page.url:
                return False
            for selector in SELECTORS:
                if await page.locator(selector).count() > 0:
                    return True
            body = await page.inner_text("body")
            return len(body) > 100
        except Exception as e:
            logger.error("Login check failed: %s", e)
            return False

    async def get_conversation_list(self, page) -> list[RawConversation]:
        conversations: list[RawConversation] = []
        await page.wait_for_load_state("networkidle", timeout=15000)
        await page.wait_for_timeout(2000)

        found_selector = None
        for selector in SELECTORS:
            if await page.locator(selector).count() > 0:
                found_selector = selector
                break

        if not found_selector:
            logger.warning("No ChatGPT conversation elements found")
            return conversations

        elements = await page.locator(found_selector).all()
        for el in elements:
            try:
                href = await el.get_attribute("href")
                if not href or ("/c/" not in href and "/chat/" not in href):
                    continue
                title_text = await el.inner_text()
                title = title_text.strip() if title_text else "Untitled"
                url = href if href.startswith("http") else f"https://chatgpt.com{href}"
                conversations.append(RawConversation(
                    platform="chatgpt", title=title, url=url,
                ))
            except Exception as e:
                logger.error("Error extracting ChatGPT element: %s", e)
        logger.info("Collected %d conversations from ChatGPT", len(conversations))
        return conversations
