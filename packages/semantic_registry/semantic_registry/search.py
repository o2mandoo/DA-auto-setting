"""Deterministic lexical card search over loaded Semantic Packs."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

from semantic_contracts import SemanticPack
from semantic_contracts.mcp_tool_contracts import ResolveBusinessTermsResponse

from .cards import CardDocument, CardRegistry, iter_pack_card_documents
from .store import PackStore

DEFAULT_PACK_ROOT = Path("semantic_packs")
_GENERIC_KOREAN_DOMAIN_TOKENS = {"고객", "매출", "금액", "날짜", "지역", "상품", "건수", "수량"}


@dataclass(frozen=True)
class CardSearchResult:
    pack_id: str
    card_type: str
    card_id: str
    title: str
    snippet: str
    score: int
    status: str = "unknown"
    text: str = ""
    metadata: Mapping[str, Any] | None = None
    source_path: str = ""

    @property
    def source_pack(self) -> str:
        return self.pack_id

    def as_dict(self) -> dict[str, object]:
        return {
            "pack_id": self.pack_id,
            "source_pack": self.source_pack,
            "card_type": self.card_type,
            "card_id": self.card_id,
            "title": self.title,
            "snippet": self.snippet,
            "score": self.score,
            "status": self.status,
            "text": self.text,
            "metadata": dict(self.metadata or {}),
            "source_path": self.source_path,
        }


class SearchIndex:
    """Small plain lexical search index."""

    def __init__(self, packs: Iterable[SemanticPack] | SemanticPack):
        if isinstance(packs, SemanticPack):
            packs = [packs]
        self._cards = [card for pack in packs for card in _iter_cards(pack)]

    @classmethod
    def from_pack(cls, pack: SemanticPack) -> "SearchIndex":
        return cls([pack])

    def search(
        self,
        query: str,
        card_types: Iterable[str] | None = None,
        limit: int = 10,
    ) -> list[CardSearchResult]:
        return self.search_cards(query, card_types=card_types, limit=limit)

    def search_cards(
        self,
        query: str,
        card_types: Iterable[str] | None = None,
        limit: int = 10,
    ) -> list[CardSearchResult]:
        if limit <= 0:
            return []
        normalized_query = _normalize(query)
        terms = [term for term in normalized_query.split() if term]
        allowed_types = {_normalize_card_type(card_type) for card_type in card_types or []}
        results: list[CardSearchResult] = []
        for card in self._cards:
            if allowed_types and card["card_type"] not in allowed_types:
                continue
            metadata = dict(card.get("metadata") or {})
            if metadata.get("can_use_for_text2sql") is False:
                continue
            haystack = card["search_text"]
            score = _score(normalized_query, terms, haystack)
            if score <= 0:
                continue
            results.append(CardSearchResult(
                pack_id=card["pack_id"],
                card_type=card["card_type"],
                card_id=card["card_id"],
                title=card["title"],
                snippet=card["snippet"],
                score=score,
                status=card["status"],
                text=card["text"],
                metadata=card["metadata"],
                source_path=card["source_path"],
            ))
        results.sort(key=lambda item: (-item.score, item.card_type, item.card_id))
        return results[:limit]


def search_cards(
    query: str,
    card_types: Iterable[str] | None = None,
    limit: int = 10,
    root: str | Path = DEFAULT_PACK_ROOT,
) -> list[CardSearchResult]:
    store = PackStore(root)
    packs = [store.load_pack(info.pack_id) for info in store.list_packs()]
    return SearchIndex(packs).search_cards(query, card_types=card_types, limit=limit)


def resolve_terms(
    terms: Iterable[str],
    pack: SemanticPack | None = None,
    space_id: str | None = None,
    root: str | Path = DEFAULT_PACK_ROOT,
) -> ResolveBusinessTermsResponse:
    """Resolve business terms by id, label, or alias using local packs only."""

    packs = [pack] if pack is not None else _load_resolution_packs(space_id=space_id, root=root)
    cards = [card for candidate in packs for card in CardRegistry.from_pack(candidate).cards]
    return CardRegistry(cards).resolve_terms(terms)


def _load_resolution_packs(space_id: str | None, root: str | Path) -> list[SemanticPack]:
    store = PackStore(root)
    if space_id:
        try:
            return [store.load_pack(space_id)]
        except KeyError:
            return []
    return [store.load_pack(info.pack_id) for info in store.list_packs()]


def _iter_cards(pack: SemanticPack) -> Iterable[dict[str, Any]]:
    for document in iter_pack_card_documents(pack):
        yield _card_from_document(document)


def _card_from_document(document: CardDocument) -> dict[str, Any]:
    title = _title_from_document(document)
    snippet = document.text[:240]
    return {
        "pack_id": document.pack_id,
        "card_type": document.card_type,
        "card_id": document.card_id,
        "title": title,
        "snippet": snippet,
        "status": document.status,
        "text": document.text,
        "metadata": dict(document.metadata),
        "source_path": document.source_path,
        "search_text": _normalize(document.text),
    }


def _title_from_document(document: CardDocument) -> str:
    metadata = dict(document.metadata)
    if document.card_type in {"column", "value_dictionary"}:
        table = metadata.get("table")
        column = metadata.get("column")
        if table and column:
            return f"{table}.{column}"
    for key in ("label", "term", "question", "physical_name", "name"):
        value = metadata.get(key)
        if value:
            return str(value)
    return document.card_id

def _card(pack_id: str, card_type: str, card_id: str, title: str, *parts: Any) -> dict[str, Any]:
    text_parts = [pack_id, card_type, card_id, title, *("" if part is None else str(part) for part in parts)]
    text = " ".join(text_parts)
    return {
        "pack_id": pack_id,
        "card_type": card_type,
        "card_id": card_id,
        "title": title,
        "snippet": " ".join(str(part) for part in [title, *parts] if part)[:240],
        "status": "unknown",
        "text": text,
        "metadata": {},
        "source_path": "",
        "search_text": _normalize(text),
    }


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
    }
    return aliases.get(value, value)


def _score(normalized_query: str, terms: list[str], haystack: str) -> int:
    if not normalized_query:
        return 0
    score = 0
    exact_phrase = normalized_query in haystack
    if exact_phrase:
        score += 10 + len(normalized_query)
    matched_terms = [term for term in terms if term in haystack]
    meaningful_terms = [term for term in matched_terms if term not in _GENERIC_KOREAN_DOMAIN_TOKENS]
    if not exact_phrase and matched_terms and not meaningful_terms:
        # Do not let broad Korean domain words such as "고객" turn an unknown
        # phrase like "휴면 고객" into a confident hit for "신규 고객".
        return 0
    for term in matched_terms:
        score += 3 + len(term)
    return score
