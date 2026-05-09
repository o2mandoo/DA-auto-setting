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


def test_n8n_confirmation_workflow_is_comment_aware_reverse_question_demo() -> None:
    data = json.loads(Path("n8n/workflows/02_confirmation_pack_promotion.json").read_text(encoding="utf-8"))
    assert data["name"] == "02 Comment-aware Reverse Question Demo"
    assert "comment-aware reverse questions" in data["nodes"][1]["parameters"]["content"]
    assert "comment-aware reverse questions" in data["nodes"][2]["parameters"]["jsonBody"]


def test_n8n_templates_call_only_product_api_routes_and_no_credentials() -> None:
    required_routes = {
        "01_onboarding_demo.json": {"POST /api/onboarding/run"},
        "02_confirmation_pack_promotion.json": {
            "POST /api/confirmation/session",
            "POST /api/confirmation/answer",
            "POST /api/pack/promote",
        },
        "03_query_runtime_comparison_demo.json": {"POST /api/product/answer", "POST /api/product/compare-sql"},
        "04_20_domain_benchmark_runner.json": {"POST /api/eval/run"},
        "05_failure_review_loop.json": {"POST /api/product/answer — unsafe SQL", "POST /api/product/answer — missing context", "POST /api/product/answer — draft warning", "POST /api/failure-review/run"},
    }
    for path in Path("n8n/workflows").glob("*.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        text = path.read_text(encoding="utf-8")
        route_nodes = {
            node["name"]
            for node in data["nodes"]
            if isinstance(node, dict) and isinstance(node.get("name"), str) and node["name"].startswith("POST /api/")
        }
        expected = required_routes[path.name]
        assert expected.issubset(route_nodes)
        assert "{{$env.SDC_PRODUCT_API_BASE_URL}}" in text
        assert "{{$env.SDC_DEMO_KEY}}" in text
        assert "password" not in text.casefold()
        assert "postgres://" not in text.casefold()
        assert ("owner" + "@" + "example.com") not in text
        assert data["meta"]["semanticDataContext"]["noSilentFallback"] is True
        assert data["meta"]["semanticDataContext"]["noSqlRun"] is True
        assert data["meta"]["semanticDataContext"]["route"] in {"/api/onboarding/run", "/api/confirmation/session", "/api/product/answer", "/api/eval/run", "/api/failure-review/run"}


def test_comment_aware_and_failure_safe_demos_are_explicit() -> None:
    confirmation = json.loads(Path("n8n/workflows/02_confirmation_pack_promotion.json").read_text(encoding="utf-8"))
    failure_safe = json.loads(Path("n8n/workflows/05_failure_review_loop.json").read_text(encoding="utf-8"))

    confirmation_note = next(node for node in confirmation["nodes"] if node["name"] == "Safety Gate Note")
    assert "reverse questions" in confirmation_note["parameters"]["content"]
    assert "promotion" in confirmation_note["parameters"]["content"]

    confirmation_routes = {node["name"] for node in confirmation["nodes"] if node["name"].startswith("POST /api/")}
    assert "POST /api/confirmation/answer" in confirmation_routes
    assert "POST /api/pack/promote" in confirmation_routes

    failure_note = next(node for node in failure_safe["nodes"] if node["name"] == "Safety Gate Note")
    assert "blocked SQL" in failure_note["parameters"]["content"]
    assert "PII blocking" in failure_note["parameters"]["content"]
    assert "visible failure states" in failure_note["parameters"]["content"]
    failure_routes = {node["name"] for node in failure_safe["nodes"] if node["name"].startswith("POST /api/")}
    assert "POST /api/product/answer — unsafe SQL" in failure_routes
    assert "POST /api/product/answer — missing context" in failure_routes
    assert "POST /api/product/answer — draft warning" in failure_routes
    assert "POST /api/failure-review/run" in failure_routes
    assert any(
        "visible_failure_states" in node.get("parameters", {}).get("jsonBody", "")
        for node in failure_safe["nodes"]
    )


def test_n8n_templates_do_not_include_direct_sql_connector_nodes() -> None:
    forbidden_node_types = {
        "n8n-nodes-base.postgres",
        "n8n-nodes-base.mysql",
        "n8n-nodes-base.mssql",
        "n8n-nodes-base.sqlite",
        "n8n-nodes-base.mariadb",
        "n8n-nodes-base.oracledb",
        "n8n-nodes-base.snowflake",
    }
    for path in Path("n8n/workflows").glob("*.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        node_types = {node.get("type") for node in data.get("nodes", [])}
        assert node_types.isdisjoint(forbidden_node_types)

def test_query_runtime_comparison_workflow_stays_on_product_api() -> None:
    data = json.loads(Path("n8n/workflows/03_query_runtime_comparison_demo.json").read_text(encoding="utf-8"))
    safety_note = next(
        node["parameters"]["content"]
        for node in data["nodes"]
        if node["type"] == "n8n-nodes-base.stickyNote"
    )
    assert "baseline not_executed" in safety_note
    assert "failure state" in safety_note
    assert "Do not run SQL directly" in safety_note
    assert data["meta"]["semanticDataContext"]["route"] == "/api/product/answer"
    assert data["meta"]["semanticDataContext"]["noSqlRun"] is True


def test_n8n_readme_documents_safety_boundary() -> None:
    text = Path("n8n/README.md").read_text(encoding="utf-8")
    assert "no credentials" in text
    assert "hidden substitute" in text
