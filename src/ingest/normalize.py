"""Normalize collected conversation data."""
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class RawConversation:
    platform: str
    title: str
    url: str
    date: Optional[str] = None
    preview: Optional[str] = None


def normalize_title(title: str) -> str:
    """Strip whitespace, collapse multiple spaces."""
    return " ".join(title.split()).strip()


def normalize_url(url: str) -> str:
    """Strip trailing slashes and whitespace."""
    return url.strip().rstrip("/")


def normalize_conversation(raw: RawConversation) -> RawConversation:
    """Return a new normalized conversation (immutable)."""
    return RawConversation(
        platform=raw.platform.lower().strip(),
        title=normalize_title(raw.title),
        url=normalize_url(raw.url),
        date=raw.date,
        preview=raw.preview.strip() if raw.preview else None,
    )
