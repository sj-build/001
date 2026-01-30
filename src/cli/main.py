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

    results = asyncio.run(run_all(platforms=platforms, headless=headless))
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
    from src.search.bm25 import search

    query_parts = []
    if args.tag:
        query_parts.append(args.tag)
    if args.q:
        query_parts.append(args.q)

    query = " ".join(query_parts) if query_parts else ""
    if not query:
        print("Provide --tag or --q for search")
        return

    results = search(query, days=args.days)
    if not results:
        print("No results found.")
        return

    for conv, score in results:
        print(f"  [{score:.1f}] {conv.title}")
        print(f"         {conv.url}")
        print(f"         tags={conv.tags}  category={conv.category}")
        print()


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
    """Build morning digest."""
    from src.morning.digest import build_digest

    markdown = build_digest()
    print("Morning digest built.")
    print(markdown[:500])


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
    p_search.set_defaults(func=cmd_search)

    # bundle
    p_bundle = subparsers.add_parser("bundle", help="Create context bundle")
    p_bundle.add_argument("--query", required=True)
    p_bundle.add_argument("--top", type=int, default=7)
    p_bundle.set_defaults(func=cmd_bundle)

    # morning
    p_morning = subparsers.add_parser("morning", help="Morning digest")
    p_morning.add_argument("action", choices=["build"])
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
