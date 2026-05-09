from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.n8n import live_runtime_smoke


def test_live_smoke_expected_routes_cover_current_templates() -> None:
    observed: set[str] = set()
    for path in Path("n8n/workflows").glob("*.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        for node in data.get("nodes", []):
            params = node.get("parameters", {}) if isinstance(node, dict) else {}
            url = params.get("url")
            method = params.get("method")
            if isinstance(url, str) and "/api/" in url and isinstance(method, str):
                observed.add(f"{method.upper()} {url.split('}}', 1)[-1]}")
    assert observed <= live_runtime_smoke.EXPECTED_ROUTES
    assert live_runtime_smoke.EXPECTED_ROUTES - {"GET /readyz"} >= observed


def test_live_smoke_safety_scan_rejects_direct_sql_node(tmp_path: Path) -> None:
    workflow = {
        "name": "unsafe",
        "nodes": [{"name": "Postgres", "type": "n8n-nodes-base.postgres"}],
        "meta": {"semanticDataContext": {"noSilentFallback": True, "noSqlRun": True}},
    }
    (tmp_path / "unsafe.json").write_text(json.dumps(workflow), encoding="utf-8")
    with pytest.raises(RuntimeError, match="direct SQL"):
        live_runtime_smoke._assert_workflows_safe(tmp_path)


def test_live_smoke_safety_scan_rejects_credentials(tmp_path: Path) -> None:
    workflow = {
        "name": "unsafe",
        "nodes": [],
        "meta": {"semanticDataContext": {"noSilentFallback": True, "noSqlRun": True}},
        "example": "postgres://user:pass@localhost/db",
    }
    (tmp_path / "unsafe.json").write_text(json.dumps(workflow), encoding="utf-8")
    with pytest.raises(RuntimeError, match="unsafe literal"):
        live_runtime_smoke._assert_workflows_safe(tmp_path)


def test_live_smoke_safety_scan_rejects_raw_pii_example(tmp_path: Path) -> None:
    workflow = {
        "name": "unsafe",
        "nodes": [],
        "meta": {"semanticDataContext": {"noSilentFallback": True, "noSqlRun": True}},
        "example": "customer@example.com",
    }
    (tmp_path / "unsafe.json").write_text(json.dumps(workflow), encoding="utf-8")
    with pytest.raises(RuntimeError, match="raw PII"):
        live_runtime_smoke._assert_workflows_safe(tmp_path)
