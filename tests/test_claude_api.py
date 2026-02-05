"""Tests for Claude.ai API-based conversation collector."""
import pytest
from datetime import date, timedelta
from unittest.mock import patch, MagicMock

import httpx

from src.collectors.claude_api import (
    _extract_date,
    _get_org_id,
    _get_session_cookie,
    _make_headers,
    collect_claude,
)


# ── _get_session_cookie ──────────────────────────────────────────


class TestGetSessionCookie:
    """Test sessionKey extraction from Chrome cookies."""

    @patch("src.collectors.claude_api.get_cookies_for_domain")
    def test_returns_session_key(self, mock_cookies):
        mock_cookies.return_value = {"sessionKey": "sk-ant-123"}
        assert _get_session_cookie() == "sk-ant-123"

    @patch("src.collectors.claude_api.get_cookies_for_domain")
    def test_raises_when_no_session_key(self, mock_cookies):
        mock_cookies.return_value = {"other": "value"}
        with pytest.raises(ValueError, match="sessionKey cookie not found"):
            _get_session_cookie()

    @patch("src.collectors.claude_api.get_cookies_for_domain")
    def test_raises_when_empty_session_key(self, mock_cookies):
        mock_cookies.return_value = {"sessionKey": ""}
        with pytest.raises(ValueError, match="sessionKey cookie not found"):
            _get_session_cookie()


# ── _make_headers ────────────────────────────────────────────────


class TestMakeHeaders:
    """Test header construction."""

    def test_includes_cookie(self):
        headers = _make_headers("test-key")
        assert headers["Cookie"] == "sessionKey=test-key"

    def test_includes_user_agent(self):
        headers = _make_headers("test-key")
        assert "User-Agent" in headers
        assert "Chrome" in headers["User-Agent"]

    def test_includes_accept_json(self):
        headers = _make_headers("test-key")
        assert headers["Accept"] == "application/json"


# ── _get_org_id ──────────────────────────────────────────────────


class TestGetOrgId:
    """Test organization ID retrieval."""

    @patch("src.collectors.claude_api.httpx.Client")
    def test_returns_first_org_uuid(self, mock_client_cls):
        mock_resp = MagicMock()
        mock_resp.json.return_value = [{"uuid": "org-abc-123"}]
        mock_resp.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = mock_resp
        mock_client_cls.return_value = mock_client

        org_id = _get_org_id("test-key")
        assert org_id == "org-abc-123"

    @patch("src.collectors.claude_api.httpx.Client")
    def test_raises_when_no_orgs(self, mock_client_cls):
        mock_resp = MagicMock()
        mock_resp.json.return_value = []
        mock_resp.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = mock_resp
        mock_client_cls.return_value = mock_client

        with pytest.raises(ValueError, match="No organizations found"):
            _get_org_id("test-key")


# ── _extract_date ────────────────────────────────────────────────


class TestExtractDate:
    """Test date extraction from Claude conversation dicts."""

    def test_extracts_updated_at(self):
        conv = {"updated_at": "2025-01-15T10:30:00.000Z"}
        assert _extract_date(conv) == "2025-01-15"

    def test_extracts_created_at_fallback(self):
        conv = {"created_at": "2025-01-10T08:00:00.000Z"}
        assert _extract_date(conv) == "2025-01-10"

    def test_prefers_updated_at(self):
        conv = {
            "updated_at": "2025-01-15T10:30:00.000Z",
            "created_at": "2025-01-10T08:00:00.000Z",
        }
        assert _extract_date(conv) == "2025-01-15"

    def test_returns_none_for_missing_dates(self):
        assert _extract_date({}) is None

    def test_returns_none_for_non_string(self):
        assert _extract_date({"updated_at": 1234567890}) is None

    def test_returns_none_for_invalid_date(self):
        assert _extract_date({"updated_at": "not-a-date-xxx"}) is None


# ── collect_claude ───────────────────────────────────────────────


class TestCollectClaude:
    """Test the main collection function."""

    @patch("src.collectors.claude_api._fetch_conversations")
    @patch("src.collectors.claude_api._get_org_id")
    @patch("src.collectors.claude_api._get_session_cookie")
    def test_collects_conversations(self, mock_cookie, mock_org, mock_fetch):
        mock_cookie.return_value = "sk-test"
        mock_org.return_value = "org-123"

        today = date.today().isoformat()
        mock_fetch.return_value = [
            {
                "uuid": "conv-1",
                "name": "Test Chat",
                "updated_at": f"{today}T10:00:00.000Z",
                "summary": "A test conversation",
            },
        ]

        result = collect_claude(days=30)

        assert len(result) == 1
        assert result[0].platform == "claude"
        assert result[0].title == "Test Chat"
        assert result[0].url == "https://claude.ai/chat/conv-1"
        assert result[0].date == today
        assert result[0].preview == "A test conversation"

    @patch("src.collectors.claude_api._fetch_conversations")
    @patch("src.collectors.claude_api._get_org_id")
    @patch("src.collectors.claude_api._get_session_cookie")
    def test_filters_old_conversations(self, mock_cookie, mock_org, mock_fetch):
        mock_cookie.return_value = "sk-test"
        mock_org.return_value = "org-123"

        old_date = (date.today() - timedelta(days=60)).isoformat()
        mock_fetch.return_value = [
            {
                "uuid": "conv-old",
                "name": "Old Chat",
                "updated_at": f"{old_date}T10:00:00.000Z",
            },
        ]

        result = collect_claude(days=30)
        assert len(result) == 0

    @patch("src.collectors.claude_api._get_session_cookie")
    def test_returns_empty_on_cookie_failure(self, mock_cookie):
        mock_cookie.side_effect = ValueError("No cookie")

        result = collect_claude(days=30)
        assert result == []

    @patch("src.collectors.claude_api._get_org_id")
    @patch("src.collectors.claude_api._get_session_cookie")
    def test_returns_empty_on_auth_failure(self, mock_cookie, mock_org):
        mock_cookie.return_value = "sk-test"

        response = MagicMock()
        response.status_code = 401
        mock_org.side_effect = httpx.HTTPStatusError(
            "Unauthorized", request=MagicMock(), response=response,
        )

        result = collect_claude(days=30)
        assert result == []

    @patch("src.collectors.claude_api._fetch_conversations")
    @patch("src.collectors.claude_api._get_org_id")
    @patch("src.collectors.claude_api._get_session_cookie")
    def test_uses_title_fallback(self, mock_cookie, mock_org, mock_fetch):
        mock_cookie.return_value = "sk-test"
        mock_org.return_value = "org-123"

        today = date.today().isoformat()
        mock_fetch.return_value = [
            {"uuid": "conv-1", "updated_at": f"{today}T10:00:00.000Z"},
        ]

        result = collect_claude(days=30)
        assert result[0].title == "Untitled"
