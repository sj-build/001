"""Claude.ai conversation collector via web API.

Extracts the sessionKey cookie from Chrome and calls the internal
claude.ai REST API to list recent conversations.
"""
import logging
from datetime import date, timedelta
from typing import Optional

import httpx

from src.collectors.chrome_cookies import get_cookies_for_domain
from src.ingest.normalize import RawConversation

logger = logging.getLogger("sj_home_agent.collectors.claude_api")

_BASE_URL = "https://claude.ai"
_DOMAIN = "claude.ai"

# Suppress httpx debug logging (may echo cookies)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)


def _get_session_cookie() -> str:
    """Read the sessionKey cookie from Chrome."""
    cookies = get_cookies_for_domain(_DOMAIN)
    session_key = cookies.get("sessionKey", "")
    if not session_key:
        raise ValueError(
            "sessionKey cookie not found for claude.ai. "
            "Please log in to claude.ai in Chrome."
        )
    return session_key


def _get_org_id(session_key: str) -> str:
    """Fetch the first organization ID from the Claude API."""
    with httpx.Client(timeout=30) as client:
        resp = client.get(
            f"{_BASE_URL}/api/organizations",
            headers=_make_headers(session_key),
        )
        resp.raise_for_status()
        orgs = resp.json()

    if not orgs:
        raise ValueError("No organizations found on claude.ai")

    return orgs[0]["uuid"]


def _make_headers(session_key: str) -> dict[str, str]:
    return {
        "Cookie": f"sessionKey={session_key}",
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        ),
        "Referer": f"{_BASE_URL}/chats",
        "Accept": "application/json",
    }


def _fetch_conversations(
    session_key: str,
    org_id: str,
) -> list[dict]:
    """Fetch the conversation list from Claude API."""
    with httpx.Client(timeout=30) as client:
        resp = client.get(
            f"{_BASE_URL}/api/organizations/{org_id}/chat_conversations",
            headers=_make_headers(session_key),
        )
        resp.raise_for_status()
        return resp.json()


def collect_claude(days: int = 30) -> list[RawConversation]:
    """Collect Claude.ai conversations via REST API.

    Args:
        days: Only return conversations from the last N days.

    Returns:
        List of RawConversation for each conversation.
    """
    try:
        session_key = _get_session_cookie()
    except (FileNotFoundError, ValueError) as exc:
        logger.warning("Claude cookie extraction failed: %s", exc)
        return []
    except Exception as exc:
        logger.error("Unexpected error reading Claude cookies: %s", exc)
        return []

    try:
        org_id = _get_org_id(session_key)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 401:
            logger.warning("Claude session expired. Please log in to claude.ai in Chrome.")
            print("\n[!] Claude session expired. Please log in to claude.ai in Chrome.\n")
        else:
            logger.error("Claude API error (HTTP %d): %s", exc.response.status_code, exc)
        return []
    except Exception as exc:
        logger.error("Failed to get Claude org ID: %s", exc)
        return []

    try:
        raw_convos = _fetch_conversations(session_key, org_id)
    except httpx.HTTPStatusError as exc:
        logger.error("Claude API error (HTTP %d): %s", exc.response.status_code, exc)
        return []
    except httpx.RequestError as exc:
        logger.error("Claude API request failed: %s", exc)
        return []

    cutoff = (date.today() - timedelta(days=days)).isoformat()
    conversations: list[RawConversation] = []

    for conv in raw_convos:
        conv_date = _extract_date(conv)
        if conv_date and conv_date < cutoff:
            continue

        title = conv.get("name") or conv.get("title") or "Untitled"
        uuid = conv.get("uuid", "")
        url = f"{_BASE_URL}/chat/{uuid}" if uuid else ""

        preview = conv.get("summary") or None

        conversations.append(RawConversation(
            platform="claude",
            title=title,
            url=url,
            date=conv_date,
            preview=preview,
        ))

    logger.info(
        "Collected %d Claude conversations via API (last %d days)",
        len(conversations),
        days,
    )
    return conversations


def _extract_date(conv: dict) -> Optional[str]:
    """Extract ISO date from a Claude conversation dict."""
    for key in ("updated_at", "created_at"):
        val = conv.get(key)
        if val and isinstance(val, str):
            candidate = val[:10]
            try:
                date.fromisoformat(candidate)
                return candidate
            except ValueError:
                continue
    return None
