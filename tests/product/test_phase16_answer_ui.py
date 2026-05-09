from __future__ import annotations

from pathlib import Path

from semantic_registry.product.api import handle_product_api, post_product_answer


def test_product_answer_returns_ui_ready_side_by_side_model() -> None:
    view = post_product_answer({"question": "월별 신규 고객 순매출을 보여줘", "role": "marketing_analyst"})
    assert view["mode"] == "C_QUERY_RUNTIME"
    assert view["baseline_sql_panel"]["not_executed"] is True
    assert "users.created_at" in view["baseline_sql_panel"]["sql"]
    assert view["system_sql_panel"]["execution_allowed"] is False
    assert "users.first_paid_at" in view["system_sql_panel"]["sql"]
    assert view["verification_panel"]["execution_allowed"] is False
    assert view["execution_allowed"] is False
    assert view["difference_summary_panel"]["items"]


def test_product_answer_pii_request_surfaces_failure_state() -> None:
    view = post_product_answer({"question": "사용자 이메일을 보여줘", "role": "marketing_analyst"})
    assert view["failure_state_panel"]["state"] == "pii_blocked"
    assert view["baseline_sql_panel"]["not_executed"] is True


def test_handle_product_api_routes_answer() -> None:
    view = handle_product_api("POST", "/api/product/answer", {"question": "월별 신규 고객 순매출을 보여줘"})
    assert view["space_id"] == "demo_company.revenue"


def test_static_ui_contains_required_pages_and_panels() -> None:
    html = Path("apps/product_ui/index.html").read_text(encoding="utf-8")
    for page in ["query-demo", "onboarding-status", "question-queue", "benchmark-evidence", "failure-review"]:
        assert page in html
    for panel in [
        "baseline-sql-panel",
        "system-sql-panel",
        "difference-summary-panel",
        "applied-definitions-panel",
        "verification-panel",
        "failure-state-panel",
        "preview-result-panel",
        "suggested-actions-panel",
    ]:
        assert panel in html
