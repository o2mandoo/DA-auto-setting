"""Compatibility runtime query planning over local Semantic Packs."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

from pydantic import Field

from semantic_contracts import SemanticPack
from semantic_contracts.mcp_tool_contracts import PlanDataQueryResponse
from semantic_contracts.runtime_contracts import SqlDraft, SqlDraftSource, StrictRuntimeModel

from semantic_registry.query_planner import QueryPlanner as RegistryQueryPlanner
from semantic_registry.query_planner import load_space_packs as registry_load_space_packs
from semantic_registry.store import DEFAULT_PACK_ROOT, PackStore


class RuntimeQueryPlan(StrictRuntimeModel):
    required_terms: list[str] = Field(default_factory=list)
    required_metrics: list[str] = Field(default_factory=list)
    candidate_tables: list[str] = Field(default_factory=list)
    join_recipes: list[str] = Field(default_factory=list)
    filters: list[str] = Field(default_factory=list)
    policy_notes: list[str] = Field(default_factory=list)
    ambiguities: list[dict[str, Any]] = Field(default_factory=list)
    execution_allowed: bool = False
    selected_verified_query: str | None = None
    used_cards: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0, le=1)
    warnings: list[str] = Field(default_factory=list)
    sql_draft_allowed: bool = False


@dataclass(frozen=True)
class _VerifiedQueryMatch:
    query_id: str
    sql: str
    question: str


class DomainQueryPlanner:
    """Lift the registry planner into a runtime query-plan contract."""

    def __init__(self, packs: Iterable[SemanticPack]) -> None:
        self.packs = tuple(packs)

    @classmethod
    def from_pack(cls, pack: SemanticPack) -> "DomainQueryPlanner":
        return cls((pack,))

    @classmethod
    def from_packs(cls, packs: Iterable[SemanticPack]) -> "DomainQueryPlanner":
        return cls(tuple(packs))

    @classmethod
    def from_store(cls, space_id: str, pack_root: str | Path = DEFAULT_PACK_ROOT) -> "DomainQueryPlanner":
        return cls.from_packs(registry_load_space_packs(space_id, pack_root))

    def plan(self, question: str, role: str | None = None) -> RuntimeQueryPlan:
        base_plan = RegistryQueryPlanner.from_packs(self.packs).plan(question, role=role)
        required_terms = list(base_plan.required_terms)
        required_metrics = list(base_plan.required_metrics)
        candidate_tables = list(base_plan.candidate_tables)
        join_recipes = list(base_plan.join_recipes)
        filters = list(base_plan.filters)
        if not required_metrics and _looks_generic_revenue_question(question):
            revenue_metrics = self._revenue_metrics()
            if revenue_metrics:
                required_metrics = revenue_metrics
                candidate_tables = _merge_unique(candidate_tables + [table for metric in self._metric_objects(revenue_metrics) for table in metric.required_tables])
                filters = _merge_unique(filters + [flt for metric in self._metric_objects(revenue_metrics) for flt in metric.default_filters])
        match = self._match_verified_query(question, base_plan)
        used_cards = list(dict.fromkeys([*required_terms, *required_metrics, *join_recipes]))
        warnings = self._plan_warnings(base_plan)
        selected_verified_query = match.query_id if match is not None else None
        sql_draft_allowed = match is not None and _matches_monthly_new_customer_revenue(_normalize_text(question), _normalize_text(match.question))
        if selected_verified_query:
            used_cards.append(selected_verified_query)
        confidence = 0.95 if selected_verified_query else (0.88 if used_cards else 0.45)
        if (selected_verified_query is None and (base_plan.required_terms or base_plan.required_metrics)) or (selected_verified_query and not sql_draft_allowed):
            warnings.append("clarification_required_before_sql_draft")
        return RuntimeQueryPlan(
            required_terms=required_terms,
            required_metrics=required_metrics,
            candidate_tables=candidate_tables,
            join_recipes=join_recipes,
            filters=filters,
            policy_notes=list(base_plan.policy_notes),
            ambiguities=[_ambiguity_to_dict(item) for item in base_plan.ambiguities],
            execution_allowed=False,
            selected_verified_query=selected_verified_query,
            used_cards=list(dict.fromkeys(used_cards)),
            confidence=confidence,
            warnings=warnings,
            sql_draft_allowed=sql_draft_allowed,
        )

    def _match_verified_query(self, question: str, plan: PlanDataQueryResponse) -> _VerifiedQueryMatch | None:  # noqa: ARG002
        normalized_question = _normalize_text(question)
        for pack in self.packs:
            for verified_query in pack.verified_queries:
                normalized_verified_question = _normalize_text(verified_query.question)
                if _matches_monthly_new_customer_revenue(normalized_question, normalized_verified_question):
                    return _VerifiedQueryMatch(
                        query_id=verified_query.id,
                        sql=verified_query.sql,
                        question=verified_query.question,
                    )
        return None

    def _plan_warnings(self, plan: PlanDataQueryResponse) -> list[str]:
        warnings: list[str] = []
        if not plan.required_terms and not plan.required_metrics:
            warnings.append("unresolved_question")
            return warnings
        if len(plan.required_metrics) > 1:
            warnings.append("metric_choice_required")
        return warnings

    def _revenue_metrics(self) -> list[str]:
        return [metric.id for metric in self._metric_objects() if _looks_like_revenue_metric(metric)]

    def _metric_objects(self, metric_ids: Iterable[str] | None = None) -> list[Any]:
        wanted = set(metric_ids or [])
        metrics: list[Any] = []
        for pack in self.packs:
            for metric in pack.metrics:
                if not wanted or metric.id in wanted:
                    metrics.append(metric)
        return metrics


class SqlDraftGenerator:
    """Generate a validation-only SQL draft from a runtime query plan."""

    def __init__(self, packs: Iterable[SemanticPack]) -> None:
        self.packs = tuple(packs)

    @classmethod
    def from_pack(cls, pack: SemanticPack) -> "SqlDraftGenerator":
        return cls((pack,))

    @classmethod
    def from_packs(cls, packs: Iterable[SemanticPack]) -> "SqlDraftGenerator":
        return cls(tuple(packs))

    def draft(self, plan: RuntimeQueryPlan | PlanDataQueryResponse, role: str | None = None) -> SqlDraft:  # noqa: ARG002
        runtime_plan = _coerce_runtime_plan(plan)
        if not runtime_plan.sql_draft_allowed or not runtime_plan.selected_verified_query:
            return SqlDraft(
                sql=None,
                source=SqlDraftSource.NONE,
                selected_verified_query=runtime_plan.selected_verified_query,
                used_cards=list(runtime_plan.used_cards),
                confidence=0.0,
                warnings=[*runtime_plan.warnings, "sql_draft_not_allowed"],
            )

        verified = self._find_verified_query(runtime_plan.selected_verified_query)
        if verified is None:
            return SqlDraft(
                sql=None,
                source=SqlDraftSource.NONE,
                selected_verified_query=runtime_plan.selected_verified_query,
                used_cards=list(runtime_plan.used_cards),
                confidence=0.0,
                warnings=[*runtime_plan.warnings, "verified_query_template_missing"],
            )

        return SqlDraft(
            sql=verified.sql,
            source=SqlDraftSource.VERIFIED_QUERY_TEMPLATE,
            selected_verified_query=verified.query_id,
            used_cards=[*runtime_plan.used_cards, verified.query_id],
            confidence=max(runtime_plan.confidence, 0.9),
            warnings=list(runtime_plan.warnings),
            execution_allowed=False,
        )

    def _find_verified_query(self, query_id: str) -> _VerifiedQueryMatch | None:
        for pack in self.packs:
            for verified_query in pack.verified_queries:
                if verified_query.id == query_id:
                    return _VerifiedQueryMatch(query_id=verified_query.id, sql=verified_query.sql, question=verified_query.question)
        return None


def plan_domain_query(
    space_id: str,
    question: str,
    role: str | None = None,
    pack_root: str | Path = DEFAULT_PACK_ROOT,
    root: str | Path | None = None,
) -> RuntimeQueryPlan:
    effective_root = root if root is not None else pack_root
    return DomainQueryPlanner.from_store(space_id, effective_root).plan(question=question, role=role)


def generate_sql_draft(
    space_id: str,
    plan: RuntimeQueryPlan | PlanDataQueryResponse,
    role: str | None = None,
    pack_root: str | Path = DEFAULT_PACK_ROOT,
    root: str | Path | None = None,
) -> SqlDraft:
    effective_root = root if root is not None else pack_root
    generator = SqlDraftGenerator.from_packs(registry_load_space_packs(space_id, effective_root))
    return generator.draft(plan, role=role)


def _coerce_runtime_plan(plan: RuntimeQueryPlan | PlanDataQueryResponse) -> RuntimeQueryPlan:
    if isinstance(plan, RuntimeQueryPlan):
        return plan
    if isinstance(plan, Mapping):
        plan_mapping = plan
        ambiguities = plan_mapping.get("ambiguities", [])
        warnings = plan_mapping.get("warnings", [])
        return RuntimeQueryPlan(
            required_terms=list(plan_mapping.get("required_terms", [])),
            required_metrics=list(plan_mapping.get("required_metrics", [])),
            candidate_tables=list(plan_mapping.get("candidate_tables", [])),
            join_recipes=list(plan_mapping.get("join_recipes", [])),
            filters=list(plan_mapping.get("filters", [])),
            policy_notes=list(plan_mapping.get("policy_notes", [])),
            ambiguities=[_ambiguity_to_dict(item) for item in ambiguities],
            execution_allowed=bool(plan_mapping.get("execution_allowed", False)),
            selected_verified_query=plan_mapping.get("selected_verified_query"),
            used_cards=list(plan_mapping.get("used_cards", [])),
            confidence=float(plan_mapping.get("confidence", 0.0)),
            warnings=list(warnings),
            sql_draft_allowed=bool(plan_mapping.get("sql_draft_allowed", False)),
        )
    return RuntimeQueryPlan(
        required_terms=list(getattr(plan, "required_terms", [])),
        required_metrics=list(getattr(plan, "required_metrics", [])),
        candidate_tables=list(getattr(plan, "candidate_tables", [])),
        join_recipes=list(getattr(plan, "join_recipes", [])),
        filters=list(getattr(plan, "filters", [])),
        policy_notes=list(getattr(plan, "policy_notes", [])),
        ambiguities=[_ambiguity_to_dict(item) for item in getattr(plan, "ambiguities", [])],
        execution_allowed=bool(getattr(plan, "execution_allowed", False)),
        warnings=list(getattr(plan, "warnings", [])),
    )


def _ambiguity_to_dict(item: Any) -> dict[str, Any]:
    if hasattr(item, "model_dump"):
        return dict(item.model_dump(mode="json"))
    if isinstance(item, dict):
        return dict(item)
    return {
        "id": getattr(item, "id", None),
        "target": getattr(item, "target", None),
        "question": getattr(item, "question", ""),
        "reason": getattr(item, "reason", None),
    }


def _normalize_text(value: str) -> str:
    return value.casefold().replace("_", " ").replace(".", " ").replace("-", " ")


def _merge_unique(values: Iterable[Any]) -> list[Any]:
    seen: set[Any] = set()
    result: list[Any] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _looks_generic_revenue_question(question: str) -> bool:
    normalized = _normalize_text(question)
    return "매출" in question or "revenue" in normalized


def _looks_like_revenue_metric(metric: Any) -> bool:
    text = _normalize_text(" ".join(str(getattr(metric, attr, "")) for attr in ("id", "name", "label", "description")))
    return "revenue" in text or "매출" in text


def _matches_monthly_new_customer_revenue(question: str, verified_question: str) -> bool:
    if "신규 고객" not in question or "순매출" not in question:
        return False
    if "신규 고객" not in verified_question or "순매출" not in verified_question:
        return False
    time_markers = ("월별", "지난달", "monthly", "month")
    return any(marker in question for marker in time_markers)


__all__ = [
    "DomainQueryPlanner",
    "RuntimeQueryPlan",
    "SqlDraftGenerator",
    "generate_sql_draft",
    "plan_domain_query",
    "SqlDraftSource",
]
