"""Granola meeting notes collector via REST API.

Reads the local WorkOS token from Granola's desktop app and fetches
meeting notes directly from the API, bypassing browser/CDP entirely.
"""
import json
import logging
import time
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

import httpx

from src.ingest.normalize import RawConversation

logger = logging.getLogger("sj_home_agent.collectors.granola_api")

# Prevent httpx/httpcore from logging Bearer tokens at DEBUG/TRACE level
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

SUPABASE_PATH = (
    Path.home() / "Library" / "Application Support" / "Granola" / "supabase.json"
)
API_URL = "https://api.granola.ai/v2/get-documents"
_TOKEN_EXPIRY_BUFFER_S = 300  # treat as expired 5 min early
_MAX_PAGES = 100  # safety limit: 100 * 50 = 5,000 documents


def _read_tokens(
    path: Path = SUPABASE_PATH,
) -> tuple[str, str, float, int]:
    """Read WorkOS tokens from Granola's local storage.

    Returns:
        (access_token, refresh_token, obtained_at_s, expires_in_s)

    Raises:
        FileNotFoundError: supabase.json missing (Granola not installed).
        ValueError: JSON structure unexpected.
    """
    raw = path.read_text(encoding="utf-8")
    data = json.loads(raw)

    workos_raw = data.get("workos_tokens")
    if workos_raw is None:
        raise ValueError("workos_tokens key missing in supabase.json")

    tokens = json.loads(workos_raw) if isinstance(workos_raw, str) else workos_raw

    access_token = tokens.get("access_token")
    refresh_token = tokens.get("refresh_token", "")
    expires_in = int(tokens.get("expires_in", 0))
    obtained_at_ms = tokens.get("obtained_at")

    if not access_token:
        raise ValueError("access_token missing in workos_tokens")
    if obtained_at_ms is None:
        raise ValueError("obtained_at missing in workos_tokens")

    obtained_at_s = float(obtained_at_ms) / 1000.0
    return (access_token, refresh_token, obtained_at_s, expires_in)


def _is_token_expired(obtained_at_s: float, expires_in_s: int) -> bool:
    """Check whether the access token has expired (with buffer)."""
    expiry = obtained_at_s + expires_in_s - _TOKEN_EXPIRY_BUFFER_S
    return time.time() > expiry


def _fetch_documents(
    token: str,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    """Fetch documents from Granola API.

    Returns the list of document dicts from the response.
    """
    with httpx.Client(timeout=30) as client:
        resp = client.post(
            API_URL,
            headers={"Authorization": f"Bearer {token}"},
            json={"limit": limit, "offset": offset},
        )
        resp.raise_for_status()
        body = resp.json()

    if isinstance(body, list):
        return body
    return body.get("docs", body.get("documents", body.get("data", [])))


def _prosemirror_to_text(node: dict | list | None) -> str:
    """Recursively extract plain text from a ProseMirror JSON tree."""
    if node is None:
        return ""
    if isinstance(node, list):
        return "".join(_prosemirror_to_text(child) for child in node)
    if isinstance(node, str):
        return node

    parts: list[str] = []

    if node.get("type") == "text":
        parts.append(node.get("text", ""))

    for child in node.get("content", []):
        parts.append(_prosemirror_to_text(child))

    node_type = node.get("type", "")
    if node_type in ("paragraph", "heading", "bulletList", "orderedList", "listItem"):
        return "".join(parts) + "\n"

    return "".join(parts)


def _extract_date(doc: dict) -> Optional[str]:
    """Extract ISO date string from a Granola document dict."""
    for key in ("created_at", "date", "updated_at", "start_time"):
        val = doc.get(key)
        if val and isinstance(val, str):
            candidate = val[:10]
            try:
                date.fromisoformat(candidate)
                return candidate
            except ValueError:
                continue
    return None


def collect_granola(
    days: int = 30,
    supabase_path: Optional[Path] = None,
) -> list[RawConversation]:
    """Collect Granola meeting notes via REST API.

    Args:
        days: Only return documents from the last N days.
        supabase_path: Override path to supabase.json (for testing).

    Returns:
        List of RawConversation for each meeting note.
    """
    token_path = supabase_path or SUPABASE_PATH

    try:
        access_token, _refresh, obtained_at_s, expires_in_s = _read_tokens(token_path)
    except FileNotFoundError:
        logger.warning("Granola not installed — %s not found", token_path)
        return []
    except (ValueError, json.JSONDecodeError) as exc:
        logger.error("Failed to read Granola tokens: %s", exc)
        return []

    if _is_token_expired(obtained_at_s, expires_in_s):
        logger.warning("Granola token expired. Please open the Granola app to refresh.")
        print("\n[!] Granola access token has expired.")
        print("    Please open the Granola desktop app, then rerun.\n")
        return []

    cutoff = (date.today() - timedelta(days=days)).isoformat()
    conversations: list[RawConversation] = []
    offset = 0
    page_size = 50

    for _page_num in range(_MAX_PAGES):
        try:
            docs = _fetch_documents(access_token, limit=page_size, offset=offset)
        except httpx.HTTPStatusError as exc:
            logger.error("Granola API error (HTTP %d): %s", exc.response.status_code, exc)
            break
        except httpx.RequestError as exc:
            logger.error("Granola API request failed: %s", exc)
            break

        if not docs:
            break

        for doc in docs:
            doc_date = _extract_date(doc)
            if doc_date and doc_date < cutoff:
                continue

            title = doc.get("title") or "Untitled Meeting"
            doc_id = doc.get("id", "")
            url = f"https://granola.ai/note/{doc_id}" if doc_id else ""

            preview_text = ""
            content = doc.get("content") or doc.get("notes")
            if content:
                raw_text = (
                    _prosemirror_to_text(content)
                    if isinstance(content, dict)
                    else str(content)
                )
                preview_text = raw_text.strip()[:200] if raw_text else ""

            conversations.append(RawConversation(
                platform="granola",
                title=title,
                url=url,
                date=doc_date,
                preview=preview_text or None,
            ))

        if len(docs) < page_size:
            break
        offset += page_size
    else:
        logger.warning(
            "Hit maximum page limit (%d pages). Results may be incomplete.", _MAX_PAGES,
        )

    logger.info(
        "Collected %d Granola notes via API (last %d days)", len(conversations), days,
    )
    return conversations
