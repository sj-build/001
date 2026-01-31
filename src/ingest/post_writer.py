"""Write posts to Obsidian and export as HTML."""
import re
from datetime import date
from pathlib import Path

from src.app.config import get_settings
from src.storage.dao import Post


def _slugify(text: str) -> str:
    """Create filesystem-safe slug from text."""
    slug = re.sub(r"[^\w\s-]", "", text.lower().strip())
    return re.sub(r"[\s_]+", "-", slug)[:60]


def write_post_to_obsidian(post: Post) -> Path:
    """Write a post to Obsidian vault as markdown with YAML frontmatter.

    Returns the file path.
    """
    settings = get_settings()
    posts_dir = settings.output_path / "posts"
    posts_dir.mkdir(parents=True, exist_ok=True)

    d = post.published_at[:10] if post.published_at else date.today().isoformat()
    slug = _slugify(post.title)
    filename = f"{d}_{slug}.md"
    filepath = posts_dir / filename

    tags_list = [t.strip() for t in post.tags.split(",") if t.strip()]
    tags_yaml = ", ".join(tags_list) if tags_list else ""

    frontmatter = "\n".join([
        "---",
        f"title: \"{post.title}\"",
        f"date: {d}",
        f"status: {post.status}",
        f"category: {post.category}",
        f"tags: [{tags_yaml}]",
        "---",
        "",
    ])

    content = frontmatter + post.content
    filepath.write_text(content, encoding="utf-8")
    return filepath


def export_post_to_html(post: Post, output_dir: Path | None = None) -> Path:
    """Export a post as standalone HTML with minimal CSS.

    Returns the file path.
    """
    settings = get_settings()
    target_dir = output_dir or (settings.output_path / "posts" / "html")
    target_dir.mkdir(parents=True, exist_ok=True)

    d = post.published_at[:10] if post.published_at else date.today().isoformat()
    slug = _slugify(post.title)
    filename = f"{d}_{slug}.html"
    filepath = target_dir / filename

    # Simple markdown-to-html: paragraphs, headers, bold, italic, code
    html_body = _simple_md_to_html(post.content)

    html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{post.title}</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; max-width: 720px; margin: 2rem auto; padding: 0 1rem; line-height: 1.7; color: #333; }}
        h1 {{ border-bottom: 2px solid #eee; padding-bottom: 0.5rem; }}
        .meta {{ color: #888; font-size: 0.9rem; margin-bottom: 2rem; }}
        pre {{ background: #f5f5f5; padding: 1rem; border-radius: 4px; overflow-x: auto; }}
        code {{ background: #f0f0f0; padding: 0.15rem 0.3rem; border-radius: 3px; font-size: 0.9em; }}
        pre code {{ background: none; padding: 0; }}
        blockquote {{ border-left: 3px solid #ddd; margin-left: 0; padding-left: 1rem; color: #666; }}
    </style>
</head>
<body>
    <article>
        <h1>{post.title}</h1>
        <div class="meta">{d} &middot; {post.category} &middot; {post.tags}</div>
        {html_body}
    </article>
</body>
</html>"""

    filepath.write_text(html, encoding="utf-8")
    return filepath


def _simple_md_to_html(md: str) -> str:
    """Minimal markdown to HTML conversion."""
    import html as html_mod

    lines = md.split("\n")
    result: list[str] = []
    in_code_block = False

    for line in lines:
        if line.startswith("```"):
            if in_code_block:
                result.append("</code></pre>")
                in_code_block = False
            else:
                result.append("<pre><code>")
                in_code_block = True
            continue

        if in_code_block:
            result.append(html_mod.escape(line))
            continue

        stripped = line.strip()

        if stripped.startswith("### "):
            result.append(f"<h3>{html_mod.escape(stripped[4:])}</h3>")
        elif stripped.startswith("## "):
            result.append(f"<h2>{html_mod.escape(stripped[3:])}</h2>")
        elif stripped.startswith("# "):
            result.append(f"<h1>{html_mod.escape(stripped[2:])}</h1>")
        elif stripped.startswith("> "):
            result.append(f"<blockquote>{html_mod.escape(stripped[2:])}</blockquote>")
        elif stripped.startswith("- ") or stripped.startswith("* "):
            result.append(f"<li>{html_mod.escape(stripped[2:])}</li>")
        elif stripped == "":
            result.append("<br>")
        else:
            # Inline formatting
            text = html_mod.escape(stripped)
            text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
            text = re.sub(r"\*(.+?)\*", r"<em>\1</em>", text)
            text = re.sub(r"`(.+?)`", r"<code>\1</code>", text)
            result.append(f"<p>{text}</p>")

    if in_code_block:
        result.append("</code></pre>")

    return "\n".join(result)
