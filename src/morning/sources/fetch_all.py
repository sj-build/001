"""Unified news fetcher: RSS + Twitter/Nitter."""
import logging

from src.app.config import get_settings
from src.morning.sources.rss import ingest_rss_feeds
from src.morning.sources.twitter import ingest_twitter_accounts

logger = logging.getLogger("sj_home_agent.morning.fetch_all")


def fetch_all_sources(days: int = 7) -> dict[str, int]:
    """Fetch news from all configured sources.

    Returns {source_type: count} dict.
    """
    settings = get_settings()
    results: dict[str, int] = {}

    # RSS feeds
    rss_feeds = settings.get_rss_feeds()
    if rss_feeds:
        rss_count = ingest_rss_feeds(rss_feeds, days=days)
        results["rss"] = rss_count
        logger.info("RSS: %d items from %d feeds", rss_count, len(rss_feeds))
    else:
        results["rss"] = 0
        logger.info("No RSS feeds configured")

    # Twitter via Nitter
    twitter_accounts = settings.get_twitter_accounts()
    if twitter_accounts:
        twitter_count = ingest_twitter_accounts(
            twitter_accounts,
            nitter_instance=settings.nitter_instance,
            days=days,
        )
        results["twitter"] = twitter_count
        logger.info("Twitter: %d items from %d accounts", twitter_count, len(twitter_accounts))
    else:
        results["twitter"] = 0
        logger.info("No Twitter accounts configured")

    total = sum(results.values())
    logger.info("Total fetched: %d items", total)
    return results
