from __future__ import annotations

import json
from pathlib import Path


def test_n8n_templates_exist_for_five_workflows() -> None:
    paths = sorted(Path("n8n/workflows").glob("*.json"))
    assert len(paths) == 5
    assert {path.name for path in paths} == {
        "01_onboarding_demo.json",
        "02_confirmation_pack_promotion.json",
        "03_query_runtime_comparison_demo.json",
        "04_20_domain_benchmark_runner.json",
        "05_failure_review_loop.json",
    }


def test_n8n_templates_call_only_product_api_routes_and_no_credentials() -> None:
    allowed_routes = {
        "/api/onboarding/run",
        "/api/confirmation/session",
        "/api/product/answer",
        "/api/eval/run",
        "/api/failure-review/run",
    }
    for path in Path("n8n/workflows").glob("*.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        text = path.read_text(encoding="utf-8")
        assert "{{$env.SDC_PRODUCT_API_BASE_URL}}" in text
        assert "{{$env.SDC_DEMO_KEY}}" in text
        assert "password" not in text.casefold()
        assert "postgres://" not in text.casefold()
        assert ("owner" + "@" + "example.com") not in text
        assert data["meta"]["semanticDataContext"]["noSilentFallback"] is True
        assert data["meta"]["semanticDataContext"]["noSqlRun"] is True
        assert data["meta"]["semanticDataContext"]["route"] in allowed_routes


def test_n8n_readme_documents_safety_boundary() -> None:
    text = Path("n8n/README.md").read_text(encoding="utf-8")
    assert "no credentials" in text
    assert "hidden substitute" in text
