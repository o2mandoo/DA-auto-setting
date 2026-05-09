"""PostgreSQL fixture DDL/comment planner and optional local live loader.

The functions here are product-external. They prepare local fixture schemas only,
refuse production-looking DSNs or non-fixture schema names, and never substitute
another backend when PostgreSQL is unavailable.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import importlib
import os
from typing import Any, Callable, Mapping, Sequence
from urllib.parse import urlparse

from .fixture_modes import FixtureTablePlan


POSTGRES_DSN_ENV = "SEMANTIC_CONTEXT_POSTGRES_FIXTURE_DSN"
FIXTURE_GATE_ENV = "SEMANTIC_CONTEXT_FIXTURE_DB"


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


@dataclass(frozen=True)
class PostgresLiveLoadStatus:
    backend: str
    status: str
    attempted: bool
    safe: bool
    reasons: list[str]
    executed_statement_count: int = 0
    row_count: int = 0
    plan_checksum: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


ConnectionFactory = Callable[[str], Any]


def assert_fixture_environment(
    *,
    dsn: str,
    schema_name: str,
    env: Mapping[str, str] | None = None,
) -> FixtureSafetyResult:
    source_env = os.environ if env is None else env
    reasons: list[str] = []
    if source_env.get(FIXTURE_GATE_ENV) != "1":
        reasons.append(f"{FIXTURE_GATE_ENV}=1 is required")
    if not schema_name.startswith("semantic_fixture_"):
        reasons.append("schema_name must start with semantic_fixture_*")
    parsed = urlparse(dsn)
    if parsed.scheme and parsed.scheme not in {"postgres", "postgresql"}:
        reasons.append("only PostgreSQL fixture DSNs are supported; no MySQL/DuckDB/SQLite fallback")
    host = parsed.hostname or ""
    database = (parsed.path or "").lstrip("/")
    if host and host not in {"localhost", "127.0.0.1", "::1", "host.docker.internal"}:
        reasons.append("fixture DSN host must be local unless explicitly implemented later")
    if any(token in dsn.casefold() for token in ("prod", "production", "warehouse", "analytics")):
        reasons.append("production-looking DSNs are refused for fixture loading")
    if database and not database.startswith("semantic_fixture_"):
        reasons.append("database name should use semantic_fixture_* prefix for fixture safety")
    return FixtureSafetyResult(safe=not reasons, reasons=reasons)


def build_postgres_sql_plan(
    plan: FixtureTablePlan,
    rows: Sequence[Mapping[str, Any]] | None = None,
    *,
    reset: bool = True,
) -> FixtureSqlPlan:
    fixture_rows = list(rows or [])
    statements = [f'CREATE SCHEMA IF NOT EXISTS "{plan.schema_name}";']
    if reset:
        statements.append(f'DROP TABLE IF EXISTS "{plan.schema_name}"."{plan.table_name}";')
    column_defs = ", ".join(f'"{column}" TEXT' for column in plan.columns) or '"_empty" TEXT'
    statements.append(f'CREATE TABLE "{plan.schema_name}"."{plan.table_name}" ({column_defs});')
    if plan.table_comment:
        statements.append(f'COMMENT ON TABLE "{plan.schema_name}"."{plan.table_name}" IS {sql_literal(plan.table_comment)};')
    for column, comment in sorted(plan.column_comments.items()):
        statements.append(f'COMMENT ON COLUMN "{plan.schema_name}"."{plan.table_name}"."{column}" IS {sql_literal(comment)};')
    statements.extend(_insert_statements(plan, fixture_rows))
    return FixtureSqlPlan(
        schema_name=plan.schema_name,
        table_name=plan.table_name,
        statements=statements,
        row_count=len(fixture_rows),
        checksum=_checksum(fixture_rows),
        mode=plan.mode.value,
        backend="postgres",
    )


def load_postgres_fixture_from_env(
    fixture_plan: FixtureTablePlan,
    rows: Sequence[Mapping[str, Any]] | None = None,
    *,
    env: Mapping[str, str] | None = None,
    connection_factory: ConnectionFactory | None = None,
) -> PostgresLiveLoadStatus:
    """Attempt optional live PostgreSQL fixture loading via env-gated settings."""

    source_env = os.environ if env is None else env
    dsn = source_env.get(POSTGRES_DSN_ENV, "").strip()
    if not dsn:
        return PostgresLiveLoadStatus(
            backend="postgres",
            status="pending",
            attempted=False,
            safe=False,
            reasons=[f"{POSTGRES_DSN_ENV} is not set; no fallback backend was used"],
        )
    return load_postgres_fixture(
        dsn=dsn,
        fixture_plan=fixture_plan,
        rows=rows,
        env=source_env,
        connection_factory=connection_factory,
    )


def load_postgres_fixture(
    *,
    dsn: str,
    fixture_plan: FixtureTablePlan,
    rows: Sequence[Mapping[str, Any]] | None = None,
    env: Mapping[str, str] | None = None,
    connection_factory: ConnectionFactory | None = None,
) -> PostgresLiveLoadStatus:
    """Safely execute the PostgreSQL fixture plan when all local gates pass."""

    safety = assert_fixture_environment(dsn=dsn, schema_name=fixture_plan.schema_name, env=env)
    plan = build_postgres_sql_plan(fixture_plan, rows)
    if not safety.safe:
        return PostgresLiveLoadStatus(
            backend="postgres",
            status="blocked",
            attempted=False,
            safe=False,
            reasons=safety.reasons,
            row_count=plan.row_count,
            plan_checksum=plan.checksum,
        )
    factory = connection_factory or _postgres_connection_factory()
    if factory is None:
        return PostgresLiveLoadStatus(
            backend="postgres",
            status="pending",
            attempted=False,
            safe=True,
            reasons=["optional dependency 'psycopg' or 'psycopg2' is not installed; no fallback backend was used"],
            row_count=plan.row_count,
            plan_checksum=plan.checksum,
        )
    connection = factory(dsn)
    executed = _execute_statements(connection, plan.statements)
    return PostgresLiveLoadStatus(
        backend="postgres",
        status="loaded",
        attempted=True,
        safe=True,
        reasons=[],
        executed_statement_count=executed,
        row_count=plan.row_count,
        plan_checksum=plan.checksum,
    )


def sql_literal(value: Any) -> str:
    if value is None:
        return "NULL"
    return "'" + str(value).replace("'", "''") + "'"


def _postgres_connection_factory() -> ConnectionFactory | None:
    for module_name in ("psycopg", "psycopg2"):
        try:
            driver = importlib.import_module(module_name)
        except ModuleNotFoundError:
            continue
        connect = getattr(driver, "connect", None)
        if callable(connect):
            return connect
    return None


def _execute_statements(connection: Any, statements: Sequence[str]) -> int:
    cursor = connection.cursor()
    executed = 0
    try:
        for statement in statements:
            cursor.execute(statement)
            executed += 1
        commit = getattr(connection, "commit", None)
        if callable(commit):
            commit()
    finally:
        close_cursor = getattr(cursor, "close", None)
        if callable(close_cursor):
            close_cursor()
        close_connection = getattr(connection, "close", None)
        if callable(close_connection):
            close_connection()
    return executed


def _insert_statements(plan: FixtureTablePlan, rows: Sequence[Mapping[str, Any]]) -> list[str]:
    if not rows:
        return []
    columns = list(plan.columns)
    column_sql = ", ".join(f'"{column}"' for column in columns)
    qualified = f'"{plan.schema_name}"."{plan.table_name}"'
    statements: list[str] = []
    for row in rows:
        values = ", ".join(sql_literal(row.get(column)) for column in columns)
        statements.append(f"INSERT INTO {qualified} ({column_sql}) VALUES ({values});")
    return statements


def _checksum(rows: Sequence[Mapping[str, Any]]) -> str:
    digest = hashlib.sha256()
    for row in rows:
        digest.update(repr(sorted(row.items())).encode("utf-8"))
    return digest.hexdigest()[:16]


__all__ = [
    "FIXTURE_GATE_ENV",
    "POSTGRES_DSN_ENV",
    "FixtureSafetyResult",
    "FixtureSqlPlan",
    "PostgresLiveLoadStatus",
    "assert_fixture_environment",
    "build_postgres_sql_plan",
    "load_postgres_fixture",
    "load_postgres_fixture_from_env",
]
