from __future__ import annotations

from semantic_registry.product.baseline import generate_baseline_sql
from semantic_registry.product.comparison import compare_baseline_vs_system_sql, profile_sql
from semantic_registry.query_planner import load_space_packs

SYSTEM_SQL = """SELECT DATE_TRUNC('month', users.first_paid_at) AS month,
       SUM(payments.amount - payments.refund_amount - payments.discount_amount) AS net_revenue
FROM users
JOIN payments ON users.user_id = payments.user_id
WHERE users.first_paid_at >= {start_date}
  AND users.first_paid_at < {end_date}
  AND payments.status = 'PAID'
GROUP BY 1"""


def test_comparison_detects_wrong_date_and_metric_basis() -> None:
    baseline = generate_baseline_sql("월별 신규 고객 순매출을 보여줘").candidate.generated_sql
    result = compare_baseline_vs_system_sql("월별 신규 고객 순매출을 보여줘", baseline, SYSTEM_SQL)
    categories = {item.category for item in result.differences}

    assert "wrong_date_basis" in categories
    assert "wrong_metric_basis" in categories
    assert result.semantic_coverage.score >= 0.75
    assert result.execution_allowed is False
    assert result.baseline_profile.not_executed is True


def test_profiler_blocks_pii_and_unsafe_sql() -> None:
    packs = load_space_packs("demo_company.revenue")
    pii = profile_sql("SELECT users.email FROM users", packs=packs, role="marketing_analyst", candidate_name="baseline")
    assert "users.email" in pii.pii_columns
    assert any("blocked_pii_column" in violation for violation in pii.policy_violations)

    unsafe = profile_sql("SELECT * FROM users; DROP TABLE users;", packs=packs, role="marketing_analyst", candidate_name="baseline")
    assert "multi_statement" in unsafe.safety_violations


def test_missing_system_sql_becomes_explicit_product_state() -> None:
    baseline = "SELECT SUM(payments.amount) AS revenue FROM payments"
    result = compare_baseline_vs_system_sql("매출 보여줘", baseline, None)
    assert any(item.category == "system_sql_not_available" for item in result.differences)
    assert result.recommendation.decision == "ask_or_enrich_context"
