"""PostgreSQL fixture DDL/comment planner for DB-backed experiments.

The functions here are product-external. They prepare local fixture schemas only
and refuse production-looking DSNs or non-fixture schema names.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
import hashlib
import os
from typing import Any, Mapping
from urllib.parse import urlparse

from .fixture_modes import FixtureTablePlan


@dataclass(frozen=True)
class FixtureSafetyResult:
    safe: bool
    reasons: list[str]


@dataclass(frozen=True)
class FixtureSqlPlan:
    schema_name: str
    table_name: str
    statements: list[str]
    row_count: int = 0
    checksum: str | None = None
    mode: str = "no_comments"
    backend: str = "postgres"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def assert_fixture_environment(*, dsn: str, schema_name: str, env: Mapping[str, str] | None = None) -> FixtureSafetyResult:
    source_env = os.environ if env is None else env
    reasons: list[str] = []
    if source_env.get("SEMANTIC_CONTEXT_FIXTURE_DB") != "1":
        reasons.append("SEMANTIC_CONTEXT_FIXTURE_DB=1 is required")
    if not schema_name.startswith("semantic_fixture_"):
        reasons.append("schema_name must start with semantic_fixture_*")
    parsed = urlparse(dsn)
    if parsed.scheme and parsed.scheme not in {"postgres", "postgresql"}:
        reasons.append("only PostgreSQL fixture DSNs are supported; no MySQL/Oracle fake support")
    host = parsed.hostname or ""
    database = (parsed.path or "").lstrip("/")
    if host and host not in {"localhost", "127.0.0.1", "::1", "host.docker.internal"}:
        reasons.append("fixture DSN host must be local unless explicitly implemented later")
    if any(token in dsn.casefold() for token in ("prod", "production", "warehouse", "analytics")):
        reasons.append("production-looking DSNs are refused for fixture loading")
    if database and not database.startswith("semantic_fixture_"):
        reasons.append("database name should use semantic_fixture_* prefix for fixture safety")
    return FixtureSafetyResult(safe=not reasons, reasons=reasons)


def build_postgres_sql_plan(plan: FixtureTablePlan, rows: list[Mapping[str, Any]] | None = None, *, reset: bool = True) -> FixtureSqlPlan:
    rows = list(rows or [])
    statements = [f'CREATE SCHEMA IF NOT EXISTS "{plan.schema_name}";']
    if reset:
        statements.append(f'DROP TABLE IF EXISTS "{plan.schema_name}"."{plan.table_name}";')
    column_defs = ", ".join(f'"{column}" TEXT' for column in plan.columns) or '"_empty" TEXT'
    statements.append(f'CREATE TABLE "{plan.schema_name}"."{plan.table_name}" ({column_defs});')
    if plan.table_comment:
        statements.append(f'COMMENT ON TABLE "{plan.schema_name}"."{plan.table_name}" IS {sql_literal(plan.table_comment)};')
    for column, comment in sorted(plan.column_comments.items()):
        statements.append(f'COMMENT ON COLUMN "{plan.schema_name}"."{plan.table_name}"."{column}" IS {sql_literal(comment)};')
    return FixtureSqlPlan(
        schema_name=plan.schema_name,
        table_name=plan.table_name,
        statements=statements,
        row_count=len(rows),
        checksum=_checksum(rows),
        mode=plan.mode.value,
        backend="postgres",
    )


def sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _checksum(rows: list[Mapping[str, Any]]) -> str:
    digest = hashlib.sha256()
    for row in rows:
        digest.update(repr(sorted(row.items())).encode("utf-8"))
    return digest.hexdigest()[:16]


__all__ = ["FixtureSafetyResult", "FixtureSqlPlan", "assert_fixture_environment", "build_postgres_sql_plan"]
