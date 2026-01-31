"""Twitter/X source via Nitter RSS proxy."""
import logging
from datetime import datetime
from typing import Optional

from src.ingest.dedupe import make_source_item_id
from src.storage.dao import SourceItem, SourceItemDAO
from src.tagging.classifier import classify

try:
    import feedparser as _feedparser
except ImportError:
    _feedparser = None

logger = logging.getLogger("sj_home_agent.morning.twitter")


def fetch_twitter_via_nitter(
    username: str,
    nitter_instance: str = "nitter.net",
    days: int = 0,
) -> list[SourceItem]:
    """Fetch tweets from a user via Nitter RSS.

    Nitter provides public RSS feeds for Twitter accounts without API keys.
    Args:
        username: Twitter username (without @)
        nitter_instance: Nitter instance hostname
        days: Only include items from last N days (0 = no filter)
    """
    if _feedparser is None:
        logger.warning("feedparser not installed; Twitter/Nitter disabled")
        return []

    feed_url = f"https://{nitter_instance}/{username}/rss"
    source_name = f"twitter/{username}"
    now = datetime.now().isoformat()
    items: list[SourceItem] = []

    try:
        feed = _feedparser.parse(feed_url)

        if feed.bozo and not feed.entries:
            logger.warning(
                "Nitter feed for @%s returned no entries (instance may be down: %s)",
                username, nitter_instance,
            )
            return []

        from src.morning.sources.rss import _parse_published_date, _is_within_days, _score_importance

        for entry in feed.entries[:50]:
            title = getattr(entry, "title", "")
            link = getattr(entry, "link", "")
            published = _parse_published_date(entry)
            summary = getattr(entry, "summary", None)

            if not link:
                continue

            # Date filtering
            if days > 0 and not _is_within_days(published, days):
                continue

            # Use title or truncated summary as title
            display_title = title if title else (summary[:100] if summary else "Tweet")

            category, tags = classify(display_title, summary or "")
            importance = _score_importance(display_title, summary or "", category)

            # Convert Nitter URLs to Twitter URLs for canonical links
            canonical_link = link.replace(f"https://{nitter_instance}", "https://x.com")

            item_id = make_source_item_id(source_name, canonical_link)
            items.append(SourceItem(
                id=item_id,
                source=source_name,
                title=display_title,
                url=canonical_link,
                published_at=published,
                fetched_at=now,
                summary=summary[:500] if summary else None,
                tags=",".join(tags),
                importance=importance,
                status="new",
            ))

    except Exception as e:
        logger.error("Failed to fetch Nitter feed for @%s: %s", username, e)

    logger.info("Fetched %d tweets from @%s", len(items), username)
    return items


def ingest_twitter_accounts(
    accounts: list[str],
    nitter_instance: str = "nitter.net",
    days: int = 0,
) -> int:
    """Fetch tweets from multiple accounts and save to DB.

    Returns total items ingested.
    """
    dao = SourceItemDAO()
    total = 0
    for username in accounts:
        items = fetch_twitter_via_nitter(username, nitter_instance, days=days)
        for item in items:
            dao.upsert(item)
            total += 1
    logger.info("Ingested %d tweets from %d accounts", total, len(accounts))
    return total
