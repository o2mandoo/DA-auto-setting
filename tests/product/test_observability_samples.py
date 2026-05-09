from __future__ import annotations

import json
from pathlib import Path


SAMPLE_PATH = Path("docs/observability/product_api_audit_sample.jsonl")
DOC_PATH = Path("docs/observability/OBSERVABILITY_SAMPLES.md")


def _sample_records() -> list[dict[str, object]]:
    return [json.loads(line) for line in SAMPLE_PATH.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_product_api_audit_sample_is_jsonl_with_success_and_failure_records() -> None:
    records = _sample_records()

    assert len(records) >= 2
    assert {record["status_code"] for record in records} >= {200, 400}
    assert all(record["correlation_id"] for record in records)
    assert all(record["execution_allowed"] is False for record in records)
    assert all(str(record["route"]).startswith("POST /api/product/") for record in records)


def test_observability_sample_stays_local_and_credential_free() -> None:
    sample_text = SAMPLE_PATH.read_text(encoding="utf-8")
    doc_text = DOC_PATH.read_text(encoding="utf-8")
    combined = f"{sample_text}\n{doc_text}".lower()

    assert "execute_query" not in sample_text
    assert "password" not in combined
    assert "secret" not in combined
    assert "api_key" not in combined
    assert "production logging stack" in combined
    assert "correlation_id" in combined
