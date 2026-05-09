"""Validation-only SQL guard contract models for Phase 0."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class SqlCheckName(StrEnum):
    SELECT_ONLY = "select_only"
    MULTI_STATEMENT = "multi_statement"
    ALLOWED_TABLES = "allowed_tables"
    BLOCKED_COLUMNS = "blocked_columns"


class SqlCheckStatus(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    WARNING = "warning"
    NOT_APPLICABLE = "not_applicable"


class SqlGuardCheck(StrictModel):
    name: SqlCheckName
    status: SqlCheckStatus
    message: str | None = None


class SqlGuardRequest(StrictModel):
    space_id: str
    sql: str
    role: str | None = None
    allowed_tables: list[str] = Field(default_factory=list)
    blocked_columns: list[str] = Field(default_factory=list)


class SqlGuardResult(StrictModel):
    valid: bool
    execution_allowed: Literal[False] = False
    checks: dict[SqlCheckName, SqlCheckStatus]
    referenced_tables: list[str] = Field(default_factory=list)
    referenced_columns: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def valid_requires_no_failed_checks(self) -> "SqlGuardResult":
        failed = [name.value for name, status in self.checks.items() if status == SqlCheckStatus.FAIL]
        if self.valid and failed:
            raise ValueError(f"valid SQL guard result cannot contain failed checks: {failed}")
        if self.execution_allowed is not False:
            raise ValueError("Phase 0 SQL guard is validation-only and must never allow execution")
        return self
