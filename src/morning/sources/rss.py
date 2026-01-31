"""RSS feed source for morning digest."""
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from src.ingest.dedupe import make_source_item_id
from src.storage.dao import SourceItem, SourceItemDAO
from src.tagging.classifier import classify

try:
    import feedparser as _feedparser
except ImportError:
    _feedparser = None

logger = logging.getLogger("sj_home_agent.morning.rss")

IMPORTANCE_KEYWORDS = {
    "bitcoin": 0.2,
    "ethereum": 0.2,
    "crypto": 0.2,
    "ai": 0.15,
    "fundraise": 0.2,
    "acquisition": 0.2,
    "ipo": 0.2,
    "funding": 0.2,
    "venture": 0.15,
    "startup": 0.1,
}


def _score_importance(title: str, summary: str, category: str) -> float:
    """Score importance of a news item.

    Base 0.5, +0.3 for Work/*, +0.2 for Crypto-related, keyword boosts.
    """
    score = 0.5

    if category.startswith("Work/"):
        score += 0.3
    if "Investment" in category or "Crypto" in category.lower():
        score += 0.2

    combined = f"{title} {summary}".lower()
    for keyword, boost in IMPORTANCE_KEYWORDS.items():
        if keyword in combined:
            score += boost

    return min(score, 1.0)


def _parse_published_date(entry) -> Optional[str]:
    """Extract published date from feed entry."""
    for attr in ("published_parsed", "updated_parsed"):
        parsed = getattr(entry, attr, None)
        if parsed:
            try:
                from time import mktime
                dt = datetime.fromtimestamp(mktime(parsed), tz=timezone.utc)
                return dt.isoformat()
            except Exception:
                continue

    for attr in ("published", "updated"):
        val = getattr(entry, attr, None)
        if val:
            return val

    return None


def _is_within_days(published_str: Optional[str], days: int) -> bool:
    """Check if a published date string is within N days of now."""
    if not published_str or days <= 0:
        return True

    try:
        # Try ISO format
        if "T" in published_str:
            dt = datetime.fromisoformat(published_str.replace("Z", "+00:00"))
        else:
            dt = datetime.fromisoformat(published_str)

        cutoff = datetime.now(tz=timezone.utc) - timedelta(days=days)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt >= cutoff
    except Exception:
        # Can't parse date, include it (conservative)
        return True


def fetch_rss(feed_url: str, source_name: str, days: int = 0) -> list[SourceItem]:
    """Fetch and parse an RSS feed, returning SourceItem list.

    Requires feedparser. If not installed, returns empty list.
    Args:
        feed_url: URL of the RSS feed
        source_name: Name to identify the source
        days: Only include items from last N days (0 = no filter)
    """
    if _feedparser is None:
        logger.warning("feedparser not installed; RSS disabled")
        return []

    items: list[SourceItem] = []
    now = datetime.now().isoformat()

    try:
        feed = _feedparser.parse(feed_url)
        for entry in feed.entries[:50]:
            title = getattr(entry, "title", "Untitled")
            link = getattr(entry, "link", "")
            published = _parse_published_date(entry)
            summary = getattr(entry, "summary", None)

            if not link:
                continue

            # Date filtering
            if days > 0 and not _is_within_days(published, days):
                continue

            # Classification and importance scoring
            category, tags = classify(title, summary or "")
            importance = _score_importance(title, summary or "", category)

            item_id = make_source_item_id(source_name, link)
            items.append(SourceItem(
                id=item_id,
                source=source_name,
                title=title,
                url=link,
                published_at=published,
                fetched_at=now,
                summary=summary[:500] if summary else None,
                tags=",".join(tags),
                importance=importance,
                status="new",
            ))
    except Exception as e:
        logger.error("Failed to fetch RSS %s: %s", feed_url, e)

    return items


def ingest_rss_feeds(feeds: dict[str, str], days: int = 0) -> int:
    """Fetch multiple RSS feeds and save to DB.

    feeds: dict of {source_name: feed_url}
    days: only include items from last N days (0 = no filter)
    Returns total items ingested.
    """
    dao = SourceItemDAO()
    total = 0
    for name, url in feeds.items():
        items = fetch_rss(url, name, days=days)
        for item in items:
            dao.upsert(item)
            total += 1
    logger.info("Ingested %d RSS items from %d feeds", total, len(feeds))
    return total
