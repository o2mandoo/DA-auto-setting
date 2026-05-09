"""JSON-compatible MCP tool request/response contract models without MCP runtime."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .sql_guard_contracts import SqlGuardResult


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class ListSemanticSpacesRequest(StrictModel):
    pass


class SemanticSpaceSummary(StrictModel):
    space_id: str
    title: str
    version: str
    status: str


class ListSemanticSpacesResponse(StrictModel):
    spaces: list[SemanticSpaceSummary] = Field(default_factory=list)


class SearchFilters(StrictModel):
    card_types: list[str] = Field(default_factory=list)
    limit: int = Field(default=10, ge=1, le=100)


class SearchSemanticContextRequest(StrictModel):
    space_id: str
    query: str
    filters: SearchFilters = Field(default_factory=SearchFilters)


class SearchContextResult(StrictModel):
    card_id: str
    card_type: str
    title: str
    snippet: str | None = None
    score: float = Field(ge=0, le=1)
    source_pack: str


class SearchSemanticContextResponse(StrictModel):
    results: list[SearchContextResult] = Field(default_factory=list)


class ResolveBusinessTermsRequest(StrictModel):
    space_id: str
    terms: list[str]


class ResolvedTerm(StrictModel):
    input: str
    term_id: str
    definition: str
    sql_condition: str | None = None
    status: str


class ResolveBusinessTermsResponse(StrictModel):
    resolved_terms: list[ResolvedTerm] = Field(default_factory=list)
    unresolved_terms: list[str] = Field(default_factory=list)


class PlanDataQueryRequest(StrictModel):
    space_id: str
    question: str
    role: str | None = None


class PlannedAmbiguity(StrictModel):
    id: str | None = None
    target: str | None = None
    question: str
    reason: str | None = None


class PlanDataQueryResponse(StrictModel):
    intent: str
    required_terms: list[str] = Field(default_factory=list)
    required_metrics: list[str] = Field(default_factory=list)
    candidate_tables: list[str] = Field(default_factory=list)
    join_recipes: list[str] = Field(default_factory=list)
    filters: list[str] = Field(default_factory=list)
    policy_notes: list[str] = Field(default_factory=list)
    ambiguities: list[PlannedAmbiguity] = Field(default_factory=list)
    used_context_sources: list[str] = Field(default_factory=list)
    cards_used: list[str] = Field(default_factory=list)
    source_status: dict[str, str] = Field(default_factory=dict)
    context_warnings: list[str] = Field(default_factory=list)
    execution_allowed: Literal[False] = False


class ValidateSqlRequest(StrictModel):
    space_id: str
    sql: str
    role: str | None = None


class ValidateSqlResponse(SqlGuardResult):
    pass


class RecordFeedbackRequest(StrictModel):
    space_id: str
    card_id: str | None = None
    feedback_type: Literal["correction", "confirmation", "question", "other"]
    message: str
    source: str | None = None


class FeedbackReceipt(StrictModel):
    feedback_id: str
    accepted: bool = True
    stored: bool = True


class RecordFeedbackResponse(StrictModel):
    receipt: FeedbackReceipt


__all__ = [
    "ListSemanticSpacesRequest",
    "ListSemanticSpacesResponse",
    "SearchSemanticContextRequest",
    "SearchSemanticContextResponse",
    "ResolveBusinessTermsRequest",
    "ResolveBusinessTermsResponse",
    "PlanDataQueryRequest",
    "PlanDataQueryResponse",
    "ValidateSqlRequest",
    "ValidateSqlResponse",
    "RecordFeedbackRequest",
    "RecordFeedbackResponse",
]
