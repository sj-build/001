"""Tests for news sources: RSS and Twitter/Nitter."""
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock

from src.morning.sources.rss import (
    fetch_rss, _score_importance, _is_within_days, _parse_published_date,
)
from src.morning.sources.twitter import fetch_twitter_via_nitter
from src.morning.sources.fetch_all import fetch_all_sources
from src.app.config import Settings


# ── _score_importance tests ─────────────────────────────────────


class TestScoreImportance:
    def test_base_score(self):
        score = _score_importance("Generic title", "Generic summary", "Other")
        assert score == 0.5

    def test_work_category_boost(self):
        score = _score_importance("Meeting notes", "Summary", "Work/NewDeal")
        assert score >= 0.8  # 0.5 + 0.3

    def test_keyword_boost(self):
        score = _score_importance("Bitcoin hits new high", "", "Other")
        assert score > 0.5  # 0.5 + 0.2 for "bitcoin"

    def test_multiple_keywords(self):
        score = _score_importance(
            "Bitcoin ETF approved by SEC",
            "Crypto funding round announced",
            "Other",
        )
        assert score > 0.7

    def test_capped_at_one(self):
        score = _score_importance(
            "Bitcoin ethereum crypto funding startup venture acquisition IPO AI",
            "bitcoin ethereum crypto funding startup venture acquisition ipo ai",
            "Work/Market",
        )
        assert score <= 1.0


# ── _is_within_days tests ──────────────────────────────────────


class TestIsWithinDays:
    def test_none_published_returns_true(self):
        assert _is_within_days(None, 7) is True

    def test_zero_days_returns_true(self):
        assert _is_within_days("2020-01-01", 0) is True

    def test_recent_date_within_range(self):
        recent = (datetime.now(tz=timezone.utc) - timedelta(days=2)).isoformat()
        assert _is_within_days(recent, 7) is True

    def test_old_date_outside_range(self):
        old = (datetime.now(tz=timezone.utc) - timedelta(days=30)).isoformat()
        assert _is_within_days(old, 7) is False

    def test_unparseable_returns_true(self):
        assert _is_within_days("not-a-date", 7) is True

    def test_iso_datetime_with_z(self):
        recent = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        assert _is_within_days(recent, 7) is True


# ── _parse_published_date tests ─────────────────────────────────


class TestParsePublishedDate:
    def test_with_published_parsed(self):
        entry = MagicMock()
        from time import localtime
        entry.published_parsed = localtime()
        entry.updated_parsed = None
        entry.published = None
        entry.updated = None

        result = _parse_published_date(entry)
        assert result is not None
        assert "T" in result  # ISO format

    def test_with_published_string(self):
        entry = MagicMock()
        entry.published_parsed = None
        entry.updated_parsed = None
        entry.published = "Mon, 20 Jan 2025 12:00:00 GMT"
        entry.updated = None

        result = _parse_published_date(entry)
        assert result == "Mon, 20 Jan 2025 12:00:00 GMT"

    def test_no_date_returns_none(self):
        entry = MagicMock()
        entry.published_parsed = None
        entry.updated_parsed = None
        entry.published = None
        entry.updated = None

        result = _parse_published_date(entry)
        assert result is None


# ── fetch_rss tests ─────────────────────────────────────────────


class TestFetchRss:
    @patch("src.morning.sources.rss._feedparser")
    def test_fetch_rss_returns_items(self, mock_fp):
        entry = MagicMock()
        entry.title = "Test Article"
        entry.link = "https://example.com/article/1"
        entry.published_parsed = None
        entry.updated_parsed = None
        entry.published = None
        entry.updated = None
        entry.summary = "Test summary"

        mock_fp.parse.return_value = MagicMock(entries=[entry])

        items = fetch_rss("https://example.com/rss", "test")
        assert len(items) == 1
        assert items[0].title == "Test Article"
        assert items[0].url == "https://example.com/article/1"
        assert items[0].source == "test"
        assert items[0].importance > 0

    @patch("src.morning.sources.rss._feedparser")
    def test_fetch_rss_skips_no_link(self, mock_fp):
        entry = MagicMock()
        entry.title = "No Link Article"
        entry.link = ""
        entry.summary = "Summary"
        entry.published_parsed = None
        entry.updated_parsed = None
        entry.published = None
        entry.updated = None

        mock_fp.parse.return_value = MagicMock(entries=[entry])

        items = fetch_rss("https://example.com/rss", "test")
        assert len(items) == 0

    @patch("src.morning.sources.rss._feedparser")
    def test_fetch_rss_date_filter(self, mock_fp):
        old_entry = MagicMock()
        old_entry.title = "Old Article"
        old_entry.link = "https://example.com/old"
        old_entry.published_parsed = None
        old_entry.updated_parsed = None
        old_entry.published = (datetime.now(tz=timezone.utc) - timedelta(days=30)).isoformat()
        old_entry.updated = None
        old_entry.summary = "Old"

        new_entry = MagicMock()
        new_entry.title = "New Article"
        new_entry.link = "https://example.com/new"
        new_entry.published_parsed = None
        new_entry.updated_parsed = None
        new_entry.published = datetime.now(tz=timezone.utc).isoformat()
        new_entry.updated = None
        new_entry.summary = "New"

        mock_fp.parse.return_value = MagicMock(entries=[old_entry, new_entry])

        items = fetch_rss("https://example.com/rss", "test", days=7)
        assert len(items) == 1
        assert items[0].title == "New Article"


# ── fetch_twitter_via_nitter tests ──────────────────────────────


class TestFetchTwitterViaNitter:
    @patch("src.morning.sources.twitter._feedparser")
    def test_fetch_tweets(self, mock_fp):
        entry = MagicMock()
        entry.title = "Interesting thread on crypto"
        entry.link = "https://nitter.net/testuser/status/123"
        entry.published_parsed = None
        entry.updated_parsed = None
        entry.published = None
        entry.updated = None
        entry.summary = "A long thread about crypto markets"

        mock_fp.parse.return_value = MagicMock(entries=[entry], bozo=False)

        items = fetch_twitter_via_nitter("testuser", "nitter.net")
        assert len(items) == 1
        assert items[0].source == "twitter/testuser"
        # Should convert Nitter URL to X URL
        assert "x.com" in items[0].url

    @patch("src.morning.sources.twitter._feedparser")
    def test_empty_feed(self, mock_fp):
        mock_fp.parse.return_value = MagicMock(entries=[], bozo=True)

        items = fetch_twitter_via_nitter("testuser", "nitter.net")
        assert len(items) == 0


# ── Config parsing tests ────────────────────────────────────────


class TestConfigParsing:
    def test_get_rss_feeds_empty(self):
        settings = Settings(rss_feeds="")
        assert settings.get_rss_feeds() == {}

    def test_get_rss_feeds_single(self):
        settings = Settings(rss_feeds="TechCrunch:https://techcrunch.com/feed/")
        feeds = settings.get_rss_feeds()
        assert feeds == {"TechCrunch": "https://techcrunch.com/feed/"}

    def test_get_rss_feeds_multiple(self):
        settings = Settings(
            rss_feeds="CoinDesk:https://coindesk.com/rss/,TC:https://techcrunch.com/feed/"
        )
        feeds = settings.get_rss_feeds()
        assert len(feeds) == 2
        assert "CoinDesk" in feeds
        assert "TC" in feeds

    def test_get_twitter_accounts_empty(self):
        settings = Settings(twitter_accounts="")
        assert settings.get_twitter_accounts() == []

    def test_get_twitter_accounts_multiple(self):
        settings = Settings(twitter_accounts="VitalikButerin,balajis,naval")
        accounts = settings.get_twitter_accounts()
        assert accounts == ["VitalikButerin", "balajis", "naval"]


# ── fetch_all_sources tests ─────────────────────────────────────


class TestFetchAllSources:
    @patch("src.morning.sources.fetch_all.get_settings")
    @patch("src.morning.sources.fetch_all.ingest_rss_feeds")
    @patch("src.morning.sources.fetch_all.ingest_twitter_accounts")
    def test_fetch_all_with_config(self, mock_twitter, mock_rss, mock_settings):
        mock_settings.return_value = MagicMock(
            get_rss_feeds=MagicMock(return_value={"TC": "https://tc.com/feed/"}),
            get_twitter_accounts=MagicMock(return_value=["testuser"]),
            nitter_instance="nitter.net",
        )
        mock_rss.return_value = 5
        mock_twitter.return_value = 3

        results = fetch_all_sources(days=7)
        assert results["rss"] == 5
        assert results["twitter"] == 3

    @patch("src.morning.sources.fetch_all.get_settings")
    @patch("src.morning.sources.fetch_all.ingest_rss_feeds")
    @patch("src.morning.sources.fetch_all.ingest_twitter_accounts")
    def test_fetch_all_no_config(self, mock_twitter, mock_rss, mock_settings):
        mock_settings.return_value = MagicMock(
            get_rss_feeds=MagicMock(return_value={}),
            get_twitter_accounts=MagicMock(return_value=[]),
            nitter_instance="nitter.net",
        )

        results = fetch_all_sources(days=7)
        assert results["rss"] == 0
        assert results["twitter"] == 0
        mock_rss.assert_not_called()
        mock_twitter.assert_not_called()
