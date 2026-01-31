"""CLI entry point for SJ Home Agent."""
import argparse
import asyncio
import logging
import sys

from src.app.config import get_settings
from src.app.logging import setup_logging
from src.app.paths import ensure_dirs
from src.storage.db import init_db


def cmd_collect(args):
    """Run collectors for specified platforms."""
    from src.collectors.runner import run_all

    platforms = None if args.platform == "all" else [args.platform]
    headless = args.headless.lower() == "true" if hasattr(args, "headless") and args.headless else False
    days = args.days

    results = asyncio.run(run_all(platforms=platforms, headless=headless, days=days))
    for platform, count in results.items():
        print(f"  {platform}: {count} conversations")


def cmd_serve(args):
    """Start the web server."""
    import uvicorn
    from src.web.server import app

    settings = get_settings()
    port = args.port or settings.web_port
    host = settings.web_host

    print(f"Starting server at http://{host}:{port}")
    uvicorn.run(app, host=host, port=port)


def cmd_search(args):
    """Search conversations."""
    from src.search.hybrid import search

    query_parts = []
    if args.tag:
        query_parts.append(args.tag)
    if args.q:
        query_parts.append(args.q)

    query = " ".join(query_parts) if query_parts else ""
    if not query:
        print("Provide --tag or --q for search")
        return

    mode = getattr(args, "mode", "hybrid") or "hybrid"
    results = search(query, days=args.days, mode=mode)
    if not results:
        print("No results found.")
        return

    print(f"  mode={mode}")
    for conv, score in results:
        print(f"  [{score:.3f}] {conv.title}")
        print(f"         {conv.url}")
        print(f"         tags={conv.tags}  category={conv.category}")
        print()


def cmd_reindex(args):
    """Reindex all conversations into the vector store."""
    from src.search import vector as vector_mod
    from src.storage.dao import ConversationDAO

    if not vector_mod.is_available():
        print("Vector search not available. Install chromadb and sentence-transformers.")
        return

    dao = ConversationDAO()
    total = dao.count_all()
    print(f"Reindexing {total} conversations...")

    batch_size = 50
    indexed = 0
    offset = 0
    while offset < total:
        batch = dao.find_all(limit=batch_size, offset=offset)
        if not batch:
            break
        offset += len(batch)
        ids = [c.id for c in batch]
        texts = [
            f"{c.title} {c.tags.replace(',', ' ')} {c.preview or ''}".strip()
            for c in batch
        ]
        metas = [
            {"platform": c.platform, "category": c.category}
            for c in batch
        ]
        vector_mod.index_batch(ids, texts, metas)
        indexed += len(batch)
        print(f"  {indexed}/{total}")

    print(f"Done. {vector_mod.count()} documents in vector index.")


def cmd_bundle(args):
    """Create a context bundle."""
    from src.search.bundle import create_bundle

    if not args.query:
        print("Provide --query for bundle creation")
        return

    bundle = create_bundle(args.query, top_n=args.top)
    print(f"Bundle created: {bundle.id}")
    print(bundle.markdown[:500])


def cmd_morning(args):
    """Handle morning digest commands."""
    if args.action == "build":
        from src.morning.digest import build_digest
        markdown = build_digest()
        print("Morning digest built.")
        print(markdown[:500])
    elif args.action == "fetch":
        from src.morning.sources.fetch_all import fetch_all_sources
        days = args.days
        results = fetch_all_sources(days=days)
        print("News sources fetched:")
        for source_type, count in results.items():
            print(f"  {source_type}: {count} items")


def cmd_ask(args):
    """Run the Thinking Partner."""
    from src.thinking.agent import think, ThinkingInput

    input_data = ThinkingInput(
        url=args.url,
        text=args.text,
        question=args.q or "",
    )
    result = think(input_data)
    print(result.analysis)


def main():
    setup_logging()
    ensure_dirs()
    init_db()

    parser = argparse.ArgumentParser(
        prog="sj-home-agent",
        description="SJ Home Agent: Second Brain + Knowledge Hub",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # collect
    p_collect = subparsers.add_parser("collect", help="Collect conversations")
    p_collect.add_argument(
        "--platform", default="all",
        choices=["all", "claude", "chatgpt", "gemini", "granola", "fyxer"],
    )
    p_collect.add_argument("--headless", default="false")
    p_collect.add_argument("--days", type=int, default=30, help="Only keep conversations from last N days")
    p_collect.set_defaults(func=cmd_collect)

    # serve
    p_serve = subparsers.add_parser("serve", help="Start web server")
    p_serve.add_argument("--port", type=int, default=None)
    p_serve.set_defaults(func=cmd_serve)

    # search
    p_search = subparsers.add_parser("search", help="Search conversations")
    p_search.add_argument("--tag", default=None)
    p_search.add_argument("--q", default=None)
    p_search.add_argument("--days", type=int, default=None)
    p_search.add_argument(
        "--mode", default="hybrid",
        choices=["keyword", "semantic", "hybrid"],
        help="Search mode (default: hybrid)",
    )
    p_search.set_defaults(func=cmd_search)

    # reindex
    p_reindex = subparsers.add_parser("reindex", help="Reindex all conversations into vector store")
    p_reindex.set_defaults(func=cmd_reindex)

    # bundle
    p_bundle = subparsers.add_parser("bundle", help="Create context bundle")
    p_bundle.add_argument("--query", required=True)
    p_bundle.add_argument("--top", type=int, default=7)
    p_bundle.set_defaults(func=cmd_bundle)

    # morning
    p_morning = subparsers.add_parser("morning", help="Morning digest")
    p_morning.add_argument("action", choices=["build", "fetch"])
    p_morning.add_argument("--days", type=int, default=7, help="Fetch news from last N days")
    p_morning.set_defaults(func=cmd_morning)

    # ask
    p_ask = subparsers.add_parser("ask", help="Ask the Thinking Partner")
    p_ask.add_argument("--url", default=None)
    p_ask.add_argument("--text", default=None)
    p_ask.add_argument("--q", default=None)
    p_ask.set_defaults(func=cmd_ask)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
