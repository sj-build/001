"""Vector search stub (optional, for future use)."""


class VectorIndex:
    """Stub for future vector-based search using chromadb or sentence-transformers."""

    def index(self, doc_id: str, text: str) -> None:
        raise NotImplementedError("Vector search not yet implemented")

    def search(self, query: str, limit: int = 10) -> list[tuple[str, float]]:
        raise NotImplementedError("Vector search not yet implemented")
