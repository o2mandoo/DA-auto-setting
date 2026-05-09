"""Retrieval backends for Phase 7 semantic card search.

The package exposes an explicit keyword backend and an explicit Weaviate seam.
It does not auto-fallback between them; callers must choose the backend they
intend to use so VDB coverage is never silently overstated.
"""

from .backends import (
    KeywordSearchBackend,
    SearchBackend,
    SearchDocument,
    SearchResult,
    WeaviateSearchBackend,
    WeaviateUnavailableError,
    documents_from_pack,
)
from .semantic_query import (
    SemanticMatch,
    SemanticQueryUnderstanding,
    analyze_semantic_query,
    normalize_query,
)
from .embeddings import (
    DeterministicEmbeddingProvider,
    EmbeddingProvider,
    EmbeddingSafetyError,
    LocalEmbeddingConfig,
    LocalEmbeddingProvider,
    LocalEmbeddingProviderUnavailable,
    assert_embedding_safe_text,
)

__all__ = [
    "DeterministicEmbeddingProvider",
    "EmbeddingProvider",
    "EmbeddingSafetyError",
    "KeywordSearchBackend",
    "LocalEmbeddingConfig",
    "LocalEmbeddingProvider",
    "LocalEmbeddingProviderUnavailable",
    "SearchBackend",
    "SearchDocument",
    "SearchResult",
    "WeaviateSearchBackend",
    "WeaviateUnavailableError",
    "assert_embedding_safe_text",
    "documents_from_pack",
    "SemanticMatch",
    "SemanticQueryUnderstanding",
    "analyze_semantic_query",
    "normalize_query",
]
