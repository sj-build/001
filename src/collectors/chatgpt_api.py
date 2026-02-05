"""ChatGPT conversation collector via web API.

Extracts session cookies from Chrome, converts to an access token,
and calls the internal chatgpt.com backend API to list conversations.
"""
import logging
from datetime import date, timedelta
from typing import Optional

import httpx

from src.collectors.chrome_cookies import get_cookies_for_domain
from src.ingest.normalize import RawConversation

logger = logging.getLogger("sj_home_agent.collectors.chatgpt_api")

_BASE_URL = "https://chatgpt.com"
_DOMAIN = "chatgpt.com"
_PAGE_SIZE = 28
_MAX_PAGES = 50

# Suppress httpx debug logging (may echo cookies)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)


def _get_session_cookie() -> str:
    """Read the NextAuth session token cookie from Chrome."""
    cookies = get_cookies_for_domain(_DOMAIN)
    token = cookies.get("__Secure-next-auth.session-token", "")
    if not token:
        raise ValueError(
            "ChatGPT session cookie not found. "
            "Please log in to chatgpt.com in Chrome."
        )
    return token


def _get_access_token(session_token: str) -> str:
    """Exchange the session cookie for a Bearer access token."""
    with httpx.Client(timeout=30) as client:
        resp = client.get(
            f"{_BASE_URL}/api/auth/session",
            headers={
                "Cookie": f"__Secure-next-auth.session-token={session_token}",
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/131.0.0.0 Safari/537.36"
                ),
            },
        )
        resp.raise_for_status()
        data = resp.json()

    access_token = data.get("accessToken", "")
    if not access_token:
        raise ValueError("accessToken not found in session response")
    return access_token


def _make_headers(access_token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {access_token}",
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json",
    }


def _fetch_conversations(
    access_token: str,
    limit: int = _PAGE_SIZE,
    offset: int = 0,
) -> dict:
    """Fetch a page of conversations from the ChatGPT backend API."""
    with httpx.Client(timeout=30) as client:
        resp = client.get(
            f"{_BASE_URL}/backend-api/conversations",
            params={"limit": limit, "offset": offset},
            headers=_make_headers(access_token),
        )
        resp.raise_for_status()
        return resp.json()


def collect_chatgpt(days: int = 30) -> list[RawConversation]:
    """Collect ChatGPT conversations via REST API.

    Args:
        days: Only return conversations from the last N days.

    Returns:
        List of RawConversation for each conversation.
    """
    try:
        session_token = _get_session_cookie()
    except (FileNotFoundError, ValueError) as exc:
        logger.warning("ChatGPT cookie extraction failed: %s", exc)
        return []
    except Exception as exc:
        logger.error("Unexpected error reading ChatGPT cookies: %s", exc)
        return []

    try:
        access_token = _get_access_token(session_token)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code in (401, 403):
            logger.warning(
                "ChatGPT session expired. Please log in to chatgpt.com in Chrome."
            )
            print("\n[!] ChatGPT session expired. Please log in to chatgpt.com in Chrome.\n")
        else:
            logger.error(
                "ChatGPT auth error (HTTP %d): %s", exc.response.status_code, exc
            )
        return []
    except (ValueError, Exception) as exc:
        logger.error("Failed to get ChatGPT access token: %s", exc)
        return []

    cutoff = (date.today() - timedelta(days=days)).isoformat()
    conversations: list[RawConversation] = []
    offset = 0

    for _page in range(_MAX_PAGES):
        try:
            data = _fetch_conversations(access_token, limit=_PAGE_SIZE, offset=offset)
        except httpx.HTTPStatusError as exc:
            logger.error(
                "ChatGPT API error (HTTP %d): %s", exc.response.status_code, exc
            )
            break
        except httpx.RequestError as exc:
            logger.error("ChatGPT API request failed: %s", exc)
            break

        items = data.get("items", [])
        if not items:
            break

        for item in items:
            conv_date = _extract_date(item)
            if conv_date and conv_date < cutoff:
                continue

            title = item.get("title") or "Untitled"
            conv_id = item.get("id", "")
            url = f"{_BASE_URL}/c/{conv_id}" if conv_id else ""

            conversations.append(RawConversation(
                platform="chatgpt",
                title=title,
                url=url,
                date=conv_date,
                preview=None,
            ))

        total = data.get("total", 0)
        offset += _PAGE_SIZE
        if offset >= total or len(items) < _PAGE_SIZE:
            break
    else:
        logger.warning("Hit max page limit (%d). Results may be incomplete.", _MAX_PAGES)

    logger.info(
        "Collected %d ChatGPT conversations via API (last %d days)",
        len(conversations),
        days,
    )
    return conversations


def _extract_date(item: dict) -> Optional[str]:
    """Extract ISO date from a ChatGPT conversation dict."""
    for key in ("update_time", "create_time"):
        val = item.get(key)
        if val and isinstance(val, str):
            candidate = val[:10]
            try:
                date.fromisoformat(candidate)
                return candidate
            except ValueError:
                continue
    return None
