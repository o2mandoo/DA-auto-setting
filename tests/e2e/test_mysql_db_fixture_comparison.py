from __future__ import annotations

import pytest

from experiments.db_fixtures.scripts.fixture_modes import build_fixture_table_plan
from experiments.db_fixtures.scripts.mode_comparison import compare_comment_modes
from experiments.db_fixtures.scripts.mysql_fixture_loader import build_mysql_sql_plan


def test_mysql_comment_mode_comparison_is_explicit_mysql_not_postgres_fallback() -> None:
    comparisons = {
        item.mode: item
        for item in compare_comment_modes(
            dataset_id="sales",
            schema_name="semantic_fixture_sales",
            table_name="orders",
            columns=["status", "amount"],
            real_comments={"table": "Actual orders", "columns": {"status": "Lifecycle status"}},
            backend="mysql",
        )
    }

    assert {item.backend for item in comparisons.values()} == {"mysql"}
    assert comparisons["real_comments"].available is True
    assert comparisons["real_comments"].text2sql_context_available is True
    assert comparisons["real_comments"].sql_comment_statements == 2
    assert comparisons["synthetic_comments"].text2sql_context_available is False
    assert comparisons["synthetic_comments"].useful_metadata_coverage == 0
    assert "test_only_synthetic_metadata_excluded" in comparisons["synthetic_comments"].runtime_warnings


def test_mysql_planner_embeds_comments_in_create_table_only() -> None:
    plan = build_fixture_table_plan(
        dataset_id="sales",
        schema_name="semantic_fixture_sales",
        table_name="orders",
        columns=["status"],
        mode="real_comments",
        real_comments={"table": "Actual orders", "columns": {"status": "Lifecycle status"}},
    )

    sql_plan = build_mysql_sql_plan(plan)
    text = "\n".join(sql_plan.statements)

    assert sql_plan.backend == "mysql"
    assert "CREATE DATABASE IF NOT EXISTS `semantic_fixture_sales`;" in text
    assert "CREATE TABLE `semantic_fixture_sales`.`orders`" in text
    assert "`status` TEXT COMMENT 'Lifecycle status'" in text
    assert "COMMENT='Actual orders'" in text
    assert "COMMENT ON" not in text


def test_unsupported_fixture_backend_fails_instead_of_falling_back() -> None:
    with pytest.raises(ValueError, match="unsupported fixture backend"):
        compare_comment_modes(
            dataset_id="sales",
            schema_name="semantic_fixture_sales",
            table_name="orders",
            columns=["status"],
            backend="oracle",
        )
