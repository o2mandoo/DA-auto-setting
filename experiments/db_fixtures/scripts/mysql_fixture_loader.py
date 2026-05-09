"""MySQL fixture DDL/comment planner and optional local live loader.

This module is product-external. It prepares and optionally loads local MySQL
fixture schemas only. It never falls back to PostgreSQL, DuckDB, or SQLite when
MySQL is unavailable; missing gates, unsafe DSNs, and missing drivers are
reported as explicit status records.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import importlib
import os
from typing import Any, Callable, Mapping, Sequence
from urllib.parse import urlparse

from .fixture_modes import FixtureTablePlan


MYSQL_DSN_ENV = "SEMANTIC_CONTEXT_MYSQL_FIXTURE_DSN"
FIXTURE_GATE_ENV = "SEMANTIC_CONTEXT_FIXTURE_DB"


@dataclass(frozen=True)
class MySQLFixtureSafetyResult:
    safe: bool
    reasons: list[str]


@dataclass(frozen=True)
class MySQLFixtureSqlPlan:
    schema_name: str
    table_name: str
    statements: list[str]
    row_count: int = 0
    checksum: str | None = None
    mode: str = "no_comments"
    backend: str = "mysql"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MySQLLiveLoadStatus:
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


def assert_mysql_fixture_environment(
    *,
    dsn: str,
    schema_name: str | None = None,
    database_name: str | None = None,
    env: Mapping[str, str] | None = None,
) -> MySQLFixtureSafetyResult:
    """Return whether a MySQL fixture DSN is safe for optional live loading."""

    source_env = os.environ if env is None else env
    fixture_name = schema_name or database_name or ""
    reasons: list[str] = []
    if source_env.get(FIXTURE_GATE_ENV) != "1":
        reasons.append(f"{FIXTURE_GATE_ENV}=1 is required")
    if not fixture_name.startswith("semantic_fixture_"):
        reasons.append("database/schema name must start with semantic_fixture_*")
    parsed = urlparse(dsn)
    if parsed.scheme and parsed.scheme not in {"mysql", "mysql+pymysql"}:
        reasons.append(
            "only MySQL fixture DSNs are supported; no PostgreSQL/DuckDB/SQLite fallback"
        )
    host = parsed.hostname or ""
    database = (parsed.path or "").lstrip("/")
    if host and host not in {"localhost", "127.0.0.1", "::1", "host.docker.internal"}:
        reasons.append("fixture DSN host must be local")
    if any(
        token in dsn.casefold()
        for token in ("prod", "production", "warehouse", "analytics")
    ):
        reasons.append("production-looking DSNs are refused for fixture loading")
    if database and not database.startswith("semantic_fixture_"):
        reasons.append("database name should use semantic_fixture_* prefix for fixture safety")
    return MySQLFixtureSafetyResult(safe=not reasons, reasons=reasons)


def build_mysql_sql_plan(
    plan: FixtureTablePlan,
    rows: Sequence[Mapping[str, Any]] | None = None,
    *,
    reset: bool = True,
) -> MySQLFixtureSqlPlan:
    """Build MySQL-specific fixture DDL and optional INSERT statements."""

    fixture_rows = list(rows or [])
    statements = [f"CREATE DATABASE IF NOT EXISTS {_quote_identifier(plan.schema_name)};"]
    qualified = _qualified_name(plan.schema_name, plan.table_name)
    if reset:
        statements.append(f"DROP TABLE IF EXISTS {qualified};")
    column_defs = [_column_definition(column, plan.column_comments.get(column)) for column in plan.columns]
    if not column_defs:
        column_defs = ["`_empty` TEXT"]
    table_comment = f" COMMENT={sql_literal(plan.table_comment)}" if plan.table_comment else ""
    statements.append(f"CREATE TABLE {qualified} ({', '.join(column_defs)}){table_comment};")
    statements.extend(_insert_statements(plan, fixture_rows))
    return MySQLFixtureSqlPlan(
        schema_name=plan.schema_name,
        table_name=plan.table_name,
        statements=statements,
        row_count=len(fixture_rows),
        checksum=_checksum(fixture_rows),
        mode=plan.mode.value,
    )


def load_mysql_fixture_from_env(
    fixture_plan: FixtureTablePlan,
    rows: Sequence[Mapping[str, Any]] | None = None,
    *,
    env: Mapping[str, str] | None = None,
    connection_factory: ConnectionFactory | None = None,
) -> MySQLLiveLoadStatus:
    """Attempt the optional live MySQL fixture load using env-gated settings."""

    source_env = os.environ if env is None else env
    dsn = source_env.get(MYSQL_DSN_ENV, "").strip()
    if not dsn:
        return MySQLLiveLoadStatus(
            backend="mysql",
            status="pending",
            attempted=False,
            safe=False,
            reasons=[f"{MYSQL_DSN_ENV} is not set; no fallback backend was used"],
        )
    return load_mysql_fixture(
        dsn=dsn,
        fixture_plan=fixture_plan,
        rows=rows,
        env=source_env,
        connection_factory=connection_factory,
    )


def load_mysql_fixture(
    *,
    dsn: str,
    fixture_plan: FixtureTablePlan,
    rows: Sequence[Mapping[str, Any]] | None = None,
    env: Mapping[str, str] | None = None,
    connection_factory: ConnectionFactory | None = None,
) -> MySQLLiveLoadStatus:
    """Safely execute the MySQL fixture plan when all local gates pass."""

    safety = assert_mysql_fixture_environment(
        dsn=dsn,
        schema_name=fixture_plan.schema_name,
        env=env,
    )
    plan = build_mysql_sql_plan(fixture_plan, rows)
    if not safety.safe:
        return MySQLLiveLoadStatus(
            backend="mysql",
            status="blocked",
            attempted=False,
            safe=False,
            reasons=safety.reasons,
            row_count=plan.row_count,
            plan_checksum=plan.checksum,
        )
    factory = connection_factory or _pymysql_connection_factory()
    if factory is None:
        return MySQLLiveLoadStatus(
            backend="mysql",
            status="pending",
            attempted=False,
            safe=True,
            reasons=["optional dependency 'pymysql' is not installed; no fallback backend was used"],
            row_count=plan.row_count,
            plan_checksum=plan.checksum,
        )
    connection = factory(dsn)
    executed = _execute_statements(connection, plan.statements)
    return MySQLLiveLoadStatus(
        backend="mysql",
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
    return "'" + str(value).replace("\\", "\\\\").replace("'", "''") + "'"


def _pymysql_connection_factory() -> ConnectionFactory | None:
    try:
        driver = importlib.import_module("pymysql")
    except ModuleNotFoundError:
        return None
    connect = getattr(driver, "connect", None)
    if not callable(connect):
        return None
    return connect


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


def _insert_statements(
    plan: FixtureTablePlan,
    rows: Sequence[Mapping[str, Any]],
) -> list[str]:
    if not rows:
        return []
    columns = list(plan.columns)
    column_sql = ", ".join(_quote_identifier(column) for column in columns)
    qualified = _qualified_name(plan.schema_name, plan.table_name)
    statements: list[str] = []
    for row in rows:
        values = ", ".join(sql_literal(row.get(column)) for column in columns)
        statements.append(f"INSERT INTO {qualified} ({column_sql}) VALUES ({values});")
    return statements


def _column_definition(column: str, comment: str | None) -> str:
    definition = f"{_quote_identifier(column)} TEXT"
    if comment:
        definition = f"{definition} COMMENT {sql_literal(comment)}"
    return definition


def _qualified_name(schema_name: str, table_name: str) -> str:
    return f"{_quote_identifier(schema_name)}.{_quote_identifier(table_name)}"


def _quote_identifier(value: str) -> str:
    escaped = value.replace("`", "``")
    return f"`{escaped}`"


def _checksum(rows: Sequence[Mapping[str, Any]]) -> str:
    digest = hashlib.sha256()
    for row in rows:
        digest.update(repr(sorted(row.items())).encode("utf-8"))
    return digest.hexdigest()[:16]


__all__ = [
    "FIXTURE_GATE_ENV",
    "MYSQL_DSN_ENV",
    "MySQLFixtureSafetyResult",
    "MySQLFixtureSqlPlan",
    "MySQLLiveLoadStatus",
    "assert_mysql_fixture_environment",
    "build_mysql_sql_plan",
    "load_mysql_fixture",
    "load_mysql_fixture_from_env",
]
