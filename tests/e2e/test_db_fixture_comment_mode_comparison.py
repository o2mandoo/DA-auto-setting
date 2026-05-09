from __future__ import annotations

import pytest

from experiments.db_fixtures.scripts.mode_comparison import compare_comment_modes


@pytest.mark.parametrize("backend", ["postgres", "mysql"])
def test_comment_mode_comparison_shows_no_real_and_synthetic_differences(backend: str) -> None:
    comparisons = {
        item.mode: item
        for item in compare_comment_modes(
            dataset_id="sales",
            schema_name="semantic_fixture_sales",
            table_name="orders",
            columns=["status", "order_date", "updated_date", "amount", "cost", "customer_id"],
            real_comments={
                "table": "Actual order payments table",
                "columns": {"status": "Lifecycle status", "amount": "Paid amount"},
            },
            backend=backend,
        )
    }

    assert {item.backend for item in comparisons.values()} == {backend}

    no_comments = comparisons["no_comments"]
    real_comments = comparisons["real_comments"]
    synthetic_comments = comparisons["synthetic_comments"]

    assert no_comments.available is True
    assert no_comments.reverse_question_count > real_comments.reverse_question_count
    assert no_comments.text2sql_context_available is False
    assert "metadata_gap_not_context_truth" in no_comments.runtime_warnings

    assert real_comments.available is True
    assert real_comments.text2sql_context_available is True
    assert real_comments.useful_metadata_coverage > 0
    assert "comment_only_draft_context" in real_comments.runtime_warnings

    assert synthetic_comments.available is True
    assert synthetic_comments.text2sql_context_available is False
    assert synthetic_comments.useful_metadata_coverage == 0
    assert "test_only_synthetic_metadata_excluded" in synthetic_comments.runtime_warnings


@pytest.mark.parametrize("backend", ["postgres", "mysql"])
def test_real_comment_mode_missing_manifest_is_explicit_not_synthetic_fallback(backend: str) -> None:
    comparisons = {
        item.mode: item
        for item in compare_comment_modes(
            dataset_id="population",
            schema_name="semantic_fixture_population",
            table_name="population",
            columns=["region", "year", "count"],
            real_comments=None,
            backend=backend,
        )
    }

    real_comments = comparisons["real_comments"]
    assert real_comments.available is False
    assert real_comments.text2sql_context_available is False
    assert "real_comments_manifest_missing" in real_comments.runtime_warnings
    assert "no synthetic fallback was used" in real_comments.notes
