"""CDP Chrome profile configuration for multi-account collection.

Maps platforms to Chrome CDP profiles so personal and company accounts
can use separate browser sessions.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.app.config import PROJECT_ROOT


@dataclass(frozen=True)
class CDPProfile:
    """A Chrome CDP profile bound to specific platforms."""

    name: str
    platforms: tuple[str, ...]


DEFAULT_PROFILES: tuple[CDPProfile, ...] = (
    CDPProfile(name="personal", platforms=("claude", "chatgpt")),
    CDPProfile(name="company", platforms=("gemini", "fyxer", "granola")),
)


def get_profile_for_platform(
    platform: str,
    profiles: tuple[CDPProfile, ...] = DEFAULT_PROFILES,
) -> CDPProfile | None:
    """Return the CDPProfile that owns the given platform, or None."""
    for profile in profiles:
        if platform in profile.platforms:
            return profile
    return None


def get_cdp_data_dir(profile: CDPProfile) -> Path:
    """Return the CDP user-data-dir for a profile."""
    return PROJECT_ROOT / "data" / "chrome_cdp_profiles" / profile.name


def group_platforms_by_profile(
    platforms: list[str],
    profiles: tuple[CDPProfile, ...] = DEFAULT_PROFILES,
) -> list[tuple[CDPProfile | None, list[str]]]:
    """Group platforms by their CDP profile.

    Returns a list of (profile, platforms) tuples, preserving input order.
    Platforms without a mapped profile are grouped under None (legacy fallback).
    """
    seen_keys: list[str | None] = []
    groups: dict[str | None, tuple[CDPProfile | None, list[str]]] = {}

    for platform in platforms:
        profile = get_profile_for_platform(platform, profiles)
        key = profile.name if profile else None
        if key not in groups:
            seen_keys.append(key)
            groups[key] = (profile, [])
        groups[key][1].append(platform)

    return [groups[k] for k in seen_keys]
