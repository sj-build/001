"""Thinking Partner agent.

Pipeline: input -> summarize -> retrieve memories -> compose response.
Uses NoLLMClient by default (no API calls needed).
"""
import logging
import re
from dataclasses import dataclass
from typing import Optional

from src.app.config import get_settings
from src.search.hybrid import search
from src.tagging.classifier import classify
from src.thinking.models import LLMClient, NoLLMClient
from src.thinking.prompts import build_analysis_prompt, build_summary_prompt

logger = logging.getLogger("sj_home_agent.thinking")


@dataclass(frozen=True)
class ThinkingInput:
    url: Optional[str] = None
    text: Optional[str] = None
    question: str = ""


@dataclass(frozen=True)
class ThinkingResult:
    summary: str
    memories: list[dict]
    analysis: str
    suggested_query: str


def _extract_text_from_url(url: str) -> str:
    """Try to fetch and extract text from a URL. Falls back gracefully."""
    try:
        import httpx
        from bs4 import BeautifulSoup

        response = httpx.get(url, timeout=10, follow_redirects=True)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        # Remove scripts and styles
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()

        text = soup.get_text(separator="\n", strip=True)
        return text[:3000]
    except ImportError:
        logger.warning("httpx/beautifulsoup4 not installed; URL extraction disabled")
        return f"[URL: {url}]"
    except Exception as e:
        logger.error("Failed to extract text from %s: %s", url, e)
        return f"[URL: {url} - extraction failed]"


def _extract_keywords(text: str) -> list[str]:
    """Simple keyword extraction using regex heuristics."""
    # Extract capitalized phrases, Korean words, and common terms
    words = re.findall(r"[A-Z][a-z]+(?:\s[A-Z][a-z]+)*", text)
    korean = re.findall(r"[\uac00-\ud7af]+", text)
    # Dedupe and limit
    seen: set[str] = set()
    result: list[str] = []
    for w in [*words, *korean]:
        w_clean = w.strip()
        if w_clean and w_clean.lower() not in seen and len(w_clean) > 1:
            seen.add(w_clean.lower())
            result.append(w_clean)
        if len(result) >= 10:
            break
    return result


def _build_search_query(
    question: str,
    keywords: list[str],
    tags: list[str],
) -> str:
    """Build a search query from question, keywords, and inferred tags."""
    parts = []
    parts.extend(tags[:3])
    parts.extend(keywords[:3])
    question_words = [w for w in question.split() if len(w) > 2]
    parts.extend(question_words[:3])
    return " ".join(parts)


def get_llm_client() -> LLMClient:
    """Get the configured LLM client (default: NoLLMClient)."""
    settings = get_settings()
    if settings.llm_provider == "none" or not settings.llm_provider:
        return NoLLMClient()
    # Future: add OpenAI/Anthropic clients here
    return NoLLMClient()


def think(input_data: ThinkingInput) -> ThinkingResult:
    """Run the thinking partner pipeline.

    1) Normalize input (fetch URL if provided)
    2) Summarize
    3) Retrieve relevant memories
    4) Compose structured response
    """
    # Step 1: Normalize input
    raw_text = input_data.text or ""
    if input_data.url:
        url_text = _extract_text_from_url(input_data.url)
        raw_text = f"{url_text}\n\n{raw_text}".strip()

    if not raw_text and not input_data.question:
        return ThinkingResult(
            summary="No input provided.",
            memories=[],
            analysis="Please provide a URL, text, or question.",
            suggested_query="",
        )

    # Step 2: Summarize (5-10 lines max)
    summary = build_summary_prompt(raw_text) if raw_text else "(No text provided)"

    # Step 3: Retrieve relevant memories
    keywords = _extract_keywords(raw_text + " " + input_data.question)
    category, tags = classify(
        input_data.question,
        raw_text[:500],
    )

    query = _build_search_query(input_data.question, keywords, tags)
    search_results = search(query, limit=5) if query.strip() else []

    memories = [
        {
            "title": conv.title,
            "tags": conv.tags,
            "url": conv.url,
            "match_reason": f"score {score:.1f} — keyword/tag overlap",
            "preview": conv.preview or "",
        }
        for conv, score in search_results
    ]

    # Step 4: Compose response
    client = get_llm_client()
    prompt = build_analysis_prompt(summary, memories, input_data.question)
    analysis = client.generate(prompt)

    # Suggested query for bundle creation
    suggested_query = " ".join(tags[:2] + keywords[:2])

    return ThinkingResult(
        summary=summary,
        memories=memories,
        analysis=analysis,
        suggested_query=suggested_query,
    )
