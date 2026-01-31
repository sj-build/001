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
            await page.wait_for_timeout(LOAD_WAIT_MS)

            current_url = page.url
            if "/login" in current_url or "/signin" in current_url:
                logger.warning("Redirected to login page - not logged in")
                return False

            # Poll for conversation elements using base helper
            found = await self._wait_for_content(page, SELECTORS)
            if found:
                return True

            # Check body text as fallback
            try:
                body_text = await page.inner_text("body", timeout=3000)
                if len(body_text) > 200:
                    logger.info("Login confirmed via body text length (%d chars)", len(body_text))
                    return True
            except Exception:
                pass

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

        # Find working selector using base helper
        found_selector = await self._find_working_selector(page, SELECTORS)

        if found_selector is None:
            # Try scrolling to trigger lazy-loaded content
            logger.info("No elements found; attempting scroll to trigger lazy load")
            try:
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await page.wait_for_timeout(2000)
                found_selector = await self._find_working_selector(page, SELECTORS)
            except Exception:
                pass

        if found_selector is None:
            logger.warning("No conversation elements found with any selector")
            return conversations

        # Scroll to load all lazy content
        await self._scroll_to_load_all(page, found_selector)

        elements = await page.locator(found_selector).all()
        for el in elements:
            try:
                href = await el.get_attribute("href")
                if not href or "/chat/" not in href:
                    continue

                title_text = await el.inner_text()
                title = title_text.strip() if title_text else "Untitled"

                url = href if href.startswith("http") else f"https://claude.ai{href}"

                # Try to get preview and date from parent element
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
                    platform="claude",
                    title=title,
                    url=url,
                    date=conv_date,
                    preview=preview,
                ))
            except Exception as e:
                logger.error("Error extracting conversation element: %s", e)
                continue

        logger.info("Collected %d conversations from Claude", len(conversations))
        return conversations
