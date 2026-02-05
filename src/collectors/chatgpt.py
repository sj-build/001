"""ChatGPT conversation collector."""
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

# Selectors for the collapsed "My chats" sidebar section
CHAT_SECTION_EXPAND_SELECTORS = [
    'button:has(h2.__menu-label)',
    'button[aria-expanded="false"]',
]

LOAD_WAIT_MS = 5000


class ChatGPTCollector(BaseCollector):
    platform = "chatgpt"

    def get_url(self) -> str:
        return "https://chatgpt.com"

    async def _expand_chat_sections(self, page) -> None:
        """Expand collapsed sidebar sections (e.g. 'My chats') to reveal conversation links."""
        try:
            buttons = await page.locator(
                'button[aria-expanded="false"]:has(h2.__menu-label)'
            ).all()
            for btn in buttons:
                try:
                    label = await btn.inner_text()
                    logger.info("Expanding sidebar section: %s", label.strip())
                    await btn.click()
                    await page.wait_for_timeout(1500)
                except Exception as e:
                    logger.warning("Failed to expand section: %s", e)
        except Exception as e:
            logger.warning("Could not find sidebar sections to expand: %s", e)

    async def check_login(self, page) -> bool:
        """Check login via polling instead of networkidle."""
        try:
            await page.wait_for_timeout(LOAD_WAIT_MS)

            if "/auth" in page.url or "/login" in page.url:
                return False

            # Check for profile button (present when logged in)
            try:
                profile = page.locator('[data-testid="accounts-profile-button"]')
                if await profile.count() > 0:
                    return True
            except Exception:
                pass

            found = await self._wait_for_content(page, SELECTORS)
            if found:
                return True

            # Fallback: check body text
            try:
                body = await page.inner_text("body", timeout=3000)
                if len(body) > 100:
                    return True
            except Exception:
                pass

            return False
        except Exception as e:
            logger.error("Login check failed: %s", e)
            return False

    async def get_conversation_list(self, page) -> list[RawConversation]:
        """Scrape conversation list from ChatGPT."""
        conversations: list[RawConversation] = []

        await page.wait_for_timeout(LOAD_WAIT_MS)

        # ChatGPT 2025+ UI: sidebar sections are collapsed by default.
        # Expand all sections (especially "My chats") to reveal conversation links.
        await self._expand_chat_sections(page)
        await page.wait_for_timeout(2000)

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
            logger.warning("No ChatGPT conversation elements found")
            return conversations

        # Scroll sidebar to load all lazy content
        try:
            sidebar_nav = page.locator('nav[aria-label]').first
            if await sidebar_nav.count() > 0:
                for _ in range(10):
                    before_count = await page.locator(found_selector).count()
                    await sidebar_nav.evaluate(
                        "el => el.scrollTo(0, el.scrollHeight)"
                    )
                    await page.wait_for_timeout(1500)
                    after_count = await page.locator(found_selector).count()
                    logger.info(
                        "Sidebar scroll: %d → %d elements", before_count, after_count
                    )
                    if after_count == before_count:
                        break
            else:
                await self._scroll_to_load_all(page, found_selector)
        except Exception:
            await self._scroll_to_load_all(page, found_selector)

        elements = await page.locator(found_selector).all()
        for el in elements:
            try:
                href = await el.get_attribute("href")
                if not href or ("/c/" not in href and "/chat/" not in href):
                    continue

                title_text = await el.inner_text()
                title = title_text.strip() if title_text else "Untitled"
                url = href if href.startswith("http") else f"https://chatgpt.com{href}"

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
                    platform="chatgpt",
                    title=title,
                    url=url,
                    date=conv_date,
                    preview=preview,
                ))
            except Exception as e:
                logger.error("Error extracting ChatGPT element: %s", e)
        logger.info("Collected %d conversations from ChatGPT", len(conversations))
        return conversations
