"""Collector runner: orchestrates browser-based collection across platforms."""
import logging
import os
import shutil
import signal
import socket
import subprocess
import time
from datetime import date, datetime, timedelta
from pathlib import Path

from src.app.config import get_settings
from src.app.profiles import (
    get_cdp_data_dir,
    get_profile_for_platform,
    group_platforms_by_profile,
)
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
    try:
        result = subprocess.run(
            ["pgrep", "-x", "Google Chrome"],
            capture_output=True, text=True,
        )
        return result.returncode == 0
    except Exception:
        return False


def _is_cdp_available(port: int) -> bool:
    """Check if Chrome CDP is listening on the given port."""
    try:
        with socket.create_connection(("localhost", port), timeout=2):
            return True
    except (ConnectionRefusedError, OSError):
        return False


def _close_chrome(cdp_port: int | None = None) -> None:
    """Gracefully shut down Chrome (SIGTERM, then SIGKILL if needed).

    Waits up to 5 seconds for graceful exit before force-killing.
    Optionally waits for the CDP port to be freed.
    """
    try:
        result = subprocess.run(
            ["pgrep", "-x", "Google Chrome"],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            return

        pids = [p.strip() for p in result.stdout.strip().split("\n") if p.strip()]
        for pid in pids:
            try:
                os.kill(int(pid), signal.SIGTERM)
            except (ProcessLookupError, ValueError):
                pass

        for _ in range(10):
            time.sleep(0.5)
            if not _is_chrome_running():
                logger.info("Chrome closed gracefully")
                break
        else:
            result = subprocess.run(
                ["pgrep", "-x", "Google Chrome"],
                capture_output=True, text=True,
            )
            if result.returncode == 0:
                for pid in result.stdout.strip().split("\n"):
                    pid = pid.strip()
                    if pid:
                        try:
                            os.kill(int(pid), signal.SIGKILL)
                        except (ProcessLookupError, ValueError):
                            pass
                logger.warning("Chrome force-killed")

        if cdp_port is not None:
            for _ in range(10):
                if not _is_cdp_available(cdp_port):
                    break
                time.sleep(0.5)

    except Exception as e:
        logger.error("Failed to close Chrome: %s", e)


def _prepare_cdp_profile(source_profile: Path, cdp_data_dir: Path) -> None:
    """Copy essential auth files from the user's Chrome profile to the CDP dir.

    Chrome requires --user-data-dir to be non-default for CDP to work.
    We copy cookies and session files so existing logins are preserved.
    Chrome can decrypt these via macOS Keychain (same binary = same access).
    """
    target = cdp_data_dir / "Default"
    target.mkdir(parents=True, exist_ok=True)

    essential_files = [
        "Cookies",
        "Login Data",
        "Web Data",
        "Preferences",
        "Secure Preferences",
    ]
    for fname in essential_files:
        src_file = source_profile / fname
        if src_file.exists():
            try:
                shutil.copy2(str(src_file), str(target / fname))
            except Exception as e:
                logger.warning("Could not copy %s: %s", fname, e)

    # Local State lives in the Chrome root (parent of profile dir)
    local_state = source_profile.parent / "Local State"
    if local_state.exists():
        try:
            shutil.copy2(str(local_state), str(cdp_data_dir / "Local State"))
        except Exception as e:
            logger.warning("Could not copy Local State: %s", e)


def _launch_chrome_with_cdp(
    chrome_path: str,
    port: int,
    cdp_data_dir: Path,
) -> subprocess.Popen:
    """Launch Chrome with remote debugging enabled.

    Uses a non-default --user-data-dir (required by Chrome for CDP)
    populated with copied session files from the real profile.
    Returns the subprocess handle.
    """
    path = Path(chrome_path)
    if not path.exists():
        raise FileNotFoundError(f"Chrome not found at {path}")

    proc = subprocess.Popen(
        [
            str(path),
            f"--remote-debugging-port={port}",
            f"--user-data-dir={cdp_data_dir}",
            "--no-first-run",
            "--disable-blink-features=AutomationControlled",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    # Wait for CDP to become available (up to 15 seconds)
    for _ in range(15):
        time.sleep(1)
        if _is_cdp_available(port):
            logger.info("Chrome launched with CDP on port %d (pid=%d)", port, proc.pid)
            return proc

    proc.kill()
    raise TimeoutError(f"Chrome did not start CDP on port {port} within 15 seconds")


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
    cdp_data_dir: Path | None = None,
) -> list[RawConversation]:
    """Run a single platform collector via CDP connection to Chrome.

    Flow:
      1. If CDP port is open -> connect to existing Chrome
      2. If Chrome is not running -> launch Chrome with CDP, then connect
      3. If Chrome is running without CDP -> ask user to close Chrome

    Args:
        platform: Platform name (claude, chatgpt, gemini, etc.)
        headless: Not used (kept for API compatibility).
        days: Only keep conversations from the last N days.
        cdp_data_dir: Override the CDP profile directory. When None,
            automatically selects based on the platform's profile mapping.
    """
    from playwright.async_api import async_playwright

    if platform not in COLLECTORS:
        logger.error("Unknown platform: %s", platform)
        return []

    settings = get_settings()
    collector = COLLECTORS[platform]()
    cdp_port = settings.cdp_port
    conversations: list[RawConversation] = []

    # Resolve CDP data directory
    if cdp_data_dir is None:
        profile = get_profile_for_platform(platform)
        if profile:
            cdp_data_dir = get_cdp_data_dir(profile)
        else:
            cdp_data_dir = settings.db_path.parent / "chrome_cdp_profile"

    # --- Determine CDP availability ---
    if _is_cdp_available(cdp_port):
        logger.info("CDP already available on port %d", cdp_port)
    elif _is_chrome_running():
        logger.warning("Chrome is running without CDP on port %d", cdp_port)
        print("\n[!] Chrome is running but CDP (remote debugging) is not enabled.")
        print("    Please close Chrome (Cmd+Q), then rerun this command.")
        print("    We'll automatically relaunch Chrome with CDP enabled.\n")
        return []
    else:
        logger.info("Chrome not running; launching with CDP on port %d", cdp_port)
        # Only seed the CDP profile on first run (empty dir).
        # After the user logs in once, sessions persist in this dir.
        if not (cdp_data_dir / "Default").exists():
            print("[*] First run: seeding CDP profile from Chrome...")
            _prepare_cdp_profile(settings.chrome_profile, cdp_data_dir)
        print("[*] Launching Chrome with remote debugging...")
        try:
            _launch_chrome_with_cdp(settings.chrome_path, cdp_port, cdp_data_dir)
        except Exception as e:
            logger.error("Failed to launch Chrome with CDP: %s", e)
            print(f"\n[!] Failed to launch Chrome: {e}\n")
            return []

    # --- Connect via CDP and collect ---
    page = None
    async with async_playwright() as pw:
        try:
            browser = await pw.chromium.connect_over_cdp(
                f"http://localhost:{cdp_port}"
            )
            context = browser.contexts[0]
            page = await context.new_page()

            await page.goto(
                collector.get_url(),
                wait_until="domcontentloaded",
                timeout=30000,
            )

            logged_in = await collector.check_login(page)
            if not logged_in:
                logger.error("Not logged in to %s", platform)
                print(f"\n[!] Not logged in to {platform}.")
                print(f"    Please log in to {platform} in Chrome, then rerun.\n")
                await _save_debug_info(page, platform)
                await page.close()
                return []

            raw_list = await collector.get_conversation_list(page)

            if not raw_list:
                logger.warning("0 conversations found for %s", platform)
                await _save_debug_info(page, platform)
            else:
                conversations = [normalize_conversation(r) for r in raw_list]
                before_count = len(conversations)
                conversations = _filter_by_date(conversations, days)
                logger.info(
                    "Date filter (last %d days): %d -> %d conversations",
                    days, before_count, len(conversations),
                )

            await page.close()

        except Exception as e:
            logger.error("Collector error for %s: %s", platform, e)
            try:
                if page:
                    await _save_debug_info(page, platform)
                    await page.close()
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
    profile_override: str | None = None,
) -> dict[str, int]:
    """Run collectors for specified platforms, grouping by CDP profile.

    Platforms are grouped by their CDP profile. When switching between
    profiles, Chrome is restarted with the new profile's data directory.

    Args:
        platforms: List of platform names, or None for all.
        headless: Not used (kept for API compatibility).
        days: Only keep conversations from the last N days.
        profile_override: Force all platforms to use this profile name.
    """
    from src.app.profiles import DEFAULT_PROFILES

    init_db()

    settings = get_settings()
    target_platforms = platforms or list(COLLECTORS.keys())
    results: dict[str, int] = {}

    if profile_override:
        profile = next(
            (p for p in DEFAULT_PROFILES if p.name == profile_override), None,
        )
        if profile is None:
            logger.error("Unknown profile: %s", profile_override)
            print(f"\n[!] Unknown profile: {profile_override}")
            print(f"    Available: {', '.join(p.name for p in DEFAULT_PROFILES)}\n")
            return results
        groups = [(profile, target_platforms)]
    else:
        groups = group_platforms_by_profile(target_platforms)

    last_profile_name: str | None = None

    for profile, group_platforms in groups:
        current_name = profile.name if profile else None

        if current_name != last_profile_name and last_profile_name is not None:
            logger.info(
                "Switching CDP profile: %s -> %s", last_profile_name, current_name,
            )
            print(f"\n[*] Switching Chrome profile: {last_profile_name} -> {current_name}")
            _close_chrome(cdp_port=settings.cdp_port)

        last_profile_name = current_name

        cdp_data_dir = get_cdp_data_dir(profile) if profile else None

        for platform in group_platforms:
            logger.info("--- Collecting from %s (profile=%s) ---", platform, current_name)
            try:
                conversations = await run_collector(
                    platform, headless=headless, days=days, cdp_data_dir=cdp_data_dir,
                )
                count = _persist_conversations(platform, conversations)
                results[platform] = count
            except Exception as e:
                logger.error("Failed to collect from %s: %s", platform, e)
                results[platform] = 0

    return results
