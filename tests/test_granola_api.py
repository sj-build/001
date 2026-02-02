"""Tests for Granola REST API collector."""
import json
import time

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from src.collectors.granola_api import (
    _read_tokens,
    _is_token_expired,
    _prosemirror_to_text,
    _extract_date,
    collect_granola,
)
from src.ingest.normalize import RawConversation


# ── _read_tokens tests ───────────────────────────────────────────


class TestReadTokens:
    """Test token reading from supabase.json."""

    def test_reads_valid_tokens(self, tmp_path):
        tokens = {
            "access_token": "tok_abc",
            "refresh_token": "ref_xyz",
            "expires_in": 21599,
            "obtained_at": 1700000000000,
        }
        data = {"workos_tokens": json.dumps(tokens)}
        path = tmp_path / "supabase.json"
        path.write_text(json.dumps(data))

        access, refresh, obtained, expires = _read_tokens(path)
        assert access == "tok_abc"
        assert refresh == "ref_xyz"
        assert obtained == 1700000000.0
        assert expires == 21599

    def test_reads_tokens_as_dict(self, tmp_path):
        tokens = {
            "access_token": "tok_abc",
            "refresh_token": "ref_xyz",
            "expires_in": 21599,
            "obtained_at": 1700000000000,
        }
        data = {"workos_tokens": tokens}
        path = tmp_path / "supabase.json"
        path.write_text(json.dumps(data))

        access, refresh, obtained, expires = _read_tokens(path)
        assert access == "tok_abc"

    def test_file_not_found(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            _read_tokens(tmp_path / "nonexistent.json")

    def test_missing_workos_tokens_key(self, tmp_path):
        path = tmp_path / "supabase.json"
        path.write_text(json.dumps({"other": "data"}))

        with pytest.raises(ValueError, match="workos_tokens key missing"):
            _read_tokens(path)

    def test_missing_access_token(self, tmp_path):
        tokens = {"refresh_token": "ref", "expires_in": 100, "obtained_at": 1000}
        path = tmp_path / "supabase.json"
        path.write_text(json.dumps({"workos_tokens": json.dumps(tokens)}))

        with pytest.raises(ValueError, match="access_token missing"):
            _read_tokens(path)

    def test_missing_obtained_at(self, tmp_path):
        tokens = {"access_token": "tok", "expires_in": 100}
        path = tmp_path / "supabase.json"
        path.write_text(json.dumps({"workos_tokens": json.dumps(tokens)}))

        with pytest.raises(ValueError, match="obtained_at missing"):
            _read_tokens(path)

    def test_invalid_json(self, tmp_path):
        path = tmp_path / "supabase.json"
        path.write_text("not valid json")

        with pytest.raises(json.JSONDecodeError):
            _read_tokens(path)


# ── _is_token_expired tests ─────────────────────────────────────


class TestIsTokenExpired:
    """Test token expiry detection."""

    def test_valid_token(self):
        obtained = time.time() - 100
        result = _is_token_expired(obtained, 21599)
        assert result is False

    def test_expired_token(self):
        obtained = time.time() - 30000
        result = _is_token_expired(obtained, 21599)
        assert result is True

    def test_within_buffer(self):
        obtained = time.time() - 21400
        result = _is_token_expired(obtained, 21599)
        assert result is True


# ── _prosemirror_to_text tests ──────────────────────────────────


class TestProsemirrorToText:
    """Test ProseMirror JSON to plain text conversion."""

    def test_none_returns_empty(self):
        assert _prosemirror_to_text(None) == ""

    def test_text_node(self):
        node = {"type": "text", "text": "hello"}
        assert _prosemirror_to_text(node) == "hello"

    def test_paragraph(self):
        node = {
            "type": "paragraph",
            "content": [{"type": "text", "text": "Hello world"}],
        }
        assert _prosemirror_to_text(node) == "Hello world\n"

    def test_heading(self):
        node = {
            "type": "heading",
            "attrs": {"level": 1},
            "content": [{"type": "text", "text": "Title"}],
        }
        assert _prosemirror_to_text(node) == "Title\n"

    def test_bullet_list(self):
        node = {
            "type": "bulletList",
            "content": [
                {
                    "type": "listItem",
                    "content": [
                        {
                            "type": "paragraph",
                            "content": [{"type": "text", "text": "Item 1"}],
                        }
                    ],
                },
                {
                    "type": "listItem",
                    "content": [
                        {
                            "type": "paragraph",
                            "content": [{"type": "text", "text": "Item 2"}],
                        }
                    ],
                },
            ],
        }
        result = _prosemirror_to_text(node)
        assert "Item 1" in result
        assert "Item 2" in result

    def test_nested_structure(self):
        doc = {
            "type": "doc",
            "content": [
                {
                    "type": "heading",
                    "content": [{"type": "text", "text": "Meeting"}],
                },
                {
                    "type": "paragraph",
                    "content": [{"type": "text", "text": "Notes here."}],
                },
            ],
        }
        result = _prosemirror_to_text(doc)
        assert "Meeting" in result
        assert "Notes here." in result

    def test_list_input(self):
        nodes = [
            {"type": "text", "text": "a"},
            {"type": "text", "text": "b"},
        ]
        assert _prosemirror_to_text(nodes) == "ab"

    def test_string_input(self):
        assert _prosemirror_to_text("raw string") == "raw string"


# ── _extract_date tests ─────────────────────────────────────────


class TestExtractDate:
    """Test date extraction from document dicts."""

    def test_created_at(self):
        assert _extract_date({"created_at": "2025-06-15T10:00:00Z"}) == "2025-06-15"

    def test_date_field(self):
        assert _extract_date({"date": "2025-06-15"}) == "2025-06-15"

    def test_start_time(self):
        assert _extract_date({"start_time": "2025-06-15T09:00:00"}) == "2025-06-15"

    def test_no_date(self):
        assert _extract_date({"title": "no date here"}) is None

    def test_priority_order(self):
        doc = {
            "created_at": "2025-01-01T00:00:00Z",
            "date": "2025-02-02",
        }
        assert _extract_date(doc) == "2025-01-01"


# ── collect_granola integration tests ────────────────────────────


class TestCollectGranola:
    """Test the main collect_granola function with mocked dependencies."""

    def test_file_not_found_returns_empty(self, tmp_path):
        result = collect_granola(days=7, supabase_path=tmp_path / "missing.json")
        assert result == []

    def test_invalid_json_returns_empty(self, tmp_path):
        path = tmp_path / "supabase.json"
        path.write_text("bad json")
        result = collect_granola(days=7, supabase_path=path)
        assert result == []

    @patch("src.collectors.granola_api._is_token_expired", return_value=True)
    def test_expired_token_returns_empty(self, mock_expired, tmp_path):
        tokens = {
            "access_token": "tok",
            "refresh_token": "ref",
            "expires_in": 21599,
            "obtained_at": 1000,
        }
        path = tmp_path / "supabase.json"
        path.write_text(json.dumps({"workos_tokens": json.dumps(tokens)}))

        result = collect_granola(days=7, supabase_path=path)
        assert result == []

    @patch("src.collectors.granola_api._fetch_documents")
    @patch("src.collectors.granola_api._is_token_expired", return_value=False)
    def test_successful_collection(self, mock_expired, mock_fetch, tmp_path):
        tokens = {
            "access_token": "tok",
            "refresh_token": "ref",
            "expires_in": 21599,
            "obtained_at": int(time.time() * 1000),
        }
        path = tmp_path / "supabase.json"
        path.write_text(json.dumps({"workos_tokens": json.dumps(tokens)}))

        mock_fetch.return_value = [
            {
                "id": "doc-1",
                "title": "Sprint Planning",
                "created_at": "2026-01-30T10:00:00Z",
                "content": {
                    "type": "doc",
                    "content": [
                        {
                            "type": "paragraph",
                            "content": [{"type": "text", "text": "Review tasks"}],
                        }
                    ],
                },
            },
            {
                "id": "doc-2",
                "title": "1:1 with Manager",
                "created_at": "2026-01-29T14:00:00Z",
            },
        ]

        result = collect_granola(days=30, supabase_path=path)

        assert len(result) == 2
        assert result[0].platform == "granola"
        assert result[0].title == "Sprint Planning"
        assert result[0].url == "https://granola.ai/note/doc-1"
        assert result[0].preview == "Review tasks"
        assert result[1].title == "1:1 with Manager"
        assert result[1].preview is None

    @patch("src.collectors.granola_api._fetch_documents")
    @patch("src.collectors.granola_api._is_token_expired", return_value=False)
    def test_date_filtering(self, mock_expired, mock_fetch, tmp_path):
        tokens = {
            "access_token": "tok",
            "refresh_token": "ref",
            "expires_in": 21599,
            "obtained_at": int(time.time() * 1000),
        }
        path = tmp_path / "supabase.json"
        path.write_text(json.dumps({"workos_tokens": json.dumps(tokens)}))

        mock_fetch.return_value = [
            {"id": "recent", "title": "Recent", "created_at": "2026-01-30T10:00:00Z"},
            {"id": "old", "title": "Old", "created_at": "2020-01-01T10:00:00Z"},
        ]

        result = collect_granola(days=7, supabase_path=path)

        titles = [c.title for c in result]
        assert "Recent" in titles
        assert "Old" not in titles

    @patch("src.collectors.granola_api._fetch_documents")
    @patch("src.collectors.granola_api._is_token_expired", return_value=False)
    def test_pagination(self, mock_expired, mock_fetch, tmp_path):
        tokens = {
            "access_token": "tok",
            "refresh_token": "ref",
            "expires_in": 21599,
            "obtained_at": int(time.time() * 1000),
        }
        path = tmp_path / "supabase.json"
        path.write_text(json.dumps({"workos_tokens": json.dumps(tokens)}))

        page1 = [
            {"id": f"doc-{i}", "title": f"Doc {i}", "created_at": "2026-01-30T10:00:00Z"}
            for i in range(50)
        ]
        page2 = [
            {"id": "doc-50", "title": "Doc 50", "created_at": "2026-01-30T10:00:00Z"},
        ]
        mock_fetch.side_effect = [page1, page2]

        result = collect_granola(days=30, supabase_path=path)
        assert len(result) == 51
        assert mock_fetch.call_count == 2

    @patch("src.collectors.granola_api._fetch_documents")
    @patch("src.collectors.granola_api._is_token_expired", return_value=False)
    def test_api_error_handled(self, mock_expired, mock_fetch, tmp_path):
        import httpx

        tokens = {
            "access_token": "tok",
            "refresh_token": "ref",
            "expires_in": 21599,
            "obtained_at": int(time.time() * 1000),
        }
        path = tmp_path / "supabase.json"
        path.write_text(json.dumps({"workos_tokens": json.dumps(tokens)}))

        mock_fetch.side_effect = httpx.RequestError("Connection failed")

        result = collect_granola(days=7, supabase_path=path)
        assert result == []
