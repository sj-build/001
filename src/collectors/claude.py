"""Claude.ai conversation collector using Playwright."""
import logging
from src.collectors.base import BaseCollector
from src.ingest.normalize import RawConversation

logger = logging.getLogger("sj_home_agent.collectors.claude")

# Selector fallback list (try sequentially)
SELECTORS = [
    'a[href*="/chat/"]',
    'div[data-testid="conversation-list"] a',
    'nav a[href*="/chat/"]',
    'a[class*="conversation"]',
]

RECENTS_URL = "https://claude.ai/recents"

# Wait config — Claude is an SPA, never use networkidle
LOAD_WAIT_MS = 5000
MAX_LOGIN_WAIT_MS = 30000


class ClaudeCollector(BaseCollector):
    platform = "claude"

    def get_url(self) -> str:
        return RECENTS_URL

    async def check_login(self, page) -> bool:
        """Check if logged into Claude.

        Strategy: wait for DOM content, then poll for conversation links
        or check for login redirect. Avoids networkidle (SPA never settles).
        """
        try:
            # Wait for initial DOM
            await page.wait_for_timeout(LOAD_WAIT_MS)

            current_url = page.url
            if "/login" in current_url or "/signin" in current_url:
                logger.warning("Redirected to login page - not logged in")
                return False

            # Poll for conversation elements (SPA may still be hydrating)
            for attempt in range(6):
                for selector in SELECTORS:
                    count = await page.locator(selector).count()
                    if count > 0:
                        logger.info("Login confirmed via selector %s (%d elements)", selector, count)
                        return True
                # Check body text as fallback
                try:
                    body_text = await page.inner_text("body", timeout=3000)
                    if len(body_text) > 200:
                        logger.info("Login confirmed via body text length (%d chars)", len(body_text))
                        return True
                except Exception:
                    pass
                logger.info("Login check attempt %d/6 - waiting for content...", attempt + 1)
                await page.wait_for_timeout(3000)

            # Final URL check after all waits
            current_url = page.url
            if "claude.ai" in current_url and "/login" not in current_url:
                logger.info("Login assumed OK (on claude.ai, no login redirect)")
                return True

            return False
        except Exception as e:
            logger.error("Login check failed: %s", e)
            return False

    async def get_conversation_list(self, page) -> list[RawConversation]:
        """Scrape conversation list from Claude recents page."""
        conversations: list[RawConversation] = []

        # Wait for SPA content to render (don't use networkidle)
        await page.wait_for_timeout(3000)

        found_selector = None
        for selector in SELECTORS:
            try:
                count = await page.locator(selector).count()
                if count > 0:
                    found_selector = selector
                    logger.info("Using selector: %s (found %d elements)", selector, count)
                    break
            except Exception:
                continue

        if found_selector is None:
            # Try scrolling to trigger lazy-loaded content
            logger.info("No elements found; attempting scroll to trigger lazy load")
            try:
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await page.wait_for_timeout(2000)
                for selector in SELECTORS:
                    count = await page.locator(selector).count()
                    if count > 0:
                        found_selector = selector
                        logger.info("After scroll, using selector: %s (%d elements)", selector, count)
                        break
            except Exception:
                pass

        if found_selector is None:
            logger.warning("No conversation elements found with any selector")
            return conversations

        elements = await page.locator(found_selector).all()
        for el in elements:
            try:
                href = await el.get_attribute("href")
                if not href or "/chat/" not in href:
                    continue

                title_text = await el.inner_text()
                title = title_text.strip() if title_text else "Untitled"

                url = href if href.startswith("http") else f"https://claude.ai{href}"

                # Try to get a preview snippet from parent or sibling
                preview = None
                try:
                    parent = el.locator("..")
                    parent_text = await parent.inner_text()
                    if parent_text and len(parent_text) > len(title) + 5:
                        preview = parent_text.replace(title, "").strip()[:200]
                except Exception:
                    pass

                conversations.append(RawConversation(
                    platform="claude",
                    title=title,
                    url=url,
                    preview=preview,
                ))
            except Exception as e:
                logger.error("Error extracting conversation element: %s", e)
                continue

        logger.info("Collected %d conversations from Claude", len(conversations))
        return conversations
