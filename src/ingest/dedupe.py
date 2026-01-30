"""Deduplication utilities using content hashing."""
import hashlib


def make_conversation_id(platform: str, url: str) -> str:
    """Stable hash ID from platform + url."""
    raw = f"{platform.lower().strip()}:{url.strip().rstrip('/')}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def make_content_hash(title: str, preview: str = "") -> str:
    """Hash of content for change detection."""
    raw = f"{title}:{preview}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def make_source_item_id(source: str, url: str) -> str:
    """Stable hash ID for source items."""
    raw = f"{source.lower().strip()}:{url.strip().rstrip('/')}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
