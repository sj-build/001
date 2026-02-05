"""Tests for ChatGPT API-based conversation collector."""
import pytest
from datetime import date, timedelta
from unittest.mock import patch, MagicMock

import httpx

from src.collectors.chatgpt_api import (
    _extract_date,
    _get_access_token,
    _get_session_cookie,
    _make_headers,
    _fetch_conversations,
    collect_chatgpt,
)


# ── _get_session_cookie ──────────────────────────────────────────


class TestGetSessionCookie:
    """Test NextAuth session token extraction from Chrome cookies."""

    @patch("src.collectors.chatgpt_api.get_cookies_for_domain")
    def test_returns_session_token(self, mock_cookies):
        mock_cookies.return_value = {
            "__Secure-next-auth.session-token": "token-xyz",
        }
        assert _get_session_cookie() == "token-xyz"

    @patch("src.collectors.chatgpt_api.get_cookies_for_domain")
    def test_raises_when_no_token(self, mock_cookies):
        mock_cookies.return_value = {"other": "value"}
        with pytest.raises(ValueError, match="session cookie not found"):
            _get_session_cookie()

    @patch("src.collectors.chatgpt_api.get_cookies_for_domain")
    def test_raises_when_empty_token(self, mock_cookies):
        mock_cookies.return_value = {
            "__Secure-next-auth.session-token": "",
        }
        with pytest.raises(ValueError, match="session cookie not found"):
            _get_session_cookie()


# ── _get_access_token ────────────────────────────────────────────


class TestGetAccessToken:
    """Test session token -> access token exchange."""

    @patch("src.collectors.chatgpt_api.httpx.Client")
    def test_returns_access_token(self, mock_client_cls):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"accessToken": "at-123"}
        mock_resp.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = mock_resp
        mock_client_cls.return_value = mock_client

        token = _get_access_token("session-token")
        assert token == "at-123"

    @patch("src.collectors.chatgpt_api.httpx.Client")
    def test_raises_when_no_access_token(self, mock_client_cls):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"user": "someone"}
        mock_resp.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = mock_resp
        mock_client_cls.return_value = mock_client

        with pytest.raises(ValueError, match="accessToken not found"):
            _get_access_token("session-token")


# ── _make_headers ────────────────────────────────────────────────


class TestMakeHeaders:
    """Test header construction."""

    def test_includes_bearer_token(self):
        headers = _make_headers("at-123")
        assert headers["Authorization"] == "Bearer at-123"

    def test_includes_accept_json(self):
        headers = _make_headers("at-123")
        assert headers["Accept"] == "application/json"


# ── _extract_date ────────────────────────────────────────────────


class TestExtractDate:
    """Test date extraction from ChatGPT conversation dicts."""

    def test_extracts_update_time(self):
        item = {"update_time": "2025-01-15T10:30:00"}
        assert _extract_date(item) == "2025-01-15"

    def test_extracts_create_time_fallback(self):
        item = {"create_time": "2025-01-10T08:00:00"}
        assert _extract_date(item) == "2025-01-10"

    def test_prefers_update_time(self):
        item = {
            "update_time": "2025-01-15T10:30:00",
            "create_time": "2025-01-10T08:00:00",
        }
        assert _extract_date(item) == "2025-01-15"

    def test_returns_none_for_missing(self):
        assert _extract_date({}) is None

    def test_returns_none_for_non_string(self):
        assert _extract_date({"update_time": 1234567890}) is None

    def test_returns_none_for_invalid_date(self):
        assert _extract_date({"update_time": "not-a-date-xxx"}) is None


# ── collect_chatgpt ──────────────────────────────────────────────


class TestCollectChatgpt:
    """Test the main collection function."""

    @patch("src.collectors.chatgpt_api._fetch_conversations")
    @patch("src.collectors.chatgpt_api._get_access_token")
    @patch("src.collectors.chatgpt_api._get_session_cookie")
    def test_collects_conversations(self, mock_cookie, mock_token, mock_fetch):
        mock_cookie.return_value = "session-token"
        mock_token.return_value = "at-123"

        today = date.today().isoformat()
        mock_fetch.return_value = {
            "items": [
                {
                    "id": "conv-1",
                    "title": "Test Chat",
                    "update_time": f"{today}T10:00:00",
                },
            ],
            "total": 1,
        }

        result = collect_chatgpt(days=30)

        assert len(result) == 1
        assert result[0].platform == "chatgpt"
        assert result[0].title == "Test Chat"
        assert result[0].url == "https://chatgpt.com/c/conv-1"
        assert result[0].date == today

    @patch("src.collectors.chatgpt_api._fetch_conversations")
    @patch("src.collectors.chatgpt_api._get_access_token")
    @patch("src.collectors.chatgpt_api._get_session_cookie")
    def test_filters_old_conversations(self, mock_cookie, mock_token, mock_fetch):
        mock_cookie.return_value = "session-token"
        mock_token.return_value = "at-123"

        old_date = (date.today() - timedelta(days=60)).isoformat()
        mock_fetch.return_value = {
            "items": [
                {
                    "id": "conv-old",
                    "title": "Old Chat",
                    "update_time": f"{old_date}T10:00:00",
                },
            ],
            "total": 1,
        }

        result = collect_chatgpt(days=30)
        assert len(result) == 0

    @patch("src.collectors.chatgpt_api._get_session_cookie")
    def test_returns_empty_on_cookie_failure(self, mock_cookie):
        mock_cookie.side_effect = ValueError("No cookie")

        result = collect_chatgpt(days=30)
        assert result == []

    @patch("src.collectors.chatgpt_api._get_access_token")
    @patch("src.collectors.chatgpt_api._get_session_cookie")
    def test_returns_empty_on_auth_failure(self, mock_cookie, mock_token):
        mock_cookie.return_value = "session-token"

        response = MagicMock()
        response.status_code = 403
        mock_token.side_effect = httpx.HTTPStatusError(
            "Forbidden", request=MagicMock(), response=response,
        )

        result = collect_chatgpt(days=30)
        assert result == []

    @patch("src.collectors.chatgpt_api._fetch_conversations")
    @patch("src.collectors.chatgpt_api._get_access_token")
    @patch("src.collectors.chatgpt_api._get_session_cookie")
    def test_pagination(self, mock_cookie, mock_token, mock_fetch):
        mock_cookie.return_value = "session-token"
        mock_token.return_value = "at-123"

        today = date.today().isoformat()

        def fetch_side_effect(access_token, limit, offset):
            if offset == 0:
                return {
                    "items": [
                        {
                            "id": f"conv-{i}",
                            "title": f"Chat {i}",
                            "update_time": f"{today}T10:00:00",
                        }
                        for i in range(28)
                    ],
                    "total": 30,
                }
            return {
                "items": [
                    {
                        "id": "conv-28",
                        "title": "Chat 28",
                        "update_time": f"{today}T10:00:00",
                    },
                    {
                        "id": "conv-29",
                        "title": "Chat 29",
                        "update_time": f"{today}T10:00:00",
                    },
                ],
                "total": 30,
            }

        mock_fetch.side_effect = fetch_side_effect

        result = collect_chatgpt(days=30)
        assert len(result) == 30
        assert mock_fetch.call_count == 2

    @patch("src.collectors.chatgpt_api._fetch_conversations")
    @patch("src.collectors.chatgpt_api._get_access_token")
    @patch("src.collectors.chatgpt_api._get_session_cookie")
    def test_stops_on_empty_items(self, mock_cookie, mock_token, mock_fetch):
        mock_cookie.return_value = "session-token"
        mock_token.return_value = "at-123"

        mock_fetch.return_value = {"items": [], "total": 0}

        result = collect_chatgpt(days=30)
        assert result == []
        assert mock_fetch.call_count == 1

    @patch("src.collectors.chatgpt_api._fetch_conversations")
    @patch("src.collectors.chatgpt_api._get_access_token")
    @patch("src.collectors.chatgpt_api._get_session_cookie")
    def test_uses_title_fallback(self, mock_cookie, mock_token, mock_fetch):
        mock_cookie.return_value = "session-token"
        mock_token.return_value = "at-123"

        today = date.today().isoformat()
        mock_fetch.return_value = {
            "items": [
                {"id": "conv-1", "update_time": f"{today}T10:00:00"},
            ],
            "total": 1,
        }

        result = collect_chatgpt(days=30)
        assert result[0].title == "Untitled"
