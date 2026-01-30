"""Context bundle generator.

Creates structured markdown bundles from search results
for knowledge retrieval and context building.
"""
import json
import logging
from datetime import datetime
from pathlib import Path

from src.app.config import get_settings
from src.ingest.dedupe import make_source_item_id
from src.search.bm25 import search
from src.storage.dao import BundleDAO, Bundle, Conversation

logger = logging.getLogger("sj_home_agent.search.bundle")


def _slug(query: str) -> str:
    """Create a filesystem-safe slug from query."""
    safe = query.replace("#", "").replace(" ", "_").replace("/", "-")
    return safe[:50].strip("_-")


def _format_bundle_markdown(
    query: str,
    items: list[tuple[Conversation, float]],
    created_at: str,
) -> str:
    """Generate the context bundle markdown."""
    lines = [
        "---",
        f"date: {created_at[:10]}",
        "type: context_bundle",
        f"query: \"{query}\"",
        f"items: {len(items)}",
        "---",
        "",
        f"# Context Bundle: {query}",
        "",
        "## Why these were selected",
        f"- Searched for: `{query}`",
        f"- {len(items)} most relevant conversations by tag/keyword match + recency",
        "",
        f"## Selected memories ({len(items)})",
        "",
    ]

    for i, (conv, score) in enumerate(items, 1):
        lines.append(f"### {i}) {conv.title}")
        lines.append(f"- **tags**: {conv.tags}")
        lines.append(f"- **link**: {conv.url}")
        lines.append(f"- **match score**: {score:.1f}")
        lines.append(f"- **collected**: {conv.collected_at[:10]}")
        if conv.preview:
            preview_lines = conv.preview[:300].split("\n")[:3]
            lines.append("- **preview**:")
            for pl in preview_lines:
                stripped = pl.strip()
                if stripped:
                    lines.append(f"  - {stripped}")
        lines.append("")

    lines.extend([
        "## Guardrails",
        "- This bundle is for recalling context, not forcing decisions.",
        "- Next steps should be max 1~2.",
        "",
    ])

    return "\n".join(lines)


def create_bundle(
    query: str,
    top_n: int = 7,
    days: int | None = None,
) -> Bundle:
    """Create a context bundle from a search query.

    Searches conversations, formats as markdown, saves to DB and Obsidian.
    """
    results = search(query, days=days, limit=top_n)
    now = datetime.now().isoformat()

    markdown = _format_bundle_markdown(query, results, now)

    item_ids = [conv.id for conv, _ in results]
    bundle_id = make_source_item_id("bundle", f"{query}:{now[:10]}")

    bundle = Bundle(
        id=bundle_id,
        created_at=now,
        query=query,
        items_json=json.dumps(item_ids),
        markdown=markdown,
    )

    # Save to DB
    dao = BundleDAO()
    dao.insert(bundle)

    # Write to Obsidian
    settings = get_settings()
    bundles_dir = settings.bundles_path
    bundles_dir.mkdir(parents=True, exist_ok=True)

    slug = _slug(query)
    filename = f"{now[:10]}_{slug}.md"
    filepath = bundles_dir / filename
    filepath.write_text(markdown, encoding="utf-8")
    logger.info("Bundle written to %s", filepath)

    return bundle
