"""MCP semantic-context search adapter with explicit backend selection.

This module stays metadata-only: it indexes local Semantic Pack cards and never
executes SQL, opens databases, calls LLMs, or talks to a VDB unless the caller
explicitly selects that backend and provides the required configuration.
"""

from __future__ import annotations

import inspect
from pathlib import Path
from typing import Any, Iterable, Mapping

from semantic_registry.store import DEFAULT_PACK_ROOT, PackStore

_CARD_TYPE_ALIASES = {
    "business_terms": "business_term",
    "terms": "business_term",
    "metrics": "metric",
    "tables": "table",
    "columns": "column",
    "join_recipes": "join_recipe",
    "policies": "policy",
    "verified_queries": "verified_query",
    "value_dictionaries": "value_dictionary",
    "reverse_questions": "reverse_question",
    "ambiguity_rules": "ambiguity_rule",
}
_SUPPORTED_BACKENDS = {"keyword", "weaviate"}
_SUPPORTED_QUERY_MODES = {"keyword", "bm25", "hybrid", "near_vector"}


class SearchBackendConfigurationError(RuntimeError):
    """Raised when an explicitly selected backend cannot be configured."""


def search_semantic_context(
    space_id: str,
    query: str,
    filters: Mapping[str, Any] | None = None,
    pack_root: str | Path = DEFAULT_PACK_ROOT,
    root: str | Path | None = None,
    backend: str | None = None,
) -> dict[str, Any]:
    """Search local Semantic Pack cards and return structured MCP results.

    The backend is explicit. ``keyword`` is the local default. ``weaviate`` is a
    seam only: if its dependency/config is absent, the tool returns an explicit
    error instead of silently using keyword search.
    """

    effective_root = root if root is not None else pack_root
    filter_payload = dict(filters or {})
    selected_backend = _normalize_backend(backend or filter_payload.pop("backend", None) or "keyword")
    card_types = [_normalize_card_type(value) for value in _list_filter(filter_payload.pop("card_types", []))]
    limit = _coerce_limit(filter_payload.pop("limit", 10))
    backend_config_raw = filter_payload.pop("backend_config", None) or filter_payload.pop("weaviate", None)
    backend_config = dict(backend_config_raw) if isinstance(backend_config_raw, Mapping) else backend_config_raw
    query_vector = (
        filter_payload.pop("query_vector", None)
        or (backend_config.get("query_vector") if isinstance(backend_config, Mapping) else None)
    )
    query_mode = _normalize_query_mode(
        filter_payload.pop("query_mode", None)
        or (backend_config.get("query_mode") if isinstance(backend_config, Mapping) else None)
        or ("hybrid" if selected_backend == "weaviate" else "keyword")
    )
    applied_filters = _backend_filters(filter_payload, card_types)

    try:
        packs = _load_space_packs(space_id, effective_root)
    except KeyError:
        return {
            "backend": selected_backend,
            "query_mode": query_mode,
            "filters_applied": applied_filters,
            "fallback_used": False,
            "results": [],
            "warnings": [f"Unknown semantic space: {space_id}"],
            "error": {
                "code": "unknown_space",
                "message": f"Unknown semantic space: {space_id}",
                "backend": selected_backend,
                "query_mode": query_mode,
                "filters_applied": applied_filters,
            },
        }

    status_by_id = _status_lookup(packs)
    source_by_id = _source_uri_lookup(packs)
    try:
        raw_results, backend_warnings = _run_backend(
            selected_backend,
            packs,
            query=query,
            card_types=card_types,
            limit=limit,
            filters=applied_filters,
            backend_config=backend_config,
            query_mode=query_mode,
            query_vector=query_vector,
        )
    except SearchBackendConfigurationError as exc:
        return {
            "backend": selected_backend,
            "query_mode": query_mode,
            "filters_applied": applied_filters,
            "fallback_used": False,
            "results": [],
            "warnings": [str(exc)],
            "error": {
                "code": "backend_configuration_error",
                "message": str(exc),
                "backend": selected_backend,
                "query_mode": query_mode,
                "filters_applied": applied_filters,
            },
        }

    max_score = max((_raw_score(result) for result in raw_results), default=1.0) or 1.0
    normalized_results = [
        _structured_result(result, max_score=max_score, status_by_id=status_by_id, source_by_id=source_by_id)
        for result in raw_results
    ]
    return {
        "backend": selected_backend,
        "query_mode": query_mode,
        "filters_applied": applied_filters,
        "fallback_used": bool(backend_warnings),
        "results": normalized_results,
        "warnings": backend_warnings,
        "error": None,
    }


def _run_backend(
    selected_backend: str,
    packs: Iterable[Any],
    *,
    query: str,
    card_types: list[str],
    limit: int,
    filters: Mapping[str, Any],
    backend_config: Mapping[str, Any] | None,
    query_mode: str,
    query_vector: Any | None,
) -> tuple[list[Any], list[str]]:
    if selected_backend == "keyword":
        backend = _optional_keyword_backend()
        if backend is None:
            raise SearchBackendConfigurationError(
                "keyword backend selected, but semantic_registry.retrieval.KeywordSearchBackend is unavailable; "
                "no keyword fallback was used"
            )
        backend_filters = _backend_filters(filters, card_types)
        if hasattr(backend, "index_pack"):
            for pack in packs:
                backend.index_pack(pack)
            return _invoke_search(
                backend,
                query=query,
                card_types=card_types,
                limit=limit,
                filters=backend_filters,
                query_mode=query_mode,
                query_vector=query_vector,
            ), []
        if hasattr(backend, "index_documents"):
            backend.index_documents(_search_documents_from_packs(packs))
            return _invoke_search(
                backend,
                query=query,
                card_types=card_types,
                limit=limit,
                filters=backend_filters,
                query_mode=query_mode,
                query_vector=query_vector,
            ), []
        raise SearchBackendConfigurationError(
            "keyword backend selected, but semantic_registry.retrieval.KeywordSearchBackend does not expose "
            "an indexable/searchable interface"
        )

    if selected_backend == "weaviate":
        backend_cls = _optional_weaviate_backend()
        if backend_cls is None:
            raise SearchBackendConfigurationError(
                "weaviate backend selected, but semantic_registry.retrieval.WeaviateSearchBackend is unavailable; no keyword fallback was used"
            )
        if not backend_config:
            raise SearchBackendConfigurationError(
                "weaviate backend selected, but backend_config is required; no keyword fallback was used"
            )
        try:
            from semantic_registry.retrieval import WeaviateUnavailableError
        except ModuleNotFoundError as exc:  # pragma: no cover - guarded by _optional_weaviate_backend.
            raise SearchBackendConfigurationError(
                "weaviate backend selected, but semantic_registry.retrieval is unavailable; no keyword fallback was used"
            ) from exc

        try:
            backend = backend_cls(**_weaviate_backend_init_kwargs(backend_cls, backend_config))
            if hasattr(backend, "index_pack"):
                for pack in packs:
                    backend.index_pack(pack)
                return _invoke_search(
                    backend,
                    query=query,
                    card_types=card_types,
                    limit=limit,
                    filters=filters,
                    query_mode=query_mode,
                    query_vector=query_vector,
                ), []
            backend.index_documents(_search_documents_from_packs(packs))
            return _invoke_search(
                backend,
                query=query,
                card_types=card_types,
                limit=limit,
                filters=filters,
                query_mode=query_mode,
                query_vector=query_vector,
            ), []
        except WeaviateUnavailableError as exc:
            raise SearchBackendConfigurationError(str(exc)) from exc

    raise SearchBackendConfigurationError(f"Unsupported search backend: {selected_backend}")


def _optional_keyword_backend() -> Any | None:
    try:
        from semantic_registry.retrieval import KeywordSearchBackend
    except ModuleNotFoundError as exc:
        if exc.name == "semantic_registry.retrieval":
            return None
        raise
    except ImportError as exc:
        if "KeywordSearchBackend" in str(exc):
            return None
        raise
    return KeywordSearchBackend()


def _optional_weaviate_backend() -> Any | None:
    try:
        from semantic_registry.retrieval import WeaviateSearchBackend
    except ModuleNotFoundError as exc:
        if exc.name == "semantic_registry.retrieval":
            return None
        raise
    except ImportError as exc:
        if "WeaviateSearchBackend" in str(exc):
            return None
        raise
    return WeaviateSearchBackend


def _structured_result(
    result: Any, *, max_score: float, status_by_id: Mapping[str, str], source_by_id: Mapping[str, str]
) -> dict[str, Any]:
    card_id = str(_get(result, "card_id", "doc_id", "id"))
    card_type = str(_get(result, "card_type", "type"))
    status = str(_get(result, "status", default=status_by_id.get(card_id, "unknown")))
    score = _raw_score(result)
    normalized_score = score / max_score if max_score > 1 else score
    warnings = [str(value) for value in _list_filter(_get(result, "warnings", default=[]))]
    if status == "draft":
        warnings.append("draft_card")

    summary = _get(result, "summary", "snippet", "text", default="")
    title = _get(result, "title", default=None)
    source_uri = _get(result, "source_uri", "source_path", default=source_by_id.get(card_id, ""))
    source_pack = _get(result, "source_pack", "pack_id", default="")
    return {
        "card_type": card_type,
        "card_id": card_id,
        "score": round(float(normalized_score), 6),
        "summary": str(summary or title or "")[:500],
        "source_uri": str(source_uri),
        "status": status,
        "warnings": _unique(warnings),
        # Legacy keys remain for existing MCP clients and tests while the new
        # structured fields above become the preferred Phase 7 contract.
        "title": title or card_id,
        "snippet": summary,
        "source_pack": source_pack,
    }


def _search_documents_from_packs(packs: Iterable[Any]) -> list[Any]:
    from semantic_registry.cards import iter_pack_cards
    from semantic_registry.retrieval import SearchDocument

    documents: list[Any] = []
    for pack in packs:
        for card in iter_pack_cards(pack):
            payload = card.payload
            status = str(getattr(payload, "status", getattr(pack, "status", "unknown")))
            metadata = {
                "card_id": card.card_id,
                "card_type": card.card_type,
                "pack_id": pack.id,
                "space_id": card.space_id,
                "status": status,
                "source_uri": f"semantic://packs/{pack.id}/{card.card_type}/{card.card_id}",
            }
            roles = _roles_for_payload(payload)
            if roles:
                metadata["roles"] = roles
            # Keep metadata filterable but keep raw/blocked values out of indexed
            # text. This projection uses titles, snippets, and safe descriptive
            # keywords only; no SQL is executed and no database values are read.
            documents.append(SearchDocument(
                doc_id=card.card_id,
                title=card.title,
                text=_safe_document_text(card),
                metadata=metadata,
            ))
    return documents


def _safe_document_text(card: Any) -> str:
    parts = [card.snippet or ""]
    if card.card_type != "policy":
        parts.extend(str(value) for value in card.keywords if value)
    return " ".join(parts)


def _roles_for_payload(payload: Any) -> list[str]:
    applies_to = getattr(payload, "applies_to", None)
    roles = getattr(applies_to, "roles", None)
    return [str(role) for role in roles] if roles else []


def _backend_filters(filters: Mapping[str, Any], card_types: list[str]) -> dict[str, Any]:
    backend_filters = dict(filters)
    if card_types:
        backend_filters["card_type"] = card_types
    allowed_role = backend_filters.pop("allowed_role", None)
    if allowed_role is not None:
        backend_filters["roles"] = allowed_role
    return backend_filters


def _invoke_search(
    backend: Any,
    *,
    query: str,
    card_types: list[str],
    limit: int,
    filters: Mapping[str, Any],
    query_mode: str,
    query_vector: Any | None,
) -> list[Any]:
    search = getattr(backend, "search")
    kwargs: dict[str, Any] = {"card_types": card_types, "limit": limit, "filters": filters}
    if query_mode and _search_accepts_query_mode(search):
        kwargs["query_mode"] = query_mode
    if query_vector is not None and _search_accepts_query_vector(search):
        kwargs["query_vector"] = query_vector
    return list(search(query, **kwargs))


def _search_accepts_query_mode(search: Any) -> bool:
    try:
        return "query_mode" in inspect.signature(search).parameters
    except (TypeError, ValueError):
        return False


def _search_accepts_query_vector(search: Any) -> bool:
    try:
        return "query_vector" in inspect.signature(search).parameters
    except (TypeError, ValueError):
        return False


def _weaviate_backend_init_kwargs(backend_cls: Any, backend_config: Mapping[str, Any]) -> dict[str, Any]:
    try:
        parameters = inspect.signature(backend_cls).parameters
    except (TypeError, ValueError):
        parameters = {}
    allowed = {name for name in parameters if name != "self"}
    init_kwargs = {str(key): value for key, value in backend_config.items() if str(key) in allowed}
    # Live Weaviate config may carry extra transport fields such as URL/API key
    # for a future client factory. We keep the MCP path explicit by only passing
    # constructor-supported kwargs to the registry backend seam.
    return init_kwargs


def _load_space_packs(space_id: str, pack_root: str | Path) -> list[Any]:
    store = PackStore(pack_root)
    packs = store.load_packs()
    selected = [pack for pack in packs if pack.id == space_id or any(space.id == space_id for space in pack.spaces)]
    if not selected:
        raise KeyError(f"Unknown semantic space: {space_id}")
    return selected


def _status_lookup(packs: Iterable[Any]) -> dict[str, str]:
    statuses: dict[str, str] = {}
    for pack in packs:
        pack_status = str(getattr(pack, "status", "unknown"))
        families = (
            ("table", getattr(pack, "tables", ())),
            ("column", getattr(pack, "columns", ())),
            ("metric", getattr(pack, "metrics", ())),
            ("business_term", getattr(pack, "business_terms", ())),
            ("verified_query", getattr(pack, "verified_queries", ())),
            ("reverse_question", getattr(pack, "reverse_questions", ())),
        )
        for _card_type, items in families:
            for item in items:
                statuses[item.id] = str(getattr(item, "status", pack_status))
        for item in getattr(pack, "value_dictionaries", ()):  # dictionary status is entry-level in the contract.
            statuses[item.id] = str(item.values[0].status if item.values else pack_status)
        for item in getattr(pack, "join_recipes", ()):  # join/policy cards inherit pack status.
            statuses[item.id] = pack_status
        for item in getattr(pack, "policies", ()):  # policies have no per-card status in Phase 0.
            statuses[item.id] = pack_status
        for term in getattr(pack, "business_terms", ()):  # ambiguity rules are nested cards for retrieval.
            for rule in getattr(term, "ambiguity_rules", ()):
                statuses[rule.id] = str(getattr(rule, "status", pack_status))
    return statuses


def _source_uri_lookup(packs: Iterable[Any]) -> dict[str, str]:
    source_uris: dict[str, str] = {}
    for pack in packs:
        for card_type, items in (
            ("table", getattr(pack, "tables", ())),
            ("column", getattr(pack, "columns", ())),
            ("value_dictionary", getattr(pack, "value_dictionaries", ())),
            ("metric", getattr(pack, "metrics", ())),
            ("business_term", getattr(pack, "business_terms", ())),
            ("join_recipe", getattr(pack, "join_recipes", ())),
            ("policy", getattr(pack, "policies", ())),
            ("verified_query", getattr(pack, "verified_queries", ())),
            ("reverse_question", getattr(pack, "reverse_questions", ())),
        ):
            for item in items:
                source_uris[item.id] = f"semantic://packs/{pack.id}/{card_type}/{item.id}"
        for term in getattr(pack, "business_terms", ()):
            for rule in getattr(term, "ambiguity_rules", ()):
                source_uris[rule.id] = f"semantic://packs/{pack.id}/ambiguity_rule/{rule.id}"
    return source_uris


def _normalize_backend(value: str) -> str:
    normalized = str(value).strip().casefold()
    if normalized not in _SUPPORTED_BACKENDS:
        raise SearchBackendConfigurationError(f"Unsupported search backend: {value}")
    return normalized


def _normalize_query_mode(value: Any) -> str:
    normalized = str(value).strip().casefold()
    if normalized not in _SUPPORTED_QUERY_MODES:
        raise SearchBackendConfigurationError(f"Unsupported search query_mode: {value}")
    return normalized


def _normalize_card_type(value: str) -> str:
    lowered = str(value).strip().casefold()
    return _CARD_TYPE_ALIASES.get(lowered, lowered)


def _coerce_limit(value: Any) -> int:
    limit = int(value)
    return max(1, min(limit, 100))


def _raw_score(result: Any) -> float:
    try:
        return float(_get(result, "score", default=0.0) or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _get(result: Any, *names: str, default: Any = None) -> Any:
    for name in names:
        if isinstance(result, Mapping) and name in result:
            return result[name]
        if hasattr(result, name):
            return getattr(result, name)
    metadata = result.get("metadata") if isinstance(result, Mapping) else getattr(result, "metadata", None)
    if isinstance(metadata, Mapping):
        for name in names:
            if name in metadata:
                return metadata[name]
    return default


def _list_filter(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    return list(value)


def _unique(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


__all__ = ["SearchBackendConfigurationError", "search_semantic_context"]
