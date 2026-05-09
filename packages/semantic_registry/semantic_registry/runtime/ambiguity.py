"""Ambiguity-gate compatibility facade."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

from semantic_contracts import SemanticPack

from ..store import DEFAULT_PACK_ROOT
from .query_planner import DomainQueryPlanner, plan_domain_query
from .models import QueryPlan


@dataclass(frozen=True)
class RuntimeAmbiguity:
    id: str
    target: str | None
    question: str
    reason: str | None = None
    choices: tuple[str, ...] = ()


@dataclass(frozen=True)
class RuntimeWarning:
    code: str
    target: str | None
    message: str


@dataclass(frozen=True)
class AmbiguityGateResult:
    ambiguities: tuple[RuntimeAmbiguity, ...]
    warnings: tuple[RuntimeWarning, ...]
    unresolved_terms: tuple[str, ...]
    requires_clarification: bool
    execution_allowed: bool
    plan: Any


class AmbiguityGate:
    """Detect when a question still needs human clarification."""

    def __init__(self, packs: Iterable[SemanticPack] | None = None) -> None:
        self.packs = tuple(packs or ())

    @classmethod
    def from_pack(cls, pack: SemanticPack) -> "AmbiguityGate":
        return cls((pack,))

    @classmethod
    def from_packs(cls, packs: Iterable[SemanticPack]) -> "AmbiguityGate":
        return cls(tuple(packs))

    def assess(self, plan: QueryPlan | Any) -> dict[str, Any]:
        ambiguities, warnings, unresolved_terms = self._classify(plan)
        return {
            "ambiguities": [_ambiguity_to_dict(ambiguity) for ambiguity in ambiguities],
            "warnings": [warning.__dict__ for warning in warnings],
            "unresolved_terms": unresolved_terms,
            "requires_clarification": bool(ambiguities or unresolved_terms),
            "execution_allowed": False,
            "plan": plan,
        }

    def evaluate(
        self,
        question: str,
        role: str | None = None,
        pack_root: str | Path = DEFAULT_PACK_ROOT,
        root: str | Path | None = None,
    ) -> AmbiguityGateResult:
        effective_root = root if root is not None else pack_root
        if self.packs:
            plan = DomainQueryPlanner.from_packs(self.packs).plan(question, role=role)
        else:
            plan = plan_domain_query("demo_company.revenue", question, role=role, pack_root=effective_root)
        verdict = self.assess(plan)
        if not _field(plan, "required_terms", []) and not _field(plan, "required_metrics", []) and _field(plan, "selected_verified_query") is None:
            verdict["unresolved_terms"] = (question,)
            verdict["requires_clarification"] = True
        return AmbiguityGateResult(
            ambiguities=tuple(_dict_to_ambiguity(item) for item in verdict["ambiguities"]),
            warnings=tuple(RuntimeWarning(**item) for item in verdict["warnings"]),
            unresolved_terms=tuple(verdict["unresolved_terms"]),
            requires_clarification=bool(verdict["requires_clarification"]),
            execution_allowed=False,
            plan=plan,
        )

    def _classify(self, plan: QueryPlan | Any) -> tuple[list[RuntimeAmbiguity], list[RuntimeWarning], tuple[str, ...]]:
        ambiguities: list[RuntimeAmbiguity] = []
        warnings: list[RuntimeWarning] = []
        unresolved_terms: tuple[str, ...] = ()

        required_terms = list(_field(plan, "required_terms", []))
        required_metrics = list(_field(plan, "required_metrics", []))
        selected_verified_query = _field(plan, "selected_verified_query")

        for planned in _field(plan, "ambiguities", []):
            ambiguities.append(_planned_ambiguity_to_runtime(planned))

        if len(required_metrics) > 1:
            ambiguities.append(
                RuntimeAmbiguity(
                    id="runtime.metric_choice_required",
                    target="metric_choice",
                    question="Which revenue metric should be used?",
                    reason="The plan matched multiple metric candidates.",
                    choices=tuple(required_metrics),
                )
            )
        if not required_terms and not required_metrics and selected_verified_query is None:
            unresolved_terms = (selected_verified_query or "unresolved_question",)

        if self.packs:
            ambiguities.extend(self._reverse_question_ambiguities(required_terms, required_metrics, ambiguities))
            warnings.extend(self._draft_warnings(plan))

        plan_warnings = list(_field(plan, "warnings", []))
        if not ambiguities and plan_warnings:
            for warning in plan_warnings:
                if warning == "clarification_required_before_sql_draft":
                    ambiguities.append(
                        RuntimeAmbiguity(
                            id="runtime.clarification_required_before_sql_draft",
                            target="semantic_plan",
                            question="Clarification is required before drafting SQL.",
                            reason=warning,
                        )
                    )

        return ambiguities, warnings, unresolved_terms

    def _draft_warnings(self, plan: QueryPlan) -> list[RuntimeWarning]:
        draft_warnings: list[RuntimeWarning] = []
        required_terms = list(_field(plan, "required_terms", []))
        required_metrics = list(_field(plan, "required_metrics", []))
        for pack in self.packs:
            terms = {term.id: term for term in pack.business_terms}
            metrics = {metric.id: metric for metric in pack.metrics}
            for term_id in required_terms:
                term = terms.get(term_id)
                if term is not None and str(term.status).casefold() == "draft":
                    draft_warnings.append(
                        RuntimeWarning(
                            code="draft_semantic_card",
                            target=term_id,
                            message="Draft semantic card must not be treated as confirmed truth.",
                        )
                    )
            for metric_id in required_metrics:
                metric = metrics.get(metric_id)
                if metric is not None and str(metric.status).casefold() == "draft":
                    draft_warnings.append(
                        RuntimeWarning(
                            code="draft_semantic_card",
                            target=metric_id,
                            message="Draft semantic card must not be treated as confirmed truth.",
                        )
                    )
        return draft_warnings

    def _reverse_question_ambiguities(
        self,
        required_terms: Iterable[str],
        required_metrics: Iterable[str],
        existing: Iterable[RuntimeAmbiguity],
    ) -> list[RuntimeAmbiguity]:
        targets = set(required_terms) | set(required_metrics)
        seen_ids = {ambiguity.id for ambiguity in existing}
        result: list[RuntimeAmbiguity] = []
        for pack in self.packs:
            for question in pack.reverse_questions:
                if question.target not in targets or question.id in seen_ids:
                    continue
                seen_ids.add(question.id)
                result.append(
                    RuntimeAmbiguity(
                        id=question.id,
                        target=question.target,
                        question=question.question,
                        reason=question.reason,
                    )
                )
        return result


def evaluate_ambiguity_gate_dict(
    space_id: str,
    question: str,
    role: str | None = None,
    pack_root: str | Path = DEFAULT_PACK_ROOT,
    root: str | Path | None = None,
) -> dict[str, Any]:
    effective_root = root if root is not None else pack_root
    plan = plan_domain_query(space_id, question, role=role, pack_root=effective_root)
    gate = AmbiguityGate.from_packs(DomainQueryPlanner.from_store(space_id, effective_root).packs)
    verdict = gate.assess(plan)
    return {
        "space_id": space_id,
        "question": question,
        "role": role,
        "plan": plan.model_dump(mode="json"),
        "ambiguities": list(verdict["ambiguities"]),
        "warnings": list(verdict["warnings"]),
        "unresolved_terms": list(verdict["unresolved_terms"]),
        "requires_clarification": verdict["requires_clarification"],
        "execution_allowed": False,
    }


def _planned_ambiguity_to_runtime(planned: Any) -> RuntimeAmbiguity:
    return RuntimeAmbiguity(
        id=str(_field(planned, "id") or "runtime.ambiguity"),
        target=_field(planned, "target"),
        question=str(_field(planned, "question", "")),
        reason=_field(planned, "reason"),
    )


def _ambiguity_to_dict(ambiguity: RuntimeAmbiguity) -> dict[str, Any]:
    return {
        "id": ambiguity.id,
        "target": ambiguity.target,
        "question": ambiguity.question,
        "reason": ambiguity.reason,
        "choices": list(ambiguity.choices),
    }


def _dict_to_ambiguity(payload: dict[str, Any]) -> RuntimeAmbiguity:
    return RuntimeAmbiguity(
        id=str(payload["id"]),
        target=payload.get("target"),
        question=str(payload["question"]),
        reason=payload.get("reason"),
        choices=tuple(payload.get("choices", ())),
    )


def _field(obj: Any, name: str, default: Any = None) -> Any:
    if isinstance(obj, Mapping):
        return obj.get(name, default)
    return getattr(obj, name, default)
