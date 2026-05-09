from __future__ import annotations

from experiments.db_fixtures.scripts.fixture_modes import (
    FixtureCommentMode,
    TEST_ONLY_MARKER,
    build_fixture_table_plan,
    fixture_mode_summary,
)
from experiments.db_fixtures.scripts.mode_comparison import compare_comment_modes
from experiments.db_fixtures.scripts.postgres_fixture_loader import assert_fixture_environment


def test_mysql_fixture_modes_preserve_comment_truth_boundaries() -> None:
    no_comments = build_fixture_table_plan(
        dataset_id="mysql_demo",
        schema_name="semantic_fixture_mysql",
        table_name="orders",
        columns=["status", "customer_email"],
        mode=FixtureCommentMode.NO_COMMENTS,
    )
    real_comments = build_fixture_table_plan(
        dataset_id="mysql_demo",
        schema_name="semantic_fixture_mysql",
        table_name="orders",
        columns=["status", "customer_email"],
        mode=FixtureCommentMode.REAL_COMMENTS,
        real_comments={
            "table": "Real MySQL order table comment",
            "columns": {"status": "Real MySQL lifecycle state"},
        },
    )
    synthetic = build_fixture_table_plan(
        dataset_id="mysql_demo",
        schema_name="semantic_fixture_mysql",
        table_name="orders",
        columns=["status", "customer_email"],
        mode=FixtureCommentMode.SYNTHETIC_COMMENTS,
    )

    assert no_comments.table_comment is None
    assert no_comments.column_comments == {}
    assert real_comments.table_comment == "Real MySQL order table comment"
    assert real_comments.column_comments == {"status": "Real MySQL lifecycle state"}
    assert real_comments.is_test_only is False
    assert TEST_ONLY_MARKER not in (real_comments.table_comment or "")
    assert TEST_ONLY_MARKER in (synthetic.table_comment or "")
    assert all(TEST_ONLY_MARKER in comment for comment in synthetic.column_comments.values())
    assert synthetic.is_test_only is True

    summary = fixture_mode_summary([no_comments, real_comments, synthetic])
    assert summary["fixture_only"] is True
    assert summary["not_product_runtime"] is True
    assert summary["synthetic_truth_blocked"] is True
    assert summary["modes"] == ["no_comments", "real_comments", "synthetic_comments"]


def test_mysql_fixture_comparison_does_not_promote_synthetic_comments_to_text2sql_context() -> None:
    comparisons = compare_comment_modes(
        dataset_id="mysql_demo",
        schema_name="semantic_fixture_mysql",
        table_name="orders",
        columns=["status", "customer_email"],
        real_comments={
            "table": "Real MySQL order table comment",
            "columns": {"status": "Real MySQL lifecycle state"},
        },
    )
    by_mode = {comparison.mode: comparison for comparison in comparisons}

    assert by_mode["real_comments"].available is True
    assert by_mode["real_comments"].text2sql_context_available is True
    assert by_mode["real_comments"].useful_metadata_coverage > 0
    assert "comment_only_draft_context" in by_mode["real_comments"].runtime_warnings

    assert by_mode["synthetic_comments"].available is True
    assert by_mode["synthetic_comments"].text2sql_context_available is False
    assert by_mode["synthetic_comments"].useful_metadata_coverage == 0.0
    assert "test_only_synthetic_metadata_excluded" in by_mode["synthetic_comments"].runtime_warnings
    assert any(TEST_ONLY_MARKER in note for note in by_mode["synthetic_comments"].notes)


def test_mysql_fixture_dsn_is_not_silently_routed_through_postgres_loader() -> None:
    result = assert_fixture_environment(
        dsn="mysql://localhost/semantic_fixture_lab",
        schema_name="semantic_fixture_mysql",
        env={"SEMANTIC_CONTEXT_FIXTURE_DB": "1"},
    )

    assert result.safe is False
    assert any("no MySQL/Oracle fake support" in reason for reason in result.reasons)
