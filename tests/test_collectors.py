"""Tests for collector base helpers and individual collectors."""
import pytest
from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock, patch, call

from src.collectors.base import BaseCollector
from src.collectors.claude import ClaudeCollector
from src.collectors.chatgpt import ChatGPTCollector
from src.collectors.gemini import GeminiCollector
from src.collectors.fyxer import FyxerCollector
from src.collectors.runner import (
    _close_cdp_chrome, _filter_by_date, _is_cdp_available,
    _launch_chrome_with_cdp, _prepare_cdp_profile, run_all,
)
from src.ingest.normalize import RawConversation


# ── _extract_date_from_text tests ───────────────────────────────


class TestExtractDateFromText:
    """Test the static date extraction helper."""

    def test_today(self):
        result = BaseCollector._extract_date_from_text("Today")
        assert result == date.today().isoformat()

    def test_today_lowercase(self):
        result = BaseCollector._extract_date_from_text("today")
        assert result == date.today().isoformat()

    def test_yesterday(self):
        result = BaseCollector._extract_date_from_text("Yesterday")
        expected = (date.today() - timedelta(days=1)).isoformat()
        assert result == expected

    def test_n_days_ago(self):
        result = BaseCollector._extract_date_from_text("5 days ago")
        expected = (date.today() - timedelta(days=5)).isoformat()
        assert result == expected

    def test_one_day_ago(self):
        result = BaseCollector._extract_date_from_text("1 day ago")
        expected = (date.today() - timedelta(days=1)).isoformat()
        assert result == expected

    def test_n_weeks_ago(self):
        result = BaseCollector._extract_date_from_text("2 weeks ago")
        expected = (date.today() - timedelta(weeks=2)).isoformat()
        assert result == expected

    def test_iso_date(self):
        result = BaseCollector._extract_date_from_text("2025-01-15")
        assert result == "2025-01-15"

    def test_iso_datetime(self):
        result = BaseCollector._extract_date_from_text("2025-01-15T10:30:00")
        assert result == "2025-01-15"

    def test_mdy_format(self):
        result = BaseCollector._extract_date_from_text("01/15/2025")
        assert result == "2025-01-15"

    def test_empty_string(self):
        result = BaseCollector._extract_date_from_text("")
        assert result is None

    def test_none(self):
        result = BaseCollector._extract_date_from_text(None)
        assert result is None

    def test_unrecognized_text(self):
        result = BaseCollector._extract_date_from_text("Hello world")
        assert result is None

    def test_embedded_date(self):
        result = BaseCollector._extract_date_from_text("Created on 2025-03-20 by user")
        assert result == "2025-03-20"


# ── _find_working_selector tests ────────────────────────────────


class TestFindWorkingSelector:
    """Test the working selector finder with mocked page."""

    @pytest.mark.asyncio
    async def test_finds_first_matching_selector(self):
        page = AsyncMock()

        # First selector returns 0, second returns 3
        locator_mock_1 = AsyncMock()
        locator_mock_1.count = AsyncMock(return_value=0)
        locator_mock_2 = AsyncMock()
        locator_mock_2.count = AsyncMock(return_value=3)

        def locator_side_effect(sel):
            if sel == "a.first":
                return locator_mock_1
            return locator_mock_2

        page.locator = MagicMock(side_effect=locator_side_effect)

        collector = ClaudeCollector()
        result = await collector._find_working_selector(page, ["a.first", "a.second"])
        assert result == "a.second"

    @pytest.mark.asyncio
    async def test_returns_none_when_no_match(self):
        page = AsyncMock()
        locator_mock = AsyncMock()
        locator_mock.count = AsyncMock(return_value=0)
        page.locator = MagicMock(return_value=locator_mock)

        collector = ClaudeCollector()
        result = await collector._find_working_selector(page, ["a.first", "a.second"])
        assert result is None

    @pytest.mark.asyncio
    async def test_handles_exception_gracefully(self):
        page = AsyncMock()
        locator_mock = AsyncMock()
        locator_mock.count = AsyncMock(side_effect=Exception("timeout"))
        page.locator = MagicMock(return_value=locator_mock)

        collector = ClaudeCollector()
        result = await collector._find_working_selector(page, ["a.first"])
        assert result is None


# ── _wait_for_content tests ─────────────────────────────────────


class TestWaitForContent:
    """Test the content polling helper."""

    @pytest.mark.asyncio
    async def test_finds_content_on_first_attempt(self):
        page = AsyncMock()
        locator_mock = AsyncMock()
        locator_mock.count = AsyncMock(return_value=5)
        page.locator = MagicMock(return_value=locator_mock)
        page.wait_for_timeout = AsyncMock()

        collector = ClaudeCollector()
        result = await collector._wait_for_content(
            page, ["a.test"], max_attempts=3, poll_interval=100,
        )
        assert result == "a.test"

    @pytest.mark.asyncio
    async def test_returns_none_after_max_attempts(self):
        page = AsyncMock()
        locator_mock = AsyncMock()
        locator_mock.count = AsyncMock(return_value=0)
        page.locator = MagicMock(return_value=locator_mock)
        page.wait_for_timeout = AsyncMock()

        collector = ClaudeCollector()
        result = await collector._wait_for_content(
            page, ["a.test"], max_attempts=2, poll_interval=100,
        )
        assert result is None


# ── _scroll_to_load_all tests ───────────────────────────────────


class TestScrollToLoadAll:
    """Test scroll-to-load helper."""

    @pytest.mark.asyncio
    async def test_stops_when_no_new_elements(self):
        page = AsyncMock()
        locator_mock = AsyncMock()
        locator_mock.count = AsyncMock(return_value=10)
        page.locator = MagicMock(return_value=locator_mock)
        page.evaluate = AsyncMock()
        page.wait_for_timeout = AsyncMock()

        collector = ClaudeCollector()
        count = await collector._scroll_to_load_all(
            page, "a.test", max_scrolls=3, scroll_delay=100,
        )
        assert count == 10

    @pytest.mark.asyncio
    async def test_loads_more_elements(self):
        page = AsyncMock()
        locator_mock = AsyncMock()
        # 5 -> 10 -> 10 (stop)
        locator_mock.count = AsyncMock(side_effect=[5, 10, 10])
        page.locator = MagicMock(return_value=locator_mock)
        page.evaluate = AsyncMock()
        page.wait_for_timeout = AsyncMock()

        collector = ClaudeCollector()
        count = await collector._scroll_to_load_all(
            page, "a.test", max_scrolls=5, scroll_delay=100,
        )
        assert count == 10


# ── Collector login check tests ─────────────────────────────────


class TestClaudeCheckLogin:
    """Test ClaudeCollector login detection."""

    @pytest.mark.asyncio
    async def test_detects_login_redirect(self):
        page = AsyncMock()
        page.url = "https://claude.ai/login"
        page.wait_for_timeout = AsyncMock()

        collector = ClaudeCollector()
        result = await collector.check_login(page)
        assert result is False

    @pytest.mark.asyncio
    async def test_confirms_login_via_selector(self):
        page = AsyncMock()
        page.url = "https://claude.ai/recents"
        page.wait_for_timeout = AsyncMock()
        locator_mock = AsyncMock()
        locator_mock.count = AsyncMock(return_value=5)
        page.locator = MagicMock(return_value=locator_mock)

        collector = ClaudeCollector()
        result = await collector.check_login(page)
        assert result is True


class TestChatGPTCheckLogin:
    """Test ChatGPTCollector login detection."""

    @pytest.mark.asyncio
    async def test_detects_auth_redirect(self):
        page = AsyncMock()
        page.url = "https://chatgpt.com/auth/login"
        page.wait_for_timeout = AsyncMock()

        collector = ChatGPTCollector()
        result = await collector.check_login(page)
        assert result is False


class TestGeminiCheckLogin:
    """Test GeminiCollector login detection."""

    @pytest.mark.asyncio
    async def test_detects_signin_redirect(self):
        page = AsyncMock()
        page.url = "https://accounts.google.com/signin"
        page.wait_for_timeout = AsyncMock()

        collector = GeminiCollector()
        result = await collector.check_login(page)
        assert result is False


# ── _filter_by_date tests ───────────────────────────────────────


class TestFilterByDate:
    """Test date filtering in runner."""

    def test_keeps_items_without_date(self):
        convs = [
            RawConversation(platform="claude", title="No date", url="https://example.com/1"),
        ]
        result = _filter_by_date(convs, days=30)
        assert len(result) == 1

    def test_keeps_recent_items(self):
        today = date.today().isoformat()
        convs = [
            RawConversation(
                platform="claude", title="Recent", url="https://example.com/1",
                date=today,
            ),
        ]
        result = _filter_by_date(convs, days=30)
        assert len(result) == 1

    def test_filters_old_items(self):
        old_date = (date.today() - timedelta(days=60)).isoformat()
        convs = [
            RawConversation(
                platform="claude", title="Old", url="https://example.com/1",
                date=old_date,
            ),
        ]
        result = _filter_by_date(convs, days=30)
        assert len(result) == 0

    def test_mixed_items(self):
        today = date.today().isoformat()
        old_date = (date.today() - timedelta(days=60)).isoformat()
        convs = [
            RawConversation(platform="claude", title="No date", url="https://example.com/1"),
            RawConversation(platform="claude", title="Recent", url="https://example.com/2", date=today),
            RawConversation(platform="claude", title="Old", url="https://example.com/3", date=old_date),
        ]
        result = _filter_by_date(convs, days=30)
        assert len(result) == 2
        titles = [c.title for c in result]
        assert "No date" in titles
        assert "Recent" in titles
        assert "Old" not in titles


# ── Collector get_conversation_list tests ────────────────────────


class TestCollectorConversationList:
    """Test conversation list extraction with mocked page."""

    @pytest.mark.asyncio
    async def test_claude_extracts_conversations(self):
        page = AsyncMock()
        page.wait_for_timeout = AsyncMock()

        # Mock _find_working_selector to return a selector
        locator_mock = AsyncMock()
        locator_mock.count = AsyncMock(return_value=2)

        el1 = AsyncMock()
        el1.get_attribute = AsyncMock(return_value="/chat/abc123")
        el1.inner_text = AsyncMock(return_value="Test Conversation")
        parent1 = AsyncMock()
        parent1.inner_text = AsyncMock(return_value="Test Conversation Today some preview text")
        el1.locator = MagicMock(return_value=parent1)

        el2 = AsyncMock()
        el2.get_attribute = AsyncMock(return_value="/chat/def456")
        el2.inner_text = AsyncMock(return_value="Another Chat")
        parent2 = AsyncMock()
        parent2.inner_text = AsyncMock(return_value="Another Chat")
        el2.locator = MagicMock(return_value=parent2)

        locator_mock.all = AsyncMock(return_value=[el1, el2])

        page.locator = MagicMock(return_value=locator_mock)
        page.evaluate = AsyncMock()

        collector = ClaudeCollector()
        result = await collector.get_conversation_list(page)

        assert len(result) == 2
        assert result[0].title == "Test Conversation"
        assert result[0].url == "https://claude.ai/chat/abc123"
        assert result[1].title == "Another Chat"

    @pytest.mark.asyncio
    async def test_chatgpt_skips_invalid_hrefs(self):
        page = AsyncMock()
        page.wait_for_timeout = AsyncMock()

        locator_mock = AsyncMock()
        locator_mock.count = AsyncMock(return_value=1)

        el = AsyncMock()
        el.get_attribute = AsyncMock(return_value="/settings")
        el.inner_text = AsyncMock(return_value="Settings")

        locator_mock.all = AsyncMock(return_value=[el])
        page.locator = MagicMock(return_value=locator_mock)
        page.evaluate = AsyncMock()

        collector = ChatGPTCollector()
        result = await collector.get_conversation_list(page)
        assert len(result) == 0


# ── CDP helper tests ──────────────────────────────────────────


class TestIsCdpAvailable:
    """Test CDP port detection."""

    @patch("src.collectors.runner.socket.create_connection")
    def test_returns_true_when_port_open(self, mock_conn):
        mock_conn.return_value.__enter__ = MagicMock()
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)
        assert _is_cdp_available(9222) is True

    @patch("src.collectors.runner.socket.create_connection")
    def test_returns_false_when_port_closed(self, mock_conn):
        mock_conn.side_effect = ConnectionRefusedError
        assert _is_cdp_available(9222) is False

    @patch("src.collectors.runner.socket.create_connection")
    def test_returns_false_on_os_error(self, mock_conn):
        mock_conn.side_effect = OSError("timeout")
        assert _is_cdp_available(9222) is False


class TestLaunchChromeWithCdp:
    """Test Chrome launch with CDP."""

    @patch("src.collectors.runner._is_cdp_available")
    @patch("src.collectors.runner.subprocess.Popen")
    def test_launch_success(self, mock_popen, mock_cdp, tmp_path):
        import src.collectors.runner as runner_mod

        mock_cdp.side_effect = [False, True]  # not available, then available
        mock_proc = MagicMock()
        mock_proc.pid = 12345
        mock_popen.return_value = mock_proc

        result = _launch_chrome_with_cdp(
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            9222,
            tmp_path / "cdp",
        )
        assert result == mock_proc
        assert runner_mod._cdp_proc == mock_proc

    @patch("src.collectors.runner._is_cdp_available", return_value=False)
    @patch("src.collectors.runner.subprocess.Popen")
    @patch("src.collectors.runner.time.sleep")
    def test_launch_timeout(self, mock_sleep, mock_popen, mock_cdp, tmp_path):
        mock_proc = MagicMock()
        mock_popen.return_value = mock_proc

        with pytest.raises(TimeoutError):
            _launch_chrome_with_cdp(
                "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                9222,
                tmp_path / "cdp",
            )
        mock_proc.kill.assert_called_once()

    def test_launch_chrome_not_found(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            _launch_chrome_with_cdp("/nonexistent/path/to/chrome", 9222, tmp_path / "cdp")


class TestPrepareCdpProfile:
    """Test Chrome profile copy for CDP."""

    def test_copies_essential_files(self, tmp_path):
        # Create fake Chrome profile
        source = tmp_path / "Chrome" / "Default"
        source.mkdir(parents=True)
        (source / "Cookies").write_text("cookie-data")
        (source / "Preferences").write_text("pref-data")
        (source.parent / "Local State").write_text("local-state")

        cdp_dir = tmp_path / "cdp_profile"
        _prepare_cdp_profile(source, cdp_dir)

        assert (cdp_dir / "Default" / "Cookies").read_text() == "cookie-data"
        assert (cdp_dir / "Default" / "Preferences").read_text() == "pref-data"
        assert (cdp_dir / "Local State").read_text() == "local-state"

    def test_skips_missing_files(self, tmp_path):
        source = tmp_path / "Chrome" / "Default"
        source.mkdir(parents=True)
        # Only Cookies exists
        (source / "Cookies").write_text("cookie-data")

        cdp_dir = tmp_path / "cdp_profile"
        _prepare_cdp_profile(source, cdp_dir)

        assert (cdp_dir / "Default" / "Cookies").exists()
        assert not (cdp_dir / "Default" / "Login Data").exists()


# ── _close_cdp_chrome tests ───────────────────────────────────────


class TestCloseCdpChrome:
    """Test CDP Chrome shutdown (only kills our process, not user Chrome)."""

    def test_noop_when_no_cdp_proc(self):
        import src.collectors.runner as runner_mod
        runner_mod._cdp_proc = None
        _close_cdp_chrome()
        # Should not raise or attempt to kill anything

    @patch("src.collectors.runner.os.kill")
    def test_graceful_shutdown(self, mock_kill):
        import src.collectors.runner as runner_mod

        mock_proc = MagicMock()
        mock_proc.pid = 12345
        mock_proc.wait = MagicMock(return_value=0)
        runner_mod._cdp_proc = mock_proc

        _close_cdp_chrome()

        import signal
        mock_kill.assert_called_once_with(12345, signal.SIGTERM)
        assert runner_mod._cdp_proc is None

    @patch("src.collectors.runner.os.kill")
    def test_force_kill_after_timeout(self, mock_kill):
        import subprocess as sp
        import src.collectors.runner as runner_mod

        mock_proc = MagicMock()
        mock_proc.pid = 12345
        mock_proc.wait = MagicMock(side_effect=[sp.TimeoutExpired("chrome", 5), None])
        runner_mod._cdp_proc = mock_proc

        _close_cdp_chrome()

        import signal
        sigterm_calls = [c for c in mock_kill.call_args_list if c == call(12345, signal.SIGTERM)]
        sigkill_calls = [c for c in mock_kill.call_args_list if c == call(12345, signal.SIGKILL)]
        assert len(sigterm_calls) == 1
        assert len(sigkill_calls) == 1
        assert runner_mod._cdp_proc is None

    @patch("src.collectors.runner.time.sleep")
    @patch("src.collectors.runner._is_cdp_available")
    @patch("src.collectors.runner.os.kill")
    def test_waits_for_cdp_port_freed(self, mock_kill, mock_cdp, mock_sleep):
        import src.collectors.runner as runner_mod

        mock_proc = MagicMock()
        mock_proc.pid = 12345
        mock_proc.wait = MagicMock(return_value=0)
        runner_mod._cdp_proc = mock_proc

        mock_cdp.side_effect = [True, True, False]

        _close_cdp_chrome(cdp_port=9222)

        assert mock_cdp.call_count == 3


# ── Profile-aware run_all tests ──────────────────────────────────


class TestRunAllWithProfiles:
    """Test run_all with profile grouping and switching."""

    @pytest.mark.asyncio
    @patch("src.collectors.runner._close_cdp_chrome")
    @patch("src.collectors.runner._persist_conversations", return_value=5)
    @patch("src.collectors.runner.run_collector")
    @patch("src.collectors.runner.init_db")
    async def test_groups_by_profile(self, mock_init, mock_collector, mock_persist, mock_close):
        mock_collector.return_value = [
            RawConversation(platform="claude", title="Test", url="https://example.com/1"),
        ]

        results = await run_all(platforms=["claude", "chatgpt", "gemini"])

        assert "claude" in results
        assert "chatgpt" in results
        assert "gemini" in results

    @pytest.mark.asyncio
    @patch("src.collectors.runner._close_cdp_chrome")
    @patch("src.collectors.runner._persist_conversations", return_value=3)
    @patch("src.collectors.runner.run_collector")
    @patch("src.collectors.runner.init_db")
    async def test_chrome_restart_on_profile_switch(self, mock_init, mock_collector, mock_persist, mock_close):
        mock_collector.return_value = []

        await run_all(platforms=["claude", "gemini"])

        # Should close Chrome when switching from personal to company
        mock_close.assert_called_once()

    @pytest.mark.asyncio
    @patch("src.collectors.runner._close_cdp_chrome")
    @patch("src.collectors.runner._persist_conversations", return_value=2)
    @patch("src.collectors.runner.run_collector")
    @patch("src.collectors.runner.init_db")
    async def test_no_restart_within_same_profile(self, mock_init, mock_collector, mock_persist, mock_close):
        mock_collector.return_value = []

        await run_all(platforms=["claude", "chatgpt"])

        # Both are personal profile, no restart needed
        mock_close.assert_not_called()

    @pytest.mark.asyncio
    @patch("src.collectors.runner._close_cdp_chrome")
    @patch("src.collectors.runner._persist_conversations", return_value=1)
    @patch("src.collectors.runner.run_collector")
    @patch("src.collectors.runner.init_db")
    async def test_profile_override(self, mock_init, mock_collector, mock_persist, mock_close):
        mock_collector.return_value = []

        results = await run_all(
            platforms=["gemini"],
            profile_override="personal",
        )

        # Gemini forced to use personal profile
        assert "gemini" in results
        # No profile switch since everything is one profile
        mock_close.assert_not_called()

    @pytest.mark.asyncio
    @patch("src.collectors.runner.init_db")
    async def test_unknown_profile_override(self, mock_init):
        results = await run_all(
            platforms=["claude"],
            profile_override="nonexistent",
        )
        assert results == {}
