"""UI-ready view models for the local product demo."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class BaselineSqlPanel:
    sql: str | None
    provider: str
    warnings: list[str] = field(default_factory=list)
    risk_notes: list[dict[str, Any]] = field(default_factory=list)
    not_executed: bool = True


@dataclass(frozen=True)
class SystemSqlPanel:
    sql: str | None
    source: str
    selected_terms: list[str] = field(default_factory=list)
    selected_metrics: list[str] = field(default_factory=list)
    selected_tables: list[str] = field(default_factory=list)
    selected_joins: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    used_context_sources: list[str] = field(default_factory=list)
    source_status: dict[str, str] = field(default_factory=dict)
    context_warnings: list[str] = field(default_factory=list)
    execution_allowed: bool = False


@dataclass(frozen=True)
class DifferenceSummaryPanel:
    items: list[dict[str, Any]] = field(default_factory=list)
    recommendation: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AppliedDefinitionsPanel:
    business_terms: list[dict[str, Any]] = field(default_factory=list)
    metrics: list[dict[str, Any]] = field(default_factory=list)
    policies: list[dict[str, Any]] = field(default_factory=list)
    verified_queries: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class VerificationPanel:
    policy_verdict: dict[str, Any] = field(default_factory=dict)
    semantic_verdict: dict[str, Any] = field(default_factory=dict)
    preview_eligible: bool = False
    execution_allowed: bool = False


@dataclass(frozen=True)
class FailureStatePanel:
    state: str
    message: str
    reasons: list[str] = field(default_factory=list)
    next_actions: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class PreviewResultPanel:
    status: str = "not_requested"
    columns: list[str] = field(default_factory=list)
    rows: list[dict[str, Any]] = field(default_factory=list)
    errors: list[dict[str, Any]] = field(default_factory=list)
    execution_allowed: bool = False


@dataclass(frozen=True)
class SuggestedActionsPanel:
    actions: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class AnswerComparisonViewModel:
    mode: str
    question: str
    role: str | None
    space_id: str
    baseline_sql_panel: BaselineSqlPanel
    system_sql_panel: SystemSqlPanel
    difference_summary_panel: DifferenceSummaryPanel
    applied_definitions_panel: AppliedDefinitionsPanel
    verification_panel: VerificationPanel
    failure_state_panel: FailureStatePanel | None = None
    preview_result_panel: PreviewResultPanel = field(default_factory=PreviewResultPanel)
    suggested_actions_panel: SuggestedActionsPanel = field(default_factory=SuggestedActionsPanel)
    execution_allowed: bool = False

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["execution_allowed"] = False
        return data


__all__ = [
    "AnswerComparisonViewModel",
    "AppliedDefinitionsPanel",
    "BaselineSqlPanel",
    "DifferenceSummaryPanel",
    "FailureStatePanel",
    "PreviewResultPanel",
    "SuggestedActionsPanel",
    "SystemSqlPanel",
    "VerificationPanel",
]
