"""Simple search implementation using SQLite LIKE queries.

This module provides ranked search over conversations using
tag matching, title matching, and preview matching with
configurable weights and recency boosting.
"""
import logging
from datetime import datetime, timedelta
from typing import Optional

from src.storage.dao import ConversationDAO, Conversation

logger = logging.getLogger("sj_home_agent.search")

TAG_WEIGHT = 3.0
TITLE_WEIGHT = 2.0
PREVIEW_WEIGHT = 1.0
RECENCY_BOOST_DAYS = 30
RECENCY_BOOST_FACTOR = 1.5


def _score_conversation(
    conv: Conversation,
    query_terms: list[str],
    query_tags: list[str],
) -> float:
    """Score a conversation against query terms and tags."""
    score = 0.0

    conv_tags_lower = conv.tags.lower()
    title_lower = conv.title.lower()
    preview_lower = (conv.preview or "").lower()

    for tag in query_tags:
        if tag.lower() in conv_tags_lower:
            score += TAG_WEIGHT

    for term in query_terms:
        term_lower = term.lower()
        if term_lower in title_lower:
            score += TITLE_WEIGHT
        if term_lower in preview_lower:
            score += PREVIEW_WEIGHT

    # Recency boost
    try:
        collected = datetime.fromisoformat(conv.collected_at)
        days_ago = (datetime.now() - collected).days
        if days_ago <= RECENCY_BOOST_DAYS:
            score *= RECENCY_BOOST_FACTOR
    except (ValueError, TypeError):
        pass

    return score


def _parse_query(query: str) -> tuple[list[str], list[str]]:
    """Parse query into (terms, tags). Tags start with #."""
    parts = query.split()
    tags = [p for p in parts if p.startswith("#")]
    terms = [p for p in parts if not p.startswith("#")]
    return (terms, tags)


def search(
    query: str,
    days: Optional[int] = None,
    platform: Optional[str] = None,
    limit: int = 20,
) -> list[tuple[Conversation, float]]:
    """Search conversations with ranked results.

    Returns list of (conversation, score) tuples sorted by score desc.
    """
    terms, tags = _parse_query(query)
    dao = ConversationDAO()

    # Use first tag and first term for DB-level filtering
    tag_filter = tags[0] if tags else None
    keyword_filter = terms[0] if terms else None

    candidates = dao.search(
        tags=tag_filter,
        keyword=keyword_filter,
        days=days,
        platform=platform,
        limit=limit * 3,  # Fetch more for re-ranking
    )

    scored = [
        (conv, _score_conversation(conv, terms, tags))
        for conv in candidates
    ]

    # Filter out zero-score results
    scored = [(c, s) for c, s in scored if s > 0]

    # Sort by score descending
    scored.sort(key=lambda x: x[1], reverse=True)

    return scored[:limit]
