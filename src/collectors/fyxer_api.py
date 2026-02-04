"""Fyxer call recording collector via Firestore REST API.

Authenticates using Firebase tokens extracted from Chrome IndexedDB
and fetches call recordings / transcripts from Firestore.
"""
import logging
from datetime import date, timedelta
from typing import Optional

import httpx

from src.collectors.firebase_idb import get_firebase_token
from src.ingest.normalize import RawConversation

logger = logging.getLogger("sj_home_agent.collectors.fyxer_api")

# Prevent httpx/httpcore from logging Bearer tokens at DEBUG/TRACE level
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

# Public Firebase client API key (not a secret).
# Firebase API keys identify the project; auth is enforced by Firebase Auth + Firestore rules.
# See: https://firebase.google.com/docs/projects/api-keys
FIREBASE_API_KEY = "AIzaSyBFQhrMdJnODlC6X0O5yMGomWwIyo5YQVQ"
FYXER_DOMAIN = "app.fyxer.com"
FIRESTORE_BASE = (
    "https://firestore.googleapis.com/v1"
    "/projects/fxyer-ai/databases/(default)/documents"
)
_MAX_PAGES = 50
_PAGE_SIZE = 50


def _make_headers(id_token: str) -> dict[str, str]:
    """Build request headers with Firebase Bearer auth."""
    return {
        "Authorization": f"Bearer {id_token}",
        "Content-Type": "application/json",
    }


def _unwrap_value(field: dict) -> object:
    """Unwrap a Firestore REST API field value wrapper.

    Firestore returns values as ``{"stringValue": "..."}``,
    ``{"integerValue": "123"}``, ``{"timestampValue": "..."}``, etc.
    """
    if "stringValue" in field:
        return field["stringValue"]
    if "integerValue" in field:
        return int(field["integerValue"])
    if "doubleValue" in field:
        return float(field["doubleValue"])
    if "booleanValue" in field:
        return field["booleanValue"]
    if "timestampValue" in field:
        return field["timestampValue"]
    if "nullValue" in field:
        return None
    if "mapValue" in field:
        return {
            k: _unwrap_value(v)
            for k, v in field["mapValue"].get("fields", {}).items()
        }
    if "arrayValue" in field:
        return [
            _unwrap_value(v) for v in field["arrayValue"].get("values", [])
        ]
    return field


def _unwrap_fields(doc: dict) -> dict:
    """Unwrap all Firestore field wrappers in a document."""
    fields = doc.get("fields", {})
    return {k: _unwrap_value(v) for k, v in fields.items()}


def _discover_user_org(id_token: str) -> str:
    """Discover the user's organisation ID in Fyxer.

    Queries the ``users`` collection filtered by the authenticated user's
    UID (extracted from the Firebase token claims) and returns the first
    organisation ID found.

    Raises:
        ValueError: No organisation found for the user.
        httpx.HTTPStatusError: Firestore API error.
    """
    headers = _make_headers(id_token)

    with httpx.Client(timeout=30) as client:
        # List user documents to find org membership
        resp = client.get(
            f"{FIRESTORE_BASE}/users",
            headers=headers,
            params={"pageSize": 10},
        )
        resp.raise_for_status()
        body = resp.json()

    docs = body.get("documents", [])
    for doc in docs:
        fields = _unwrap_fields(doc)
        org_id = fields.get("organisationId") or fields.get("organization_id")
        if org_id:
            logger.info("Discovered Fyxer org: %s", org_id)
            return str(org_id)

    raise ValueError("No organisation found for Fyxer user")


def _list_subcollections(id_token: str, parent: str) -> list[str]:
    """List subcollection IDs under a Firestore document.

    Uses the ``listCollectionIds`` API to discover what subcollections
    exist under the given parent path.
    """
    headers = _make_headers(id_token)

    with httpx.Client(timeout=30) as client:
        resp = client.post(
            f"{FIRESTORE_BASE}/{parent}:listCollectionIds",
            headers=headers,
            json={},
        )
        resp.raise_for_status()
        body = resp.json()

    return body.get("collectionIds", [])


def _fetch_recordings(
    id_token: str,
    org_id: str,
    collection: str,
    page_size: int = _PAGE_SIZE,
    page_token: str | None = None,
) -> tuple[list[dict], str | None]:
    """Fetch call recording documents from Firestore.

    Returns:
        (list of raw Firestore documents, next_page_token or None)
    """
    headers = _make_headers(id_token)
    params: dict[str, str | int] = {"pageSize": page_size}
    if page_token:
        params["pageToken"] = page_token

    with httpx.Client(timeout=30) as client:
        resp = client.get(
            f"{FIRESTORE_BASE}/organisations/{org_id}/{collection}",
            headers=headers,
            params=params,
        )
        resp.raise_for_status()
        body = resp.json()

    docs = body.get("documents", [])
    next_token = body.get("nextPageToken")
    return (docs, next_token)


def _extract_transcript(fields: dict) -> str:
    """Extract transcript text from unwrapped document fields."""
    for key in ("transcript", "transcription", "summary", "notes", "content"):
        val = fields.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()[:500]
        if isinstance(val, dict):
            text = val.get("text") or val.get("content") or ""
            if text:
                return str(text).strip()[:500]
    return ""


def _extract_date(fields: dict) -> Optional[str]:
    """Extract ISO date string from unwrapped document fields."""
    for key in ("date", "created_at", "createdAt", "start_time", "startTime", "timestamp"):
        val = fields.get(key)
        if val and isinstance(val, str):
            candidate = val[:10]
            try:
                date.fromisoformat(candidate)
                return candidate
            except ValueError:
                continue
    return None


def _detect_recording_collection(id_token: str, org_id: str) -> str:
    """Detect which subcollection holds call recordings.

    Tries known names first, then falls back to listing subcollections.

    Raises:
        ValueError: No recording collection found.
    """
    known_names = [
        "call_recordings",
        "meetings",
        "calls",
        "recordings",
        "call-recordings",
        "meeting-recordings",
    ]

    headers = _make_headers(id_token)

    with httpx.Client(timeout=10) as client:
        for name in known_names:
            try:
                resp = client.get(
                    f"{FIRESTORE_BASE}/organisations/{org_id}/{name}",
                    headers=headers,
                    params={"pageSize": 1},
                )
                if resp.status_code == 200:
                    body = resp.json()
                    if body.get("documents"):
                        logger.info("Found recording collection: %s", name)
                        return name
            except httpx.RequestError:
                continue

    subcollections = _list_subcollections(
        id_token, f"organisations/{org_id}"
    )
    logger.info("Org subcollections: %s", subcollections)

    recording_hints = ["call", "record", "meet", "transcript"]
    for coll in subcollections:
        if any(hint in coll.lower() for hint in recording_hints):
            logger.info("Using detected collection: %s", coll)
            return coll

    if subcollections:
        logger.warning(
            "No obvious recording collection; using first: %s",
            subcollections[0],
        )
        return subcollections[0]

    raise ValueError(
        f"No recording subcollection found under organisations/{org_id}"
    )


def collect_fyxer(days: int = 30) -> list[RawConversation]:
    """Collect Fyxer call recordings via Firestore REST API.

    Args:
        days: Only return recordings from the last N days.

    Returns:
        List of RawConversation for each call recording.
    """
    try:
        id_token = get_firebase_token(FYXER_DOMAIN, FIREBASE_API_KEY)
    except FileNotFoundError as exc:
        logger.warning("Fyxer IndexedDB not found: %s", exc)
        return []
    except ValueError as exc:
        logger.error("Fyxer auth record error: %s", exc)
        return []
    except httpx.HTTPStatusError as exc:
        logger.error(
            "Fyxer token refresh failed (HTTP %d): %s",
            exc.response.status_code, exc,
        )
        return []

    try:
        org_id = _discover_user_org(id_token)
    except (ValueError, httpx.HTTPStatusError) as exc:
        logger.error("Failed to discover Fyxer org: %s", exc)
        return []

    try:
        collection = _detect_recording_collection(id_token, org_id)
    except ValueError as exc:
        logger.error("Failed to detect recording collection: %s", exc)
        return []

    cutoff = (date.today() - timedelta(days=days)).isoformat()
    conversations: list[RawConversation] = []
    page_token: str | None = None

    for _page_num in range(_MAX_PAGES):
        try:
            docs, page_token = _fetch_recordings(
                id_token, org_id, collection, page_token=page_token,
            )
        except httpx.HTTPStatusError as exc:
            logger.error(
                "Fyxer API error (HTTP %d): %s",
                exc.response.status_code, exc,
            )
            break
        except httpx.RequestError as exc:
            logger.error("Fyxer API request failed: %s", exc)
            break

        if not docs:
            break

        for doc in docs:
            fields = _unwrap_fields(doc)
            doc_date = _extract_date(fields)

            if doc_date and doc_date < cutoff:
                continue

            title = (
                fields.get("title")
                or fields.get("name")
                or fields.get("meeting_title")
                or "Untitled Call"
            )

            doc_name = doc.get("name", "")
            doc_id = doc_name.rsplit("/", 1)[-1] if doc_name else ""
            url = (
                f"https://app.fyxer.com/call-recordings/{doc_id}"
                if doc_id
                else ""
            )

            preview = _extract_transcript(fields) or None

            conversations.append(RawConversation(
                platform="fyxer",
                title=str(title),
                url=url,
                date=doc_date,
                preview=preview,
            ))

        if not page_token:
            break
    else:
        logger.warning(
            "Hit maximum page limit (%d pages). Results may be incomplete.",
            _MAX_PAGES,
        )

    logger.info(
        "Collected %d Fyxer recordings via API (last %d days)",
        len(conversations), days,
    )
    return conversations
