"""Morning digest builder.

Builds a daily digest from source_items, ranks them,
and writes to Obsidian and the web UI.
"""
import logging
from datetime import date, datetime

from src.app.config import get_settings
from src.morning.rank import rank_items
from src.storage.dao import SourceItemDAO, SourceItem
from src.tagging.classifier import classify

logger = logging.getLogger("sj_home_agent.morning.digest")


def build_digest(target_date: date | None = None) -> str:
    """Build the morning digest markdown.

    Fetches all recent source_items, ranks them,
    returns markdown with Top3 + categorized rest.
    """
    dao = SourceItemDAO()
    all_items = dao.find_all(limit=50)

    ranked = rank_items(all_items)

    d = target_date or date.today()
    top3 = ranked[:3]
    rest = ranked[3:]

    lines = [
        "---",
        f"date: {d.isoformat()}",
        "type: morning_digest",
        f"items: {len(ranked)}",
        "---",
        "",
        f"# Morning Window - {d.isoformat()}",
        "",
        "## Top 3",
        "",
    ]

    for i, item in enumerate(top3, 1):
        category, tags = classify(item.title, item.summary or "")
        lines.append(f"### {i}. {item.title}")
        lines.append(f"- **Source**: {item.source}")
        lines.append(f"- **Link**: {item.url}")
        lines.append(f"- **Category**: {category}")
        if tags:
            lines.append(f"- **Tags**: {', '.join(tags)}")
        if item.summary:
            lines.append(f"- **Summary**: {item.summary[:200]}")
        lines.append("")

    if rest:
        # Group by category
        categories: dict[str, list[SourceItem]] = {}
        for item in rest:
            cat, _ = classify(item.title, item.summary or "")
            group = categories.get(cat, [])
            categories[cat] = [*group, item]

        lines.append("## Other Items (collapsed by default)")
        lines.append("")
        for cat, cat_items in sorted(categories.items()):
            lines.append(f"### {cat}")
            for item in cat_items:
                lines.append(f"- [{item.title}]({item.url}) ({item.source})")
            lines.append("")

    lines.extend([
        "---",
        "",
        "*Recovery-first: take what resonates, leave the rest.*",
        "",
    ])

    markdown = "\n".join(lines)

    # Write to Obsidian
    settings = get_settings()
    morning_dir = settings.morning_path
    morning_dir.mkdir(parents=True, exist_ok=True)
    filepath = morning_dir / f"{d.isoformat()}_Morning_Window.md"
    filepath.write_text(markdown, encoding="utf-8")
    logger.info("Morning digest written to %s", filepath)

    return markdown
