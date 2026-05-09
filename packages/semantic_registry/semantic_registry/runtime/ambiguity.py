"""Runtime ambiguity gating over local Semantic Packs."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

from pydantic import Field

from semantic_contracts import SemanticPack
from semantic_contracts.mcp_tool_contracts import PlannedAmbiguity
from semantic_contracts.runtime_contracts import StrictRuntimeModel

from semantic_registry.store import DEFAULT_PACK_ROOT

from .query_planner import DomainQueryPlanner, RuntimeQueryPlan, plan_domain_query


class AmbiguityChoice(StrictRuntimeModel):
    id: str
    target: str | None = None
    question: str
    reason: str | None = None
    choices: list[str] = Field(default_factory=list)


class AmbiguityWarning(StrictRuntimeModel):
    code: str
    target: str
    message: str


class AmbiguityAssessment(StrictRuntimeModel):
    requires_clarification: bool = False
    execution_allowed: bool = False
    ambiguities: list[AmbiguityChoice] = Field(default_factory=list)
    warnings: list[AmbiguityWarning] = Field(default_factory=list)
    unresolved_terms: tuple[str, ...] = ()
    plan: RuntimeQueryPlan


@dataclass(frozen=True)
class _PackLookup:
    packs: tuple[SemanticPack, ...]


class AmbiguityGate:
    """Assess whether a plan needs clarification before proceeding."""

    def __init__(self, packs: Iterable[SemanticPack] = ()) -> None:
        self._lookup = _PackLookup(tuple(packs))

    @classmethod
    def from_pack(cls, pack: SemanticPack) -> "AmbiguityGate":
        return cls((pack,))

    @classmethod
    def from_packs(cls, packs: Iterable[SemanticPack]) -> "AmbiguityGate":
        return cls(tuple(packs))

    @classmethod
    def from_store(cls, space_id: str, pack_root: str | Path = DEFAULT_PACK_ROOT) -> "AmbiguityGate":
        planner = DomainQueryPlanner.from_store(space_id, pack_root)
        return cls(planner.packs)

    def evaluate(self, question: str, role: str | None = None, *, space_id: str = "demo_company.revenue", pack_root: str | Path = DEFAULT_PACK_ROOT, root: str | Path | None = None) -> AmbiguityAssessment:
        plan = plan_domain_query(space_id, question, role=role, pack_root=pack_root, root=root)
        return self._assess_model(plan, question=question)

    def assess(self, plan: RuntimeQueryPlan | Any, *, question: str | None = None) -> dict[str, Any]:
        return self._assess_model(plan, question=question).model_dump(mode="json")

    def _assess_model(self, plan: RuntimeQueryPlan | Any, *, question: str | None = None) -> AmbiguityAssessment:
        runtime_plan = _coerce_plan(plan)
        ambiguities = [_runtime_ambiguity(item) for item in runtime_plan.ambiguities]
        if len(runtime_plan.required_metrics) > 1:
            ambiguities.append(
                AmbiguityChoice(
                    id="runtime.metric_choice_required",
                    target="metric_choice",
                    question="Which revenue metric should be used?",
                    reason="The plan matched multiple revenue metrics.",
                    choices=list(runtime_plan.required_metrics),
            )
        )

        warnings = self._draft_warnings(runtime_plan)
        unresolved_terms: tuple[str, ...]
        if not runtime_plan.required_terms and not runtime_plan.required_metrics:
            unresolved_terms = (question or "unresolved question",)
        else:
            unresolved_terms = ()
        requires_clarification = bool(ambiguities or unresolved_terms)
        return AmbiguityAssessment(
            requires_clarification=requires_clarification,
            execution_allowed=False,
            ambiguities=ambiguities,
            warnings=warnings,
            unresolved_terms=unresolved_terms,
            plan=runtime_plan,
        )

    def _draft_warnings(self, plan: RuntimeQueryPlan) -> list[AmbiguityWarning]:
        warnings: list[AmbiguityWarning] = []
        if not self._lookup.packs:
            return warnings

        target_ids = set(plan.required_terms) | set(plan.required_metrics) | set(plan.used_cards)
        for pack in self._lookup.packs:
            for term in pack.business_terms:
                if term.id in target_ids and term.status == "draft":
                    warnings.append(
                        AmbiguityWarning(
                            code="draft_semantic_card",
                            target=term.id,
                            message=f"{term.id} is a draft semantic card and should not be treated as confirmed truth.",
                        )
                    )
            for metric in pack.metrics:
                if metric.id in target_ids and metric.status == "draft":
                    warnings.append(
                        AmbiguityWarning(
                            code="draft_semantic_card",
                            target=metric.id,
                            message=f"{metric.id} is a draft semantic card and should not be treated as confirmed truth.",
                        )
                    )
        return _dedupe_by_key(warnings, key=lambda item: (item.code, item.target))


def evaluate_ambiguity_gate_dict(
    space_id: str,
    question: str,
    *,
    role: str | None = None,
    pack_root: str | Path = DEFAULT_PACK_ROOT,
    root: str | Path | None = None,
) -> dict[str, Any]:
    gate = AmbiguityGate.from_store(space_id, root if root is not None else pack_root)
    return gate.evaluate(question, role=role, space_id=space_id, pack_root=pack_root, root=root).model_dump(mode="json")


def _coerce_plan(plan: RuntimeQueryPlan | Any) -> RuntimeQueryPlan:
    if isinstance(plan, RuntimeQueryPlan):
        return plan
    if isinstance(plan, Mapping):
        plan_mapping = plan
        return RuntimeQueryPlan(
            required_terms=list(plan_mapping.get("required_terms", [])),
            required_metrics=list(plan_mapping.get("required_metrics", [])),
            candidate_tables=list(plan_mapping.get("candidate_tables", [])),
            join_recipes=list(plan_mapping.get("join_recipes", [])),
            filters=list(plan_mapping.get("filters", [])),
            policy_notes=list(plan_mapping.get("policy_notes", [])),
            ambiguities=[_planned_ambiguity_to_choice(item) for item in plan_mapping.get("ambiguities", [])],
            execution_allowed=bool(plan_mapping.get("execution_allowed", False)),
            selected_verified_query=plan_mapping.get("selected_verified_query"),
            used_cards=list(plan_mapping.get("used_cards", [])),
            confidence=float(plan_mapping.get("confidence", 0.0)),
            warnings=list(plan_mapping.get("warnings", [])),
            sql_draft_allowed=bool(plan_mapping.get("sql_draft_allowed", False)),
        )
    return RuntimeQueryPlan(
        required_terms=list(getattr(plan, "required_terms", [])),
        required_metrics=list(getattr(plan, "required_metrics", [])),
        candidate_tables=list(getattr(plan, "candidate_tables", [])),
        join_recipes=list(getattr(plan, "join_recipes", [])),
        filters=list(getattr(plan, "filters", [])),
        policy_notes=list(getattr(plan, "policy_notes", [])),
        ambiguities=[_planned_ambiguity_to_choice(item) for item in getattr(plan, "ambiguities", [])],
        execution_allowed=bool(getattr(plan, "execution_allowed", False)),
        selected_verified_query=getattr(plan, "selected_verified_query", None),
        used_cards=list(getattr(plan, "used_cards", [])),
        confidence=float(getattr(plan, "confidence", 0.0)),
        warnings=list(getattr(plan, "warnings", [])),
        sql_draft_allowed=bool(getattr(plan, "sql_draft_allowed", False)),
    )


def _runtime_ambiguity(item: dict[str, Any] | PlannedAmbiguity | AmbiguityChoice | Any) -> AmbiguityChoice:
    if isinstance(item, AmbiguityChoice):
        return item
    if hasattr(item, "model_dump"):
        payload = dict(item.model_dump(mode="json"))
    elif isinstance(item, dict):
        payload = dict(item)
    else:
        payload = {
            "id": getattr(item, "id", None),
            "target": getattr(item, "target", None),
            "question": getattr(item, "question", ""),
            "reason": getattr(item, "reason", None),
        }
    return AmbiguityChoice(
        id=str(payload.get("id") or "runtime.ambiguity"),
        target=payload.get("target"),
        question=str(payload.get("question") or ""),
        reason=payload.get("reason"),
    )


def _planned_ambiguity_to_choice(item: Any) -> dict[str, Any]:
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


def _dedupe_by_key(items: Iterable[Any], *, key) -> list[Any]:
    seen: set[Any] = set()
    result: list[Any] = []
    for item in items:
        dedupe_key = key(item)
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        result.append(item)
    return result


__all__ = [
    "AmbiguityAssessment",
    "AmbiguityChoice",
    "AmbiguityGate",
    "AmbiguityWarning",
    "evaluate_ambiguity_gate_dict",
]
