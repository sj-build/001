"""RSS feed source for morning digest (optional, stub-ready)."""
import logging
from datetime import datetime
from typing import Optional

from src.ingest.dedupe import make_source_item_id
from src.storage.dao import SourceItem, SourceItemDAO

logger = logging.getLogger("sj_home_agent.morning.rss")


def fetch_rss(feed_url: str, source_name: str) -> list[SourceItem]:
    """Fetch and parse an RSS feed, returning SourceItem list.

    Requires feedparser. If not installed, returns empty list.
    """
    try:
        import feedparser
    except ImportError:
        logger.warning("feedparser not installed; RSS disabled")
        return []

    items: list[SourceItem] = []
    now = datetime.now().isoformat()

    try:
        feed = feedparser.parse(feed_url)
        for entry in feed.entries[:20]:
            title = getattr(entry, "title", "Untitled")
            link = getattr(entry, "link", "")
            published = getattr(entry, "published", None)
            summary = getattr(entry, "summary", None)

            if not link:
                continue

            item_id = make_source_item_id(source_name, link)
            items.append(SourceItem(
                id=item_id,
                source=source_name,
                title=title,
                url=link,
                published_at=published,
                fetched_at=now,
                summary=summary[:500] if summary else None,
                tags="",
                importance=0.0,
                status="new",
            ))
    except Exception as e:
        logger.error("Failed to fetch RSS %s: %s", feed_url, e)

    return items


def ingest_rss_feeds(feeds: dict[str, str]) -> int:
    """Fetch multiple RSS feeds and save to DB.

    feeds: dict of {source_name: feed_url}
    Returns total items ingested.
    """
    dao = SourceItemDAO()
    total = 0
    for name, url in feeds.items():
        items = fetch_rss(url, name)
        for item in items:
            dao.upsert(item)
            total += 1
    logger.info("Ingested %d RSS items from %d feeds", total, len(feeds))
    return total
