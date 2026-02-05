"""Subprocess helper: visit a domain in Chromium to trigger App Check.

This script is invoked as a subprocess by firebase_idb.py to avoid
conflicts with the running asyncio event loop (Playwright Sync API
cannot be used inside an asyncio loop).

Launches a headed (visible) browser because reCAPTCHA Enterprise
blocks headless browsers from generating App Check tokens.

Usage:
    python -m src.collectors._app_check_helper <domain> <profile_dir> <wait_ms>
"""
import sys

from playwright.sync_api import sync_playwright


def main() -> None:
    domain = sys.argv[1]
    profile_dir = sys.argv[2]
    wait_ms = int(sys.argv[3])

    with sync_playwright() as pw:
        context = pw.chromium.launch_persistent_context(
            user_data_dir=profile_dir,
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--window-size=800,600",
                "--window-position=0,0",
            ],
        )
        try:
            page = context.new_page()
            page.goto(
                f"https://{domain}",
                wait_until="domcontentloaded",
                timeout=30_000,
            )
            page.wait_for_timeout(wait_ms)
            page.close()
        finally:
            context.close()


if __name__ == "__main__":
    main()
