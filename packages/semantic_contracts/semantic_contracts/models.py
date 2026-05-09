"""Pydantic models for the Phase 0 Semantic Pack contract."""

from __future__ import annotations

from enum import StrEnum
import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class PackStatus(StrEnum):
    DRAFT = "draft"
    REVIEWED = "reviewed"
    APPROVED = "approved"


class CardStatus(StrEnum):
    DRAFT = "draft"
    REVIEWED = "reviewed"
    APPROVED = "approved"
    CONFIRMED = "confirmed"


class ProposalStatus(StrEnum):
    DRAFT = "draft"
    REVIEWED = "reviewed"
    APPROVED = "approved"
    REJECTED = "rejected"
    DISMISSED = "dismissed"


class ConfirmationStatus(StrEnum):
    DRAFT = "draft"
    REVIEWED = "reviewed"
    APPROVED = "approved"
    REJECTED = "rejected"
    DISMISSED = "dismissed"


class SourceKind(StrEnum):
    FILE = "file"
    POSTGRESQL = "postgresql"
    BI_DOC = "bi_doc"
    QUERY_LOG = "query_log"


class TableRole(StrEnum):
    FACT = "fact"
    DIMENSION = "dimension"
    BRIDGE = "bridge"
    EVENT = "event"
    UNKNOWN = "unknown"


class PiiLevel(StrEnum):
    NONE = "none"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"


class RawValueStorage(StrEnum):
    ALLOWED = "allowed"
    BLOCKED = "blocked"


class ValueSource(StrEnum):
    PROFILER = "profiler"
    LLM = "llm"
    HUMAN = "human"
    VERIFIED_QUERY = "verified_query"


class ReverseQuestionStatus(StrEnum):
    OPEN = "open"
    ANSWERED = "answered"
    DISMISSED = "dismissed"


class Owner(StrictModel):
    role: str
    name: str


class SourceRef(StrictModel):
    type: SourceKind
    name: str
    safe_reference: bool = True




# Phase 6 confirmation/proposal payloads may later be indexed, but this
# package does not implement a VDB/Weaviate client. These checks keep the local
# contract safe for a future text projection without storing raw PII values.
_EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.IGNORECASE)
_PHONE_RE = re.compile(r"(?<!\d)(?:\+?\d[\d\-\s().]{7,}\d)(?!\d)")
_RAW_VALUE_KEYS = {
    "raw_value",
    "raw_values",
    "sample_value",
    "sample_values",
    "top_value",
    "top_values",
    "literal_value",
    "literal_values",
    "email_value",
    "phone_value",
}


def _reject_raw_pii_payload(value: Any, path: str = "payload") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            key_text = str(key)
            if key_text.casefold() in _RAW_VALUE_KEYS:
                raise ValueError(f"{path}.{key_text} must not store raw values")
            _reject_raw_pii_payload(child, f"{path}.{key_text}")
        return
    if isinstance(value, list):
        for index, child in enumerate(value):
            _reject_raw_pii_payload(child, f"{path}[{index}]")
        return
    if isinstance(value, str) and (_EMAIL_RE.search(value) or _PHONE_RE.search(value)):
        raise ValueError(f"{path} must not contain raw PII-like values")


class EvidenceRef(StrictModel):
    """PII-safe source/evidence pointer for human confirmation workflows."""

    source_kind: Literal[SourceKind.FILE, SourceKind.POSTGRESQL]
    reference_id: str
    safe_reference: bool = True
    file_path: str | None = None
    sheet_name: str | None = None
    database: str | None = None
    schema_name: str | None = None
    table_name: str | None = None
    column_refs: list[str] = Field(default_factory=list)
    row_locator_digest: str | None = None
    query_fingerprint: str | None = None
    notes: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def require_safe_origin_pointer(self) -> "EvidenceRef":
        if self.safe_reference is not True:
            raise ValueError("evidence refs must be marked safe_reference=true")
        if self.source_kind == SourceKind.FILE and not self.file_path:
            raise ValueError("file evidence refs require file_path")
        if self.source_kind == SourceKind.POSTGRESQL and not (self.table_name or self.query_fingerprint):
            raise ValueError("postgresql evidence refs require table_name or query_fingerprint")
        _reject_raw_pii_payload(self.metadata, "evidence.metadata")
        for text_path, text in (
            ("evidence.reference_id", self.reference_id),
            ("evidence.notes", self.notes),
            ("evidence.file_path", self.file_path),
            ("evidence.database", self.database),
            ("evidence.schema_name", self.schema_name),
            ("evidence.table_name", self.table_name),
            ("evidence.query_fingerprint", self.query_fingerprint),
        ):
            if text is not None:
                _reject_raw_pii_payload(text, text_path)
        for index, column_ref in enumerate(self.column_refs):
            _reject_raw_pii_payload(column_ref, f"evidence.column_refs[{index}]")
        return self


class HumanConfirmation(StrictModel):
    """Auditable human decision; it never mutates Semantic Packs by itself."""

    confirmation_id: str
    proposal_id: str
    status: ConfirmationStatus = ConfirmationStatus.DRAFT
    reviewer: str | None = None
    rationale: str | None = None
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)
    decided_at: str | None = None

    @model_validator(mode="after")
    def terminal_decisions_require_reviewer_and_safe_text(self) -> "HumanConfirmation":
        if self.status in {ConfirmationStatus.APPROVED, ConfirmationStatus.REJECTED, ConfirmationStatus.DISMISSED} and not self.reviewer:
            raise ValueError("terminal confirmation decisions require reviewer")
        _reject_raw_pii_payload(self.rationale, "confirmation.rationale")
        return self


class PackProposal(StrictModel):
    """Local proposal record for pack changes pending explicit confirmation."""

    proposal_id: str
    pack_id: str
    target_ref: str
    change_type: Literal["add", "update", "deprecate", "dismiss"] = "update"
    status: ProposalStatus = ProposalStatus.DRAFT
    proposed_patch: dict[str, Any] = Field(default_factory=dict)
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)
    confirmations: list[HumanConfirmation] = Field(default_factory=list)
    created_by: str | None = None
    created_at: str | None = None
    indexable_summary: str | None = None

    @model_validator(mode="after")
    def require_safe_proposal_payload(self) -> "PackProposal":
        _reject_raw_pii_payload(self.proposed_patch, "proposal.proposed_patch")
        _reject_raw_pii_payload(self.indexable_summary, "proposal.indexable_summary")
        return self


class SemanticSpace(StrictModel):
    id: str
    title: str


class ColumnProfile(StrictModel):
    null_ratio: float | None = Field(default=None, ge=0, le=1)
    cardinality: int | None = Field(default=None, ge=0)
    top_values_safe: bool = False
    min_value: str | int | float | None = None
    max_value: str | int | float | None = None


class PiiPolicy(StrictModel):
    is_candidate: bool = False
    raw_value_storage: RawValueStorage = RawValueStorage.BLOCKED
    masking_notes: str | None = None

    @model_validator(mode="after")
    def block_candidate_raw_values(self) -> "PiiPolicy":
        if self.is_candidate and self.raw_value_storage != RawValueStorage.BLOCKED:
            raise ValueError("PII candidate columns must block raw value storage")
        return self


class TableCard(StrictModel):
    id: str
    space_id: str
    physical_name: str
    title: str
    description: str | None = None
    role: TableRole = TableRole.UNKNOWN
    grain: str | None = None
    primary_key: str | None = None
    columns: list[str] = Field(default_factory=list)
    pii_level: PiiLevel = PiiLevel.NONE
    status: CardStatus = CardStatus.DRAFT
    confidence: float | None = Field(default=None, ge=0, le=1)


class ColumnCard(StrictModel):
    id: str
    table: str
    name: str
    data_type: str
    nullable: bool = True
    semantic_type: str | None = None
    description: str | None = None
    profile: ColumnProfile = Field(default_factory=ColumnProfile)
    pii: PiiPolicy = Field(default_factory=PiiPolicy)
    status: CardStatus = CardStatus.DRAFT
    confidence: float | None = Field(default=None, ge=0, le=1)


class ValueDictionaryEntry(StrictModel):
    value: str | int | float | bool
    label: str | None = None
    description: str | None = None
    count: int | None = Field(default=None, ge=0)
    source: ValueSource = ValueSource.PROFILER
    status: CardStatus = CardStatus.DRAFT


class ValueDictionary(StrictModel):
    id: str
    table: str
    column: str
    values: list[ValueDictionaryEntry] = Field(default_factory=list)


class Metric(StrictModel):
    id: str
    name: str
    label: str
    description: str | None = None
    formula_sql: str
    date_basis: str | None = None
    required_tables: list[str] = Field(default_factory=list)
    default_filters: list[str] = Field(default_factory=list)
    status: CardStatus = CardStatus.DRAFT
    owner: str | None = None


class AmbiguityRule(StrictModel):
    """Contract for model/tool behavior when domain intent is under-specified."""

    id: str
    target: str
    condition: str
    question: str
    required_when: str | None = None
    status: CardStatus = CardStatus.DRAFT


class BusinessTerm(StrictModel):
    id: str
    term: str
    aliases: list[str] = Field(default_factory=list)
    definition: str
    sql_condition: str | None = None
    related_tables: list[str] = Field(default_factory=list)
    related_metrics: list[str] = Field(default_factory=list)
    ambiguity_policy: str | None = None
    ambiguity_rules: list[AmbiguityRule] = Field(default_factory=list)
    status: CardStatus = CardStatus.DRAFT


class JoinRecipe(StrictModel):
    id: str
    left_table: str
    right_table: str
    join_type: Literal["one_to_one", "one_to_many", "many_to_one", "many_to_many"]
    condition: str
    recommended: bool = False
    warnings: list[str] = Field(default_factory=list)


class PolicyAppliesTo(StrictModel):
    roles: list[str] = Field(default_factory=list)


class Policy(StrictModel):
    id: str
    applies_to: PolicyAppliesTo = Field(default_factory=PolicyAppliesTo)
    allowed_tables: list[str] = Field(default_factory=list)
    blocked_columns: list[str] = Field(default_factory=list)
    # Phase 9 preview is bounded even for local fixtures; policies can lower
    # the default cap without implying production SQL execution authority.
    max_preview_rows: int = Field(default=100, ge=1, le=1000)
    notes: list[str] = Field(default_factory=list)


class VerifiedQuery(StrictModel):
    id: str
    question: str
    sql: str
    related_terms: list[str] = Field(default_factory=list)
    related_metrics: list[str] = Field(default_factory=list)
    status: CardStatus = CardStatus.CONFIRMED


class ReverseQuestion(StrictModel):
    id: str
    target: str
    question: str
    reason: str
    status: ReverseQuestionStatus = ReverseQuestionStatus.OPEN
    answer: str | None = None

    @model_validator(mode="after")
    def answered_questions_require_answer(self) -> "ReverseQuestion":
        if self.status == ReverseQuestionStatus.ANSWERED and not self.answer:
            raise ValueError("answered reverse questions must include answer")
        return self


class SemanticPack(StrictModel):
    id: str
    version: str
    status: PackStatus = PackStatus.DRAFT
    title: str
    description: str | None = None
    locale: str = "ko-KR"
    owners: list[Owner] = Field(default_factory=list)
    source_refs: list[SourceRef] = Field(default_factory=list)
    spaces: list[SemanticSpace] = Field(default_factory=list)
    tables: list[TableCard] = Field(default_factory=list)
    columns: list[ColumnCard] = Field(default_factory=list)
    value_dictionaries: list[ValueDictionary] = Field(default_factory=list)
    metrics: list[Metric] = Field(default_factory=list)
    business_terms: list[BusinessTerm] = Field(default_factory=list)
    join_recipes: list[JoinRecipe] = Field(default_factory=list)
    policies: list[Policy] = Field(default_factory=list)
    verified_queries: list[VerifiedQuery] = Field(default_factory=list)
    reverse_questions: list[ReverseQuestion] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("id", "version", "title")
    @classmethod
    def required_strings_not_blank(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("required string must not be blank")
        return value


class SemanticPackDocument(StrictModel):
    semantic_pack: SemanticPack
