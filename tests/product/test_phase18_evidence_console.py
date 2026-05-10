from __future__ import annotations

from pathlib import Path

from semantic_registry.product.evidence import build_product_readiness_report, write_evidence_reports


LOCAL_SINAGONG_MANIFEST = Path("eval/datasets/sinagong_tableau_2026.yaml")


def test_twenty_domain_evidence_uses_manifest_without_inventing_scores() -> None:
    report = build_product_readiness_report()
    if not LOCAL_SINAGONG_MANIFEST.exists():
        assert report.domain_summaries == []
        assert LOCAL_SINAGONG_MANIFEST.as_posix() in report.missing_evidence
        assert any(pattern.pattern == "local_dataset_manifest_not_tracked" for pattern in report.failure_patterns)
        return
    assert len(report.domain_summaries) == 20
    assert all(summary.dataset_id == "sinagong_tableau_2026" for summary in report.domain_summaries)
    assert any("per-file score is not invented" in " ".join(summary.notes) for summary in report.domain_summaries)
    assert report.capability_matrix.capabilities



def test_evidence_console_reports_missing_benchmark_without_inventing_scores(tmp_path: Path) -> None:
    report = build_product_readiness_report(benchmark_root=tmp_path / "missing-benchmarks")
    if not LOCAL_SINAGONG_MANIFEST.exists():
        assert report.domain_summaries == []
        assert LOCAL_SINAGONG_MANIFEST.as_posix() in report.missing_evidence
        return
    assert len(report.domain_summaries) == 20
    assert report.missing_evidence
    assert all(summary.benchmark_artifact is None for summary in report.domain_summaries)
    assert any("benchmark artifact missing" in " ".join(summary.notes) for summary in report.domain_summaries)
    assert any("per-file score is not invented" in " ".join(summary.notes) for summary in report.domain_summaries)


def test_evidence_console_handles_untracked_local_manifest_explicitly(tmp_path: Path) -> None:
    missing_manifest = tmp_path / "not-tracked.yaml"
    report = build_product_readiness_report(manifest_path=missing_manifest)

    assert report.domain_summaries == []
    assert str(missing_manifest) in report.missing_evidence
    assert any(pattern.pattern == "local_dataset_manifest_not_tracked" for pattern in report.failure_patterns)


def test_evidence_reports_are_written() -> None:
    paths = write_evidence_reports()
    for path in paths.values():
        assert Path(path).exists()
    summary = Path("reports/final/20_domain_benchmark_summary.md").read_text(encoding="utf-8")
    expected_targets = "20" if LOCAL_SINAGONG_MANIFEST.exists() else "0"
    assert f"Domain targets: {expected_targets}" in summary
    assert "Missing evidence targets" in summary


def test_product_ui_has_evidence_page() -> None:
    html = Path("apps/product_ui/index.html").read_text(encoding="utf-8")
    assert "benchmark-evidence" in html
