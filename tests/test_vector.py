"""Tests for the vector search module."""
from unittest.mock import patch, MagicMock

import pytest

from src.search import vector as vector_mod


@pytest.fixture(autouse=True)
def reset_vector_state():
    """Reset vector module global state before each test."""
    vector_mod._collection = None
    vector_mod._embed_fn = None
    vector_mod._available = None
    yield
    vector_mod._collection = None
    vector_mod._embed_fn = None
    vector_mod._available = None


class TestIsAvailable:
    def test_returns_false_when_disabled(self, tmp_settings):
        """is_available returns False when vector_search_enabled is False."""
        assert tmp_settings.vector_search_enabled is False
        result = vector_mod.is_available()
        assert result is False

    def test_returns_false_when_imports_missing(self, tmp_settings):
        """is_available returns False when chromadb is not installed."""
        with patch.object(tmp_settings, "vector_search_enabled", True):
            with patch("src.search.vector.get_settings", return_value=tmp_settings):
                import builtins
                original_import = builtins.__import__

                def mock_import(name, *args, **kwargs):
                    if name in ("chromadb", "sentence_transformers"):
                        raise ImportError(f"No module named '{name}'")
                    return original_import(name, *args, **kwargs)

                with patch("builtins.__import__", side_effect=mock_import):
                    result = vector_mod.is_available()
                    assert result is False

    def test_caches_result(self, tmp_settings):
        """is_available caches the result after first call."""
        vector_mod.is_available()
        assert vector_mod._available is False

        # Second call should use cached value without rechecking
        result = vector_mod.is_available()
        assert result is False


class TestIndexNoOp:
    def test_index_noop_when_unavailable(self, tmp_settings):
        """index() is a no-op when vector search is unavailable."""
        # Should not raise
        vector_mod.index("doc-1", "some text")

    def test_index_batch_noop_when_unavailable(self, tmp_settings):
        """index_batch() is a no-op when vector search is unavailable."""
        vector_mod.index_batch(
            ["doc-1", "doc-2"],
            ["text one", "text two"],
        )

    def test_index_batch_empty_ids(self, tmp_settings):
        """index_batch() handles empty input gracefully."""
        vector_mod.index_batch([], [])


class TestSearchEmpty:
    def test_search_returns_empty_when_unavailable(self, tmp_settings):
        """search() returns empty list when vector search is unavailable."""
        result = vector_mod.search("test query")
        assert result == []

    def test_search_returns_empty_for_blank_query(self, tmp_settings):
        """search() returns empty list for blank query."""
        result = vector_mod.search("")
        assert result == []

        result = vector_mod.search("   ")
        assert result == []


class TestCountAndDelete:
    def test_count_returns_zero_when_unavailable(self, tmp_settings):
        """count() returns 0 when vector search is unavailable."""
        assert vector_mod.count() == 0

    def test_delete_noop_when_unavailable(self, tmp_settings):
        """delete() is a no-op when vector search is unavailable."""
        vector_mod.delete("doc-1")


class TestWithMockedChromaDB:
    """Tests using a mocked ChromaDB collection."""

    def test_search_converts_distances_to_similarity(self):
        """Verify cosine distance → similarity conversion: 1 - (dist / 2)."""
        mock_collection = MagicMock()
        mock_collection.query.return_value = {
            "ids": [["doc-a", "doc-b"]],
            "distances": [[0.4, 1.0]],
        }
        mock_collection.count.return_value = 2

        vector_mod._collection = mock_collection
        vector_mod._available = True

        results = vector_mod.search("test")

        assert len(results) == 2
        assert results[0] == ("doc-a", 0.8)
        assert results[1] == ("doc-b", 0.5)

        # Verify the query was called with "query: " prefix
        call_args = mock_collection.query.call_args
        assert call_args.kwargs["query_texts"] == ["query: test"]

    def test_index_adds_passage_prefix(self):
        """Verify documents are indexed with 'passage: ' prefix."""
        mock_collection = MagicMock()
        vector_mod._collection = mock_collection
        vector_mod._available = True

        vector_mod.index("doc-1", "some text", {"platform": "claude"})

        mock_collection.upsert.assert_called_once_with(
            ids=["doc-1"],
            documents=["passage: some text"],
            metadatas=[{"platform": "claude"}],
        )

    def test_index_batch_adds_passage_prefix(self):
        """Verify batch indexing adds 'passage: ' prefix to all documents."""
        mock_collection = MagicMock()
        vector_mod._collection = mock_collection
        vector_mod._available = True

        vector_mod.index_batch(
            ["d1", "d2"],
            ["text one", "text two"],
            [{"p": "a"}, {"p": "b"}],
        )

        mock_collection.upsert.assert_called_once_with(
            ids=["d1", "d2"],
            documents=["passage: text one", "passage: text two"],
            metadatas=[{"p": "a"}, {"p": "b"}],
        )

    def test_search_handles_empty_results(self):
        """search() handles empty ChromaDB response gracefully."""
        mock_collection = MagicMock()
        mock_collection.query.return_value = {
            "ids": [[]],
            "distances": [[]],
        }
        mock_collection.count.return_value = 0

        vector_mod._collection = mock_collection
        vector_mod._available = True

        results = vector_mod.search("test")
        assert results == []

    def test_search_handles_exception(self):
        """search() returns empty list on ChromaDB exception."""
        mock_collection = MagicMock()
        mock_collection.query.side_effect = RuntimeError("DB error")
        mock_collection.count.return_value = 5

        vector_mod._collection = mock_collection
        vector_mod._available = True

        results = vector_mod.search("test")
        assert results == []

    def test_delete_calls_collection(self):
        """delete() calls collection.delete with the correct ID."""
        mock_collection = MagicMock()
        vector_mod._collection = mock_collection
        vector_mod._available = True

        vector_mod.delete("doc-1")

        mock_collection.delete.assert_called_once_with(ids=["doc-1"])

    def test_count_returns_collection_count(self):
        """count() returns the collection's document count."""
        mock_collection = MagicMock()
        mock_collection.count.return_value = 42

        vector_mod._collection = mock_collection
        vector_mod._available = True

        assert vector_mod.count() == 42
