"""Ranking logic for morning digest items."""
from src.storage.dao import SourceItem
from src.tagging.classifier import classify


WORK_BOOST = 2.0
PERSONAL_INVESTMENT_BOOST = 1.5


def rank_items(items: list[SourceItem]) -> list[SourceItem]:
    """Rank source items by importance, boosting Work and Personal/Investment.

    Returns a new sorted list (does not mutate input).
    """
    scored: list[tuple[SourceItem, float]] = []

    for item in items:
        score = item.importance

        category, _tags = classify(item.title, item.summary or "")

        if category.startswith("Work/"):
            score += WORK_BOOST
        elif category == "Personal/Investment":
            score += PERSONAL_INVESTMENT_BOOST

        scored.append((item, score))

    scored.sort(key=lambda x: x[1], reverse=True)
    return [item for item, _ in scored]
