"""Shared validation error codes and result models."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class ErrorSeverity(StrEnum):
    ERROR = "error"
    WARNING = "warning"


class ErrorCode(StrEnum):
    INVALID_YAML = "invalid_yaml"
    INVALID_MODEL = "invalid_model"
    DUPLICATE_ID = "duplicate_id"
    UNKNOWN_SPACE = "unknown_space"
    UNKNOWN_TABLE = "unknown_table"
    UNKNOWN_COLUMN = "unknown_column"
    UNKNOWN_METRIC = "unknown_metric"
    UNKNOWN_TERM = "unknown_term"
    UNKNOWN_POLICY_REF = "unknown_policy_ref"
    PII_RAW_VALUE_BLOCKED = "pii_raw_value_blocked"
    UNSAFE_VALUE_DICTIONARY = "unsafe_value_dictionary"
    INVALID_SQL_GUARD_CONTRACT = "invalid_sql_guard_contract"


class ValidationErrorDetail(BaseModel):
    """Machine-readable validation finding."""

    code: ErrorCode
    message: str
    path: str | None = None
    severity: ErrorSeverity = ErrorSeverity.ERROR
    context: dict[str, Any] = Field(default_factory=dict)


class ValidationResult(BaseModel):
    """Validation result shared by contracts, registry, and tests."""

    valid: bool
    errors: list[ValidationErrorDetail] = Field(default_factory=list)
    warnings: list[ValidationErrorDetail] = Field(default_factory=list)

    @classmethod
    def ok(cls) -> "ValidationResult":
        return cls(valid=True)

    @classmethod
    def from_errors(
        cls,
        errors: list[ValidationErrorDetail],
        warnings: list[ValidationErrorDetail] | None = None,
    ) -> "ValidationResult":
        warnings = warnings or []
        return cls(valid=not errors, errors=errors, warnings=warnings)
