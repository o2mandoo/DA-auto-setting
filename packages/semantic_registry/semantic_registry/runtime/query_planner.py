"""Validation-only runtime planning facade.

The Registry already owns the deterministic planner in
``semantic_registry.query_planner``. This module adds the runtime contract
surface expected by the demo and tests: a query planner that returns
``semantic_contracts.runtime_contracts.QueryPlan`` objects plus a SQL draft
generator that prefers confirmed verified-query templates.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Iterable

from semantic_contracts import SemanticPack
from semantic_contracts.runtime_contracts import QueryPlan, SqlDraft, SqlDraftSource

from ..query_planner import QueryPlanner as RegistryQueryPlanner, load_space_packs
from ..store import DEFAULT_PACK_ROOT


class DomainQueryPlanner:
    """Runtime-facing planner that enriches the Registry planning response."""

    def __init__(self, packs: Iterable[SemanticPack]) -> None:
        self.packs = tuple(packs)
        self._registry_planner = RegistryQueryPlanner.from_packs(self.packs)

    @classmethod
    def from_pack(cls, pack: SemanticPack) -> "DomainQueryPlanner":
        return cls((pack,))

    @classmethod
    def from_packs(cls, packs: Iterable[SemanticPack]) -> "DomainQueryPlanner":
        return cls(tuple(packs))

    @classmethod
    def from_store(cls, space_id: str, pack_root: str | Path = DEFAULT_PACK_ROOT) -> "DomainQueryPlanner":
        return cls.from_packs(load_space_packs(space_id, pack_root))

    def plan(self, question: str, role: str | None = None) -> QueryPlan:
        registry_plan = self._registry_planner.plan(question, role=role)
        required_metrics = list(registry_plan.required_metrics)
        candidate_tables = list(registry_plan.candidate_tables)
        filters = list(registry_plan.filters)
        if not required_metrics and _looks_generic_revenue_question(question):
            revenue_metrics = _revenue_metrics(self.packs)
            required_metrics = [metric.id for metric in revenue_metrics]
            candidate_tables = _unique(
                [
                    *candidate_tables,
                    *(table for metric in revenue_metrics for table in metric.required_tables),
                ]
            )
            filters = _unique(
                [
                    *filters,
                    *(flt for metric in revenue_metrics for flt in metric.default_filters),
                ]
            )

        selected_verified_query = _select_verified_query(
            self.packs,
            question,
            registry_plan.required_terms,
            required_metrics,
        )
        used_cards = _unique(
            [
                *registry_plan.required_terms,
                *required_metrics,
                *candidate_tables,
                *registry_plan.join_recipes,
                *( [selected_verified_query.id] if selected_verified_query is not None else [] ),
            ]
        )
        warnings = list(registry_plan.policy_notes)
        if registry_plan.ambiguities and "clarification_required_before_sql_draft" not in warnings:
            warnings.append("clarification_required_before_sql_draft")
        sql_draft_allowed = selected_verified_query is not None
        confidence = 0.95 if selected_verified_query is not None else 0.65
        if registry_plan.ambiguities and confidence > 0.9:
            confidence = 0.9
        return QueryPlan(
            required_terms=list(registry_plan.required_terms),
            required_metrics=required_metrics,
            candidate_tables=candidate_tables,
            join_recipes=list(registry_plan.join_recipes),
            filters=filters,
            group_by=[],
            selected_verified_query=selected_verified_query.id if selected_verified_query is not None else None,
            used_cards=used_cards,
            confidence=confidence,
            warnings=_unique(warnings),
            used_context_sources=list(getattr(registry_plan, "used_context_sources", [])),
            cards_used=list(getattr(registry_plan, "cards_used", used_cards)),
            source_status=dict(getattr(registry_plan, "source_status", {})),
            context_warnings=list(getattr(registry_plan, "context_warnings", [])),
            sql_draft_allowed=sql_draft_allowed,
        )


class SqlDraftGenerator:
    """Prefer a confirmed verified-query template, otherwise emit no SQL draft."""

    def __init__(self, packs: Iterable[SemanticPack]) -> None:
        self.packs = tuple(packs)

    @classmethod
    def from_pack(cls, pack: SemanticPack) -> "SqlDraftGenerator":
        return cls((pack,))

    @classmethod
    def from_packs(cls, packs: Iterable[SemanticPack]) -> "SqlDraftGenerator":
        return cls(tuple(packs))

    def draft(self, plan: QueryPlan, role: str | None = None) -> SqlDraft:  # noqa: ARG002
        if plan.selected_verified_query:
            verified_query = _find_verified_query(self.packs, plan.selected_verified_query)
            if verified_query is not None:
                return SqlDraft(
                    sql=verified_query.sql,
                    source=SqlDraftSource.VERIFIED_QUERY_TEMPLATE,
                    selected_verified_query=verified_query.id,
                    used_cards=list(plan.used_cards),
                    confidence=max(plan.confidence, 0.9),
                    warnings=list(plan.warnings),
                )
        return SqlDraft(
            sql=None,
            source=SqlDraftSource.NONE,
            used_cards=list(plan.used_cards),
            confidence=plan.confidence,
            warnings=_unique([*plan.warnings, "sql_draft_not_allowed"]),
        )


def plan_domain_query(
    space_id: str,
    question: str,
    role: str | None = None,
    pack_root: str | Path = DEFAULT_PACK_ROOT,
    root: str | Path | None = None,
) -> QueryPlan:
    effective_root = root if root is not None else pack_root
    return DomainQueryPlanner.from_store(space_id, effective_root).plan(question, role=role)


def generate_sql_draft(
    space_id: str,
    plan: QueryPlan,
    role: str | None = None,
    pack_root: str | Path = DEFAULT_PACK_ROOT,
    root: str | Path | None = None,
) -> SqlDraft:
    effective_root = root if root is not None else pack_root
    packs = load_space_packs(space_id, effective_root)
    return SqlDraftGenerator.from_packs(packs).draft(plan, role=role)


def _select_verified_query(
    packs: Iterable[SemanticPack],
    question: str,
    required_terms: Iterable[str],
    required_metrics: Iterable[str],
) -> Any | None:
    normalized_question = _normalize(question)
    term_set = set(required_terms)
    metric_set = set(required_metrics)
    for pack in packs:
        for verified_query in pack.verified_queries:
            if _normalize(verified_query.question) == normalized_question:
                return verified_query
    if _has_verified_query_scope(question):
        for pack in packs:
            for verified_query in pack.verified_queries:
                if term_set.issuperset(verified_query.related_terms) and metric_set.issuperset(verified_query.related_metrics):
                    return verified_query
    return None


def _find_verified_query(packs: Iterable[SemanticPack], query_id: str) -> Any | None:
    for pack in packs:
        for verified_query in pack.verified_queries:
            if verified_query.id == query_id:
                return verified_query
    return None


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value.casefold()).strip()


def _looks_generic_revenue_question(question: str) -> bool:
    normalized = _normalize(question)
    return ("매출" in normalized or "revenue" in normalized) and "순매출" not in normalized and "총매출" not in normalized


def _revenue_metrics(packs: Iterable[SemanticPack]) -> list[Any]:
    metrics: list[Any] = []
    for pack in packs:
        for metric in pack.metrics:
            text = _normalize(" ".join(str(getattr(metric, attr, "")) for attr in ("id", "name", "label", "description")))
            if "revenue" in text or "매출" in text:
                metrics.append(metric)
    return metrics


def _has_verified_query_scope(question: str) -> bool:
    normalized = _normalize(question)
    return any(token in normalized for token in ("월별", "월간", "지난달", "monthly", "month"))


def _unique(values: Iterable[Any]) -> list[Any]:
    seen: set[Any] = set()
    result: list[Any] = []
    for value in values:
        if value is None or value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result
