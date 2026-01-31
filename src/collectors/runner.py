"""Collector runner: orchestrates browser-based collection across platforms."""
import asyncio
import logging
import shutil
import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path

from src.app.config import get_settings
from src.collectors.base import BaseCollector
from src.collectors.claude import ClaudeCollector
from src.collectors.chatgpt import ChatGPTCollector
from src.collectors.gemini import GeminiCollector
from src.collectors.granola import GranolaCollector
from src.collectors.fyxer import FyxerCollector
from src.ingest.normalize import normalize_conversation, RawConversation
from src.ingest.dedupe import make_conversation_id, make_content_hash
from src.ingest.obsidian_writer import write_daily_collection
from src.tagging.classifier import classify
from src.search import vector as vector_mod
from src.storage.dao import ConversationDAO, Conversation
from src.storage.db import init_db

logger = logging.getLogger("sj_home_agent.collectors.runner")

COLLECTORS: dict[str, type[BaseCollector]] = {
    "claude": ClaudeCollector,
    "chatgpt": ChatGPTCollector,
    "gemini": GeminiCollector,
    "granola": GranolaCollector,
    "fyxer": FyxerCollector,
}


def _is_chrome_running() -> bool:
    """Check if Chrome is currently running."""
    import subprocess
    try:
        result = subprocess.run(
            ["pgrep", "-x", "Google Chrome"],
            capture_output=True, text=True,
        )
        return result.returncode == 0
    except Exception:
        return False


def _copy_chrome_profile(source: Path) -> Path:
    """Copy Chrome profile to a temp directory to avoid 'profile in use' errors.

    Copies only essential auth/cookie files to keep it fast and avoid lock conflicts.
    source = the 'Default' profile directory (e.g. .../Chrome/Default).
    Returns the parent temp dir (the user-data-dir level).
    """
    temp_dir = Path(tempfile.mkdtemp(prefix="sj_chrome_"))
    target = temp_dir / "Default"
    target.mkdir(parents=True, exist_ok=True)

    # Essential files for session persistence
    essential_files = [
        "Cookies",
        "Login Data",
        "Web Data",
        "Preferences",
        "Secure Preferences",
        "Local State",
    ]

    # Copy essential files from Default profile
    for fname in essential_files:
        src_file = source / fname
        if src_file.exists():
            try:
                shutil.copy2(str(src_file), str(target / fname))
            except Exception as e:
                logger.warning("Could not copy %s: %s", fname, e)

    # Copy Local State from parent (Chrome root dir)
    local_state = source.parent / "Local State"
    if local_state.exists():
        try:
            shutil.copy2(str(local_state), str(temp_dir / "Local State"))
        except Exception as e:
            logger.warning("Could not copy Local State: %s", e)

    logger.info("Copied Chrome profile essentials to %s", temp_dir)
    return temp_dir


async def _save_debug_info(page, platform: str) -> None:
    """Save screenshot and HTML on failure."""
    settings = get_settings()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    try:
        screenshot_path = settings.screenshot_dir / f"{platform}_{timestamp}.png"
        settings.screenshot_dir.mkdir(parents=True, exist_ok=True)
        await page.screenshot(path=str(screenshot_path), timeout=10000)
        logger.info("Debug screenshot saved: %s", screenshot_path)
    except Exception as e:
        logger.error("Failed to save screenshot: %s", e)

    try:
        html_path = settings.html_dump_dir / f"{platform}_{timestamp}.html"
        settings.html_dump_dir.mkdir(parents=True, exist_ok=True)
        content = await page.content()
        html_path.write_text(content[:50000], encoding="utf-8")
        logger.info("Debug HTML saved: %s", html_path)
    except Exception as e:
        logger.error("Failed to save HTML: %s", e)


def _filter_by_date(
    conversations: list[RawConversation],
    days: int,
) -> list[RawConversation]:
    """Filter conversations to only include those within the date range.

    Conservative: items without dates are kept (not filtered out).
    """
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    result = []
    for conv in conversations:
        if conv.date is None:
            # No date info — keep it (conservative)
            result.append(conv)
        elif conv.date >= cutoff:
            result.append(conv)
        else:
            logger.info("Filtered out (too old): %s [%s]", conv.title, conv.date)
    return result


async def run_collector(
    platform: str,
    headless: bool = False,
    days: int = 30,
) -> list[RawConversation]:
    """Run a single platform collector."""
    from playwright.async_api import async_playwright

    if platform not in COLLECTORS:
        logger.error("Unknown platform: %s", platform)
        return []

    settings = get_settings()
    collector = COLLECTORS[platform]()

    # Chrome's default data dir cannot be used with Playwright's remote debugging.
    # We always copy the profile to a temp dir. This works when Chrome is closed
    # (cookies/session files are unlocked). When Chrome is running, the profile
    # is locked and cookies are Keychain-encrypted, so it won't work.
    chrome_running = _is_chrome_running()
    if chrome_running:
        logger.warning(
            "Chrome is running. Profile is locked and cookies are "
            "Keychain-encrypted. Please close Chrome and retry."
        )
        print("\n[!] Chrome is currently running.")
        print("    Please close Chrome (Cmd+Q), then rerun this command.\n")
        return []

    logger.info("Chrome is closed; copying profile for Playwright")
    profile_dir = _copy_chrome_profile(settings.chrome_profile)
    _cleanup_profile = True

    conversations: list[RawConversation] = []

    async with async_playwright() as pw:
        try:
            context = await pw.chromium.launch_persistent_context(
                user_data_dir=str(profile_dir),
                headless=headless,
                channel="chrome",
                args=["--disable-blink-features=AutomationControlled"],
            )
            page = context.pages[0] if context.pages else await context.new_page()
            await page.goto(collector.get_url(), wait_until="domcontentloaded", timeout=30000)

            logged_in = await collector.check_login(page)
            if not logged_in:
                logger.error("Not logged in to %s", platform)
                await _save_debug_info(page, platform)
                await context.close()
                return []

            raw_list = await collector.get_conversation_list(page)

            if not raw_list:
                logger.warning("0 conversations found for %s", platform)
                await _save_debug_info(page, platform)
            else:
                conversations = [normalize_conversation(r) for r in raw_list]
                # Apply date filter
                before_count = len(conversations)
                conversations = _filter_by_date(conversations, days)
                logger.info(
                    "Date filter (last %d days): %d → %d conversations",
                    days, before_count, len(conversations),
                )

            await context.close()
        except Exception as e:
            logger.error("Collector error for %s: %s", platform, e)
            try:
                await _save_debug_info(page, platform)
            except Exception:
                pass

    # Clean up temp profile
    if _cleanup_profile:
        try:
            shutil.rmtree(str(profile_dir), ignore_errors=True)
        except Exception:
            pass

    return conversations


def _persist_conversations(
    platform: str,
    conversations: list[RawConversation],
) -> int:
    """Classify, dedupe, write Obsidian file, and insert into DB."""
    dao = ConversationDAO()
    now = datetime.now().isoformat()
    settings = get_settings()

    classified: list[tuple[RawConversation, str, list[str]]] = []
    for conv in conversations:
        category, tags = classify(conv.title, conv.preview or "")
        classified.append((conv, category, tags))

    # Write Obsidian markdown
    if classified:
        obsidian_path = write_daily_collection(platform, classified)
        logger.info("Wrote Obsidian file: %s", obsidian_path)
    else:
        obsidian_path = Path("")

    # Insert into DB
    inserted = 0
    for conv, category, tags in classified:
        cid = make_conversation_id(conv.platform, conv.url)
        content_hash = make_content_hash(conv.title, conv.preview or "")

        db_conv = Conversation(
            id=cid,
            platform=conv.platform,
            title=conv.title,
            url=conv.url,
            created_at=conv.date,
            collected_at=now,
            category=category,
            tags=",".join(tags),
            preview=conv.preview,
            obsidian_path=str(obsidian_path),
            content_hash=content_hash,
        )
        dao.upsert(db_conv)

        # Vector index: title + tags + preview
        tag_text = " ".join(tags)
        index_text = f"{conv.title} {tag_text} {conv.preview or ''}".strip()
        vector_mod.index(
            doc_id=cid,
            text=index_text,
            metadata={"platform": conv.platform, "category": category},
        )

        inserted += 1

    logger.info("Persisted %d conversations for %s", inserted, platform)
    return inserted


async def run_all(
    platforms: list[str] | None = None,
    headless: bool = False,
    days: int = 30,
) -> dict[str, int]:
    """Run collectors for specified platforms (or all)."""
    init_db()

    target_platforms = platforms or list(COLLECTORS.keys())
    results: dict[str, int] = {}

    for platform in target_platforms:
        logger.info("--- Collecting from %s ---", platform)
        try:
            conversations = await run_collector(platform, headless=headless, days=days)
            count = _persist_conversations(platform, conversations)
            results[platform] = count
        except Exception as e:
            logger.error("Failed to collect from %s: %s", platform, e)
            results[platform] = 0

    return results
