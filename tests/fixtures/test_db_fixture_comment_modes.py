from __future__ import annotations

import pytest

from experiments.db_fixtures.scripts.fixture_modes import FixtureCommentMode, TEST_ONLY_MARKER, build_fixture_table_plan, fixture_mode_summary
from experiments.db_fixtures.scripts.mysql_fixture_loader import assert_mysql_fixture_environment, build_mysql_sql_plan
from experiments.db_fixtures.scripts.postgres_fixture_loader import (
    POSTGRES_DSN_ENV,
    assert_fixture_environment,
    build_postgres_sql_plan,
    load_postgres_fixture,
    load_postgres_fixture_from_env,
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


def test_fixture_modes_distinguish_no_real_and_synthetic_comments() -> None:
    no_comments = build_fixture_table_plan(dataset_id="d", schema_name="semantic_fixture_demo", table_name="orders", columns=["status"], mode=FixtureCommentMode.NO_COMMENTS)
    real_comments = build_fixture_table_plan(dataset_id="d", schema_name="semantic_fixture_demo", table_name="orders", columns=["status"], mode=FixtureCommentMode.REAL_COMMENTS, real_comments={"table": "Real orders", "columns": {"status": "Real lifecycle state"}})
    synthetic = build_fixture_table_plan(dataset_id="d", schema_name="semantic_fixture_demo", table_name="orders", columns=["status"], mode=FixtureCommentMode.SYNTHETIC_COMMENTS)
    assert no_comments.table_comment is None
    assert real_comments.table_comment == "Real orders"
    assert TEST_ONLY_MARKER in (synthetic.table_comment or "")
    assert "fixture-only" in (synthetic.table_comment or "")
    assert synthetic.column_comments
    assert all(TEST_ONLY_MARKER in comment for comment in synthetic.column_comments.values())
    assert all("fixture-only" in comment for comment in synthetic.column_comments.values())
    assert synthetic.is_test_only is True
    summary = fixture_mode_summary([no_comments, real_comments, synthetic])
    assert summary["fixture_only"] is True
    assert summary["not_product_runtime"] is True
    assert summary["synthetic_truth_blocked"] is True


def test_fixture_mode_summary_requires_test_only_marker_on_all_synthetic_comments() -> None:
    synthetic_with_unmarked_column = build_fixture_table_plan(
        dataset_id="d",
        schema_name="semantic_fixture_demo",
        table_name="orders",
        columns=["status"],
        mode=FixtureCommentMode.SYNTHETIC_COMMENTS,
    )
    broken_plan = type(synthetic_with_unmarked_column)(
        schema_name=synthetic_with_unmarked_column.schema_name,
        table_name=synthetic_with_unmarked_column.table_name,
        columns=synthetic_with_unmarked_column.columns,
        mode=synthetic_with_unmarked_column.mode,
        table_comment=synthetic_with_unmarked_column.table_comment,
        column_comments={"status": "synthetic fixture meaning without marker"},
        is_test_only=True,
    )

    summary = fixture_mode_summary([broken_plan])

    assert summary["synthetic_truth_blocked"] is False


def test_real_comment_mode_without_manifest_does_not_use_synthetic_fallback() -> None:
    real_comments = build_fixture_table_plan(
        dataset_id="d",
        schema_name="semantic_fixture_demo",
        table_name="orders",
        columns=["status"],
        mode=FixtureCommentMode.REAL_COMMENTS,
    )
    assert real_comments.table_comment is None
    assert real_comments.column_comments == {}
    assert real_comments.is_test_only is False
    assert TEST_ONLY_MARKER not in str(real_comments.to_dict())


def test_fixture_modes_require_fixture_schema_prefix() -> None:
    with pytest.raises(ValueError, match="semantic_fixture_"):
        build_fixture_table_plan(
            dataset_id="d",
            schema_name="public",
            table_name="orders",
            columns=["status"],
            mode=FixtureCommentMode.NO_COMMENTS,
        )


def test_fixture_modes_require_at_least_one_column() -> None:
    with pytest.raises(ValueError, match="at least one column"):
        build_fixture_table_plan(
            dataset_id="d",
            schema_name="semantic_fixture_demo",
            table_name="orders",
            columns=[],
            mode=FixtureCommentMode.NO_COMMENTS,
        )


def test_postgres_fixture_safety_rejects_production_and_requires_env() -> None:
    unsafe = assert_fixture_environment(dsn="postgresql://prod.example.com/warehouse", schema_name="public", env={})
    assert unsafe.safe is False
    assert any("SEMANTIC_CONTEXT_FIXTURE_DB" in reason for reason in unsafe.reasons)
    assert any("production" in reason for reason in unsafe.reasons)

    safe = assert_fixture_environment(dsn="postgresql://localhost/semantic_fixture_lab", schema_name="semantic_fixture_demo", env={"SEMANTIC_CONTEXT_FIXTURE_DB": "1"})
    assert safe.safe is True

    unsupported = assert_fixture_environment(dsn="mysql://localhost/semantic_fixture_lab", schema_name="semantic_fixture_demo", env={"SEMANTIC_CONTEXT_FIXTURE_DB": "1"})
    assert unsupported.safe is False
    assert any("only PostgreSQL" in reason for reason in unsupported.reasons)


def test_postgres_sql_plan_applies_synthetic_comments_only_when_selected() -> None:
    synthetic = build_fixture_table_plan(dataset_id="d", schema_name="semantic_fixture_demo", table_name="orders", columns=["status"], mode="synthetic_comments")
    plan = build_postgres_sql_plan(synthetic, rows=[{"status": "PAID"}])
    text = "\n".join(plan.statements)
    assert "COMMENT ON TABLE" in text
    assert TEST_ONLY_MARKER in text
    assert 'INSERT INTO "semantic_fixture_demo"."orders"' in text
    assert plan.mode == "synthetic_comments"
    assert plan.backend == "postgres"
    assert plan.row_count == 1


def test_postgres_sql_plan_uses_real_comments_without_test_only_marker() -> None:
    real_comments = build_fixture_table_plan(
        dataset_id="d",
        schema_name="semantic_fixture_demo",
        table_name="orders",
        columns=["status"],
        mode="real_comments",
        real_comments={"table": "Bob's orders", "columns": {"status": "Customer's lifecycle state"}},
    )
    plan = build_postgres_sql_plan(real_comments)
    text = "\n".join(plan.statements)
    assert "COMMENT ON TABLE" in text
    assert "COMMENT ON COLUMN" in text
    assert "Bob''s orders" in text
    assert "Customer''s lifecycle state" in text
    assert TEST_ONLY_MARKER not in text
    assert plan.mode == "real_comments"


def test_postgres_sql_plan_has_no_comment_statements_for_no_comments_mode() -> None:
    no_comments = build_fixture_table_plan(dataset_id="d", schema_name="semantic_fixture_demo", table_name="orders", columns=["status"], mode="no_comments")
    plan = build_postgres_sql_plan(no_comments)
    text = "\n".join(plan.statements)
    assert "COMMENT ON TABLE" not in text
    assert "COMMENT ON COLUMN" not in text
    assert plan.mode == "no_comments"


def test_postgres_live_loader_reports_missing_env_as_pending_not_fallback() -> None:
    fixture_plan = build_fixture_table_plan(
        dataset_id="d",
        schema_name="semantic_fixture_demo",
        table_name="orders",
        columns=["status"],
        mode="no_comments",
    )

    status = load_postgres_fixture_from_env(fixture_plan, env={"SEMANTIC_CONTEXT_FIXTURE_DB": "1"})

    assert status.backend == "postgres"
    assert status.status == "pending"
    assert status.attempted is False
    assert any(POSTGRES_DSN_ENV in reason for reason in status.reasons)
    assert any("no fallback backend" in reason for reason in status.reasons)


def test_postgres_live_loader_executes_only_when_local_gate_passes() -> None:
    fixture_plan = build_fixture_table_plan(
        dataset_id="d",
        schema_name="semantic_fixture_demo",
        table_name="orders",
        columns=["status"],
        mode="no_comments",
    )
    connection = _FakeConnection()

    status = load_postgres_fixture(
        dsn="postgresql://localhost/semantic_fixture_lab",
        fixture_plan=fixture_plan,
        rows=[{"status": "PAID"}],
        env={"SEMANTIC_CONTEXT_FIXTURE_DB": "1"},
        connection_factory=lambda _dsn: connection,
    )

    assert status.status == "loaded"
    assert status.attempted is True
    assert status.safe is True
    assert status.executed_statement_count == len(connection.cursor_obj.statements)
    assert connection.committed is True
    assert connection.closed is True
    assert all("mysql" not in statement.lower() for statement in connection.cursor_obj.statements)


def test_mysql_fixture_safety_requires_local_semantic_fixture_database_and_env() -> None:
    unsafe = assert_mysql_fixture_environment(
        dsn="mysql://prod.example.com/warehouse",
        schema_name="warehouse",
        env={},
    )
    assert unsafe.safe is False
    assert any("SEMANTIC_CONTEXT_FIXTURE_DB" in reason for reason in unsafe.reasons)
    assert any(("schema_name" in reason or "database name" in reason) for reason in unsafe.reasons)
    assert any("host must be local" in reason for reason in unsafe.reasons)
    assert any("production" in reason for reason in unsafe.reasons)

    safe = assert_mysql_fixture_environment(
        dsn="mysql://localhost/semantic_fixture_lab",
        schema_name="semantic_fixture_lab",
        env={"SEMANTIC_CONTEXT_FIXTURE_DB": "1"},
    )
    assert safe.safe is True

    wrong_backend = assert_mysql_fixture_environment(
        dsn="postgresql://localhost/semantic_fixture_lab",
        schema_name="semantic_fixture_lab",
        env={"SEMANTIC_CONTEXT_FIXTURE_DB": "1"},
    )
    assert wrong_backend.safe is False
    assert any("only MySQL" in reason for reason in wrong_backend.reasons)


def test_mysql_sql_plan_uses_mysql_comment_syntax_without_postgres_fallback() -> None:
    synthetic = build_fixture_table_plan(
        dataset_id="d",
        schema_name="semantic_fixture_demo",
        table_name="orders",
        columns=["status", "amount"],
        mode="synthetic_comments",
    )
    plan = build_mysql_sql_plan(synthetic, rows=[{"status": "PAID", "amount": "10"}])
    text = "\n".join(plan.statements)
    assert "CREATE DATABASE IF NOT EXISTS `semantic_fixture_demo`;" in text
    assert "CREATE TABLE `semantic_fixture_demo`.`orders`" in text
    assert "COMMENT ON TABLE" not in text
    assert "COMMENT ON COLUMN" not in text
    assert " COMMENT 'TEST_ONLY_SYNTHETIC_METADATA" in text
    assert " COMMENT='TEST_ONLY_SYNTHETIC_METADATA" in text
    assert plan.backend == "mysql"
    assert plan.mode == "synthetic_comments"
    assert plan.row_count == 1
