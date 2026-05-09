"""Card extraction helpers for local Semantic Pack registry search."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping

from semantic_contracts import RawValueStorage, SemanticPack
from semantic_contracts.mcp_tool_contracts import ResolvedTerm, ResolveBusinessTermsResponse


@dataclass(frozen=True)
class CardDocument:
    """Policy-filtered document used by Phase 7 retrieval backends.

    ``text`` is the only field intended for keyword/vector indexing. It must not
    contain raw PII values; metadata carries only safe identifiers and policy
    flags needed for filtering/explainability.
    """

    card_id: str
    card_type: str
    pack_id: str
    space_id: str
    status: str
    text: str
    metadata: Mapping[str, Any] = field(default_factory=dict)
    source_path: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "card_id": self.card_id,
            "card_type": self.card_type,
            "pack_id": self.pack_id,
            "space_id": self.space_id,
            "status": self.status,
            "text": self.text,
            "metadata": dict(self.metadata),
            "source_path": self.source_path,
        }


@dataclass(frozen=True)
class RegistryCard:
    """Flattened, searchable view of one Semantic Pack card."""

    card_id: str
    card_type: str
    title: str
    snippet: str | None
    source_pack: str
    space_id: str
    keywords: tuple[str, ...] = field(default_factory=tuple)
    payload: Any | None = None


class CardRegistry:
    """In-memory registry of flattened cards from one or more Semantic Packs."""

    def __init__(self, cards: Iterable[RegistryCard] = ()) -> None:
        self._cards = tuple(cards)
        self._by_id = {card.card_id: card for card in self._cards}

    @classmethod
    def from_pack(cls, pack: SemanticPack) -> "CardRegistry":
        return cls(iter_pack_cards(pack))

    @property
    def cards(self) -> tuple[RegistryCard, ...]:
        return self._cards

    def get(self, card_id: str) -> RegistryCard | None:
        return self._by_id.get(card_id)

    def by_type(self, card_type: str) -> tuple[RegistryCard, ...]:
        return tuple(card for card in self._cards if card.card_type == card_type)

    def resolve_terms(self, terms: Iterable[str]) -> ResolveBusinessTermsResponse:
        """Resolve business terms by id, display term, or alias from indexed cards."""

        requested = [str(term) for term in terms if str(term).strip()]
        indexed: dict[str, object] = {}
        for card in self.by_type("business_term"):
            term = card.payload
            if term is None:
                continue
            for key in _term_keys(term):
                indexed[key] = term

        resolved: list[ResolvedTerm] = []
        unresolved: list[str] = []
        seen_term_ids: set[str] = set()
        for original in requested:
            match = indexed.get(_normalize_term_key(original))
            if match is None:
                unresolved.append(original)
                continue
            if match.id in seen_term_ids:
                continue
            seen_term_ids.add(match.id)
            resolved.append(ResolvedTerm(
                input=original,
                term_id=match.id,
                definition=match.definition,
                sql_condition=match.sql_condition,
                status=str(match.status),
            ))
        return ResolveBusinessTermsResponse(resolved_terms=resolved, unresolved_terms=unresolved)


def iter_pack_card_documents(pack: SemanticPack, source_path: str | Path | None = None) -> Iterable[CardDocument]:
    """Yield policy-filtered retrieval documents for Semantic Pack cards.

    The projection is metadata-only and local: it does not execute SQL, connect
    to an external database, or call a VDB. Raw value dictionary entries are
    included only for columns explicitly marked safe for raw-value storage.
    """

    source = "" if source_path is None else str(source_path)
    default_space_id = _default_space_id(pack)
    table_space = {table.physical_name: table.space_id for table in pack.tables}
    column_safety = {_column_key(column.table, column.name): _column_allows_raw_values(column) for column in pack.columns}

    for table in pack.tables:
        yield _document(
            pack=pack,
            card_id=table.id,
            card_type="table",
            space_id=table.space_id,
            status=table.status,
            text_parts=(
                table.id,
                table.title,
                table.physical_name,
                table.description,
                table.role,
                table.grain,
                table.primary_key,
                *table.columns,
            ),
            metadata={
                "physical_name": table.physical_name,
                "role": str(table.role),
                "grain": table.grain,
                "primary_key": table.primary_key,
                "columns": list(table.columns),
                "pii_level": str(table.pii_level),
                "confidence": table.confidence,
            },
            source_path=source,
        )

    for column in pack.columns:
        column_ref = f"{column.table}.{column.name}"
        yield _document(
            pack=pack,
            card_id=column.id,
            card_type="column",
            space_id=table_space.get(column.table, default_space_id),
            status=column.status,
            text_parts=(
                column.id,
                column_ref,
                column.table,
                column.name,
                column.data_type,
                column.semantic_type,
                column.description,
                "pii_candidate" if column.pii.is_candidate else None,
                f"raw_value_storage:{column.pii.raw_value_storage}",
            ),
            metadata={
                "table": column.table,
                "column": column.name,
                "data_type": column.data_type,
                "nullable": column.nullable,
                "semantic_type": column.semantic_type,
                "pii_candidate": column.pii.is_candidate,
                "raw_value_storage": str(column.pii.raw_value_storage),
                "top_values_safe": column.profile.top_values_safe,
                "confidence": column.confidence,
            },
            source_path=source,
        )

    for dictionary in pack.value_dictionaries:
        column_key = _column_key(dictionary.table, dictionary.column)
        values_are_safe = column_safety.get(column_key, False)
        value_text, value_metadata = _safe_value_dictionary_projection(dictionary, values_are_safe=values_are_safe)
        yield _document(
            pack=pack,
            card_id=dictionary.id,
            card_type="value_dictionary",
            space_id=table_space.get(dictionary.table, default_space_id),
            status=value_metadata["status"],
            text_parts=(dictionary.id, dictionary.table, dictionary.column, value_text),
            metadata={
                "table": dictionary.table,
                "column": dictionary.column,
                **value_metadata,
            },
            source_path=source,
        )

    for metric in pack.metrics:
        yield _document(
            pack=pack,
            card_id=metric.id,
            card_type="metric",
            space_id=default_space_id,
            status=metric.status,
            text_parts=(
                metric.id,
                metric.name,
                metric.label,
                metric.description,
                metric.formula_sql,
                metric.date_basis,
                metric.owner,
                *metric.required_tables,
                *metric.default_filters,
            ),
            metadata={
                "name": metric.name,
                "label": metric.label,
                "date_basis": metric.date_basis,
                "required_tables": list(metric.required_tables),
                "default_filters": list(metric.default_filters),
                "owner": metric.owner,
            },
            source_path=source,
        )

    for term in pack.business_terms:
        yield _document(
            pack=pack,
            card_id=term.id,
            card_type="business_term",
            space_id=default_space_id,
            status=term.status,
            text_parts=(
                term.id,
                term.term,
                term.definition,
                term.sql_condition,
                term.ambiguity_policy,
                *term.aliases,
                *term.related_tables,
                *term.related_metrics,
            ),
            metadata={
                "term": term.term,
                "aliases": list(term.aliases),
                "related_tables": list(term.related_tables),
                "related_metrics": list(term.related_metrics),
                "ambiguity_policy": term.ambiguity_policy,
            },
            source_path=source,
        )
        for rule in term.ambiguity_rules:
            yield _document(
                pack=pack,
                card_id=rule.id,
                card_type="ambiguity_rule",
                space_id=default_space_id,
                status=rule.status,
                text_parts=(rule.id, rule.target, rule.condition, rule.question, rule.required_when, term.id, term.term),
                metadata={
                    "target": rule.target,
                    "parent_term_id": term.id,
                    "condition": rule.condition,
                    "required_when": rule.required_when,
                },
                source_path=source,
            )

    for join in pack.join_recipes:
        yield _document(
            pack=pack,
            card_id=join.id,
            card_type="join_recipe",
            space_id=default_space_id,
            status=pack.status,
            text_parts=(join.id, join.left_table, join.right_table, join.join_type, join.condition, *join.warnings),
            metadata={
                "left_table": join.left_table,
                "right_table": join.right_table,
                "join_type": join.join_type,
                "recommended": join.recommended,
                "warnings": list(join.warnings),
            },
            source_path=source,
        )

    for policy in pack.policies:
        roles = tuple(policy.applies_to.roles)
        yield _document(
            pack=pack,
            card_id=policy.id,
            card_type="policy",
            space_id=default_space_id,
            status=pack.status,
            text_parts=(policy.id, *roles, *policy.allowed_tables, *policy.blocked_columns, *policy.notes),
            metadata={
                "allowed_roles": list(roles),
                "allowed_tables": list(policy.allowed_tables),
                "blocked_columns": list(policy.blocked_columns),
                "notes": list(policy.notes),
            },
            source_path=source,
        )

    for query in pack.verified_queries:
        yield _document(
            pack=pack,
            card_id=query.id,
            card_type="verified_query",
            space_id=default_space_id,
            status=query.status,
            text_parts=(query.id, query.question, query.sql, *query.related_terms, *query.related_metrics),
            metadata={
                "question": query.question,
                "related_terms": list(query.related_terms),
                "related_metrics": list(query.related_metrics),
            },
            source_path=source,
        )

    for question in pack.reverse_questions:
        yield _document(
            pack=pack,
            card_id=question.id,
            card_type="reverse_question",
            space_id=default_space_id,
            status=question.status,
            text_parts=(question.id, question.target, question.question, question.reason, question.answer),
            metadata={
                "target": question.target,
                "question": question.question,
                "answer_present": bool(question.answer),
            },
            source_path=source,
        )


def iter_pack_cards(pack: SemanticPack) -> Iterable[RegistryCard]:
    """Yield searchable cards for all Registry-supported card families."""

    source_pack = f"{pack.id}@{pack.version}"

    for document in iter_pack_card_documents(pack):
        metadata = dict(document.metadata)
        title = _document_title(document)
        yield RegistryCard(
            card_id=document.card_id,
            card_type=document.card_type,
            title=title,
            snippet=document.text[:240] or None,
            source_pack=source_pack,
            space_id=document.space_id,
            keywords=tuple(_keyword_values(document.text, metadata)),
            payload=_payload_for_card(pack, document.card_id, document.card_type),
        )


def _document(
    *,
    pack: SemanticPack,
    card_id: str,
    card_type: str,
    space_id: str,
    status: object,
    text_parts: Iterable[Any],
    metadata: Mapping[str, Any],
    source_path: str,
) -> CardDocument:
    status_text = _status_text(status)
    clean_metadata = {key: value for key, value in metadata.items() if value is not None}
    clean_metadata.update({"pack_version": pack.version, "pack_status": str(pack.status)})
    return CardDocument(
        card_id=card_id,
        card_type=card_type,
        pack_id=pack.id,
        space_id=space_id,
        status=status_text,
        text=_join_text(pack.id, card_type, card_id, *text_parts),
        metadata=clean_metadata,
        source_path=source_path,
    )


def _safe_value_dictionary_projection(dictionary: object, *, values_are_safe: bool) -> tuple[str, dict[str, Any]]:
    values = list(dictionary.values)
    entry_statuses = [_status_text(entry.status) for entry in values]
    status = _first_status(entry_statuses, default="draft")
    if not values_are_safe:
        # Safety boundary: blocked or untrusted columns can still be discovered by
        # table/column, but their raw dictionary values are never indexed/stored.
        return "raw values blocked by policy", {
            "status": status,
            "value_count": len(values),
            "values_indexed": False,
            "pii_raw_values_indexed": False,
        }

    safe_values = [
        {
            "value": entry.value,
            "label": entry.label,
            "description": entry.description,
            "source": str(entry.source),
            "status": _status_text(entry.status),
        }
        for entry in values
    ]
    value_text = " ".join(
        _join_text(entry["value"], entry["label"], entry["description"], entry["source"], entry["status"])
        for entry in safe_values
    )
    return value_text, {
        "status": status,
        "value_count": len(values),
        "values_indexed": True,
        "pii_raw_values_indexed": False,
        "values": safe_values,
    }


def _column_allows_raw_values(column: object) -> bool:
    return (
        not column.pii.is_candidate
        and column.pii.raw_value_storage == RawValueStorage.ALLOWED
        and column.profile.top_values_safe is True
    )


def _payload_for_card(pack: SemanticPack, card_id: str, card_type: str) -> Any | None:
    families = {
        "table": pack.tables,
        "column": pack.columns,
        "value_dictionary": pack.value_dictionaries,
        "metric": pack.metrics,
        "business_term": pack.business_terms,
        "join_recipe": pack.join_recipes,
        "policy": pack.policies,
        "verified_query": pack.verified_queries,
        "reverse_question": pack.reverse_questions,
    }
    if card_type == "ambiguity_rule":
        for term in pack.business_terms:
            for rule in term.ambiguity_rules:
                if rule.id == card_id:
                    return rule
        return None
    for item in families.get(card_type, ()):  # type: ignore[arg-type]
        if item.id == card_id:
            return item
    return None


def _document_title(document: CardDocument) -> str:
    metadata = dict(document.metadata)
    if document.card_type == "column":
        return f"{metadata.get('table')}.{metadata.get('column')}"
    if document.card_type == "value_dictionary":
        return f"{metadata.get('table')}.{metadata.get('column')}"
    for key in ("label", "term", "question", "physical_name", "name"):
        value = metadata.get(key)
        if value:
            return str(value)
    return document.card_id


def _keyword_values(text: str, metadata: Mapping[str, Any]) -> Iterable[str]:
    yield text
    for value in metadata.values():
        if isinstance(value, str):
            yield value
        elif isinstance(value, (list, tuple)):
            yield from (str(item) for item in value if not isinstance(item, Mapping))


def _join_text(*parts: Any) -> str:
    return " ".join(str(part) for part in parts if part is not None and str(part).strip())


def _default_space_id(pack: SemanticPack) -> str:
    return pack.spaces[0].id if pack.spaces else pack.id


def _column_key(table: str, column: str) -> str:
    return f"{table}.{column}".casefold()


def _status_text(value: object) -> str:
    return str(value.value if hasattr(value, "value") else value)


def _first_status(statuses: Iterable[str], *, default: str) -> str:
    for status in statuses:
        if status:
            return status
    return default


def _term_keys(term: object) -> set[str]:
    keys = {term.id, term.term, *term.aliases}
    if term.id.startswith("term."):
        keys.add(term.id.removeprefix("term."))
    return {_normalize_term_key(str(key)) for key in keys if str(key).strip()}


def _normalize_term_key(value: str) -> str:
    return value.casefold().replace("_", " ").replace(".", " ").replace("-", " ").strip()
