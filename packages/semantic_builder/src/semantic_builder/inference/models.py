"""PII-safe semantic hypothesis models for Phase 5 inference.

These models describe cautious LLM-assisted proposals only. They do not execute
SQL, call a vector database, create embeddings, or promote inferred business
meaning beyond draft status.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from semantic_contracts.models import RawValueStorage, SourceKind, TableRole


class StrictInferenceModel(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True, use_enum_values=True)


class ConfidenceLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Uncertainty(StrictInferenceModel):
    """A concrete reason a hypothesis needs human confirmation."""

    code: str
    message: str
    severity: ConfidenceLevel = ConfidenceLevel.MEDIUM
    question_hint: str | None = None

    @field_validator("code", "message")
    @classmethod
    def required_text(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("uncertainty text must not be blank")
        return value


class EvidenceReference(StrictInferenceModel):
    """Safe pointer back to scanner/profiler evidence, not a raw value carrier.

    The reference shape intentionally supports file-origin records now and
    PostgreSQL-origin records later without storing credentials, query results,
    sample cell values, embeddings, or VDB-specific identifiers.
    """

    source_type: SourceKind
    source_name: str
    artifact_type: Literal["scan_record", "profile_record", "column_profile", "semantic_pack", "manual_note"]
    safe_reference: bool = True
    pii_safe: bool = True
    raw_value_included: bool = False
    file_path: str | None = None
    sheet_name: str | None = None
    schema_name: str | None = None
    table_name: str | None = None
    column_name: str | None = None
    record_index: int | None = Field(default=None, ge=0)
    json_pointer: str | None = None

    @field_validator("source_name")
    @classmethod
    def source_name_not_blank(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("source_name must not be blank")
        return value

    @model_validator(mode="after")
    def enforce_safe_reference(self) -> "EvidenceReference":
        if not self.safe_reference or not self.pii_safe or self.raw_value_included:
            raise ValueError("evidence references must be PII-safe pointers without raw values")
        if self.source_type == SourceKind.FILE and not (self.file_path or self.source_name):
            raise ValueError("file evidence requires a file_path or source_name")
        if self.source_type == SourceKind.POSTGRESQL and not (self.table_name or self.source_name):
            raise ValueError("postgresql evidence requires a table_name or source_name")
        return self


class SemanticHypothesis(StrictInferenceModel):
    """Base draft hypothesis with mandatory evidence and uncertainty tracking."""

    id: str
    kind: str
    title: str | None = None
    description: str | None = None
    status: Literal["draft"] = "draft"
    confidence: ConfidenceLevel = ConfidenceLevel.LOW
    confidence_score: float | None = Field(default=None, ge=0, le=1)
    evidence: list[EvidenceReference] = Field(min_length=1)
    uncertainties: list[Uncertainty] = Field(default_factory=list)
    rationale: str | None = None

    @field_validator("id", "kind")
    @classmethod
    def required_identifiers(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("hypothesis identifiers must not be blank")
        return value


class TableHypothesis(SemanticHypothesis):
    kind: Literal["table"] = "table"
    table_name: str
    role: TableRole = TableRole.UNKNOWN
    grain: str | None = None
    primary_key: str | None = None


class ColumnHypothesis(SemanticHypothesis):
    kind: Literal["column"] = "column"
    table_name: str
    column_name: str
    data_type: str | None = None
    semantic_type: str | None = None
    pii_candidate: bool = False
    raw_value_storage: RawValueStorage = RawValueStorage.BLOCKED

    @model_validator(mode="after")
    def pii_candidates_block_raw_values(self) -> "ColumnHypothesis":
        # Phase 5 artifacts may later feed Weaviate text projections, so PII
        # candidates must remain raw-value blocked at the hypothesis layer too.
        if self.pii_candidate and self.raw_value_storage != RawValueStorage.BLOCKED:
            raise ValueError("PII candidate hypotheses must block raw value storage")
        return self


class MetricHypothesis(SemanticHypothesis):
    kind: Literal["metric"] = "metric"
    metric_name: str
    formula_hint: str | None = None
    date_basis: str | None = None
    required_tables: list[str] = Field(default_factory=list)


class BusinessTermHypothesis(SemanticHypothesis):
    kind: Literal["business_term"] = "business_term"
    term: str
    definition_hint: str | None = None
    related_tables: list[str] = Field(default_factory=list)
    related_metrics: list[str] = Field(default_factory=list)


__all__ = [
    "BusinessTermHypothesis",
    "ColumnHypothesis",
    "ConfidenceLevel",
    "EvidenceReference",
    "MetricHypothesis",
    "SemanticHypothesis",
    "TableHypothesis",
    "Uncertainty",
]
