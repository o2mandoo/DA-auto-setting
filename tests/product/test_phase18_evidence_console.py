from __future__ import annotations

from pathlib import Path

from semantic_registry.product.evidence import build_product_readiness_report, write_evidence_reports


def test_twenty_domain_evidence_uses_manifest_without_inventing_scores() -> None:
    report = build_product_readiness_report()
    assert len(report.domain_summaries) == 20
    assert all(summary.dataset_id == "sinagong_tableau_2026" for summary in report.domain_summaries)
    assert any("per-file score is not invented" in " ".join(summary.notes) for summary in report.domain_summaries)
    assert report.capability_matrix.capabilities


def test_evidence_reports_are_written() -> None:
    paths = write_evidence_reports()
    for path in paths.values():
        assert Path(path).exists()
    summary = Path("reports/final/20_domain_benchmark_summary.md").read_text(encoding="utf-8")
    assert "Domain targets: 20" in summary
    assert "Missing evidence targets" in summary


def test_product_ui_has_evidence_page() -> None:
    html = Path("apps/product_ui/index.html").read_text(encoding="utf-8")
    assert "benchmark-evidence" in html
