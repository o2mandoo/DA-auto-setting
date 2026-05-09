"""Ambiguity-gate compatibility facade."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

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

    def assess(self, plan: QueryPlan) -> dict[str, Any]:
        ambiguities, warnings, unresolved_terms = self._classify(plan)
        return {
            "ambiguities": ambiguities,
            "warnings": warnings,
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
    ) -> dict[str, Any]:
        effective_root = root if root is not None else pack_root
        plan = plan_domain_query("demo_company.revenue", question, role=role, pack_root=effective_root)
        verdict = self.assess(plan)
        if not plan.required_terms and not plan.required_metrics and plan.selected_verified_query is None:
            verdict["unresolved_terms"] = (question,)
            verdict["requires_clarification"] = True
        return verdict

    def _classify(self, plan: QueryPlan) -> tuple[list[RuntimeAmbiguity], list[RuntimeWarning], tuple[str, ...]]:
        ambiguities: list[RuntimeAmbiguity] = []
        warnings: list[RuntimeWarning] = []
        unresolved_terms: tuple[str, ...] = ()

        if len(plan.required_metrics) > 1:
            ambiguities.append(
                RuntimeAmbiguity(
                    id="runtime.metric_choice_required",
                    target="metric_choice",
                    question="Which revenue metric should be used?",
                    reason="The plan matched multiple metric candidates.",
                    choices=tuple(plan.required_metrics),
                )
            )
        if not plan.required_terms and not plan.required_metrics and plan.selected_verified_query is None:
            unresolved_terms = (plan.selected_verified_query or "unresolved_question",)

        if self.packs:
            warnings.extend(self._draft_warnings(plan))

        if not ambiguities and plan.warnings:
            for warning in plan.warnings:
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
        for pack in self.packs:
            terms = {term.id: term for term in pack.business_terms}
            metrics = {metric.id: metric for metric in pack.metrics}
            for term_id in plan.required_terms:
                term = terms.get(term_id)
                if term is not None and str(term.status).casefold() == "draft":
                    draft_warnings.append(
                        RuntimeWarning(
                            code="draft_semantic_card",
                            target=term_id,
                            message="Draft semantic card must not be treated as confirmed truth.",
                        )
                    )
            for metric_id in plan.required_metrics:
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
        "ambiguities": [ambiguity.__dict__ for ambiguity in verdict["ambiguities"]],
        "warnings": [warning.__dict__ for warning in verdict["warnings"]],
        "unresolved_terms": list(verdict["unresolved_terms"]),
        "requires_clarification": verdict["requires_clarification"],
        "execution_allowed": False,
    }
