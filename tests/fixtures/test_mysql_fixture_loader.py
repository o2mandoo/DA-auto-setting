from __future__ import annotations

from experiments.db_fixtures.scripts.fixture_modes import build_fixture_table_plan
from experiments.db_fixtures.scripts.mysql_fixture_loader import (
    MYSQL_DSN_ENV,
    assert_mysql_fixture_environment,
    build_mysql_sql_plan,
    load_mysql_fixture,
    load_mysql_fixture_from_env,
)


class _FakeCursor:
    def __init__(self) -> None:
        self.statements: list[str] = []
        self.closed = False

    def execute(self, statement: str) -> None:
        self.statements.append(statement)

    def close(self) -> None:
        self.closed = True


class _FakeConnection:
    def __init__(self) -> None:
        self.cursor_obj = _FakeCursor()
        self.committed = False
        self.closed = False

    def cursor(self) -> _FakeCursor:
        return self.cursor_obj

    def commit(self) -> None:
        self.committed = True

    def close(self) -> None:
        self.closed = True


def _plan():
    return build_fixture_table_plan(
        dataset_id="sales",
        schema_name="semantic_fixture_sales",
        table_name="orders",
        columns=["status", "amount"],
        mode="real_comments",
        real_comments={
            "table": "Real order table",
            "columns": {"status": "Lifecycle status"},
        },
    )


def test_mysql_sql_plan_uses_mysql_ddl_and_comments() -> None:
    sql_plan = build_mysql_sql_plan(_plan(), rows=[{"status": "PAID", "amount": 10}])
    text = "\n".join(sql_plan.statements)

    assert sql_plan.backend == "mysql"
    assert "CREATE DATABASE IF NOT EXISTS `semantic_fixture_sales`" in text
    assert "CREATE TABLE `semantic_fixture_sales`.`orders`" in text
    assert "`status` TEXT COMMENT 'Lifecycle status'" in text
    assert "COMMENT='Real order table'" in text
    assert "INSERT INTO `semantic_fixture_sales`.`orders`" in text
    assert "COMMENT ON " not in text
    assert sql_plan.row_count == 1


def test_mysql_fixture_safety_rejects_non_mysql_without_fallback() -> None:
    result = assert_mysql_fixture_environment(
        dsn="postgresql://localhost/semantic_fixture_sales",
        schema_name="semantic_fixture_sales",
        env={"SEMANTIC_CONTEXT_FIXTURE_DB": "1"},
    )

    assert result.safe is False
    assert any("only MySQL fixture DSNs" in reason for reason in result.reasons)
    assert any("no PostgreSQL/DuckDB/SQLite fallback" in reason for reason in result.reasons)


def test_mysql_live_loader_reports_missing_env_as_pending_not_fallback() -> None:
    status = load_mysql_fixture_from_env(_plan(), env={"SEMANTIC_CONTEXT_FIXTURE_DB": "1"})

    assert status.backend == "mysql"
    assert status.status == "pending"
    assert status.attempted is False
    assert any(MYSQL_DSN_ENV in reason for reason in status.reasons)
    assert any("no fallback backend" in reason for reason in status.reasons)


def test_mysql_live_loader_executes_only_when_local_gate_passes() -> None:
    connection = _FakeConnection()
    status = load_mysql_fixture(
        dsn="mysql://localhost/semantic_fixture_sales",
        fixture_plan=_plan(),
        rows=[{"status": "PAID", "amount": 10}],
        env={"SEMANTIC_CONTEXT_FIXTURE_DB": "1"},
        connection_factory=lambda _dsn: connection,
    )

    assert status.status == "loaded"
    assert status.attempted is True
    assert status.safe is True
    assert status.executed_statement_count == len(connection.cursor_obj.statements)
    assert connection.committed is True
    assert connection.closed is True
    assert all("postgres" not in statement.lower() for statement in connection.cursor_obj.statements)

