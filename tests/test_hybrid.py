"""Tests for the hybrid search module."""
from unittest.mock import patch, MagicMock

import pytest

from src.search import vector as vector_mod
from src.search.hybrid import search, _rrf_score, _fuse, _vector_only_search
from src.storage.dao import Conversation


@pytest.fixture(autouse=True)
def reset_vector_for_hybrid(tmp_settings):
    """Ensure vector module uses tmp_settings (vector disabled) in all hybrid tests."""
    vector_mod._collection = None
    vector_mod._embed_fn = None
    vector_mod._available = None
    with patch("src.search.vector.get_settings", return_value=tmp_settings):
        yield
    vector_mod._collection = None
    vector_mod._embed_fn = None
    vector_mod._available = None


def _make_conv(cid: str, title: str = "Test") -> Conversation:
    """Create a minimal Conversation for testing."""
    return Conversation(
        id=cid,
        platform="test",
        title=title,
        url=f"https://example.com/{cid}",
        created_at="2025-01-15",
        collected_at="2025-01-15T10:00:00",
        category="Test",
        tags="test",
        preview="preview text",
        obsidian_path="/vault/test.md",
        content_hash="hash",
    )


class TestRRFScore:
    def test_rank_zero(self):
        """RRF score for rank 0 with K=60 is 1/61."""
        score = _rrf_score(0, k=60)
        assert abs(score - 1.0 / 61) < 1e-10

    def test_rank_one(self):
        """RRF score for rank 1 with K=60 is 1/62."""
        score = _rrf_score(1, k=60)
        assert abs(score - 1.0 / 62) < 1e-10

    def test_higher_rank_lower_score(self):
        """Higher rank should produce lower RRF score."""
        assert _rrf_score(0) > _rrf_score(1)
        assert _rrf_score(1) > _rrf_score(10)
        assert _rrf_score(10) > _rrf_score(100)

    def test_custom_k(self):
        """Custom K parameter affects the score."""
        score_k10 = _rrf_score(0, k=10)
        score_k60 = _rrf_score(0, k=60)
        # Smaller K gives higher scores
        assert score_k10 > score_k60


class TestFuse:
    def test_fuse_combines_results(self):
        """_fuse merges BM25 and vector results with RRF scoring."""
        conv_a = _make_conv("a", "Doc A")
        conv_b = _make_conv("b", "Doc B")
        conv_c = _make_conv("c", "Doc C")

        bm25_results = [(conv_a, 5.0), (conv_b, 3.0)]
        vector_results = [("b", 0.9), ("c", 0.7)]

        with patch("src.search.hybrid.ConversationDAO") as MockDAO:
            mock_dao = MagicMock()
            # Only "c" is missing from BM25 results, so find_by_ids is called with ["c"]
            mock_dao.find_by_ids.return_value = [conv_c]
            MockDAO.return_value = mock_dao

            fused = _fuse(bm25_results, vector_results, 1.0, 1.0, 10)

        # conv_b appears in both lists, should have highest score
        ids = [c.id for c, _ in fused]
        assert "b" in ids
        assert "a" in ids
        assert "c" in ids

        # b should rank first (appears in both)
        assert fused[0][0].id == "b"

    def test_fuse_with_weights(self):
        """Weights affect the relative importance of each source."""
        conv_a = _make_conv("a")
        conv_b = _make_conv("b")

        # a is rank 0 in BM25, b is rank 0 in vector
        bm25_results = [(conv_a, 5.0)]
        vector_results = [("b", 0.9)]

        with patch("src.search.hybrid.ConversationDAO") as MockDAO:
            mock_dao = MagicMock()
            mock_dao.find_by_ids.return_value = [conv_b]
            MockDAO.return_value = mock_dao

            # Heavy BM25 weight
            fused_bm25 = _fuse(bm25_results, vector_results, 2.0, 0.5, 10)
            assert fused_bm25[0][0].id == "a"

            # Heavy vector weight
            fused_vec = _fuse(bm25_results, vector_results, 0.5, 2.0, 10)
            assert fused_vec[0][0].id == "b"

    def test_fuse_respects_limit(self):
        """_fuse respects the limit parameter."""
        convs = [_make_conv(f"c{i}") for i in range(5)]
        bm25_results = [(c, float(5 - i)) for i, c in enumerate(convs)]
        vector_results = []

        fused = _fuse(bm25_results, vector_results, 1.0, 1.0, 3)
        assert len(fused) == 3

    def test_fuse_skips_unresolved_vector_ids(self):
        """_fuse skips vector IDs that don't resolve to a Conversation."""
        conv_a = _make_conv("a")
        bm25_results = [(conv_a, 5.0)]
        vector_results = [("nonexistent", 0.9)]

        with patch("src.search.hybrid.ConversationDAO") as MockDAO:
            mock_dao = MagicMock()
            mock_dao.find_by_ids.return_value = []  # not found
            MockDAO.return_value = mock_dao

            fused = _fuse(bm25_results, vector_results, 1.0, 1.0, 10)

        assert len(fused) == 1
        assert fused[0][0].id == "a"


class TestSearch:
    def test_empty_query_returns_empty(self, tmp_settings):
        """search() returns empty list for empty query."""
        result = search("", mode="hybrid")
        assert result == []

        result = search("   ", mode="keyword")
        assert result == []

    def test_keyword_mode_delegates_to_bm25(self, tmp_settings, sample_conversations):
        """keyword mode uses only BM25 search."""
        results = search("investment", mode="keyword")
        assert len(results) > 0
        # Should find the investment conversation
        titles = [c.title for c, _ in results]
        assert any("investment" in t.lower() for t in titles)

    def test_semantic_mode_returns_empty_when_unavailable(self, tmp_settings):
        """semantic mode returns empty when vector search is unavailable."""
        results = search("investment", mode="semantic")
        assert results == []

    def test_hybrid_mode_falls_back_to_bm25(self, tmp_settings, sample_conversations):
        """hybrid mode falls back to BM25 when vector search is unavailable."""
        results = search("investment", mode="hybrid")
        assert len(results) > 0


class TestVectorOnlySearch:
    def test_returns_empty_when_unavailable(self, tmp_settings):
        """_vector_only_search returns empty when vector is unavailable."""
        results = _vector_only_search("test")
        assert results == []

    def test_resolves_ids_to_conversations(self, tmp_settings, sample_conversations):
        """_vector_only_search resolves doc IDs to Conversation objects."""
        with patch("src.search.hybrid.vector_mod") as mock_vec:
            mock_vec.is_available.return_value = True
            mock_vec.search.return_value = [("conv-1", 0.9), ("conv-2", 0.8)]

            results = _vector_only_search("test")

        assert len(results) == 2
        assert results[0][0].id == "conv-1"
        assert results[0][1] == 0.9

    def test_skips_missing_conversations(self, tmp_settings, sample_conversations):
        """_vector_only_search skips IDs that don't exist in DB."""
        with patch("src.search.hybrid.vector_mod") as mock_vec:
            mock_vec.is_available.return_value = True
            mock_vec.search.return_value = [("conv-1", 0.9), ("nonexistent", 0.8)]

            results = _vector_only_search("test")

        assert len(results) == 1
        assert results[0][0].id == "conv-1"
