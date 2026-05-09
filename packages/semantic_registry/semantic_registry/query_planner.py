"""Deterministic metadata-only query planning over Semantic Packs.

The Registry owns Phase 3 planning, but it deliberately stops at structured
metadata: no SQL generation, no SQL execution, no database connection, no VDB,
and no LLM fallback. MCP tools can serialize this response for clients without
duplicating planning policy.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from semantic_contracts import SemanticPack
from semantic_contracts.mcp_tool_contracts import PlanDataQueryResponse, PlannedAmbiguity

from .search import SearchIndex
from .store import DEFAULT_PACK_ROOT, PackStore


@dataclass(frozen=True)
class QueryPlanner:
    """Plan semantic context needed to answer a data question.

    This MVP planner is intentionally lexical and pack-backed. It selects known
    terms, metrics, tables, joins, filters, policy notes, and ambiguity prompts
    without inventing SQL or attempting to execute against an external database.
    """

    packs: tuple[SemanticPack, ...]

    @classmethod
    def from_pack(cls, pack: SemanticPack) -> "QueryPlanner":
        return cls((pack,))

    @classmethod
    def from_packs(cls, packs: Iterable[SemanticPack]) -> "QueryPlanner":
        return cls(tuple(packs))

    @classmethod
    def from_store(cls, space_id: str, pack_root: str | Path = DEFAULT_PACK_ROOT) -> "QueryPlanner":
        return cls.from_packs(_load_space_packs(space_id, pack_root))

    def plan(self, question: str, role: str | None = None) -> PlanDataQueryResponse:
        question_norm = _normalize_text(question)
        matched_terms = self._match_business_terms(question_norm)
        matched_metrics = self._match_metrics(question_norm)
        matched_terms = _drop_metric_duplicate_terms(matched_terms, matched_metrics)

        if not matched_terms and not matched_metrics:
            # Fallback remains deterministic and local: lexical card search over
            # validated packs only, never an LLM or external retrieval system.
            matched_terms, matched_metrics = self._lexical_fallback(question)

        term_ids = _unique(item.id for item in matched_terms)
        metric_ids = _unique(item.id for item in matched_metrics)
        candidate_tables = self._candidate_tables(matched_terms, matched_metrics, role)
        join_recipes = self._select_join_recipes(candidate_tables)
        filters = _unique(
            [term.sql_condition for term in matched_terms if term.sql_condition]
            + [flt for metric in matched_metrics for flt in metric.default_filters]
        )
        policy_notes = self._policy_notes_for_role(role)
        ambiguities = self._collect_ambiguities(set(term_ids + metric_ids), matched_terms)

        return PlanDataQueryResponse(
            intent="semantic_context_query_plan",
            required_terms=term_ids,
            required_metrics=metric_ids,
            candidate_tables=candidate_tables,
            join_recipes=join_recipes,
            filters=filters,
            policy_notes=policy_notes,
            ambiguities=ambiguities,
            execution_allowed=False,
        )

    def _match_business_terms(self, question_norm: str) -> list[Any]:
        return [
            term
            for pack in self.packs
            for term in pack.business_terms
            if _matches_question(question_norm, [term.id, term.term, *term.aliases])
        ]

    def _match_metrics(self, question_norm: str) -> list[Any]:
        return [
            metric
            for pack in self.packs
            for metric in pack.metrics
            if _matches_question(question_norm, [metric.id, metric.name, metric.label])
        ]

    def _lexical_fallback(self, question: str) -> tuple[list[Any], list[Any]]:
        top_cards = SearchIndex(self.packs).search_cards(question, card_types=["business_term", "metric"], limit=4)
        terms = [
            payload
            for card in top_cards
            if card.card_type == "business_term" and (payload := self._payload_by_id("business_term", card.card_id)) is not None
        ]
        metrics = [
            payload
            for card in top_cards
            if card.card_type == "metric" and (payload := self._payload_by_id("metric", card.card_id)) is not None
        ]
        return terms, metrics

    def _payload_by_id(self, card_type: str, card_id: str) -> Any | None:
        attr = {"business_term": "business_terms", "metric": "metrics"}.get(card_type)
        if attr is None:
            return None
        for pack in self.packs:
            for item in getattr(pack, attr):
                if item.id == card_id:
                    return item
        return None

    def _candidate_tables(self, terms: Iterable[Any], metrics: Iterable[Any], role: str | None) -> list[str]:
        tables = _unique(
            [table for term in terms for table in term.related_tables]
            + [table for metric in metrics for table in metric.required_tables]
        )
        allowed_tables = self._allowed_tables_for_role(role)
        if not allowed_tables:
            return tables
        # Role policy is enforced in planning output so clients do not receive
        # table candidates outside the user's allowed semantic context.
        return [table for table in tables if table in allowed_tables]

    def _allowed_tables_for_role(self, role: str | None) -> set[str]:
        allowed_tables: set[str] = set()
        for pack in self.packs:
            for policy in pack.policies:
                if role is not None and role not in policy.applies_to.roles:
                    continue
                allowed_tables.update(policy.allowed_tables)
        return allowed_tables

    def _select_join_recipes(self, tables: Iterable[str]) -> list[str]:
        table_set = set(tables)
        if len(table_set) < 2:
            return []
        selected: list[str] = []
        for pack in self.packs:
            for join in pack.join_recipes:
                if join.left_table in table_set and join.right_table in table_set:
                    selected.append(join.id)
        return _unique(selected)

    def _policy_notes_for_role(self, role: str | None) -> list[str]:
        notes: list[str] = []
        for pack in self.packs:
            for policy in pack.policies:
                if role is None or role in policy.applies_to.roles:
                    notes.extend(policy.notes)
        return _unique(notes)

    def _collect_ambiguities(self, target_ids: set[str], terms: Iterable[Any]) -> list[PlannedAmbiguity]:
        ambiguities: list[PlannedAmbiguity] = []
        for term in terms:
            for rule in term.ambiguity_rules:
                ambiguities.append(PlannedAmbiguity(id=rule.id, target=rule.target, question=rule.question, reason=rule.condition))
        for pack in self.packs:
            for reverse_question in pack.reverse_questions:
                if reverse_question.target in target_ids:
                    ambiguities.append(
                        PlannedAmbiguity(
                            id=reverse_question.id,
                            target=reverse_question.target,
                            question=reverse_question.question,
                            reason=reverse_question.reason,
                        )
                    )
        return _dedupe_ambiguities(ambiguities)


def plan_data_query(
    space_id: str,
    question: str,
    role: str | None = None,
    pack_root: str | Path = DEFAULT_PACK_ROOT,
    root: str | Path | None = None,
) -> PlanDataQueryResponse:
    """Return a validation-only plan for a semantic question."""

    effective_root = root if root is not None else pack_root
    return QueryPlanner.from_store(space_id, effective_root).plan(question=question, role=role)


def load_space_packs(space_id: str, pack_root: str | Path = DEFAULT_PACK_ROOT) -> list[SemanticPack]:
    """Public helper for Registry adapters that need pack-id/space-id lookup."""

    return _load_space_packs(space_id, pack_root)


def policy_limits_for_role(packs: Iterable[SemanticPack], role: str | None) -> tuple[set[str], set[str]]:
    """Return allowed tables and blocked columns for a role from pack policies."""

    allowed_tables: set[str] = set()
    blocked_columns: set[str] = set()
    for pack in packs:
        for policy in pack.policies:
            if role is not None and role not in policy.applies_to.roles:
                continue
            allowed_tables.update(policy.allowed_tables)
            blocked_columns.update(column.casefold() for column in policy.blocked_columns)
    return allowed_tables, blocked_columns


def _load_space_packs(space_id: str, pack_root: str | Path) -> list[SemanticPack]:
    store = PackStore(pack_root)
    packs = store.load_packs()
    selected = [pack for pack in packs if pack.id == space_id or any(space.id == space_id for space in pack.spaces)]
    if not selected:
        raise KeyError(f"Unknown semantic space: {space_id}")
    return selected


def _matches_question(question_norm: str, candidates: Iterable[str | None]) -> bool:
    for candidate in candidates:
        if not candidate:
            continue
        normalized = _normalize_text(str(candidate))
        if normalized and normalized in question_norm:
            return True
    return False


def _drop_metric_duplicate_terms(terms: Iterable[Any], metrics: Iterable[Any]) -> list[Any]:
    metric_names = {_normalize_text(metric.id.replace("metric.", "")) for metric in metrics}
    metric_names.update(_normalize_text(metric.name) for metric in metrics)
    metric_names.update(_normalize_text(metric.label) for metric in metrics)
    result: list[Any] = []
    for term in terms:
        term_names = {
            _normalize_text(term.id.replace("term.", "")),
            _normalize_text(term.term),
            *(_normalize_text(alias) for alias in term.aliases),
        }
        if term_names & metric_names:
            # Metric-shaped business terms document metric semantics, but the
            # planner keeps the metric in required_metrics to avoid duplicating
            # the same concept as both a term and a metric in structured output.
            continue
        result.append(term)
    return result


def _normalize_text(value: str) -> str:
    return value.casefold().replace("_", " ").replace(".", " ").replace("-", " ")


def _unique(values: Iterable[Any]) -> list[Any]:
    seen: set[Any] = set()
    result: list[Any] = []
    for value in values:
        if value is None or value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _dedupe_ambiguities(ambiguities: Iterable[PlannedAmbiguity]) -> list[PlannedAmbiguity]:
    deduped: list[PlannedAmbiguity] = []
    seen: set[tuple[str | None, str]] = set()
    for ambiguity in ambiguities:
        key = (ambiguity.id, ambiguity.question)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(ambiguity)
    return deduped


__all__ = [
    "QueryPlanner",
    "load_space_packs",
    "plan_data_query",
    "policy_limits_for_role",
]
