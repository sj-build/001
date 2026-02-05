"""Tests for Firebase IndexedDB token extraction."""
import time
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from src.collectors.firebase_idb import (
    _find_idb_path,
    _read_firebase_auth,
    _read_app_check_token,
    _extract_valid_app_check,
    _refresh_app_check_via_browser,
    get_app_check_token,
    refresh_id_token,
    get_firebase_token,
)
import subprocess


# ── _find_idb_path tests ───────────────────────────────────────


class TestFindIdbPath:
    """Test IndexedDB path discovery."""

    def test_finds_regular_chrome_path(self, tmp_path):
        chrome_dir = tmp_path / "https_app.fyxer.com_0.indexeddb.leveldb"
        chrome_dir.mkdir()

        with patch("src.collectors.firebase_idb.CHROME_IDB_BASE", tmp_path):
            result = _find_idb_path("app.fyxer.com")

        assert result == chrome_dir

    def test_falls_back_to_cdp_path(self, tmp_path):
        cdp_dir = tmp_path / "https_app.fyxer.com_0.indexeddb.leveldb"
        cdp_dir.mkdir()

        empty_chrome = tmp_path / "chrome"
        empty_chrome.mkdir()

        with (
            patch("src.collectors.firebase_idb.CHROME_IDB_BASE", empty_chrome),
            patch("src.collectors.firebase_idb.CDP_IDB_BASE", tmp_path),
        ):
            result = _find_idb_path("app.fyxer.com")

        assert result == cdp_dir

    def test_returns_none_when_not_found(self, tmp_path):
        empty = tmp_path / "empty"
        empty.mkdir()

        with (
            patch("src.collectors.firebase_idb.CHROME_IDB_BASE", empty),
            patch("src.collectors.firebase_idb.CDP_IDB_BASE", empty),
        ):
            result = _find_idb_path("app.fyxer.com")

        assert result is None

    def test_prefers_chrome_over_cdp(self, tmp_path):
        chrome_base = tmp_path / "chrome"
        cdp_base = tmp_path / "cdp"
        chrome_base.mkdir()
        cdp_base.mkdir()

        chrome_dir = chrome_base / "https_example.com_0.indexeddb.leveldb"
        chrome_dir.mkdir()
        cdp_dir = cdp_base / "https_example.com_0.indexeddb.leveldb"
        cdp_dir.mkdir()

        with (
            patch("src.collectors.firebase_idb.CHROME_IDB_BASE", chrome_base),
            patch("src.collectors.firebase_idb.CDP_IDB_BASE", cdp_base),
        ):
            result = _find_idb_path("example.com")

        assert result == chrome_dir


# ── _read_firebase_auth tests ──────────────────────────────────


class TestReadFirebaseAuth:
    """Test IndexedDB auth record extraction."""

    def test_raises_on_missing_directory(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            _read_firebase_auth(tmp_path / "nonexistent", "test-api-key")

    @patch("src.collectors.firebase_idb.ccl_chromium_indexeddb")
    def test_raises_when_db_missing(self, mock_ccl, tmp_path):
        idb_dir = tmp_path / "leveldb"
        idb_dir.mkdir()

        mock_idb = MagicMock()
        mock_idb.__contains__ = MagicMock(return_value=False)
        mock_ccl.WrappedIndexDB.return_value = mock_idb

        with pytest.raises(ValueError, match="firebaseLocalStorageDb"):
            _read_firebase_auth(idb_dir, "test-api-key")

        mock_idb.close.assert_called_once()

    @patch("src.collectors.firebase_idb.ccl_chromium_indexeddb")
    def test_raises_when_store_missing(self, mock_ccl, tmp_path):
        idb_dir = tmp_path / "leveldb"
        idb_dir.mkdir()

        mock_db = MagicMock()
        mock_db.get_object_store_by_name.return_value = None

        mock_idb = MagicMock()
        mock_idb.__contains__ = MagicMock(return_value=True)
        mock_idb.__getitem__ = MagicMock(return_value=mock_db)
        mock_ccl.WrappedIndexDB.return_value = mock_idb

        with pytest.raises(ValueError, match="object store not found"):
            _read_firebase_auth(idb_dir, "test-api-key")

        mock_idb.close.assert_called_once()

    @patch("src.collectors.firebase_idb.ccl_chromium_indexeddb")
    def test_extracts_auth_record(self, mock_ccl, tmp_path):
        idb_dir = tmp_path / "leveldb"
        idb_dir.mkdir()

        mock_record = MagicMock()
        mock_record.value = {
            "fbase_key": "firebase:authUser:test-api-key:[DEFAULT]",
            "value": {
                "uid": "user-123",
                "email": "test@example.com",
                "stsTokenManager": {
                    "refreshToken": "refresh-abc",
                    "accessToken": "access-xyz",
                    "expirationTime": 9999999999999,
                },
            },
        }

        mock_store = MagicMock()
        mock_store.iterate_records.return_value = [mock_record]

        mock_db = MagicMock()
        mock_db.get_object_store_by_name.return_value = mock_store

        mock_idb = MagicMock()
        mock_idb.__contains__ = MagicMock(return_value=True)
        mock_idb.__getitem__ = MagicMock(return_value=mock_db)
        mock_ccl.WrappedIndexDB.return_value = mock_idb

        result = _read_firebase_auth(idb_dir, "test-api-key")

        assert result["uid"] == "user-123"
        assert result["email"] == "test@example.com"
        assert result["refreshToken"] == "refresh-abc"
        assert result["accessToken"] == "access-xyz"
        assert result["expirationTime"] == 9999999999999
        mock_idb.close.assert_called_once()

    @patch("src.collectors.firebase_idb.ccl_chromium_indexeddb")
    def test_raises_when_key_not_found(self, mock_ccl, tmp_path):
        idb_dir = tmp_path / "leveldb"
        idb_dir.mkdir()

        mock_store = MagicMock()
        mock_store.iterate_records.return_value = []

        mock_db = MagicMock()
        mock_db.get_object_store_by_name.return_value = mock_store

        mock_idb = MagicMock()
        mock_idb.__contains__ = MagicMock(return_value=True)
        mock_idb.__getitem__ = MagicMock(return_value=mock_db)
        mock_ccl.WrappedIndexDB.return_value = mock_idb

        with pytest.raises(ValueError, match="Auth user key not found"):
            _read_firebase_auth(idb_dir, "test-api-key")

        mock_idb.close.assert_called_once()


# ── refresh_id_token tests ─────────────────────────────────────


class TestRefreshIdToken:
    """Test Firebase token refresh."""

    @patch("src.collectors.firebase_idb.httpx.Client")
    def test_refresh_success(self, mock_client_cls):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "id_token": "new-id-token",
            "refresh_token": "new-refresh-token",
        }

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_resp
        mock_client_cls.return_value = mock_client

        id_token, new_refresh = refresh_id_token("api-key", "old-refresh")

        assert id_token == "new-id-token"
        assert new_refresh == "new-refresh-token"
        mock_client.post.assert_called_once()

    @patch("src.collectors.firebase_idb.httpx.Client")
    def test_refresh_http_error(self, mock_client_cls):
        import httpx

        mock_resp = MagicMock()
        mock_resp.status_code = 400
        mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Bad Request", request=MagicMock(), response=mock_resp,
        )

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_resp
        mock_client_cls.return_value = mock_client

        with pytest.raises(httpx.HTTPStatusError):
            refresh_id_token("api-key", "bad-refresh")


# ── get_firebase_token tests ───────────────────────────────────


class TestGetFirebaseToken:
    """Test end-to-end token retrieval."""

    @patch("src.collectors.firebase_idb._read_firebase_auth")
    @patch("src.collectors.firebase_idb._find_idb_path")
    def test_returns_cached_token_when_valid(self, mock_find, mock_read):
        mock_find.return_value = Path("/fake/idb")
        future_ms = (time.time() + 3600) * 1000
        mock_read.return_value = {
            "uid": "u1",
            "email": "a@b.com",
            "refreshToken": "rt",
            "accessToken": "valid-token",
            "expirationTime": future_ms,
        }

        result = get_firebase_token("app.fyxer.com", "api-key")
        assert result == "valid-token"

    @patch("src.collectors.firebase_idb.refresh_id_token")
    @patch("src.collectors.firebase_idb._read_firebase_auth")
    @patch("src.collectors.firebase_idb._find_idb_path")
    def test_refreshes_expired_token(self, mock_find, mock_read, mock_refresh):
        mock_find.return_value = Path("/fake/idb")
        past_ms = (time.time() - 3600) * 1000
        mock_read.return_value = {
            "uid": "u1",
            "email": "a@b.com",
            "refreshToken": "old-rt",
            "accessToken": "expired-token",
            "expirationTime": past_ms,
        }
        mock_refresh.return_value = ("fresh-token", "new-rt")

        result = get_firebase_token("app.fyxer.com", "api-key")
        assert result == "fresh-token"
        mock_refresh.assert_called_once_with("api-key", "old-rt")

    @patch("src.collectors.firebase_idb._find_idb_path")
    def test_raises_when_idb_not_found(self, mock_find):
        mock_find.return_value = None

        with pytest.raises(FileNotFoundError, match="IndexedDB not found"):
            get_firebase_token("app.fyxer.com", "api-key")


# ── _read_app_check_token tests ──────────────────────────────


class TestReadAppCheckToken:
    """Test App Check token extraction from IndexedDB."""

    def test_raises_on_missing_directory(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            _read_app_check_token(tmp_path / "nonexistent")

    @patch("src.collectors.firebase_idb.ccl_chromium_indexeddb")
    def test_raises_when_db_missing(self, mock_ccl, tmp_path):
        idb_dir = tmp_path / "leveldb"
        idb_dir.mkdir()

        mock_idb = MagicMock()
        mock_idb.__contains__ = MagicMock(return_value=False)
        mock_ccl.WrappedIndexDB.return_value = mock_idb

        with pytest.raises(ValueError, match="firebase-app-check-database"):
            _read_app_check_token(idb_dir)

        mock_idb.close.assert_called_once()

    @patch("src.collectors.firebase_idb.ccl_chromium_indexeddb")
    def test_raises_when_store_missing(self, mock_ccl, tmp_path):
        idb_dir = tmp_path / "leveldb"
        idb_dir.mkdir()

        mock_db = MagicMock()
        mock_db.get_object_store_by_name.return_value = None

        mock_idb = MagicMock()
        mock_idb.__contains__ = MagicMock(return_value=True)
        mock_idb.__getitem__ = MagicMock(return_value=mock_db)
        mock_ccl.WrappedIndexDB.return_value = mock_idb

        with pytest.raises(ValueError, match="firebase-app-check-store"):
            _read_app_check_token(idb_dir)

        mock_idb.close.assert_called_once()

    @patch("src.collectors.firebase_idb.ccl_chromium_indexeddb")
    def test_extracts_app_check_token(self, mock_ccl, tmp_path):
        idb_dir = tmp_path / "leveldb"
        idb_dir.mkdir()

        mock_record = MagicMock()
        mock_record.value = {
            "compositeKey": "1:408115782056:web:abc-[DEFAULT]",
            "value": {
                "token": "eyJhbGciOiJSUzI1NiJ9.test-token",
                "expireTimeMillis": 9999999999999.0,
                "issuedAtTimeMillis": 1000000000000.0,
            },
        }

        mock_store = MagicMock()
        mock_store.iterate_records.return_value = [mock_record]

        mock_db = MagicMock()
        mock_db.get_object_store_by_name.return_value = mock_store

        mock_idb = MagicMock()
        mock_idb.__contains__ = MagicMock(return_value=True)
        mock_idb.__getitem__ = MagicMock(return_value=mock_db)
        mock_ccl.WrappedIndexDB.return_value = mock_idb

        result = _read_app_check_token(idb_dir)

        assert result["token"] == "eyJhbGciOiJSUzI1NiJ9.test-token"
        assert result["expireTimeMillis"] == 9999999999999.0
        mock_idb.close.assert_called_once()

    @patch("src.collectors.firebase_idb.ccl_chromium_indexeddb")
    def test_raises_when_no_token_record(self, mock_ccl, tmp_path):
        idb_dir = tmp_path / "leveldb"
        idb_dir.mkdir()

        mock_store = MagicMock()
        mock_store.iterate_records.return_value = []

        mock_db = MagicMock()
        mock_db.get_object_store_by_name.return_value = mock_store

        mock_idb = MagicMock()
        mock_idb.__contains__ = MagicMock(return_value=True)
        mock_idb.__getitem__ = MagicMock(return_value=mock_db)
        mock_ccl.WrappedIndexDB.return_value = mock_idb

        with pytest.raises(ValueError, match="No App Check token"):
            _read_app_check_token(idb_dir)

        mock_idb.close.assert_called_once()


# ── _extract_valid_app_check tests ────────────────────────────


class TestExtractValidAppCheck:
    """Test App Check token validity check."""

    @patch("src.collectors.firebase_idb._read_app_check_token")
    def test_returns_token_when_valid(self, mock_read):
        future_ms = (time.time() + 3600) * 1000
        mock_read.return_value = {
            "token": "valid-check",
            "expireTimeMillis": future_ms,
        }
        assert _extract_valid_app_check(Path("/fake")) == "valid-check"

    @patch("src.collectors.firebase_idb._read_app_check_token")
    def test_returns_none_when_expired(self, mock_read):
        past_ms = (time.time() - 3600) * 1000
        mock_read.return_value = {
            "token": "expired",
            "expireTimeMillis": past_ms,
        }
        assert _extract_valid_app_check(Path("/fake")) is None

    @patch("src.collectors.firebase_idb._read_app_check_token")
    def test_returns_none_on_error(self, mock_read):
        mock_read.side_effect = ValueError("no token")
        assert _extract_valid_app_check(Path("/fake")) is None


# ── _refresh_app_check_via_browser tests ─────────────────────


class TestRefreshAppCheckViaBrowser:
    """Test browser-based App Check refresh."""

    @patch("src.collectors.firebase_idb._extract_valid_app_check")
    @patch("src.collectors.firebase_idb.subprocess.run")
    def test_returns_token_on_success(self, mock_run, mock_extract, tmp_path):
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        mock_extract.return_value = "fresh-token"

        with patch("src.collectors.firebase_idb._APP_CHECK_PROFILE_DIR", tmp_path):
            result = _refresh_app_check_via_browser("example.com")

        assert result == "fresh-token"
        mock_run.assert_called_once()

    @patch("src.collectors.firebase_idb.subprocess.run")
    def test_returns_none_on_subprocess_failure(self, mock_run, tmp_path):
        mock_run.return_value = MagicMock(returncode=1, stderr="error")

        with patch("src.collectors.firebase_idb._APP_CHECK_PROFILE_DIR", tmp_path):
            result = _refresh_app_check_via_browser("example.com")

        assert result is None

    @patch("src.collectors.firebase_idb.subprocess.run")
    def test_returns_none_on_timeout(self, mock_run, tmp_path):
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="test", timeout=60)

        with patch("src.collectors.firebase_idb._APP_CHECK_PROFILE_DIR", tmp_path):
            result = _refresh_app_check_via_browser("example.com")

        assert result is None

    @patch("src.collectors.firebase_idb._extract_valid_app_check")
    @patch("src.collectors.firebase_idb.subprocess.run")
    def test_returns_none_when_no_token_after_visit(self, mock_run, mock_extract, tmp_path):
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        mock_extract.return_value = None

        with patch("src.collectors.firebase_idb._APP_CHECK_PROFILE_DIR", tmp_path):
            result = _refresh_app_check_via_browser("example.com")

        assert result is None


# ── get_app_check_token tests ────────────────────────────────


class TestGetAppCheckToken:
    """Test end-to-end App Check token retrieval."""

    @patch("src.collectors.firebase_idb._refresh_app_check_via_browser")
    @patch("src.collectors.firebase_idb._extract_valid_app_check")
    @patch("src.collectors.firebase_idb._find_idb_path")
    def test_returns_valid_token_from_disk(self, mock_find, mock_extract, mock_refresh):
        mock_find.return_value = Path("/fake/idb")
        mock_extract.return_value = "disk-token"

        result = get_app_check_token("app.fyxer.com")
        assert result == "disk-token"
        mock_refresh.assert_not_called()

    @patch("src.collectors.firebase_idb._refresh_app_check_via_browser")
    @patch("src.collectors.firebase_idb._extract_valid_app_check")
    @patch("src.collectors.firebase_idb._find_idb_path")
    def test_falls_back_to_browser_refresh(self, mock_find, mock_extract, mock_refresh):
        mock_find.return_value = Path("/fake/idb")
        mock_extract.return_value = None  # expired on disk
        mock_refresh.return_value = "browser-token"

        with patch("src.collectors.firebase_idb._APP_CHECK_PROFILE_DIR", Path("/nonexistent")):
            result = get_app_check_token("app.fyxer.com")

        assert result == "browser-token"
        mock_refresh.assert_called_once_with("app.fyxer.com")

    @patch("src.collectors.firebase_idb._refresh_app_check_via_browser")
    @patch("src.collectors.firebase_idb._find_idb_path")
    def test_returns_none_when_all_fail(self, mock_find, mock_refresh):
        mock_find.return_value = None
        mock_refresh.return_value = None

        with patch("src.collectors.firebase_idb._APP_CHECK_PROFILE_DIR", Path("/nonexistent")):
            result = get_app_check_token("app.fyxer.com")

        assert result is None

    @patch("src.collectors.firebase_idb._refresh_app_check_via_browser")
    @patch("src.collectors.firebase_idb._extract_valid_app_check")
    @patch("src.collectors.firebase_idb._find_idb_path")
    def test_uses_browser_profile_cache(self, mock_find, mock_extract, mock_refresh, tmp_path):
        mock_find.return_value = None

        # Create the browser profile IndexedDB dir
        idb_dir = tmp_path / "Default" / "IndexedDB" / "https_app.fyxer.com_0.indexeddb.leveldb"
        idb_dir.mkdir(parents=True)

        # Only one call: browser profile cache returns a valid token
        mock_extract.return_value = "cached-browser-token"

        with patch("src.collectors.firebase_idb._APP_CHECK_PROFILE_DIR", tmp_path):
            result = get_app_check_token("app.fyxer.com")

        assert result == "cached-browser-token"
        mock_refresh.assert_not_called()
