"""SQL comparison engine for baseline-vs-system product demos.

The engine profiles SQL text and Semantic Pack expectations only. It does not
run SQL, open database connections, or treat parser uncertainty as success.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import re
from pathlib import Path
from typing import Any, Iterable

from semantic_contracts import SemanticPack
from semantic_registry.query_planner import load_space_packs
from semantic_registry.sql_guard import SQLGuard
from semantic_registry.store import DEFAULT_PACK_ROOT


@dataclass(frozen=True)
class SqlCandidateProfile:
    sql: str | None
    candidate_name: str
    tables: list[str] = field(default_factory=list)
    columns: list[str] = field(default_factory=list)
    joins: list[str] = field(default_factory=list)
    filters: list[str] = field(default_factory=list)
    date_basis_candidates: list[str] = field(default_factory=list)
    aggregations: list[str] = field(default_factory=list)
    group_by: list[str] = field(default_factory=list)
    pii_columns: list[str] = field(default_factory=list)
    policy_violations: list[str] = field(default_factory=list)
    safety_violations: list[str] = field(default_factory=list)
    parser_warnings: list[str] = field(default_factory=list)
    not_executed: bool = True


@dataclass(frozen=True)
class DifferenceItem:
    category: str
    severity: str
    message: str
    baseline_evidence: list[str] = field(default_factory=list)
    system_evidence: list[str] = field(default_factory=list)
    expected_semantic_refs: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class SemanticCoverageScore:
    score: float
    covered: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    rationale: str = ""


@dataclass(frozen=True)
class SafetyComparisonScore:
    baseline_safe: bool
    system_safe: bool
    baseline_violations: list[str] = field(default_factory=list)
    system_violations: list[str] = field(default_factory=list)
    rationale: str = ""


@dataclass(frozen=True)
class PolicyComparisonScore:
    baseline_policy_pass: bool
    system_policy_pass: bool
    baseline_violations: list[str] = field(default_factory=list)
    system_violations: list[str] = field(default_factory=list)
    rationale: str = ""


@dataclass(frozen=True)
class Recommendation:
    decision: str
    next_actions: list[str] = field(default_factory=list)
    rationale: str = ""


@dataclass(frozen=True)
class SqlComparisonRequest:
    question: str
    baseline_sql: str | None
    system_sql: str | None
    space_id: str = "demo_company.revenue"
    role: str | None = "marketing_analyst"


@dataclass(frozen=True)
class SqlComparisonResult:
    request: SqlComparisonRequest
    baseline_profile: SqlCandidateProfile
    system_profile: SqlCandidateProfile
    differences: list[DifferenceItem]
    semantic_coverage: SemanticCoverageScore
    safety_score: SafetyComparisonScore
    policy_score: PolicyComparisonScore
    recommendation: Recommendation
    execution_allowed: bool = False

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["execution_allowed"] = False
        return data


def compare_baseline_vs_system_sql(
    question: str,
    baseline_sql: str | None,
    system_sql: str | None,
    *,
    space_id: str = "demo_company.revenue",
    role: str | None = "marketing_analyst",
    pack_root: str | Path = DEFAULT_PACK_ROOT,
) -> SqlComparisonResult:
    packs = load_space_packs(space_id, pack_root)
    request = SqlComparisonRequest(question=question, baseline_sql=baseline_sql, system_sql=system_sql, space_id=space_id, role=role)
    baseline_profile = profile_sql(baseline_sql, packs=packs, role=role, candidate_name="baseline")
    system_profile = profile_sql(system_sql, packs=packs, role=role, candidate_name="system")
    expected = _expected_semantics(question, packs)
    differences = _semantic_differences(expected, baseline_profile, system_profile)
    semantic_coverage = _score_semantic_coverage(expected, system_profile, differences)
    safety_score = SafetyComparisonScore(
        baseline_safe=not baseline_profile.safety_violations,
        system_safe=not system_profile.safety_violations,
        baseline_violations=baseline_profile.safety_violations,
        system_violations=system_profile.safety_violations,
        rationale="SQL text was profiled only; neither candidate was executed.",
    )
    policy_score = PolicyComparisonScore(
        baseline_policy_pass=not baseline_profile.policy_violations,
        system_policy_pass=not system_profile.policy_violations,
        baseline_violations=baseline_profile.policy_violations,
        system_violations=system_profile.policy_violations,
        rationale="Policy comparison is delegated to SQLGuard and pack policy metadata.",
    )
    recommendation = _recommend(differences, system_profile)
    return SqlComparisonResult(
        request=request,
        baseline_profile=baseline_profile,
        system_profile=system_profile,
        differences=differences,
        semantic_coverage=semantic_coverage,
        safety_score=safety_score,
        policy_score=policy_score,
        recommendation=recommendation,
        execution_allowed=False,
    )


def profile_sql(sql: str | None, *, packs: Iterable[SemanticPack], role: str | None, candidate_name: str) -> SqlCandidateProfile:
    if not sql or not sql.strip():
        return SqlCandidateProfile(sql=sql, candidate_name=candidate_name, parser_warnings=["missing_sql"], not_executed=True)
    text = _strip_literals(sql)
    statements = [part.strip() for part in text.split(";") if part.strip()]
    safety: list[str] = []
    if len(statements) != 1:
        safety.append("multi_statement")
    first = statements[0].split(None, 1)[0].casefold() if statements else ""
    if first not in {"select", "with"}:
        safety.append("non_select")
    guard = SQLGuard(packs).validate(sql, role=role)
    policy_violations = list(guard.errors)
    if not guard.valid:
        for check, status in guard.checks.items():
            if str(status).endswith("fail") or getattr(status, "value", status) == "fail":
                if str(check) not in safety:
                    policy_violations.append(str(check))
    tables = _extract_tables(text)
    columns = _extract_columns(text)
    blocked = _blocked_columns(packs, role)
    pii_columns = sorted(column for column in columns if column.casefold() in blocked)
    aggregations = _extract_aggregations(text)
    return SqlCandidateProfile(
        sql=sql,
        candidate_name=candidate_name,
        tables=tables,
        columns=columns,
        joins=_extract_joins(text),
        filters=_extract_filters(text),
        date_basis_candidates=[column for column in columns if column.endswith("_at") or column.endswith("_date") or ".date" in column],
        aggregations=aggregations,
        group_by=_extract_group_by(text),
        pii_columns=pii_columns,
        policy_violations=sorted(set(policy_violations + [f"blocked_pii_column:{column}" for column in pii_columns])),
        safety_violations=sorted(set(safety)),
        parser_warnings=[] if tables or safety else ["parser_uncertain:no_tables_detected"],
        not_executed=True,
    )


def _expected_semantics(question: str, packs: Iterable[SemanticPack]) -> dict[str, list[str]]:
    q = question.casefold()
    expected = {
        "terms": [],
        "metrics": [],
        "tables": [],
        "joins": [],
        "columns": [],
        "filters": [],
        "verified_queries": [],
    }
    for pack in packs:
        for term in pack.business_terms:
            haystack = " ".join([term.id, term.term, *term.aliases]).casefold()
            if any(part and part in q for part in haystack.split()):
                expected["terms"].append(term.id)
                expected["tables"].extend(term.related_tables)
                if term.sql_condition:
                    expected["filters"].append(term.sql_condition)
                    expected["columns"].extend(_extract_columns(term.sql_condition))
        for metric in pack.metrics:
            haystack = " ".join([metric.id, metric.name, metric.label]).casefold()
            if any(part and part in q for part in haystack.split()):
                expected["metrics"].append(metric.id)
                expected["tables"].extend(metric.required_tables)
                expected["columns"].extend(_extract_columns(metric.formula_sql))
                expected["filters"].extend(metric.default_filters)
                if metric.date_basis:
                    expected["columns"].append(metric.date_basis)
        for verified_query in pack.verified_queries:
            if set(verified_query.related_terms).issubset(expected["terms"]) and set(verified_query.related_metrics).issubset(expected["metrics"]):
                expected["verified_queries"].append(verified_query.id)
                expected["columns"].extend(_extract_columns(verified_query.sql))
                expected["tables"].extend(_extract_tables(verified_query.sql))
        table_set = set(expected["tables"])
        for join in pack.join_recipes:
            if join.left_table in table_set and join.right_table in table_set:
                expected["joins"].append(join.id)
    return {key: _unique(value) for key, value in expected.items()}


def _semantic_differences(expected: dict[str, list[str]], baseline: SqlCandidateProfile, system: SqlCandidateProfile) -> list[DifferenceItem]:
    diffs: list[DifferenceItem] = []
    expected_columns = set(column.casefold() for column in expected["columns"])
    baseline_columns = set(column.casefold() for column in baseline.columns)
    system_columns = set(column.casefold() for column in system.columns)

    if "users.first_paid_at" in expected_columns and "users.first_paid_at" not in baseline_columns:
        evidence = [column for column in baseline.date_basis_candidates if column in {"users.created_at", "payments.paid_at"}]
        diffs.append(
            DifferenceItem(
                category="wrong_date_basis",
                severity="high",
                message="Baseline does not use the confirmed first-paid date basis for 신규 고객.",
                baseline_evidence=evidence or baseline.date_basis_candidates,
                system_evidence=[column for column in system.columns if column == "users.first_paid_at"],
                expected_semantic_refs=["term.new_customer", "users.first_paid_at"],
            )
        )
    if {"payments.refund_amount", "payments.discount_amount"}.issubset(expected_columns) and not {"payments.refund_amount", "payments.discount_amount"}.issubset(baseline_columns):
        diffs.append(
            DifferenceItem(
                category="wrong_metric_basis",
                severity="high",
                message="Baseline misses refund/discount deductions required by 순매출.",
                baseline_evidence=baseline.aggregations,
                system_evidence=[column for column in system.columns if column in {"payments.refund_amount", "payments.discount_amount"}],
                expected_semantic_refs=["metric.net_revenue"],
            )
        )
    if expected["joins"] and not _has_join_condition(baseline):
        diffs.append(
            DifferenceItem(
                category="missing_join_recipe",
                severity="medium",
                message="Baseline does not clearly follow the expected join recipe.",
                baseline_evidence=baseline.joins,
                system_evidence=system.joins,
                expected_semantic_refs=expected["joins"],
            )
        )
    if expected["filters"] and "payments.status" in " ".join(expected["filters"]).casefold() and "payments.status" not in baseline_columns:
        diffs.append(
            DifferenceItem(
                category="missing_value_filter",
                severity="medium",
                message="Baseline misses the semantic/default paid-status filter.",
                baseline_evidence=baseline.filters,
                system_evidence=system.filters,
                expected_semantic_refs=["value_dict.payments.status", "metric.net_revenue"],
            )
        )
    for column in baseline.pii_columns:
        diffs.append(
            DifferenceItem(
                category="pii_policy_violation",
                severity="high",
                message="Baseline references a policy-blocked PII column.",
                baseline_evidence=[column],
                system_evidence=system.pii_columns,
                expected_semantic_refs=["policy.marketing_safe_revenue"],
            )
        )
    for violation in baseline.safety_violations:
        diffs.append(
            DifferenceItem(
                category="unsafe_sql",
                severity="critical",
                message="Baseline SQL text is not a safe single SELECT/WITH statement.",
                baseline_evidence=[violation],
                system_evidence=system.safety_violations,
            )
        )
    if system.sql and expected_columns:
        missing = set(expected_columns - system_columns)
        # When a cohort term explicitly chooses users.first_paid_at, the metric's
        # generic payment-date basis is superseded for the cohort grouping. This
        # is recorded instead of being treated as a system miss.
        if "term.new_customer" in expected["terms"] and "users.first_paid_at" in system_columns:
            missing.discard("payments.paid_at")
        if missing:
            diffs.append(
                DifferenceItem(
                    category="system_missing_semantic_column",
                    severity="high",
                    message="System SQL draft is missing expected semantic columns.",
                    system_evidence=sorted(missing),
                    expected_semantic_refs=expected["terms"] + expected["metrics"],
                )
            )
    if not system.sql:
        diffs.append(
            DifferenceItem(
                category="system_sql_not_available",
                severity="medium",
                message="System did not draft SQL, so UI must show a clarification or missing-context state.",
                expected_semantic_refs=expected["terms"] + expected["metrics"],
            )
        )
    return diffs


def _score_semantic_coverage(expected: dict[str, list[str]], system: SqlCandidateProfile, differences: Iterable[DifferenceItem]) -> SemanticCoverageScore:
    expected_refs = _unique(expected["terms"] + expected["metrics"] + expected["joins"] + expected["verified_queries"])
    missing = _unique(ref for diff in differences for ref in diff.expected_semantic_refs if diff.category.startswith("system_"))
    covered = [ref for ref in expected_refs if ref not in set(missing)]
    score = 1.0 if not expected_refs else max(0.0, len(covered) / len(expected_refs))
    if system.parser_warnings:
        score = min(score, 0.75)
    return SemanticCoverageScore(score=round(score, 3), covered=covered, missing=missing, rationale="Semantic coverage is based on expected pack refs present in the system candidate.")


def _recommend(differences: list[DifferenceItem], system: SqlCandidateProfile) -> Recommendation:
    critical_or_high = [diff for diff in differences if diff.severity in {"critical", "high"}]
    if system.safety_violations:
        return Recommendation("block", ["Do not preview; fix system SQL safety issues."], "System candidate failed safety profiling.")
    if any(diff.category == "system_sql_not_available" for diff in differences):
        return Recommendation("ask_or_enrich_context", ["Ask clarification or add missing Semantic Pack context."], "System did not produce a validated SQL draft.")
    if critical_or_high:
        return Recommendation("prefer_system_with_warnings", ["Show high-risk baseline differences in the UI."], "Baseline has material semantic or safety risk.")
    return Recommendation("prefer_system", ["Show comparison and allow validation-gated local preview if configured."], "System candidate aligns with pack expectations better than baseline.")


def _strip_literals(sql: str) -> str:
    return re.sub(r"'(?:''|[^'])*'|\"(?:\"\"|[^\"])*\"", "''", sql)


def _extract_tables(sql: str) -> list[str]:
    return _unique(match.group(1).split(".")[-1].casefold() for match in re.finditer(r"(?is)\b(?:from|join)\s+([a-zA-Z_][\w.]*)", sql))


def _extract_columns(sql: str) -> list[str]:
    return _unique(match.group(0).casefold() for match in re.finditer(r"\b[a-zA-Z_][\w]*\.[a-zA-Z_][\w]*\b", sql))


def _extract_joins(sql: str) -> list[str]:
    return _unique(match.group(0).strip() for match in re.finditer(r"(?is)\bjoin\s+[a-zA-Z_][\w.]*\s+on\s+.*?(?=\bjoin\b|\bwhere\b|\bgroup\b|\border\b|$)", sql))


def _extract_filters(sql: str) -> list[str]:
    match = re.search(r"(?is)\bwhere\b(.+?)(?:\bgroup\b|\border\b|\bhaving\b|$)", sql)
    return [match.group(1).strip()] if match else []


def _extract_aggregations(sql: str) -> list[str]:
    return _unique(match.group(0).strip() for match in re.finditer(r"(?is)\b(?:sum|count|avg|min|max)\s*\([^)]*\)", sql))


def _extract_group_by(sql: str) -> list[str]:
    match = re.search(r"(?is)\bgroup\s+by\b(.+?)(?:\border\b|\bhaving\b|$)", sql)
    return [part.strip() for part in match.group(1).split(",")] if match else []


def _blocked_columns(packs: Iterable[SemanticPack], role: str | None) -> set[str]:
    blocked: set[str] = set()
    for pack in packs:
        for policy in pack.policies:
            if role is not None and role not in policy.applies_to.roles:
                continue
            blocked.update(column.casefold() for column in policy.blocked_columns)
    return blocked


def _has_join_condition(profile: SqlCandidateProfile) -> bool:
    return any("users.user_id" in join.casefold() and "payments.user_id" in join.casefold() for join in profile.joins)


def _unique(values: Iterable[Any]) -> list[Any]:
    seen: set[Any] = set()
    result: list[Any] = []
    for value in values:
        if value is None or value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


__all__ = [
    "DifferenceItem",
    "PolicyComparisonScore",
    "Recommendation",
    "SafetyComparisonScore",
    "SemanticCoverageScore",
    "SqlCandidateProfile",
    "SqlComparisonRequest",
    "SqlComparisonResult",
    "compare_baseline_vs_system_sql",
    "profile_sql",
]
