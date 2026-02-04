"""Tests for CDP profile configuration and helpers."""
import pytest
from dataclasses import FrozenInstanceError
from pathlib import Path

from src.app.config import PROJECT_ROOT
from src.app.profiles import (
    CDPProfile,
    DEFAULT_PROFILES,
    get_cdp_data_dir,
    get_profile_for_platform,
    group_platforms_by_profile,
)


# ── CDPProfile immutability ──────────────────────────────────────


class TestCDPProfileImmutability:
    """Verify CDPProfile is a frozen dataclass."""

    def test_cannot_mutate_name(self):
        profile = CDPProfile(name="test", platforms=("a",))
        with pytest.raises(FrozenInstanceError):
            profile.name = "changed"

    def test_cannot_mutate_platforms(self):
        profile = CDPProfile(name="test", platforms=("a",))
        with pytest.raises(FrozenInstanceError):
            profile.platforms = ("b",)

    def test_equality(self):
        a = CDPProfile(name="x", platforms=("gemini",))
        b = CDPProfile(name="x", platforms=("gemini",))
        assert a == b

    def test_hashable(self):
        profile = CDPProfile(name="test", platforms=("gemini",))
        assert hash(profile) == hash(CDPProfile(name="test", platforms=("gemini",)))


# ── DEFAULT_PROFILES ─────────────────────────────────────────────


class TestDefaultProfiles:
    """Verify the default profile definitions."""

    def test_company_profile_exists(self):
        names = [p.name for p in DEFAULT_PROFILES]
        assert "company" in names

    def test_only_company_profile(self):
        assert len(DEFAULT_PROFILES) == 1
        assert DEFAULT_PROFILES[0].name == "company"

    def test_company_platforms(self):
        company = next(p for p in DEFAULT_PROFILES if p.name == "company")
        assert "gemini" in company.platforms
        assert "fyxer" not in company.platforms

    def test_no_platform_overlap(self):
        all_platforms: list[str] = []
        for profile in DEFAULT_PROFILES:
            for p in profile.platforms:
                assert p not in all_platforms, f"{p} appears in multiple profiles"
                all_platforms.append(p)


# ── get_profile_for_platform ─────────────────────────────────────


class TestGetProfileForPlatform:
    """Test platform -> profile lookup."""

    def test_claude_not_in_cdp_profiles(self):
        profile = get_profile_for_platform("claude")
        assert profile is None  # claude uses API, not CDP

    def test_chatgpt_not_in_cdp_profiles(self):
        profile = get_profile_for_platform("chatgpt")
        assert profile is None  # chatgpt uses API, not CDP

    def test_gemini_maps_to_company(self):
        profile = get_profile_for_platform("gemini")
        assert profile is not None
        assert profile.name == "company"

    def test_fyxer_not_in_cdp_profiles(self):
        profile = get_profile_for_platform("fyxer")
        assert profile is None  # fyxer now uses API, not CDP

    def test_granola_not_in_cdp_profiles(self):
        profile = get_profile_for_platform("granola")
        assert profile is None  # granola uses API, not CDP

    def test_unknown_platform_returns_none(self):
        result = get_profile_for_platform("unknown_platform")
        assert result is None

    def test_custom_profiles(self):
        custom = (CDPProfile(name="custom", platforms=("foo", "bar")),)
        assert get_profile_for_platform("foo", profiles=custom).name == "custom"
        assert get_profile_for_platform("baz", profiles=custom) is None


# ── get_cdp_data_dir ─────────────────────────────────────────────


class TestGetCdpDataDir:
    """Test CDP data directory path generation."""

    def test_company_dir(self):
        profile = CDPProfile(name="company", platforms=("gemini",))
        result = get_cdp_data_dir(profile)
        expected = PROJECT_ROOT / "data" / "chrome_cdp_profiles" / "company"
        assert result == expected

    def test_arbitrary_name_dir(self):
        profile = CDPProfile(name="custom", platforms=("x",))
        result = get_cdp_data_dir(profile)
        expected = PROJECT_ROOT / "data" / "chrome_cdp_profiles" / "custom"
        assert result == expected

    def test_returns_path_object(self):
        profile = CDPProfile(name="test", platforms=("x",))
        result = get_cdp_data_dir(profile)
        assert isinstance(result, Path)


# ── group_platforms_by_profile ───────────────────────────────────


class TestGroupPlatformsByProfile:
    """Test platform grouping by profile."""

    def test_cdp_platforms_grouped(self):
        platforms = ["gemini"]
        groups = group_platforms_by_profile(platforms)

        assert len(groups) == 1
        assert groups[0][0].name == "company"
        assert groups[0][1] == ["gemini"]

    def test_api_platforms_grouped_under_none(self):
        platforms = ["claude", "chatgpt", "granola"]
        groups = group_platforms_by_profile(platforms)

        assert len(groups) == 1
        assert groups[0][0] is None
        assert set(groups[0][1]) == {"claude", "chatgpt", "granola"}

    def test_mixed_cdp_and_api_platforms(self):
        platforms = ["gemini", "claude", "fyxer"]
        groups = group_platforms_by_profile(platforms)

        assert len(groups) == 2
        assert groups[0][0].name == "company"
        assert groups[0][1] == ["gemini"]

        assert groups[1][0] is None
        assert set(groups[1][1]) == {"claude", "fyxer"}

    def test_preserves_input_order(self):
        platforms = ["claude", "gemini"]
        groups = group_platforms_by_profile(platforms)

        assert groups[0][0] is None  # claude first (API, no profile)
        assert groups[1][0].name == "company"  # gemini second

    def test_unknown_platform_grouped_under_none(self):
        groups = group_platforms_by_profile(["unknown_platform"])
        assert len(groups) == 1
        profile, platforms = groups[0]
        assert profile is None
        assert platforms == ["unknown_platform"]

    def test_empty_list(self):
        groups = group_platforms_by_profile([])
        assert groups == []

    def test_custom_profiles(self):
        custom = (CDPProfile(name="alpha", platforms=("a", "b")),)
        groups = group_platforms_by_profile(["a", "b", "c"], profiles=custom)

        assert len(groups) == 2
        assert groups[0][0].name == "alpha"
        assert set(groups[0][1]) == {"a", "b"}
        assert groups[1][0] is None
        assert groups[1][1] == ["c"]
