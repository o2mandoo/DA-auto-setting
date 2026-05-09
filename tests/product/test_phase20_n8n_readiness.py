from __future__ import annotations

from pathlib import Path


def test_n8n_readiness_docs_exist_and_define_five_workflows() -> None:
    req = Path("docs/demo/N8N_WORKFLOW_REQUIREMENTS.md").read_text(encoding="utf-8")
    report = Path("reports/productization/phase20_n8n_readiness_report.md").read_text(encoding="utf-8")
    for label in ["Workflow 01", "Workflow 02", "Workflow 03", "Workflow 04", "Workflow 05"]:
        assert label in req
    assert "PASS" in report
    assert "No silent fallback" in req
