"""Contracts for Phase 9 safe preview execution payloads.

These schemas describe bounded local preview requests/results and audit records.
They do not authorize production SQL execution or external database access.
"""

from __future__ import annotations

from enum import StrEnum
import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class StrictExecutionModel(BaseModel):
    """Closed preview schemas keep MCP/Registry handoffs deterministic."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class PreviewExecutionTarget(StrEnum):
    """Allowed Phase 9 preview targets; production databases are intentionally absent."""

    LOCAL_FIXTURE = "local_fixture"
    SAFE_TEST_DB = "safe_test_db"


class PreviewStatus(StrEnum):
    ALLOWED = "allowed"
    BLOCKED = "blocked"
    FAILED = "failed"


class ExecutionError(StrictExecutionModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)
    recoverable: bool = False

    @field_validator("code", "message")
    @classmethod
    def required_text_not_blank(cls, value: str) -> str:
        return _require_non_blank(value)


class ExecutionPolicy(StrictExecutionModel):
    role: str | None = None
    allowed_tables: list[str] = Field(default_factory=list)
    blocked_columns: list[str] = Field(default_factory=list)
    max_preview_rows: int = Field(default=100, ge=1, le=1000)
    require_validation: Literal[True] = True
    allowed_targets: list[PreviewExecutionTarget] = Field(default_factory=lambda: [PreviewExecutionTarget.LOCAL_FIXTURE])
    # Safety boundary: these contracts cannot be used as production execution grants.
    allow_production_connections: Literal[False] = False

    @field_validator("role")
    @classmethod
    def optional_role_not_blank(cls, value: str | None) -> str | None:
        return _require_non_blank(value) if value is not None else None

    @field_validator("allowed_tables")
    @classmethod
    def normalize_allowed_tables(cls, values: list[str]) -> list[str]:
        return [_normalize_identifier(value, "allowed table") for value in values]

    @field_validator("blocked_columns")
    @classmethod
    def normalize_blocked_columns(cls, values: list[str]) -> list[str]:
        normalized = [_normalize_column_ref(value) for value in values]
        for column in normalized:
            if "." not in column:
                raise ValueError("blocked_columns must use table.column references")
        return normalized

    @model_validator(mode="after")
    def require_local_or_test_target(self) -> "ExecutionPolicy":
        if not self.allowed_targets:
            raise ValueError("ExecutionPolicy requires at least one safe preview target")
        if self.allow_production_connections is not False:
            raise ValueError("Production database connections are not allowed for safe preview")
        return self


class PreviewRequest(StrictExecutionModel):
    space_id: str
    sql: str
    role: str | None = None
    requested_limit: int | None = Field(default=None, ge=1, le=1000)
    execution_target: PreviewExecutionTarget = PreviewExecutionTarget.LOCAL_FIXTURE
    fixture_ref: str | None = None
    validation_id: str | None = None
    # Validation must happen before any adapter evaluates SQL; this flag remains false.
    execution_allowed: Literal[False] = False

    @field_validator("space_id", "sql")
    @classmethod
    def required_text_not_blank(cls, value: str) -> str:
        return _require_non_blank(value)

    @field_validator("role", "fixture_ref", "validation_id")
    @classmethod
    def optional_text_not_blank(cls, value: str | None) -> str | None:
        return _require_non_blank(value) if value is not None else None

    @model_validator(mode="after")
    def require_read_only_single_statement_shape(self) -> "PreviewRequest":
        # SQLGuard remains the authority; this model-level check prevents an
        # obviously unsafe preview request from entering the execution lane.
        literal_stripped = re.sub(r"'(?:''|[^'])*'|\"(?:\"\"|[^\"])*\"", "''", self.sql.strip())
        statements = [part.strip() for part in literal_stripped.split(";") if part.strip()]
        if len(statements) != 1 or not re.match(r"(?is)^\s*(select|with)\b", statements[0]):
            raise ValueError("PreviewRequest SQL must be one read-only SELECT/WITH statement")
        if self.execution_allowed is not False:
            raise ValueError("PreviewRequest must not grant execution authority")
        return self


class PreviewResult(StrictExecutionModel):
    request: PreviewRequest
    status: PreviewStatus
    columns: list[str] = Field(default_factory=list)
    rows: list[dict[str, Any]] = Field(default_factory=list)
    row_count: int = Field(default=0, ge=0)
    applied_limit: int = Field(default=0, ge=0, le=1000)
    truncated: bool = False
    errors: list[ExecutionError] = Field(default_factory=list)
    audit_id: str | None = None
    # Even successful preview is local fixture evaluation, not production query execution.
    execution_allowed: Literal[False] = False

    @model_validator(mode="after")
    def keep_blocked_results_empty_and_counts_consistent(self) -> "PreviewResult":
        if self.status != PreviewStatus.ALLOWED and (self.rows or self.columns or self.row_count):
            raise ValueError("Blocked or failed previews must not expose result rows")
        if self.status == PreviewStatus.ALLOWED and self.errors:
            raise ValueError("Allowed preview results must not include execution errors")
        if self.row_count != len(self.rows):
            raise ValueError("row_count must match the number of preview rows returned")
        if self.execution_allowed is not False:
            raise ValueError("PreviewResult must not grant production execution authority")
        return self


class QueryAuditRecord(StrictExecutionModel):
    audit_id: str
    request: PreviewRequest
    policy: ExecutionPolicy
    status: PreviewStatus
    guard_valid: bool
    preview_allowed: bool
    row_count: int = Field(default=0, ge=0)
    errors: list[ExecutionError] = Field(default_factory=list)
    created_at: str | None = None
    # Audit records describe what happened; they never become execution grants.
    execution_allowed: Literal[False] = False

    @field_validator("audit_id")
    @classmethod
    def audit_id_not_blank(cls, value: str) -> str:
        return _require_non_blank(value)

    @model_validator(mode="after")
    def require_consistent_status(self) -> "QueryAuditRecord":
        if self.preview_allowed != (self.status == PreviewStatus.ALLOWED):
            raise ValueError("preview_allowed must match allowed audit status")
        if self.status != PreviewStatus.ALLOWED and self.row_count:
            raise ValueError("Blocked or failed audit records must not count preview rows")
        if self.execution_allowed is not False:
            raise ValueError("QueryAuditRecord must not grant execution authority")
        return self


def _require_non_blank(value: str) -> str:
    if not value or not value.strip():
        raise ValueError("required string must not be blank")
    return value.strip()


def _normalize_identifier(value: str, label: str) -> str:
    normalized = _require_non_blank(value).strip('"`[]').casefold()
    if not re.match(r"^[a-z_][a-z0-9_]*$", normalized):
        raise ValueError(f"{label} must be a simple identifier")
    return normalized


def _normalize_column_ref(value: str) -> str:
    parts = [_normalize_identifier(part, "blocked column") for part in _require_non_blank(value).split(".")]
    return ".".join(parts)


__all__ = [
    "ExecutionError",
    "ExecutionPolicy",
    "PreviewExecutionTarget",
    "PreviewRequest",
    "PreviewResult",
    "PreviewStatus",
    "QueryAuditRecord",
    "StrictExecutionModel",
]
