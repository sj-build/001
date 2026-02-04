"""Tests for Fyxer Firestore REST API collector."""
import pytest
from datetime import date, timedelta
from unittest.mock import patch, MagicMock

from src.collectors.fyxer_api import (
    _make_headers,
    _unwrap_value,
    _unwrap_fields,
    _extract_date,
    _extract_transcript,
    collect_fyxer,
)
from src.ingest.normalize import RawConversation


# ── _make_headers tests ────────────────────────────────────────


class TestMakeHeaders:
    """Test Bearer auth header construction."""

    def test_includes_bearer_token(self):
        headers = _make_headers("test-token")
        assert headers["Authorization"] == "Bearer test-token"

    def test_includes_content_type(self):
        headers = _make_headers("test-token")
        assert headers["Content-Type"] == "application/json"


# ── _unwrap_value tests ────────────────────────────────────────


class TestUnwrapValue:
    """Test Firestore field value unwrapping."""

    def test_string_value(self):
        assert _unwrap_value({"stringValue": "hello"}) == "hello"

    def test_integer_value(self):
        assert _unwrap_value({"integerValue": "42"}) == 42

    def test_double_value(self):
        assert _unwrap_value({"doubleValue": 3.14}) == 3.14

    def test_boolean_value(self):
        assert _unwrap_value({"booleanValue": True}) is True

    def test_timestamp_value(self):
        ts = "2025-01-15T10:30:00Z"
        assert _unwrap_value({"timestampValue": ts}) == ts

    def test_null_value(self):
        assert _unwrap_value({"nullValue": None}) is None

    def test_map_value(self):
        result = _unwrap_value({
            "mapValue": {
                "fields": {
                    "name": {"stringValue": "Alice"},
                    "age": {"integerValue": "30"},
                },
            },
        })
        assert result == {"name": "Alice", "age": 30}

    def test_array_value(self):
        result = _unwrap_value({
            "arrayValue": {
                "values": [
                    {"stringValue": "a"},
                    {"integerValue": "1"},
                ],
            },
        })
        assert result == ["a", 1]

    def test_empty_map_value(self):
        result = _unwrap_value({"mapValue": {}})
        assert result == {}

    def test_empty_array_value(self):
        result = _unwrap_value({"arrayValue": {}})
        assert result == []

    def test_unknown_value_type(self):
        raw = {"geoPointValue": {"latitude": 1, "longitude": 2}}
        assert _unwrap_value(raw) == raw


# ── _unwrap_fields tests ──────────────────────────────────────


class TestUnwrapFields:
    """Test full document field unwrapping."""

    def test_unwraps_all_fields(self):
        doc = {
            "name": "projects/fxyer-ai/databases/(default)/documents/test/abc",
            "fields": {
                "title": {"stringValue": "Team standup"},
                "duration": {"integerValue": "3600"},
            },
        }
        result = _unwrap_fields(doc)
        assert result == {"title": "Team standup", "duration": 3600}

    def test_empty_fields(self):
        assert _unwrap_fields({}) == {}
        assert _unwrap_fields({"fields": {}}) == {}


# ── _extract_date tests ────────────────────────────────────────


class TestExtractDate:
    """Test date extraction from unwrapped fields."""

    def test_extracts_date_field(self):
        fields = {"date": "2025-01-15T10:30:00Z"}
        assert _extract_date(fields) == "2025-01-15"

    def test_extracts_created_at(self):
        fields = {"created_at": "2025-03-20T08:00:00Z"}
        assert _extract_date(fields) == "2025-03-20"

    def test_extracts_start_time(self):
        fields = {"start_time": "2025-06-01T14:00:00Z"}
        assert _extract_date(fields) == "2025-06-01"

    def test_returns_none_when_missing(self):
        assert _extract_date({}) is None
        assert _extract_date({"title": "Meeting"}) is None

    def test_returns_none_for_invalid_date(self):
        assert _extract_date({"date": "not-a-date"}) is None

    def test_prefers_date_over_created_at(self):
        fields = {
            "date": "2025-01-15T10:00:00Z",
            "created_at": "2025-01-10T08:00:00Z",
        }
        assert _extract_date(fields) == "2025-01-15"


# ── _extract_transcript tests ──────────────────────────────────


class TestExtractTranscript:
    """Test transcript extraction from unwrapped fields."""

    def test_extracts_transcript_field(self):
        fields = {"transcript": "Speaker A: Hello\nSpeaker B: Hi"}
        result = _extract_transcript(fields)
        assert result == "Speaker A: Hello\nSpeaker B: Hi"

    def test_extracts_summary_field(self):
        fields = {"summary": "Meeting about Q1 goals"}
        assert _extract_transcript(fields) == "Meeting about Q1 goals"

    def test_extracts_from_map_value(self):
        fields = {"transcript": {"text": "Some transcript text"}}
        assert _extract_transcript(fields) == "Some transcript text"

    def test_returns_empty_when_missing(self):
        assert _extract_transcript({}) == ""
        assert _extract_transcript({"title": "Meeting"}) == ""

    def test_truncates_long_text(self):
        long_text = "A" * 1000
        fields = {"transcript": long_text}
        result = _extract_transcript(fields)
        assert len(result) == 500

    def test_strips_whitespace(self):
        fields = {"transcript": "  hello world  "}
        assert _extract_transcript(fields) == "hello world"


# ── collect_fyxer integration tests ───────────────────────────


class TestCollectFyxer:
    """Test the main collect_fyxer function with mocked dependencies."""

    @patch("src.collectors.fyxer_api.get_firebase_token")
    def test_returns_empty_on_missing_idb(self, mock_token):
        mock_token.side_effect = FileNotFoundError("not found")
        result = collect_fyxer(days=7)
        assert result == []

    @patch("src.collectors.fyxer_api.get_firebase_token")
    def test_returns_empty_on_auth_error(self, mock_token):
        mock_token.side_effect = ValueError("auth record missing")
        result = collect_fyxer(days=7)
        assert result == []

    @patch("src.collectors.fyxer_api._discover_user_org")
    @patch("src.collectors.fyxer_api.get_firebase_token")
    def test_returns_empty_on_org_error(self, mock_token, mock_org):
        mock_token.return_value = "test-token"
        mock_org.side_effect = ValueError("no org")
        result = collect_fyxer(days=7)
        assert result == []

    @patch("src.collectors.fyxer_api._fetch_recordings")
    @patch("src.collectors.fyxer_api._detect_recording_collection")
    @patch("src.collectors.fyxer_api._discover_user_org")
    @patch("src.collectors.fyxer_api.get_firebase_token")
    def test_collects_recordings(
        self, mock_token, mock_org, mock_detect, mock_fetch,
    ):
        mock_token.return_value = "test-token"
        mock_org.return_value = "org-123"
        mock_detect.return_value = "call_recordings"

        today = date.today().isoformat()
        mock_fetch.return_value = (
            [
                {
                    "name": "projects/fxyer-ai/databases/(default)/documents/organisations/org-123/call_recordings/rec-1",
                    "fields": {
                        "title": {"stringValue": "Weekly standup"},
                        "date": {"timestampValue": f"{today}T10:00:00Z"},
                        "transcript": {"stringValue": "Alice: Hi\nBob: Hello"},
                    },
                },
                {
                    "name": "projects/fxyer-ai/databases/(default)/documents/organisations/org-123/call_recordings/rec-2",
                    "fields": {
                        "title": {"stringValue": "1:1 with manager"},
                        "date": {"timestampValue": f"{today}T14:00:00Z"},
                    },
                },
            ],
            None,
        )

        result = collect_fyxer(days=7)

        assert len(result) == 2
        assert all(isinstance(r, RawConversation) for r in result)
        assert result[0].platform == "fyxer"
        assert result[0].title == "Weekly standup"
        assert result[0].url == "https://app.fyxer.com/call-recordings/rec-1"
        assert result[0].preview == "Alice: Hi\nBob: Hello"
        assert result[1].title == "1:1 with manager"
        assert result[1].preview is None

    @patch("src.collectors.fyxer_api._fetch_recordings")
    @patch("src.collectors.fyxer_api._detect_recording_collection")
    @patch("src.collectors.fyxer_api._discover_user_org")
    @patch("src.collectors.fyxer_api.get_firebase_token")
    def test_filters_old_recordings(
        self, mock_token, mock_org, mock_detect, mock_fetch,
    ):
        mock_token.return_value = "test-token"
        mock_org.return_value = "org-123"
        mock_detect.return_value = "call_recordings"

        old_date = (date.today() - timedelta(days=60)).isoformat()
        mock_fetch.return_value = (
            [
                {
                    "name": "projects/fxyer-ai/.../rec-old",
                    "fields": {
                        "title": {"stringValue": "Old meeting"},
                        "date": {"timestampValue": f"{old_date}T10:00:00Z"},
                    },
                },
            ],
            None,
        )

        result = collect_fyxer(days=7)
        assert len(result) == 0

    @patch("src.collectors.fyxer_api._fetch_recordings")
    @patch("src.collectors.fyxer_api._detect_recording_collection")
    @patch("src.collectors.fyxer_api._discover_user_org")
    @patch("src.collectors.fyxer_api.get_firebase_token")
    def test_handles_api_error(
        self, mock_token, mock_org, mock_detect, mock_fetch,
    ):
        import httpx

        mock_token.return_value = "test-token"
        mock_org.return_value = "org-123"
        mock_detect.return_value = "call_recordings"

        mock_resp = MagicMock()
        mock_resp.status_code = 403
        mock_fetch.side_effect = httpx.HTTPStatusError(
            "Forbidden", request=MagicMock(), response=mock_resp,
        )

        result = collect_fyxer(days=7)
        assert result == []

    @patch("src.collectors.fyxer_api._fetch_recordings")
    @patch("src.collectors.fyxer_api._detect_recording_collection")
    @patch("src.collectors.fyxer_api._discover_user_org")
    @patch("src.collectors.fyxer_api.get_firebase_token")
    def test_paginates_results(
        self, mock_token, mock_org, mock_detect, mock_fetch,
    ):
        mock_token.return_value = "test-token"
        mock_org.return_value = "org-123"
        mock_detect.return_value = "call_recordings"

        today = date.today().isoformat()

        def make_doc(idx):
            return {
                "name": f"projects/fxyer-ai/.../rec-{idx}",
                "fields": {
                    "title": {"stringValue": f"Meeting {idx}"},
                    "date": {"timestampValue": f"{today}T10:00:00Z"},
                },
            }

        mock_fetch.side_effect = [
            ([make_doc(i) for i in range(3)], "page2-token"),
            ([make_doc(i + 3) for i in range(2)], None),
        ]

        result = collect_fyxer(days=7)
        assert len(result) == 5
        assert mock_fetch.call_count == 2
