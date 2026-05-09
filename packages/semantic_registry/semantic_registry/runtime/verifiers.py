"""Compatibility verifiers built on the registry SQL guard."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Iterable

from semantic_contracts import SemanticPack

from ..query_planner import load_space_packs
from ..sql_guard import SQLGuard
from ..store import DEFAULT_PACK_ROOT
from .models import QueryPlan


class PolicyVerifier:
    """Policy-only SQL verifier that delegates to SQLGuard."""

    def __init__(self, packs: Iterable[SemanticPack]) -> None:
        self.packs = list(packs)

    @classmethod
    def from_pack(cls, pack: SemanticPack) -> "PolicyVerifier":
        return cls([pack])

    @classmethod
    def from_packs(cls, packs: Iterable[SemanticPack]) -> "PolicyVerifier":
        return cls(list(packs))

    def verify_sql(self, sql: str, role: str | None = None) -> dict[str, Any]:
        result = SQLGuard(self.packs).validate(sql, role=role).model_dump(mode="json")
        result["verifier"] = "policy"
        return result


class SemanticVerifier:
    """Semantic verifier that compares SQL against a validated runtime plan."""

    def __init__(self, packs: Iterable[SemanticPack]) -> None:
        self.packs = list(packs)

    @classmethod
    def from_pack(cls, pack: SemanticPack) -> "SemanticVerifier":
        return cls([pack])

    @classmethod
    def from_packs(cls, packs: Iterable[SemanticPack]) -> "SemanticVerifier":
        return cls(list(packs))

    def verify_sql(self, sql: str, plan: QueryPlan, role: str | None = None) -> dict[str, Any]:  # noqa: ARG002
        reasons: list[str] = []
        warnings: list[str] = []
        required_columns: list[str] = []

        verified_query = self._find_verified_query(plan.selected_verified_query)
        if verified_query is not None:
            required_columns = _where_columns(verified_query.sql)
            sql_columns = _qualified_columns(sql)
            missing_required = [column for column in required_columns if column not in sql_columns]
            if missing_required:
                reasons.append(f"missing required business-term condition columns: {', '.join(missing_required)}")
            if "users.first_paid_at" in required_columns and "payments.paid_at" in sql_columns:
                reasons.append("Wrong date basis: expected users.first_paid_at, not payments.paid_at")

        if not verified_query and not plan.required_terms and not plan.required_metrics:
            reasons.append("plan did not resolve a confirmed verified query template")

        valid = not reasons
        return {
            "verifier": "semantic",
            "valid": valid,
            "execution_allowed": False,
            "reasons": reasons,
            "warnings": warnings,
            "required_business_term_condition_columns": required_columns,
        }

    def _find_verified_query(self, query_id: str | None) -> Any | None:
        if not query_id:
            return None
        for pack in self.packs:
            for verified_query in pack.verified_queries:
                if verified_query.id == query_id:
                    return verified_query
        return None


def verify_policy(
    sql: str,
    *,
    space_id: str = "demo_company.revenue",
    role: str | None = None,
    pack_root: str | Path = DEFAULT_PACK_ROOT,
    root: str | Path | None = None,
) -> dict[str, Any]:
    effective_root = root if root is not None else pack_root
    packs = load_space_packs(space_id, effective_root)
    return PolicyVerifier.from_packs(packs).verify_sql(sql, role=role)


def verify_semantics(
    sql: str,
    plan: QueryPlan,
    *,
    space_id: str = "demo_company.revenue",
    role: str | None = None,
    pack_root: str | Path = DEFAULT_PACK_ROOT,
    root: str | Path | None = None,
) -> dict[str, Any]:
    effective_root = root if root is not None else pack_root
    packs = load_space_packs(space_id, effective_root)
    return SemanticVerifier.from_packs(packs).verify_sql(sql, plan=plan, role=role)


def _qualified_columns(sql: str) -> list[str]:
    return sorted(set(re.findall(r"\b[a-zA-Z_][\w]*\.[a-zA-Z_][\w]*\b", sql)))


def _where_columns(sql: str) -> list[str]:
    match = re.search(r"(?is)\bwhere\b(.+?)(?:\border\b|\bgroup\b|\bhaving\b|$)", sql)
    if not match:
        return []
    return _qualified_columns(match.group(1))
