from __future__ import annotations

from experiments.db_fixtures.scripts.fixture_modes import FixtureCommentMode, TEST_ONLY_MARKER, build_fixture_table_plan, fixture_mode_summary
from experiments.db_fixtures.scripts.postgres_fixture_loader import assert_fixture_environment, build_postgres_sql_plan


def test_fixture_modes_distinguish_no_real_and_synthetic_comments() -> None:
    no_comments = build_fixture_table_plan(dataset_id="d", schema_name="semantic_fixture_demo", table_name="orders", columns=["status"], mode=FixtureCommentMode.NO_COMMENTS)
    real_comments = build_fixture_table_plan(dataset_id="d", schema_name="semantic_fixture_demo", table_name="orders", columns=["status"], mode=FixtureCommentMode.REAL_COMMENTS, real_comments={"table": "Real orders", "columns": {"status": "Real lifecycle state"}})
    synthetic = build_fixture_table_plan(dataset_id="d", schema_name="semantic_fixture_demo", table_name="orders", columns=["status"], mode=FixtureCommentMode.SYNTHETIC_COMMENTS)
    assert no_comments.table_comment is None
    assert real_comments.table_comment == "Real orders"
    assert TEST_ONLY_MARKER in synthetic.table_comment
    assert synthetic.is_test_only is True
    summary = fixture_mode_summary([no_comments, real_comments, synthetic])
    assert summary["synthetic_truth_blocked"] is True


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
    assert plan.mode == "synthetic_comments"
    assert plan.row_count == 1


def test_postgres_sql_plan_has_no_comment_statements_for_no_comments_mode() -> None:
    no_comments = build_fixture_table_plan(dataset_id="d", schema_name="semantic_fixture_demo", table_name="orders", columns=["status"], mode="no_comments")
    plan = build_postgres_sql_plan(no_comments)
    text = "\n".join(plan.statements)
    assert "COMMENT ON TABLE" not in text
    assert "COMMENT ON COLUMN" not in text
    assert plan.mode == "no_comments"
