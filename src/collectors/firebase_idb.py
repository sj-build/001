"""Extract Firebase auth tokens from Chrome IndexedDB on disk.

Reads the LevelDB files backing Chrome's IndexedDB for a given domain,
extracts the Firebase auth user record, and refreshes the id_token when
needed via the Google securetoken API.
"""
import logging
import time
from pathlib import Path

import httpx
from ccl_chromium_reader import ccl_chromium_indexeddb

from src.app.config import PROJECT_ROOT

logger = logging.getLogger("sj_home_agent.collectors.firebase_idb")

# Prevent httpx/httpcore from logging Bearer tokens at DEBUG/TRACE level
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

CHROME_IDB_BASE = (
    Path.home()
    / "Library"
    / "Application Support"
    / "Google"
    / "Chrome"
    / "Default"
    / "IndexedDB"
)

CDP_IDB_BASE = (
    PROJECT_ROOT
    / "data"
    / "chrome_cdp_profiles"
    / "company"
    / "Default"
    / "IndexedDB"
)

_TOKEN_REFRESH_URL = "https://securetoken.googleapis.com/v1/token"
_TOKEN_EXPIRY_BUFFER_S = 300  # treat as expired 5 min early


def _find_idb_path(domain: str) -> Path | None:
    """Locate the IndexedDB LevelDB directory for *domain*.

    Checks the user's regular Chrome profile first, then falls back to
    the CDP profile used for browser-based collection.

    Returns the LevelDB directory path, or None if not found.
    """
    if "/" in domain or "\\" in domain or ".." in domain:
        raise ValueError(f"Invalid domain: {domain}")

    folder_name = f"https_{domain}_0.indexeddb.leveldb"

    chrome_path = CHROME_IDB_BASE / folder_name
    if chrome_path.is_dir():
        return chrome_path

    cdp_path = CDP_IDB_BASE / folder_name
    if cdp_path.is_dir():
        return cdp_path

    return None


def _read_firebase_auth(idb_path: Path, api_key: str) -> dict:
    """Read the Firebase auth user record from an IndexedDB LevelDB dir.

    Returns a dict with keys:
      uid, email, refreshToken, accessToken, expirationTime

    Raises:
        FileNotFoundError: LevelDB directory missing.
        ValueError: Expected database/object-store/key not found.
    """
    if not idb_path.is_dir():
        raise FileNotFoundError(f"IndexedDB directory not found: {idb_path}")

    idb = ccl_chromium_indexeddb.WrappedIndexDB(idb_path)
    try:
        if "firebaseLocalStorageDb" not in idb:
            raise ValueError(
                "firebaseLocalStorageDb not found in IndexedDB"
            )

        db = idb["firebaseLocalStorageDb"]
        store = db.get_object_store_by_name("firebaseLocalStorage")
        if store is None:
            raise ValueError(
                "firebaseLocalStorage object store not found"
            )

        target_key = f"firebase:authUser:{api_key}:[DEFAULT]"

        for record in store.iterate_records(live_only=True):
            key_str = str(record.key)
            if target_key in key_str:
                value = record.value
                if not isinstance(value, dict):
                    raise ValueError(
                        f"Unexpected record value type: {type(value)}"
                    )

                sts = value.get("stsTokenManager", {})
                return {
                    "uid": value.get("uid", ""),
                    "email": value.get("email", ""),
                    "refreshToken": sts.get("refreshToken", ""),
                    "accessToken": sts.get("accessToken", ""),
                    "expirationTime": sts.get("expirationTime", 0),
                }

        raise ValueError(
            f"Auth user key not found: {target_key}"
        )
    finally:
        idb.close()


def refresh_id_token(
    api_key: str,
    refresh_token: str,
) -> tuple[str, str]:
    """Exchange a Firebase refresh token for a fresh id_token.

    Returns:
        (id_token, new_refresh_token)

    Raises:
        httpx.HTTPStatusError: on non-2xx response.
    """
    with httpx.Client(timeout=15) as client:
        resp = client.post(
            _TOKEN_REFRESH_URL,
            params={"key": api_key},
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
            },
        )
        resp.raise_for_status()
        body = resp.json()

    return (body["id_token"], body["refresh_token"])


def get_firebase_token(domain: str, api_key: str) -> str:
    """Get a valid Firebase id_token for *domain*.

    1. Finds the IndexedDB on disk.
    2. Reads the stored auth user record.
    3. If the access token is still valid, returns it directly.
    4. Otherwise refreshes via securetoken API and returns the new token.

    Returns:
        A Bearer-ready id_token string.

    Raises:
        FileNotFoundError: IndexedDB not found on disk.
        ValueError: Auth record missing or malformed.
        httpx.HTTPStatusError: Token refresh failed.
    """
    idb_path = _find_idb_path(domain)
    if idb_path is None:
        raise FileNotFoundError(
            f"IndexedDB not found for {domain} in Chrome or CDP profile"
        )

    auth = _read_firebase_auth(idb_path, api_key)

    expiration_time = auth["expirationTime"]
    now_ms = time.time() * 1000
    buffer_ms = _TOKEN_EXPIRY_BUFFER_S * 1000

    if expiration_time > (now_ms + buffer_ms):
        logger.info("Using cached Firebase token for %s", domain)
        return auth["accessToken"]

    logger.info("Firebase token expired, refreshing for %s", domain)
    id_token, _new_refresh = refresh_id_token(api_key, auth["refreshToken"])
    return id_token
