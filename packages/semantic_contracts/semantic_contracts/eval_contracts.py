"""Contracts for Phase 11 evaluation cases, manifests, and results.

These schemas are validation-only. They describe benchmark inputs and
structured outcomes without executing queries, contacting external services,
or storing raw PII-like values in evaluation payloads.
"""

from __future__ import annotations

from enum import StrEnum
import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictEvalModel(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class EvalSeverity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class EvalCaseCategory(StrEnum):
    GOLDEN_QUESTION = "golden_question"
    RED_TEAM = "red_team"
    BUILDER_SAFETY = "builder_safety"
    RETRIEVAL = "retrieval"
    RUNTIME = "runtime"
    SQL_GUARD = "sql_guard"
    PREVIEW = "preview"


class EvalCaseStatus(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    SKIP = "skip"
    WARN = "warn"


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
    """Reject raw value dictionaries and obvious PII-like strings.

    The evaluation harness must remain PII-safe even when cases mention blocked
    columns or dangerous SQL shapes. Cases should reference columns/cards, not
    embed raw user values.
    """

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


class EvalCaseBase(StrictEvalModel):
    id: str
    category: EvalCaseCategory
    input: dict[str, Any]
    context: dict[str, Any] = Field(default_factory=dict)
    expected_behavior: str
    must_not_do: list[str] = Field(default_factory=list)
    severity: EvalSeverity = EvalSeverity.MEDIUM
    related_cards: list[str] = Field(default_factory=list)
    pass_criteria: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_case_payload(self) -> "EvalCaseBase":
        if not self.id.strip():
            raise ValueError("eval case id must not be blank")
        if not self.expected_behavior.strip():
            raise ValueError("expected_behavior must not be blank")
        if not self.pass_criteria:
            raise ValueError("eval cases require at least one pass criterion")
        _reject_raw_pii_payload(self.input, f"{self.id}.input")
        _reject_raw_pii_payload(self.context, f"{self.id}.context")
        _reject_raw_pii_payload(self.expected_behavior, f"{self.id}.expected_behavior")
        _reject_raw_pii_payload(self.must_not_do, f"{self.id}.must_not_do")
        _reject_raw_pii_payload(self.related_cards, f"{self.id}.related_cards")
        _reject_raw_pii_payload(self.pass_criteria, f"{self.id}.pass_criteria")
        return self


class GoldenQuestionCase(EvalCaseBase):
    category: Literal["golden_question"] = EvalCaseCategory.GOLDEN_QUESTION


class RedTeamCase(EvalCaseBase):
    category: Literal["red_team"] = EvalCaseCategory.RED_TEAM


class BuilderSafetyCase(EvalCaseBase):
    category: Literal["builder_safety"] = EvalCaseCategory.BUILDER_SAFETY


class RetrievalCase(EvalCaseBase):
    category: Literal["retrieval"] = EvalCaseCategory.RETRIEVAL


class RuntimeCase(EvalCaseBase):
    category: Literal["runtime"] = EvalCaseCategory.RUNTIME


class SqlGuardCase(EvalCaseBase):
    category: Literal["sql_guard"] = EvalCaseCategory.SQL_GUARD


class PreviewCase(EvalCaseBase):
    category: Literal["preview"] = EvalCaseCategory.PREVIEW


class EvalCaseResult(StrictEvalModel):
    case_id: str
    category: EvalCaseCategory
    status: EvalCaseStatus
    reason: str | None = None
    evidence: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    duration_ms: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_case_result(self) -> "EvalCaseResult":
        if not self.case_id.strip():
            raise ValueError("case_id must not be blank")
        if self.reason is not None and not self.reason.strip():
            raise ValueError("reason must not be blank when provided")
        _reject_raw_pii_payload(self.evidence, f"{self.case_id}.evidence")
        _reject_raw_pii_payload(self.warnings, f"{self.case_id}.warnings")
        return self


class BenchmarkManifest(StrictEvalModel):
    dataset_id: str
    domain: str
    tables: list[str] = Field(default_factory=list)
    files: list[str] = Field(default_factory=list)
    expected_semantic_findings: list[str] = Field(default_factory=list)
    must_generate_questions: bool = True
    must_block: list[str] = Field(default_factory=list)
    golden_questions: list[GoldenQuestionCase] = Field(default_factory=list)
    red_team_cases: list[RedTeamCase] = Field(default_factory=list)
    builder_safety_cases: list[BuilderSafetyCase] = Field(default_factory=list)
    retrieval_cases: list[RetrievalCase] = Field(default_factory=list)
    runtime_cases: list[RuntimeCase] = Field(default_factory=list)
    sql_guard_cases: list[SqlGuardCase] = Field(default_factory=list)
    preview_cases: list[PreviewCase] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_manifest_payload(self) -> "BenchmarkManifest":
        if not self.dataset_id.strip():
            raise ValueError("dataset_id must not be blank")
        if not self.domain.strip():
            raise ValueError("domain must not be blank")
        _reject_raw_pii_payload(self.tables, f"{self.dataset_id}.tables")
        _reject_raw_pii_payload(self.files, f"{self.dataset_id}.files")
        _reject_raw_pii_payload(self.expected_semantic_findings, f"{self.dataset_id}.expected_semantic_findings")
        _reject_raw_pii_payload(self.must_block, f"{self.dataset_id}.must_block")
        _reject_raw_pii_payload(self.notes, f"{self.dataset_id}.notes")
        return self


class EvalResult(StrictEvalModel):
    run_id: str
    manifest_id: str | None = None
    dataset_id: str | None = None
    status: EvalCaseStatus = EvalCaseStatus.PASS
    case_results: list[EvalCaseResult] = Field(default_factory=list)
    passed_cases: int = Field(default=0, ge=0)
    failed_cases: int = Field(default=0, ge=0)
    skipped_cases: int = Field(default=0, ge=0)
    warned_cases: int = Field(default=0, ge=0)
    notes: list[str] = Field(default_factory=list)
    generated_at: str | None = None
    report_paths: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_result_payload(self) -> "EvalResult":
        if not self.run_id.strip():
            raise ValueError("run_id must not be blank")
        if self.manifest_id is not None and not self.manifest_id.strip():
            raise ValueError("manifest_id must not be blank when provided")
        if self.dataset_id is not None and not self.dataset_id.strip():
            raise ValueError("dataset_id must not be blank when provided")
        _reject_raw_pii_payload(self.notes, f"{self.run_id}.notes")
        _reject_raw_pii_payload(self.report_paths, f"{self.run_id}.report_paths")
        counts = {
            EvalCaseStatus.PASS: self.passed_cases,
            EvalCaseStatus.FAIL: self.failed_cases,
            EvalCaseStatus.SKIP: self.skipped_cases,
            EvalCaseStatus.WARN: self.warned_cases,
        }
        for status, count in counts.items():
            if count < 0:
                raise ValueError(f"{status.value} case count must not be negative")
        if self.case_results:
            observed = {
                EvalCaseStatus.PASS: 0,
                EvalCaseStatus.FAIL: 0,
                EvalCaseStatus.SKIP: 0,
                EvalCaseStatus.WARN: 0,
            }
            for case_result in self.case_results:
                observed[case_result.status] += 1
            if observed[EvalCaseStatus.PASS] != self.passed_cases:
                raise ValueError("passed_cases must match case_results")
            if observed[EvalCaseStatus.FAIL] != self.failed_cases:
                raise ValueError("failed_cases must match case_results")
            if observed[EvalCaseStatus.SKIP] != self.skipped_cases:
                raise ValueError("skipped_cases must match case_results")
            if observed[EvalCaseStatus.WARN] != self.warned_cases:
                raise ValueError("warned_cases must match case_results")
        return self


__all__ = [
    "BenchmarkManifest",
    "BuilderSafetyCase",
    "EvalCaseBase",
    "EvalCaseCategory",
    "EvalCaseResult",
    "EvalCaseStatus",
    "EvalResult",
    "EvalSeverity",
    "GoldenQuestionCase",
    "PreviewCase",
    "RedTeamCase",
    "RetrievalCase",
    "RuntimeCase",
    "SqlGuardCase",
    "StrictEvalModel",
]
