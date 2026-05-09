from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from semantic_registry.product.http_adapter import (
    AUDIT_FILENAME,
    CORRELATION_HEADER,
    build_healthz_response,
    build_openapi_response,
    build_readyz_response,
    handle_http_request,
    inspect_readiness,
    run_check,
)


def test_healthz_is_process_only_and_sets_correlation_header() -> None:
    response = build_healthz_response(correlation_id="corr-1")
    assert response.status_code == 200
    assert response.headers[CORRELATION_HEADER] == "corr-1"
    assert response.body["ok"] is True
    assert response.body["data"]["status"] == "healthy"
    assert response.body["data"]["execution_allowed"] is False


def test_readyz_reports_pack_root_readiness() -> None:
    ready = build_readyz_response(pack_root=Path("semantic_packs"), correlation_id="corr-ready")
    assert ready.status_code == 200
    assert ready.body["ok"] is True
    assert ready.body["data"]["ready"] is True
    assert ready.body["data"]["pack_count"] > 0
    assert "demo_company.revenue" in ready.body["data"]["pack_ids"]


def test_readyz_surfaces_missing_pack_root_explicitly(tmp_path: Path) -> None:
    missing = build_readyz_response(pack_root=tmp_path / "missing", correlation_id="corr-missing")
    assert missing.status_code == 503
    assert missing.body["ok"] is False
    assert missing.body["error"]["code"] == "pack_root_missing"
    assert missing.body["error"]["details"]["pack_root"].endswith("missing")


def test_openapi_includes_current_routes_and_no_execute_route() -> None:
    response = build_openapi_response(correlation_id="corr-openapi")
    assert response.status_code == 200
    paths = response.body["data"]["paths"]
    assert "/healthz" in paths
    assert "/readyz" in paths
    assert "/openapi.json" in paths
    assert "/api/product/answer" in paths
    assert "/api/product/compare-sql" in paths
    assert "execute_query" not in json.dumps(paths)
    assert response.body["data"]["x-execution-allowed"] is False


def test_product_route_delegates_and_writes_audit(tmp_path: Path) -> None:
    response = handle_http_request(
        "POST",
        "/api/product/answer",
        {"question": "월별 신규 고객 순매출을 보여줘", "role": "marketing_analyst"},
        pack_root=Path("semantic_packs"),
        audit_root=tmp_path,
        correlation_id="corr-answer",
    )
    assert response.status_code == 200
    assert response.headers[CORRELATION_HEADER] == "corr-answer"
    assert response.body["ok"] is True
    assert response.body["data"]["execution_allowed"] is False

    audit_text = (tmp_path / AUDIT_FILENAME).read_text(encoding="utf-8")
    assert "corr-answer" in audit_text
    assert "execute_query" not in audit_text


def test_unknown_route_is_typed_404(tmp_path: Path) -> None:
    response = handle_http_request("POST", "/api/not-a-route", {}, pack_root=Path("semantic_packs"), audit_root=tmp_path)
    assert response.status_code == 404
    assert response.body["error"]["code"] == "route_not_found"
    assert response.headers[CORRELATION_HEADER]


def test_validation_error_is_typed_400(tmp_path: Path) -> None:
    response = handle_http_request("POST", "/api/product/answer", {"role": "marketing_analyst"}, pack_root=Path("semantic_packs"), audit_root=tmp_path)
    assert response.status_code == 400
    assert response.body["error"]["code"] == "validation_error"
    assert "question is required" in response.body["error"]["message"]


def test_http_adapter_check_smoke_runs(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "semantic_registry.product.http_adapter",
            "--check",
            "--pack-root",
            "semantic_packs",
            "--audit-root",
            str(tmp_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "ok"
    assert payload["checks"]["healthz"] is True
    assert payload["checks"]["readyz"] is True
    assert payload["checks"]["product_route"] is True
    assert payload["checks"]["unknown_route"] is True
    assert payload["checks"]["validation_error"] is True
    assert payload["checks"]["correlation_header"] is True
    assert payload["checks"]["audit_written"] is True


def test_inspect_readiness_returns_pack_summary() -> None:
    readiness = inspect_readiness(Path("semantic_packs"))
    assert readiness["pack_count"] > 0
    assert "demo_company.revenue" in readiness["pack_ids"]


def test_readyz_helper_matches_check_smoke(tmp_path: Path) -> None:
    result = run_check(pack_root=Path("semantic_packs"), audit_root=tmp_path)
    assert result["status"] == "ok"
    assert result["checks"]["openapi_route_count"] >= 5
