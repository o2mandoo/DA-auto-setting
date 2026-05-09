from __future__ import annotations

from pathlib import Path

import pytest

from semantic_registry.product.baseline import (
    BaselineProviderConfigurationError,
    BaselineStore,
    generate_baseline_sql,
)


def test_baseline_generates_physical_schema_only_candidate(tmp_path: Path) -> None:
    result = generate_baseline_sql(
        "월별 신규 고객 순매출을 보여줘",
        provider_name="mock",
        store_root=tmp_path,
    )

    assert result.not_executed is True
    assert result.candidate.not_executed is True
    assert result.provider == "mock"
    assert "users.created_at" in result.candidate.generated_sql
    assert "payments.amount" in result.candidate.generated_sql
    assert "refund_amount" not in result.candidate.generated_sql
    forbidden = ["verified_query", "metric.net_revenue", "policy.", "value_dictionary", "reverse_question"]
    prompt_lower = result.prompt.casefold()
    assert not any(marker in prompt_lower for marker in forbidden)

    stored = BaselineStore(tmp_path).load()
    assert stored and stored[0]["candidate"]["not_executed"] is True


def test_baseline_surfaces_wrong_metric_and_date_risks() -> None:
    result = generate_baseline_sql("지난달 신규 고객 순매출", provider_name="mock")
    categories = {note.category for note in result.candidate.risk_notes}
    assert {"date_basis", "metric_basis"}.issubset(categories)


def test_baseline_can_surface_pii_risk_without_execution() -> None:
    result = generate_baseline_sql("마케팅용 사용자 이메일을 보여줘", provider_name="mock")
    assert "users.email" in result.candidate.generated_sql
    assert result.candidate.not_executed is True
    assert any(note.category == "pii" for note in result.candidate.risk_notes)


def test_explicit_local_provider_does_not_silently_fall_back() -> None:
    with pytest.raises(BaselineProviderConfigurationError, match="no fallback"):
        generate_baseline_sql("매출 보여줘", provider_name="local", provider_config={})
