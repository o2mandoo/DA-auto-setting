"""Search backend seams for Phase 7 retrieval.

The implementation intentionally separates the deterministic keyword backend
from the Weaviate adapter. If Weaviate is unavailable or unconfigured, the
adapter raises an explicit error instead of falling back to local keyword
search; this is a product safety boundary for Phase 7 verification.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
import re
from typing import Any, Iterable, Mapping, Sequence

from semantic_contracts import SemanticPack

from semantic_registry.cards import CardDocument, iter_pack_card_documents


_EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.IGNORECASE)
_PHONE_RE = re.compile(r"(?<!\d)(?:\+?\d[\d\-\s().]{7,}\d)(?!\d)")
_RAW_VALUE_KEYS = {
    "raw_value",
    "raw_values",
    "sample_value",
    "sample_values",
    "top_value",
    "top_values",
    "literal_value",
    "literal_values",
    "email_value",
    "phone_value",
}


@dataclass(frozen=True)
class SearchDocument:
    """PII-safe text projection ready for keyword or VDB indexing."""

    doc_id: str
    text: str
    title: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not str(self.doc_id).strip():
            raise ValueError("search documents require a non-empty doc_id")
        if _contains_raw_pii(self.text):
            raise ValueError("search document text must not contain raw PII-like values")
        _reject_raw_value_payload(self.metadata, "metadata")


@dataclass(frozen=True)
class SearchResult:
    """Backend-neutral search result returned to MCP/registry callers."""

    doc_id: str
    title: str
    text: str
    score: float
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "doc_id": self.doc_id,
            "title": self.title,
            "text": self.text,
            "score": self.score,
            "metadata": dict(self.metadata),
        }


class SearchBackend(ABC):
    """Common interface for retrieval backends.

    Implementations are local library seams only: they do not execute SQL,
    mutate source datasets, or start MCP/UI/SaaS runtimes.
    """

    @abstractmethod
    def index_pack(self, pack: SemanticPack) -> None:
        """Index PII-safe card documents extracted from one Semantic Pack."""

    @abstractmethod
    def index_documents(self, documents: Iterable[SearchDocument]) -> None:
        """Add or replace documents in the backend."""

    @abstractmethod
    def search(
        self,
        query: str,
        *,
        card_types: Iterable[str] | None = None,
        limit: int = 10,
        filters: Mapping[str, Any] | None = None,
    ) -> list[SearchResult]:
        """Search indexed documents with optional metadata filters."""


class KeywordSearchBackend(SearchBackend):
    """Deterministic in-memory lexical backend for offline verification."""

    def __init__(self, documents: Iterable[SearchDocument] = ()) -> None:
        self._documents: dict[str, SearchDocument] = {}
        self.index_documents(documents)

    def index_pack(self, pack: SemanticPack) -> None:
        self.index_documents(documents_from_pack(pack))

    def index_documents(self, documents: Iterable[SearchDocument]) -> None:
        for document in documents:
            if not isinstance(document, SearchDocument):
                raise TypeError("KeywordSearchBackend indexes SearchDocument instances only")
            # Metadata is retained for filtering/return payloads, but never folded
            # into lexical text so blocked-column names or raw values cannot become
            # accidental keyword hits.
            self._documents[document.doc_id] = document

    def search(
        self,
        query: str,
        *,
        card_types: Iterable[str] | None = None,
        limit: int = 10,
        filters: Mapping[str, Any] | None = None,
    ) -> list[SearchResult]:
        if limit <= 0:
            return []
        normalized_query = _normalize(query)
        if not normalized_query:
            return []
        terms = [term for term in normalized_query.split() if term]
        combined_filters = _combine_filters(filters, card_types)
        results: list[SearchResult] = []
        for document in self._documents.values():
            if not _matches_filters(document.metadata, combined_filters):
                continue
            haystack = _normalize(" ".join(part for part in (document.title, document.text) if part))
            score = _score(normalized_query, terms, haystack)
            if score <= 0:
                continue
            results.append(SearchResult(
                doc_id=document.doc_id,
                title=document.title,
                text=document.text,
                score=float(score),
                metadata=document.metadata,
            ))
        results.sort(key=lambda result: (-result.score, result.doc_id))
        return results[:limit]


class WeaviateUnavailableError(RuntimeError):
    """Raised when the explicit Weaviate backend cannot be used."""


class WeaviateSearchBackend(SearchBackend):
    """Thin adapter over a caller-provided Weaviate collection/client.

    This class is intentionally explicit: it requires a usable Weaviate
    collection or client configuration and never substitutes keyword search when
    the VDB is unavailable.
    """

    def __init__(
        self,
        *,
        collection: Any | None = None,
        client: Any | None = None,
        collection_name: str = "SemanticCards",
        vectorizer: str = "none",
    ) -> None:
        if collection is not None:
            self._collection = collection
            return
        if client is None:
            raise WeaviateUnavailableError(
                "WeaviateSearchBackend requires an explicit Weaviate collection or client; "
                "keyword fallback is not performed."
            )
        self._collection = self._resolve_collection(client, collection_name, vectorizer)

    def index_documents(self, documents: Iterable[SearchDocument]) -> None:
        for document in documents:
            properties = {
                "doc_id": document.doc_id,
                "title": document.title,
                "text": document.text,
                **_flatten_metadata(document.metadata),
            }
            data = getattr(self._collection, "data", None)
            if data is None or not hasattr(data, "insert"):
                raise WeaviateUnavailableError("Weaviate collection does not expose data.insert")
            data.insert(properties=properties, uuid=document.doc_id)

    def index_pack(self, pack: SemanticPack) -> None:
        self.index_documents(documents_from_pack(pack))

    def search(
        self,
        query: str,
        *,
        card_types: Iterable[str] | None = None,
        limit: int = 10,
        filters: Mapping[str, Any] | None = None,
        query_mode: str = "hybrid",
        query_vector: Any | None = None,
    ) -> list[SearchResult]:
        if limit <= 0 or not str(query).strip():
            return []
        query_api = getattr(self._collection, "query", None)
        if query_api is None:
            raise WeaviateUnavailableError("Weaviate collection does not expose query operators")

        kwargs: dict[str, Any] = {"query": query, "limit": limit}
        where_filter = _build_weaviate_filter(_combine_filters(filters, card_types))
        if where_filter is not None:
            kwargs["filters"] = where_filter
        mode = str(query_mode or "hybrid").strip().casefold()
        if mode == "hybrid":
            if not hasattr(query_api, "hybrid"):
                raise WeaviateUnavailableError("Weaviate collection does not expose query.hybrid")
            response = query_api.hybrid(**kwargs)
        elif mode == "bm25":
            if not hasattr(query_api, "bm25"):
                raise WeaviateUnavailableError("Weaviate collection does not expose query.bm25")
            response = query_api.bm25(**kwargs)
        elif mode == "near_vector":
            if query_vector is None:
                raise WeaviateUnavailableError("Weaviate near_vector search requires an explicit query_vector")
            if not hasattr(query_api, "near_vector"):
                raise WeaviateUnavailableError("Weaviate collection does not expose query.near_vector")
            response = query_api.near_vector(near_vector=query_vector, limit=limit, **({} if where_filter is None else {"filters": where_filter}))
        else:
            raise WeaviateUnavailableError(f"Unsupported Weaviate query mode: {query_mode}")
        return [_result_from_weaviate_object(item) for item in getattr(response, "objects", response)]

    def _resolve_collection(self, client: Any, collection_name: str, vectorizer: str) -> Any:
        collections = getattr(client, "collections", None)
        if collections is None:
            raise WeaviateUnavailableError("Weaviate client does not expose collections")
        try:
            if hasattr(collections, "exists") and not collections.exists(collection_name):
                if not hasattr(collections, "create"):
                    raise WeaviateUnavailableError("Weaviate client cannot create missing collection")
                # Vectorizer is explicit and defaults to none so tests/offline
                # embeddings cannot silently call external model services.
                collections.create(collection_name, vectorizer_config=vectorizer)
            return collections.get(collection_name)
        except Exception as exc:  # pragma: no cover - exercised with real clients.
            raise WeaviateUnavailableError(
                f"Weaviate collection '{collection_name}' is unavailable; keyword fallback is not performed."
            ) from exc


def documents_from_pack(pack: SemanticPack) -> list[SearchDocument]:
    """Build PII-safe search documents from Semantic Pack cards.

    This is a local text projection only: it does not execute SQL, connect to an
    external database, or embed raw source values. SearchDocument validation
    rejects PII-like literals before either backend can index them.
    """

    return [_document_from_card_document(document) for document in iter_pack_card_documents(pack)]


def _document_from_card_document(document: CardDocument) -> SearchDocument:
    metadata: dict[str, Any] = {
        **dict(document.metadata),
        "pack_id": document.pack_id,
        "space_id": document.space_id,
        "card_id": document.card_id,
        "card_type": document.card_type,
        "status": document.status,
        "source_path": document.source_path or f"semantic_pack.{document.card_type}.{document.card_id}",
    }
    if "allowed_roles" in metadata and "allowed_role" not in metadata:
        metadata["allowed_role"] = tuple(metadata["allowed_roles"])
    return SearchDocument(
        doc_id=document.card_id,
        title=str(metadata.get("label") or metadata.get("term") or metadata.get("question") or document.card_id),
        text=document.text,
        metadata=metadata,
    )


def _combine_filters(
    filters: Mapping[str, Any] | None,
    card_types: Iterable[str] | None,
) -> dict[str, Any] | None:
    combined = dict(filters or {})
    normalized_card_types = [_normalize_card_type(card_type) for card_type in card_types or []]
    if normalized_card_types:
        combined["card_type"] = normalized_card_types
    return combined or None


def _matches_filters(metadata: Mapping[str, Any], filters: Mapping[str, Any] | None) -> bool:
    if not filters:
        return True
    for key, expected in filters.items():
        actual = metadata.get(key)
        if isinstance(expected, Sequence) and not isinstance(expected, (str, bytes)):
            if actual not in expected and not _overlaps(actual, expected):
                return False
            continue
        if isinstance(actual, Sequence) and not isinstance(actual, (str, bytes)):
            if expected not in actual:
                return False
            continue
        if actual != expected:
            return False
    return True


def _overlaps(actual: Any, expected_values: Sequence[Any]) -> bool:
    if isinstance(actual, Sequence) and not isinstance(actual, (str, bytes)):
        return any(item in expected_values for item in actual)
    return False


def _build_weaviate_filter(filters: Mapping[str, Any] | None) -> Any | None:
    if not filters:
        return None
    try:
        from weaviate.classes.query import Filter  # type: ignore[import-not-found]
    except Exception as exc:
        # Caller-provided test/local collection doubles can accept a plain filter
        # payload without importing the Weaviate SDK. This still stays on the
        # explicit Weaviate backend path and does not substitute keyword search.
        if exc.__class__.__name__ == "ModuleNotFoundError":
            return {"operator": "and", "conditions": dict(filters)}
        raise WeaviateUnavailableError(
            "Metadata filters for Weaviate require the weaviate client package; "
            "keyword fallback is not performed."
        ) from exc

    clauses = []
    for key, expected in filters.items():
        prop_filter = Filter.by_property(str(key))
        if isinstance(expected, Sequence) and not isinstance(expected, (str, bytes)):
            clauses.append(prop_filter.contains_any(list(expected)))
        else:
            clauses.append(prop_filter.equal(expected))
    if not clauses:
        return None
    combined = clauses[0]
    for clause in clauses[1:]:
        combined = combined & clause
    return combined


def _result_from_weaviate_object(item: Any) -> SearchResult:
    properties = dict(getattr(item, "properties", {}) or {})
    metadata = {key: value for key, value in properties.items() if key not in {"doc_id", "title", "text"}}
    score = 0.0
    metadata_obj = getattr(item, "metadata", None)
    if metadata_obj is not None:
        score = float(getattr(metadata_obj, "score", getattr(metadata_obj, "certainty", 0.0)) or 0.0)
    return SearchResult(
        doc_id=str(properties.get("doc_id") or getattr(item, "uuid", "")),
        title=str(properties.get("title") or ""),
        text=str(properties.get("text") or ""),
        score=score,
        metadata=metadata,
    )


def _flatten_metadata(metadata: Mapping[str, Any]) -> dict[str, Any]:
    flattened: dict[str, Any] = {}
    for key, value in metadata.items():
        if isinstance(value, (str, int, float, bool)) or value is None:
            flattened[str(key)] = value
        elif isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray, str)):
            flattened[str(key)] = [str(item) for item in value]
        else:
            flattened[str(key)] = str(value)
    return flattened


def _reject_raw_value_payload(value: Any, path: str) -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            key_text = str(key)
            if key_text.casefold() in _RAW_VALUE_KEYS:
                raise ValueError(f"{path}.{key_text} must not store raw values")
            _reject_raw_value_payload(child, f"{path}.{key_text}")
        return
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        for index, child in enumerate(value):
            _reject_raw_value_payload(child, f"{path}[{index}]")
        return
    if isinstance(value, str) and _contains_raw_pii(value):
        raise ValueError(f"{path} must not contain raw PII-like values")


def _contains_raw_pii(value: str) -> bool:
    return bool(_EMAIL_RE.search(value) or _PHONE_RE.search(value))


def _normalize(value: str) -> str:
    return value.casefold().replace("_", " ").replace(".", " ").replace("-", " ")


def _normalize_card_type(value: str) -> str:
    value = value.strip().casefold()
    aliases = {
        "tables": "table",
        "columns": "column",
        "value_dictionaries": "value_dictionary",
        "metrics": "metric",
        "business_terms": "business_term",
        "terms": "business_term",
        "join_recipes": "join_recipe",
        "policies": "policy",
        "verified_queries": "verified_query",
        "reverse_questions": "reverse_question",
        "ambiguity_rules": "ambiguity_rule",
    }
    return aliases.get(value, value)


def _score(normalized_query: str, terms: list[str], haystack: str) -> int:
    score = 0
    if normalized_query in haystack:
        score += 10 + len(normalized_query)
    for term in terms:
        if term in haystack:
            score += 3 + len(term)
    return score
