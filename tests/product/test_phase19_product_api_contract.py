from __future__ import annotations

from pathlib import Path

from semantic_registry.product.api import API_ENDPOINTS, handle_product_api


def test_all_required_product_api_routes_exist() -> None:
    required = {
        "POST /api/onboarding/run",
        "POST /api/confirmation/session",
        "POST /api/confirmation/answer",
        "POST /api/pack/promote",
        "POST /api/product/answer",
        "POST /api/product/compare-sql",
        "POST /api/eval/run",
        "POST /api/failure-review/run",
    }
    assert required.issubset(set(API_ENDPOINTS))


def test_product_api_answer_and_compare_routes_are_callable() -> None:
    answer = handle_product_api("POST", "/api/product/answer", {"question": "월별 신규 고객 순매출을 보여줘"})
    assert answer["execution_allowed"] is False
    assert answer["baseline_sql_panel"]["not_executed"] is True

    comparison = handle_product_api(
        "POST",
        "/api/product/compare-sql",
        {"question": "매출", "baseline_sql": "SELECT SUM(payments.amount) FROM payments", "system_sql": None},
    )
    assert comparison["execution_allowed"] is False
    assert comparison["baseline_profile"]["not_executed"] is True
    assert comparison["system_profile"]["not_executed"] is True


def test_product_api_compare_sql_surfaces_sql_guard_violations() -> None:
    comparison = handle_product_api(
        "POST",
        "/api/product/compare-sql",
        {
            "question": "마케팅용 사용자 이메일을 보여줘",
            "baseline_sql": "SELECT users.email FROM users",
            "system_sql": "SELECT users.first_paid_at FROM users",
        },
    )
    assert comparison["execution_allowed"] is False
    assert any(violation.startswith("blocked_pii_column:users.email") for violation in comparison["baseline_profile"]["policy_violations"])
    assert comparison["policy_score"]["baseline_policy_pass"] is False


def test_product_api_audit_redacts_raw_pii(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(Path.cwd())
    raw_email = "owner" + "@" + "example.com"
    response = handle_product_api(
        "POST",
        "/api/confirmation/answer",
        {"session_id": "s1", "question_id": "q1", "answer": f"contact {raw_email}", "reviewer": "data_steward"},
    )
    assert response["pack_mutated"] is False
    text = Path("runtime/product_api/audit.jsonl").read_text(encoding="utf-8")
    assert raw_email not in text
    assert "<redacted_email>" in text


def test_api_docs_and_examples_exist() -> None:
    assert Path("docs/api/PRODUCT_API.md").exists()
    assert Path("docs/api/OPENAPI_LIKE.yaml").exists()
    examples = {path.name for path in Path("docs/api/examples").glob("*.json")}
    assert {"product_answer_request.json", "compare_sql_request.json", "onboarding_run_request.json"}.issubset(examples)
