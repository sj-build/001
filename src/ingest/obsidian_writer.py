"""Write collected conversations as Obsidian markdown files."""
from datetime import date
from pathlib import Path
from typing import Sequence

from src.app.config import get_settings
from src.ingest.normalize import RawConversation


def _format_entry(conv: RawConversation, category: str, tags: list[str]) -> str:
    """Format a single conversation entry as markdown."""
    lines = [
        f"### {conv.title}",
        f"- **Platform**: {conv.platform}",
        f"- **URL**: {conv.url}",
        f"- **Category**: {category}",
    ]
    if tags:
        lines.append(f"- **Tags**: {', '.join(tags)}")
    if conv.date:
        lines.append(f"- **Date**: {conv.date}")
    if conv.preview:
        lines.append(f"- **Preview**: {conv.preview[:200]}")
    lines.append("")
    return "\n".join(lines)


def write_daily_collection(
    platform: str,
    conversations: Sequence[tuple[RawConversation, str, list[str]]],
    target_date: date | None = None,
) -> Path:
    """Write a daily collection markdown file.

    Each entry is a tuple of (RawConversation, category, tags).
    Returns the path of the written file.
    """
    settings = get_settings()
    d = target_date or date.today()
    filename = f"{d.isoformat()}_{platform}_수집.md"
    filepath = settings.output_path / filename

    settings.output_path.mkdir(parents=True, exist_ok=True)

    frontmatter = "\n".join([
        "---",
        f"date: {d.isoformat()}",
        f"platform: {platform}",
        f"type: collection",
        f"items: {len(conversations)}",
        "---",
        "",
        f"# {platform} Collection - {d.isoformat()}",
        "",
    ])

    entries = "\n".join(
        _format_entry(conv, cat, tags)
        for conv, cat, tags in conversations
    )

    content = frontmatter + entries
    filepath.write_text(content, encoding="utf-8")
    return filepath
