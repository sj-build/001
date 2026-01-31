"""Hybrid search combining BM25 keyword search with vector semantic search.

Uses Reciprocal Rank Fusion (RRF) to merge results from both search
methods. Falls back to BM25-only when vector search is unavailable.
"""
import logging
from typing import Optional

from src.search.bm25 import search as bm25_search
from src.search import vector as vector_mod
from src.storage.dao import ConversationDAO, Conversation

logger = logging.getLogger("sj_home_agent.search.hybrid")

RRF_K = 60
VALID_MODES = frozenset({"keyword", "semantic", "hybrid"})


def _rrf_score(rank: int, k: int = RRF_K) -> float:
    """Compute Reciprocal Rank Fusion score for a given rank (0-indexed)."""
    return 1.0 / (k + rank + 1)


def search(
    query: str,
    days: Optional[int] = None,
    platform: Optional[str] = None,
    limit: int = 20,
    mode: str = "hybrid",
    vector_weight: float = 1.0,
    bm25_weight: float = 1.0,
) -> list[tuple[Conversation, float]]:
    """Search conversations using hybrid BM25 + vector search.

    Args:
        query: Search query string.
        days: Limit results to last N days.
        platform: Filter by platform.
        limit: Maximum number of results.
        mode: Search mode - "keyword", "semantic", or "hybrid".
        vector_weight: Weight multiplier for vector search scores in RRF.
        bm25_weight: Weight multiplier for BM25 search scores in RRF.

    Returns:
        List of (Conversation, score) tuples sorted by score descending.
    """
    if not query.strip():
        return []

    if mode not in VALID_MODES:
        mode = "hybrid"

    if mode == "keyword":
        return bm25_search(query, days=days, platform=platform, limit=limit)

    if mode == "semantic":
        return _vector_only_search(query, limit=limit)

    # hybrid mode
    bm25_results = bm25_search(query, days=days, platform=platform, limit=limit)

    if not vector_mod.is_available():
        return bm25_results

    vector_results = vector_mod.search(query, limit=limit)

    if not vector_results:
        return bm25_results

    return _fuse(bm25_results, vector_results, bm25_weight, vector_weight, limit)


def _vector_only_search(
    query: str,
    limit: int = 20,
) -> list[tuple[Conversation, float]]:
    """Run vector-only search, resolving doc IDs to Conversation objects."""
    if not vector_mod.is_available():
        return []

    vector_results = vector_mod.search(query, limit=limit)
    if not vector_results:
        return []

    dao = ConversationDAO()
    doc_ids = [doc_id for doc_id, _ in vector_results]
    score_map = {doc_id: score for doc_id, score in vector_results}

    found = dao.find_by_ids(doc_ids)
    return [(conv, score_map[conv.id]) for conv in found if conv.id in score_map]


def _fuse(
    bm25_results: list[tuple[Conversation, float]],
    vector_results: list[tuple[str, float]],
    bm25_weight: float,
    vector_weight: float,
    limit: int,
) -> list[tuple[Conversation, float]]:
    """Fuse BM25 and vector results using Reciprocal Rank Fusion."""
    scores: dict[str, float] = {}
    conv_map: dict[str, Conversation] = {}

    # BM25 contribution
    for rank, (conv, _bm25_score) in enumerate(bm25_results):
        scores[conv.id] = scores.get(conv.id, 0.0) + bm25_weight * _rrf_score(rank)
        conv_map[conv.id] = conv

    # Vector contribution — batch-resolve missing IDs
    missing_ids = [
        doc_id for doc_id, _ in vector_results
        if doc_id not in conv_map
    ]
    if missing_ids:
        dao = ConversationDAO()
        found = dao.find_by_ids(missing_ids)
        for conv in found:
            conv_map[conv.id] = conv

    for rank, (doc_id, _vec_score) in enumerate(vector_results):
        scores[doc_id] = scores.get(doc_id, 0.0) + vector_weight * _rrf_score(rank)

    # Build sorted results (only IDs that resolved to a Conversation)
    fused = [
        (conv_map[cid], score)
        for cid, score in scores.items()
        if cid in conv_map
    ]
    fused.sort(key=lambda x: x[1], reverse=True)

    return fused[:limit]
