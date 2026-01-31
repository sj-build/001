"""Vector search using ChromaDB + sentence-transformers.

Provides semantic search over conversations. Falls back gracefully
to no-op when chromadb or sentence-transformers are not installed.

E5 model convention:
  - query prefix: "query: "
  - document prefix: "passage: "
"""
import logging
import threading
from typing import Optional

from src.app.config import get_settings

logger = logging.getLogger("sj_home_agent.search.vector")

_lock = threading.Lock()
_collection = None
_embed_fn = None
_available: Optional[bool] = None


class _E5EmbeddingFunction:
    """ChromaDB embedding function wrapping E5 model with proper prefixes."""

    def __init__(self, st_model):
        self._model = st_model

    def __call__(self, texts: list[str]) -> list[list[float]]:
        embeddings = self._model.encode(texts, normalize_embeddings=True)
        return embeddings.tolist()


def is_available() -> bool:
    """Check if vector search dependencies are installed and enabled."""
    global _available
    if _available is not None:
        return _available

    settings = get_settings()
    if not settings.vector_search_enabled:
        _available = False
        return False

    try:
        import chromadb  # noqa: F401
        import sentence_transformers  # noqa: F401
        _available = True
    except ImportError:
        logger.info("Vector search disabled: chromadb or sentence-transformers not installed")
        _available = False

    return _available


def _ensure_initialized() -> bool:
    """Lazily initialize ChromaDB collection and embedding function.

    Thread-safe via a lock. Returns True if initialization succeeded.
    """
    global _collection, _embed_fn, _available

    if _collection is not None:
        return True

    if not is_available():
        return False

    with _lock:
        # Double-check after acquiring lock
        if _collection is not None:
            return True

        try:
            import chromadb
            from sentence_transformers import SentenceTransformer

            settings = get_settings()
            persist_dir = str(settings.vector_path)

            client = chromadb.PersistentClient(path=persist_dir)
            model = SentenceTransformer(settings.vector_model_name)

            _embed_fn = _E5EmbeddingFunction(model)

            _collection = client.get_or_create_collection(
                name="conversations",
                metadata={"hnsw:space": "cosine"},
                embedding_function=_embed_fn,
            )
            logger.info(
                "Vector index initialized: %d documents, model=%s",
                _collection.count(),
                settings.vector_model_name,
            )
            return True
        except Exception as e:
            logger.error("Failed to initialize vector index: %s", e)
            _available = False
            return False


def index(
    doc_id: str,
    text: str,
    metadata: Optional[dict] = None,
) -> None:
    """Index a single document into the vector store.

    Uses "passage: " prefix for E5 model convention.
    No-op if vector search is unavailable.
    """
    if not _ensure_initialized():
        return

    prefixed_text = f"passage: {text}"
    meta = metadata or {}

    try:
        _collection.upsert(
            ids=[doc_id],
            documents=[prefixed_text],
            metadatas=[meta],
        )
    except Exception as e:
        logger.error("Failed to index document %s: %s", doc_id, e)


def index_batch(
    doc_ids: list[str],
    texts: list[str],
    metadatas: Optional[list[dict]] = None,
) -> None:
    """Index a batch of documents into the vector store.

    No-op if vector search is unavailable.
    """
    if not _ensure_initialized():
        return

    if not doc_ids:
        return

    prefixed_texts = [f"passage: {t}" for t in texts]
    metas = metadatas or [{} for _ in doc_ids]

    try:
        _collection.upsert(
            ids=doc_ids,
            documents=prefixed_texts,
            metadatas=metas,
        )
        logger.info("Indexed batch of %d documents", len(doc_ids))
    except Exception as e:
        logger.error("Failed to index batch of %d documents: %s", len(doc_ids), e)


def search(
    query: str,
    limit: int = 10,
) -> list[tuple[str, float]]:
    """Semantic search returning (doc_id, similarity_score) pairs.

    Uses "query: " prefix for E5 model convention.
    Returns empty list if vector search is unavailable.

    Similarity score is converted from cosine distance:
      similarity = 1 - (distance / 2)
    """
    if not _ensure_initialized():
        return []

    if not query.strip():
        return []

    doc_count = count()
    if doc_count == 0:
        return []

    prefixed_query = f"query: {query}"

    try:
        results = _collection.query(
            query_texts=[prefixed_query],
            n_results=min(limit, doc_count),
        )
    except Exception as e:
        logger.error("Vector search failed: %s", e)
        return []

    if not results["ids"] or not results["ids"][0]:
        return []

    ids = results["ids"][0]
    distances = results["distances"][0]

    scored = [
        (doc_id, 1.0 - (dist / 2.0))
        for doc_id, dist in zip(ids, distances)
    ]

    return scored[:limit]


def count() -> int:
    """Return the number of documents in the vector index."""
    if not _ensure_initialized():
        return 0

    try:
        return _collection.count()
    except Exception:
        return 0


def delete(doc_id: str) -> None:
    """Delete a document from the vector index."""
    if not _ensure_initialized():
        return

    try:
        _collection.delete(ids=[doc_id])
    except Exception as e:
        logger.error("Failed to delete document %s: %s", doc_id, e)
