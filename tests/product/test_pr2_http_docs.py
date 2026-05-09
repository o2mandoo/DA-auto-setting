from __future__ import annotations

from pathlib import Path


def test_pr2_http_docs_cover_adapter_surface_and_safety() -> None:
    product_api = Path("docs/api/PRODUCT_API.md").read_text(encoding="utf-8")
    openapi_like = Path("docs/api/OPENAPI_LIKE.yaml").read_text(encoding="utf-8")

    for needle in [
        "transport-only",
        "python -m semantic_registry.product.http_adapter --check",
        "python -m semantic_registry.product.http_adapter",
        "/healthz",
        "/readyz",
        "/openapi.json",
        "correlation ID",
        "no `execute_query` route or handler",
        "credential-free",
    ]:
        assert needle in product_api

    for needle in [
        "/healthz",
        "/readyz",
        "/openapi.json",
        "CorrelationId",
        "TypedError",
        "X-Correlation-ID",
    ]:
        assert needle in openapi_like

    assert "execute_query" not in openapi_like


def test_pr2_http_docs_examples_remain_credential_free() -> None:
    examples = sorted(Path("docs/api/examples").glob("*.json"))
    assert examples

    combined = "\n".join(path.read_text(encoding="utf-8") for path in examples)
    for forbidden in [
        "password",
        "postgres://",
        "mysql://",
        "owner@example.com",
    ]:
        assert forbidden not in combined

    for required in [
        "question",
        "space_id",
        "baseline_sql",
        "scenario_set",
    ]:
        assert required in combined
