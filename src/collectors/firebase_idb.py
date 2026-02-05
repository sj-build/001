"""Extract Firebase auth tokens from Chrome IndexedDB on disk.

Reads the LevelDB files backing Chrome's IndexedDB for a given domain,
extracts the Firebase auth user record, and refreshes the id_token when
needed via the Google securetoken API.
"""
import logging
import shutil
import subprocess
import sys
import time
from pathlib import Path

import httpx
from ccl_chromium_reader import ccl_chromium_indexeddb

from src.app.config import PROJECT_ROOT

logger = logging.getLogger("sj_home_agent.collectors.firebase_idb")

# Prevent httpx/httpcore from logging Bearer tokens at DEBUG/TRACE level
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

_CHROME_DEFAULT_DIR = (
    Path.home()
    / "Library"
    / "Application Support"
    / "Google"
    / "Chrome"
    / "Default"
)

CHROME_IDB_BASE = _CHROME_DEFAULT_DIR / "IndexedDB"

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
_APP_CHECK_DB = "firebase-app-check-database"
_APP_CHECK_STORE = "firebase-app-check-store"
_APP_CHECK_PROFILE_DIR = PROJECT_ROOT / "data" / "app_check_browser_profile"
_BROWSER_WAIT_MS = 12000  # time for Firebase SDK to initialize after networkidle


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
            outer = record.value
            if not isinstance(outer, dict):
                continue

            # Firebase wraps records as {"fbase_key": "...", "value": {...}}
            fbase_key = outer.get("fbase_key", "")
            if fbase_key == target_key:
                user = outer.get("value", {})
                if not isinstance(user, dict):
                    raise ValueError(
                        f"Unexpected auth value type: {type(user)}"
                    )

                sts = user.get("stsTokenManager", {})
                if not isinstance(sts, dict):
                    sts = {}
                return {
                    "uid": user.get("uid", ""),
                    "email": user.get("email", ""),
                    "refreshToken": sts.get("refreshToken", ""),
                    "accessToken": sts.get("accessToken", ""),
                    "expirationTime": sts.get("expirationTime", 0),
                }

        raise ValueError(
            f"Auth user key not found: {target_key}"
        )
    finally:
        idb.close()


def _read_app_check_token(idb_path: Path) -> dict:
    """Read the Firebase App Check token from an IndexedDB LevelDB dir.

    Returns a dict with keys: token, expireTimeMillis, issuedAtTimeMillis.

    Raises:
        FileNotFoundError: LevelDB directory missing.
        ValueError: Expected database/store/record not found.
    """
    if not idb_path.is_dir():
        raise FileNotFoundError(f"IndexedDB directory not found: {idb_path}")

    idb = ccl_chromium_indexeddb.WrappedIndexDB(idb_path)
    try:
        if _APP_CHECK_DB not in idb:
            raise ValueError(
                f"{_APP_CHECK_DB} not found in IndexedDB"
            )

        db = idb[_APP_CHECK_DB]
        store = db.get_object_store_by_name(_APP_CHECK_STORE)
        if store is None:
            raise ValueError(
                f"{_APP_CHECK_STORE} object store not found"
            )

        for record in store.iterate_records(live_only=True):
            outer = record.value
            if not isinstance(outer, dict):
                continue

            value = outer.get("value", {})
            if not isinstance(value, dict):
                continue

            token = value.get("token", "")
            if token:
                return {
                    "token": token,
                    "expireTimeMillis": value.get("expireTimeMillis", 0),
                    "issuedAtTimeMillis": value.get("issuedAtTimeMillis", 0),
                }

        raise ValueError("No App Check token record found")
    finally:
        idb.close()


def _extract_valid_app_check(idb_path: Path) -> str | None:
    """Read App Check token from *idb_path* and return it if still valid."""
    try:
        app_check = _read_app_check_token(idb_path)
    except (FileNotFoundError, ValueError):
        return None

    expire_ms = app_check.get("expireTimeMillis", 0)
    now_ms = time.time() * 1000
    if expire_ms > 0 and expire_ms < now_ms:
        return None
    return app_check["token"]


_AUTH_FILES = (
    "Cookies",
    "Login Data",
    "Web Data",
    "Preferences",
    "Secure Preferences",
    "Local State",
)


def _seed_browser_profile(profile_dir: Path) -> None:
    """Copy Chrome auth files to the browser profile so sessions persist."""
    dest = profile_dir / "Default"
    dest.mkdir(parents=True, exist_ok=True)

    for filename in _AUTH_FILES:
        src = _CHROME_DEFAULT_DIR / filename
        if src.exists():
            shutil.copy2(src, dest / filename)

    # Local State lives one level up
    local_state = _CHROME_DEFAULT_DIR.parent / "Local State"
    if local_state.exists():
        shutil.copy2(local_state, profile_dir / "Local State")


def _refresh_app_check_via_browser(domain: str) -> str | None:
    """Launch a headless browser to obtain a fresh App Check token.

    App Check tokens are generated by the Firebase JS SDK running in
    the browser (via reCAPTCHA Enterprise).  This function seeds a
    browser profile with Chrome's auth files, runs Playwright in a
    subprocess to avoid asyncio conflicts, visits *domain*, and lets
    the SDK write a fresh token to IndexedDB.

    Returns the token string, or None on failure.
    """
    profile_dir = _APP_CHECK_PROFILE_DIR
    profile_dir.mkdir(parents=True, exist_ok=True)

    _seed_browser_profile(profile_dir)

    try:
        result = subprocess.run(
            [
                sys.executable, "-m", "src.collectors._app_check_helper",
                domain, str(profile_dir), str(_BROWSER_WAIT_MS),
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            logger.warning(
                "App Check browser subprocess failed (rc=%d): %s",
                result.returncode, result.stderr[:500],
            )
            return None
    except subprocess.TimeoutExpired:
        logger.warning("App Check browser subprocess timed out")
        return None
    except OSError as exc:
        logger.warning("App Check browser subprocess error: %s", exc)
        return None

    idb_folder = f"https_{domain}_0.indexeddb.leveldb"
    idb_path = profile_dir / "Default" / "IndexedDB" / idb_folder
    token = _extract_valid_app_check(idb_path)
    if token:
        logger.info("Obtained fresh App Check token via browser for %s", domain)
    else:
        logger.warning("No valid App Check token after browser refresh for %s", domain)
    return token


def get_app_check_token(domain: str) -> str | None:
    """Get a Firebase App Check token for *domain*.

    Checks IndexedDB on disk (regular Chrome, CDP profile, and the
    dedicated browser refresh profile).  If no valid token is found,
    launches a headless browser to generate a fresh one.

    Returns the token string, or None if unavailable.
    App Check is best-effort; callers should proceed without it
    if extraction fails.
    """
    # 1. Try regular Chrome and CDP profile
    try:
        idb_path = _find_idb_path(domain)
        if idb_path is not None:
            token = _extract_valid_app_check(idb_path)
            if token:
                logger.info("Using App Check token from disk for %s", domain)
                return token
    except ValueError:
        pass

    # 2. Try the dedicated browser refresh profile
    idb_folder = f"https_{domain}_0.indexeddb.leveldb"
    browser_idb = _APP_CHECK_PROFILE_DIR / "Default" / "IndexedDB" / idb_folder
    if browser_idb.is_dir():
        token = _extract_valid_app_check(browser_idb)
        if token:
            logger.info("Using cached App Check token from browser profile for %s", domain)
            return token

    # 3. Refresh via headless browser
    logger.info("Refreshing App Check token via browser for %s", domain)
    return _refresh_app_check_via_browser(domain)


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
