"""Structured contracts for the Phase 8 domain-aware query runtime."""

from __future__ import annotations

from enum import StrEnum
import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class StrictRuntimeModel(BaseModel):
    """Runtime payload base: closed schemas keep tool outputs predictable."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class RuntimeIntent(StrEnum):
    DATA_QUERY = "data_query"
    CLARIFICATION = "clarification"
    UNSUPPORTED = "unsupported"


class AmbiguityStatus(StrEnum):
    CLEAR = "clear"
    NEEDS_CLARIFICATION = "needs_clarification"
    BLOCKED = "blocked"


class SqlDraftSource(StrEnum):
    VERIFIED_QUERY_TEMPLATE = "verified_query_template"
    RULE_BASED = "rule_based"
    NONE = "none"


class VerdictStatus(StrEnum):
    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"


class AnswerStatus(StrEnum):
    READY = "ready"
    NEEDS_CLARIFICATION = "needs_clarification"
    BLOCKED = "blocked"


_EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.IGNORECASE)
_PHONE_RE = re.compile(r"(?<!\d)(?:\+?\d[\d\-\s().]{7,}\d)(?!\d)")
_FORBIDDEN_SQL_PREFIXES = {
    "insert",
    "update",
    "delete",
    "drop",
    "alter",
    "truncate",
    "create",
    "merge",
    "copy",
    "call",
    "grant",
    "revoke",
}


def _reject_raw_pii_text(value: str, path: str) -> None:
    if _EMAIL_RE.search(value) or _PHONE_RE.search(value):
        raise ValueError(f"{path} must not contain raw PII-like values")


def _require_non_blank(value: str, path: str) -> str:
    if not value or not value.strip():
        raise ValueError(f"{path} must not be blank")
    return value


class UserQuestion(StrictRuntimeModel):
    """User question envelope before any retrieval or planning occurs."""

    question: str
    space_id: str
    role: str | None = None
    locale: str = "ko-KR"
    question_id: str | None = None

    @field_validator("question", "space_id")
    @classmethod
    def require_non_blank_text(cls, value: str, info: Any) -> str:
        return _require_non_blank(value, info.field_name)


class RuntimeContext(StrictRuntimeModel):
    """Pipeline context assembled from local Semantic Pack state only.

    This model is metadata-only: it carries pack/retrieval context and never
    represents a database handle, execution cursor, or external runtime session.
    """

    user_question: UserQuestion
    pack_ids: list[str] = Field(default_factory=list)
    retrieval_backend: str = "keyword"
    trace_id: str | None = None
    warnings: list[str] = Field(default_factory=list)

    @field_validator("pack_ids")
    @classmethod
    def pack_ids_must_not_be_blank(cls, values: list[str]) -> list[str]:
        for index, value in enumerate(values):
            _require_non_blank(value, f"pack_ids[{index}]")
        return values


class IntentResult(StrictRuntimeModel):
    intent: RuntimeIntent = RuntimeIntent.DATA_QUERY
    normalized_question: str
    requested_terms: list[str] = Field(default_factory=list)
    requested_metrics: list[str] = Field(default_factory=list)
    requested_columns: list[str] = Field(default_factory=list)
    time_grain: str | None = None
    confidence: float = Field(default=0.0, ge=0, le=1)
    warnings: list[str] = Field(default_factory=list)

    @field_validator("normalized_question")
    @classmethod
    def normalized_question_must_not_be_blank(cls, value: str) -> str:
        return _require_non_blank(value, "normalized_question")


class ContextCardRef(StrictRuntimeModel):
    card_id: str
    card_type: str
    source_pack: str
    status: str
    title: str | None = None
    score: float | None = Field(default=None, ge=0, le=1)
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def add_draft_warning(self) -> "ContextCardRef":
        if self.status.casefold() == "draft" and "draft_card" not in self.warnings:
            # Draft semantic cards are usable as context, but downstream answers
            # must surface the warning instead of presenting them as confirmed truth.
            self.warnings.append("draft_card")
        return self


class ResolvedContextBundle(StrictRuntimeModel):
    """Semantic context selected for a question after retrieval/resolution."""

    cards: list[ContextCardRef] = Field(default_factory=list)
    terms: list[str] = Field(default_factory=list)
    metrics: list[str] = Field(default_factory=list)
    tables: list[str] = Field(default_factory=list)
    joins: list[str] = Field(default_factory=list)
    policies: list[str] = Field(default_factory=list)
    verified_queries: list[str] = Field(default_factory=list)
    unresolved_terms: list[str] = Field(default_factory=list)
    blocked_columns: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def collect_card_warnings(self) -> "ResolvedContextBundle":
        for card in self.cards:
            for warning in card.warnings:
                if warning not in self.warnings:
                    self.warnings.append(warning)
        return self


class AmbiguityDecision(StrictRuntimeModel):
    status: AmbiguityStatus = AmbiguityStatus.CLEAR
    questions: list[str] = Field(default_factory=list)
    ambiguous_targets: list[str] = Field(default_factory=list)
    hard_block: bool = False
    reasons: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def clarification_requires_question(self) -> "AmbiguityDecision":
        if self.status == AmbiguityStatus.NEEDS_CLARIFICATION and not self.questions:
            raise ValueError("clarification decisions require at least one question")
        if self.hard_block and self.status == AmbiguityStatus.CLEAR:
            raise ValueError("hard ambiguity blocks cannot be marked clear")
        return self


class QueryPlan(StrictRuntimeModel):
    required_terms: list[str] = Field(default_factory=list)
    required_metrics: list[str] = Field(default_factory=list)
    candidate_tables: list[str] = Field(default_factory=list)
    join_recipes: list[str] = Field(default_factory=list)
    filters: list[str] = Field(default_factory=list)
    group_by: list[str] = Field(default_factory=list)
    selected_verified_query: str | None = None
    used_cards: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0, le=1)
    warnings: list[str] = Field(default_factory=list)
    used_context_sources: list[str] = Field(default_factory=list)
    cards_used: list[str] = Field(default_factory=list)
    source_status: dict[str, str] = Field(default_factory=dict)
    context_warnings: list[str] = Field(default_factory=list)
    sql_draft_allowed: bool = False


class SqlDraft(StrictRuntimeModel):
    """Validation-only SQL text produced for review or guard checks.

    The contract deliberately exposes no method or flag that could run the SQL;
    execution remains a later-phase concern outside this runtime model.
    """

    sql: str | None = None
    source: SqlDraftSource = SqlDraftSource.NONE
    selected_verified_query: str | None = None
    used_cards: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0, le=1)
    warnings: list[str] = Field(default_factory=list)
    execution_allowed: Literal[False] = False

    @model_validator(mode="after")
    def sql_must_be_read_only_draft(self) -> "SqlDraft":
        if self.sql is None:
            if self.source != SqlDraftSource.NONE:
                raise ValueError("missing SQL draft must use source=none")
            return self
        sql_text = _require_non_blank(self.sql, "sql").strip()
        _reject_raw_pii_text(sql_text, "sql")
        first_token = sql_text.split(None, 1)[0].casefold()
        if first_token in _FORBIDDEN_SQL_PREFIXES:
            raise ValueError("SQL draft must be read-only SELECT/WITH text")
        if first_token not in {"select", "with"}:
            raise ValueError("SQL draft must start with SELECT or WITH")
        return self


class PolicyVerdict(StrictRuntimeModel):
    status: VerdictStatus = VerdictStatus.PASS
    allowed: bool = True
    allowed_tables: list[str] = Field(default_factory=list)
    blocked_columns: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    execution_allowed: Literal[False] = False

    @model_validator(mode="after")
    def blocked_policy_requires_reason(self) -> "PolicyVerdict":
        if not self.allowed and not (self.reasons or self.blocked_columns):
            raise ValueError("blocked policy verdicts require reasons or blocked_columns")
        if not self.allowed and self.status == VerdictStatus.PASS:
            raise ValueError("blocked policy verdicts cannot have pass status")
        return self


class SemanticVerdict(StrictRuntimeModel):
    status: VerdictStatus = VerdictStatus.PASS
    valid: bool = True
    missing_terms: list[str] = Field(default_factory=list)
    missing_metrics: list[str] = Field(default_factory=list)
    missing_joins: list[str] = Field(default_factory=list)
    date_basis_warnings: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def invalid_semantics_require_evidence(self) -> "SemanticVerdict":
        evidence = self.reasons or self.missing_terms or self.missing_metrics or self.missing_joins or self.date_basis_warnings
        if not self.valid and not evidence:
            raise ValueError("invalid semantic verdicts require evidence")
        if not self.valid and self.status == VerdictStatus.PASS:
            raise ValueError("invalid semantic verdicts cannot have pass status")
        return self


class RuntimeAnswerDraft(StrictRuntimeModel):
    """Final structured explanation payload for the validation-only runtime."""

    status: AnswerStatus
    question: UserQuestion
    intent: IntentResult | None = None
    context: ResolvedContextBundle = Field(default_factory=ResolvedContextBundle)
    ambiguity: AmbiguityDecision = Field(default_factory=AmbiguityDecision)
    plan: QueryPlan | None = None
    sql_draft: SqlDraft = Field(default_factory=SqlDraft)
    policy_verdict: PolicyVerdict = Field(default_factory=PolicyVerdict)
    semantic_verdict: SemanticVerdict = Field(default_factory=SemanticVerdict)
    explanation: str | None = None
    clarification_questions: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    execution_allowed: Literal[False] = False

    @model_validator(mode="after")
    def enforce_answer_status_consistency(self) -> "RuntimeAnswerDraft":
        if self.explanation is not None:
            _reject_raw_pii_text(self.explanation, "explanation")
        if self.status == AnswerStatus.NEEDS_CLARIFICATION and not (self.clarification_questions or self.ambiguity.questions):
            raise ValueError("clarification answers require questions")
        if self.status == AnswerStatus.BLOCKED and self.policy_verdict.allowed and self.semantic_verdict.valid:
            raise ValueError("blocked answers require a failing policy or semantic verdict")
        for source in (self.context.warnings, self.sql_draft.warnings, self.policy_verdict.warnings, self.semantic_verdict.warnings):
            for warning in source:
                if warning not in self.warnings:
                    self.warnings.append(warning)
        return self


__all__ = [
    "AmbiguityDecision",
    "AmbiguityStatus",
    "AnswerStatus",
    "ContextCardRef",
    "IntentResult",
    "PolicyVerdict",
    "QueryPlan",
    "ResolvedContextBundle",
    "RuntimeAnswerDraft",
    "RuntimeContext",
    "RuntimeIntent",
    "SemanticVerdict",
    "SqlDraft",
    "SqlDraftSource",
    "StrictRuntimeModel",
    "UserQuestion",
    "VerdictStatus",
]
