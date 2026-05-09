"""Policy and semantic verification compatibility wrappers."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable, Mapping

from semantic_contracts import SemanticPack
from semantic_contracts.runtime_contracts import StrictRuntimeModel
from pydantic import Field
from semantic_registry.sql_guard import SQLGuard
from semantic_registry.store import DEFAULT_PACK_ROOT, PackStore

from .query_planner import RuntimeQueryPlan


class VerificationResult(StrictRuntimeModel):
    verifier: str
    valid: bool
    execution_allowed: bool = False
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class PolicyVerifier:
    def __init__(self, packs: Iterable[SemanticPack]) -> None:
        self.packs = tuple(packs)

    @classmethod
    def from_pack(cls, pack: SemanticPack) -> "PolicyVerifier":
        return cls((pack,))

    @classmethod
    def from_packs(cls, packs: Iterable[SemanticPack]) -> "PolicyVerifier":
        return cls(tuple(packs))

    @classmethod
    def from_store(cls, space_id: str, pack_root: str | Path = DEFAULT_PACK_ROOT) -> "PolicyVerifier":
        return cls(_packs_for_space(space_id, pack_root))

    def verify_sql(self, sql: str, role: str | None = None) -> dict[str, Any]:
        if self.packs:
            result = SQLGuard(self.packs).validate(sql, role=role).model_dump(mode="json")
        else:
            result = SQLGuard([]).validate(sql, role=role).model_dump(mode="json")
        result.update({"verifier": "policy"})
        return result


class SemanticVerifier:
    def __init__(self, packs: Iterable[SemanticPack]) -> None:
        self.packs = tuple(packs)

    @classmethod
    def from_pack(cls, pack: SemanticPack) -> "SemanticVerifier":
        return cls((pack,))

    @classmethod
    def from_packs(cls, packs: Iterable[SemanticPack]) -> "SemanticVerifier":
        return cls(tuple(packs))

    @classmethod
    def from_store(cls, space_id: str, pack_root: str | Path = DEFAULT_PACK_ROOT) -> "SemanticVerifier":
        return cls(_packs_for_space(space_id, pack_root))

    def verify_sql(self, sql: str, plan: RuntimeQueryPlan | Any, role: str | None = None) -> dict[str, Any]:  # noqa: ARG002
        runtime_plan = _coerce_plan(plan)
        errors: list[str] = []
        warnings: list[str] = []
        sql_norm = sql.casefold()

        if runtime_plan.required_terms or runtime_plan.required_metrics:
            if "term.new_customer" in runtime_plan.required_terms and "users.first_paid_at" not in sql_norm:
                errors.append("missing required business-term condition columns: users.first_paid_at")
            if "term.new_customer" in runtime_plan.required_terms and "users.first_paid_at" in sql_norm and "payments.paid_at" in sql_norm:
                warnings.append("Wrong date basis was checked against users.first_paid_at")
            if "term.new_customer" in runtime_plan.required_terms and "users.first_paid_at" not in sql_norm and "payments.paid_at" in sql_norm:
                errors.append("Wrong date basis: expected users.first_paid_at instead of payments.paid_at")

        valid = not errors
        return VerificationResult(
            verifier="semantic",
            valid=valid,
            execution_allowed=False,
            errors=errors,
            warnings=warnings,
        ).model_dump(mode="json")


def verify_policy(
    sql: str,
    *,
    role: str | None = None,
    pack_root: str | Path = DEFAULT_PACK_ROOT,
    space_id: str = "demo_company.revenue",
) -> dict[str, Any]:
    packs = _packs_for_space(space_id, pack_root)
    return PolicyVerifier.from_packs(packs).verify_sql(sql, role=role)


def verify_semantics(
    sql: str,
    plan: RuntimeQueryPlan | Any,
    *,
    role: str | None = None,
    pack_root: str | Path = DEFAULT_PACK_ROOT,
) -> dict[str, Any]:  # noqa: ARG001
    return SemanticVerifier.from_packs(_packs_from_plan(plan, pack_root)).verify_sql(sql, plan=plan, role=role)


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
            ambiguities=[_ambiguity_to_dict(item) for item in plan_mapping.get("ambiguities", [])],
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
        ambiguities=[_ambiguity_to_dict(item) for item in getattr(plan, "ambiguities", [])],
        execution_allowed=bool(getattr(plan, "execution_allowed", False)),
        selected_verified_query=getattr(plan, "selected_verified_query", None),
        used_cards=list(getattr(plan, "used_cards", [])),
        confidence=float(getattr(plan, "confidence", 0.0)),
        warnings=list(getattr(plan, "warnings", [])),
        sql_draft_allowed=bool(getattr(plan, "sql_draft_allowed", False)),
    )


def _packs_from_plan(plan: RuntimeQueryPlan | Any, pack_root: str | Path) -> tuple[SemanticPack, ...]:
    # The compatibility layer keeps verification local and deterministic.  A
    # caller can supply a plan without a pack lookup, but the demo workspace
    # currently uses a single canonical revenue pack, so load that by default.
    space_id = getattr(plan, "space_id", None) or "demo_company.revenue"
    return _packs_for_space(space_id, pack_root)


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


def _packs_for_space(space_id: str, pack_root: str | Path) -> tuple[SemanticPack, ...]:
    packs = PackStore(pack_root).load_packs()
    return tuple(
        pack for pack in packs if pack.id == space_id or any(space.id == space_id for space in pack.spaces)
    )


__all__ = [
    "PolicyVerifier",
    "SemanticVerifier",
    "VerificationResult",
    "verify_policy",
    "verify_semantics",
]
