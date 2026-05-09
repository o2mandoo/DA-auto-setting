"""MySQL fixture DDL/comment planner for DB-backed experiments.

The functions here are product-external. They prepare local fixture databases
only and refuse production-looking DSNs or non-fixture database/schema names.
They do not implement an Oracle path and they do not fall back to PostgreSQL.
"""

from __future__ import annotations

import os
from typing import Mapping
from urllib.parse import urlparse

from .fixture_modes import FixtureTablePlan
from .postgres_fixture_loader import FixtureSafetyResult, FixtureSqlPlan, sql_literal


_ALLOWED_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "host.docker.internal"}
_PRODUCTION_TOKENS = ("prod", "production", "warehouse", "analytics")


def assert_mysql_fixture_environment(*, dsn: str, database_name: str, env: Mapping[str, str] | None = None) -> FixtureSafetyResult:
    """Return whether a live MySQL fixture load is allowed.

    The gate is intentionally strict because fixture DDL can create/drop local
    objects. It requires the explicit fixture env flag, a local host, a
    ``semantic_fixture_*`` database/schema name, a MySQL DSN, and no production-
    looking DSN tokens.
    """

    source_env = os.environ if env is None else env
    reasons: list[str] = []
    if source_env.get("SEMANTIC_CONTEXT_FIXTURE_DB") != "1":
        reasons.append("SEMANTIC_CONTEXT_FIXTURE_DB=1 is required")
    if not database_name.startswith("semantic_fixture_"):
        reasons.append("database/schema name must start with semantic_fixture_*")
    parsed = urlparse(dsn)
    if parsed.scheme and parsed.scheme not in {"mysql", "mysql+pymysql"}:
        reasons.append("only MySQL fixture DSNs are supported by the MySQL fixture planner")
    host = parsed.hostname or ""
    dsn_database = (parsed.path or "").lstrip("/")
    if host and host not in _ALLOWED_LOCAL_HOSTS:
        reasons.append("fixture DSN host must be local")
    if dsn_database and not dsn_database.startswith("semantic_fixture_"):
        reasons.append("DSN database name must start with semantic_fixture_*")
    if any(token in dsn.casefold() for token in _PRODUCTION_TOKENS):
        reasons.append("production-looking DSNs are refused for fixture loading")
    return FixtureSafetyResult(safe=not reasons, reasons=reasons)


def build_mysql_sql_plan(plan: FixtureTablePlan, rows: list[Mapping[str, object]] | None = None, *, reset: bool = True) -> FixtureSqlPlan:
    """Build MySQL-specific DDL for one fixture table.

    MySQL comments are embedded in ``CREATE TABLE`` using table ``COMMENT`` and
    per-column ``COMMENT`` clauses. This differs intentionally from PostgreSQL's
    ``COMMENT ON`` statements so backend requests cannot silently fall back.
    """

    rows = list(rows or [])
    database_name = plan.schema_name
    statements = [f"CREATE DATABASE IF NOT EXISTS {_mysql_identifier(database_name)};"]
    qualified_table = f"{_mysql_identifier(database_name)}.{_mysql_identifier(plan.table_name)}"
    if reset:
        statements.append(f"DROP TABLE IF EXISTS {qualified_table};")
    column_defs = ", ".join(_mysql_column_definition(column, plan.column_comments.get(column)) for column in plan.columns)
    if not column_defs:
        column_defs = "`_empty` TEXT"
    table_comment = f" COMMENT={sql_literal(plan.table_comment)}" if plan.table_comment else ""
    statements.append(f"CREATE TABLE {qualified_table} ({column_defs}){table_comment};")
    return FixtureSqlPlan(
        schema_name=plan.schema_name,
        table_name=plan.table_name,
        statements=statements,
        row_count=len(rows),
        checksum=_checksum(rows),
        mode=plan.mode.value,
        backend="mysql",
    )


def _mysql_column_definition(column: str, comment: str | None) -> str:
    suffix = f" COMMENT {sql_literal(comment)}" if comment else ""
    return f"{_mysql_identifier(column)} TEXT{suffix}"


def _mysql_identifier(value: str) -> str:
    return "`" + value.replace("`", "``") + "`"


def _checksum(rows: list[Mapping[str, object]]) -> str:
    # Keep the checksum algorithm aligned with the PostgreSQL planner without
    # importing its private helper.
    import hashlib

    digest = hashlib.sha256()
    for row in rows:
        digest.update(repr(sorted(row.items())).encode("utf-8"))
    return digest.hexdigest()[:16]


__all__ = ["assert_mysql_fixture_environment", "build_mysql_sql_plan"]
