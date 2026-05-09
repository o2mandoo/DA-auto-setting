"""20-domain evidence aggregation for the product console.

All numbers come from manifests and existing benchmark artifacts. Missing files
or missing per-domain benchmark data are reported explicitly.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class DomainEvidenceSummary:
    domain_id: str
    dataset_id: str
    source_file: str
    file_exists: bool
    benchmark_artifact: str | None
    benchmark_summary: dict[str, Any] = field(default_factory=dict)
    status: str = "missing"
    notes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class CapabilityMatrix:
    capabilities: dict[str, dict[str, str]]


@dataclass(frozen=True)
class FailurePatternSummary:
    pattern: str
    affected_domains: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class BaselineSystemExample:
    question: str
    baseline_risk: str
    system_behavior: str
    dataset_id: str


@dataclass(frozen=True)
class ProductReadinessReport:
    domain_summaries: list[DomainEvidenceSummary]
    capability_matrix: CapabilityMatrix
    failure_patterns: list[FailurePatternSummary]
    examples: list[BaselineSystemExample]
    missing_evidence: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_product_readiness_report(
    *,
    manifest_path: str | Path = Path("eval/datasets/sinagong_tableau_2026.yaml"),
    benchmark_root: str | Path = Path("runtime/benchmarks"),
) -> ProductReadinessReport:
    manifest = yaml.safe_load(Path(manifest_path).read_text(encoding="utf-8"))
    dataset_id = manifest["dataset_id"]
    # The Sinagong manifest includes a benchmark-only semantic-gold support pack
    # alongside the 20 workbook/domain files. The product evidence console is a
    # 20-domain file-corpus view, so support packs must not be counted as target
    # domains or the evidence surface will over-claim a 21st domain.
    files = [
        source_file
        for source_file in manifest.get("files", [])
        if str(source_file).startswith("docs/reference/test_datasets/")
    ]
    artifact = Path(benchmark_root) / dataset_id / "benchmark.json"
    summary: dict[str, Any] = {}
    if artifact.exists():
        summary = json.loads(artifact.read_text(encoding="utf-8")).get("summary", {})
    domain_summaries: list[DomainEvidenceSummary] = []
    for index, source_file in enumerate(files, start=1):
        file_exists = Path(source_file).exists()
        status = "covered_by_aggregate_benchmark" if artifact.exists() and file_exists else "missing_evidence"
        notes = []
        if artifact.exists():
            notes.append("aggregate benchmark artifact exists; per-file score is not invented")
        else:
            notes.append("benchmark artifact missing")
        if not file_exists:
            notes.append("source file missing in repo")
        domain_summaries.append(
            DomainEvidenceSummary(
                domain_id=f"sinagong_domain_{index:02d}_{Path(source_file).stem}",
                dataset_id=dataset_id,
                source_file=source_file,
                file_exists=file_exists,
                benchmark_artifact=str(artifact) if artifact.exists() else None,
                benchmark_summary=summary,
                status=status,
                notes=notes,
            )
        )
    capability_matrix = _capability_matrix(domain_summaries, manifest)
    failure_patterns = _failure_patterns(domain_summaries)
    examples = [
        BaselineSystemExample(
            question="월별 신규 고객 순매출을 보여줘",
            baseline_risk="physical-schema baseline may use signup date and gross amount",
            system_behavior="Semantic Pack can use first_paid_at, net revenue formula, join recipe, and policy checks",
            dataset_id="demo_company.revenue",
        ),
        BaselineSystemExample(
            question="지역별 매출과 이익을 보여줘",
            baseline_risk="generic baseline may miss Returns/People workbook semantics",
            system_behavior="file-corpus benchmark records Superstore as a covered sales-order target",
            dataset_id="tableau_superstore",
        ),
    ]
    missing = [summary.domain_id for summary in domain_summaries if summary.status != "covered_by_aggregate_benchmark"]
    return ProductReadinessReport(domain_summaries, capability_matrix, failure_patterns, examples, missing)


def write_evidence_reports(out_dir: str | Path = Path("reports/final")) -> dict[str, Path]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    report = build_product_readiness_report()
    paths = {
        "summary": out / "20_domain_benchmark_summary.md",
        "matrix": out / "final_capability_matrix.md",
        "failures": out / "known_failure_patterns.md",
        "narrative": out / "demo_narrative.md",
        "json": out / "20_domain_benchmark_summary.json",
    }
    paths["json"].write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    paths["summary"].write_text(_summary_md(report), encoding="utf-8")
    paths["matrix"].write_text(_matrix_md(report), encoding="utf-8")
    paths["failures"].write_text(_failures_md(report), encoding="utf-8")
    paths["narrative"].write_text(_narrative_md(report), encoding="utf-8")
    return paths


def _capability_matrix(domains: list[DomainEvidenceSummary], manifest: dict[str, Any]) -> CapabilityMatrix:
    capabilities = {}
    for domain in domains:
        capabilities[domain.domain_id] = {
            "file_present": "pass" if domain.file_exists else "missing",
            "aggregate_benchmark": "pass" if domain.benchmark_artifact else "missing",
            "semantic_findings_declared": "pass" if manifest.get("expected_semantic_findings") else "missing",
            "gold_questions_declared": "pass" if manifest.get("golden_questions") else "missing",
            "red_team_declared": "pass" if manifest.get("red_team_cases") else "missing",
            "weaviate_modes": "documented_optional" if Path("reports/benchmarks/weaviate_mode_comparison_report.md").exists() else "missing",
        }
    return CapabilityMatrix(capabilities)


def _failure_patterns(domains: list[DomainEvidenceSummary]) -> list[FailurePatternSummary]:
    missing_files = [domain.domain_id for domain in domains if not domain.file_exists]
    missing_per_file = [domain.domain_id for domain in domains if domain.benchmark_artifact and domain.file_exists]
    patterns = []
    if missing_files:
        patterns.append(FailurePatternSummary("source_file_missing", missing_files, ["manifest file path not found"]))
    if missing_per_file:
        patterns.append(
            FailurePatternSummary(
                "per_file_scores_not_available",
                missing_per_file,
                ["aggregate benchmark exists; per-file domain scores must be generated before claiming exact per-domain pass rates"],
            )
        )
    return patterns


def _summary_md(report: ProductReadinessReport) -> str:
    lines = ["# 20-Domain Benchmark Summary", "", "Counts are based on manifest entries and existing benchmark artifacts only.", ""]
    lines.append(f"- Domain targets: {len(report.domain_summaries)}")
    lines.append(f"- Missing evidence targets: {len(report.missing_evidence)}")
    lines.append("")
    lines.append("| Domain | File exists | Status | Benchmark |")
    lines.append("|---|---:|---|---|")
    for domain in report.domain_summaries:
        bench = domain.benchmark_artifact or "missing"
        lines.append(f"| `{domain.domain_id}` | {domain.file_exists} | {domain.status} | `{bench}` |")
    return "\n".join(lines) + "\n"


def _matrix_md(report: ProductReadinessReport) -> str:
    lines = ["# Final Capability Matrix", "", "| Domain | File | Aggregate benchmark | Semantic findings | Gold | Red-team | Weaviate modes |", "|---|---|---|---|---|---|---|"]
    for domain_id, caps in report.capability_matrix.capabilities.items():
        lines.append(
            f"| `{domain_id}` | {caps['file_present']} | {caps['aggregate_benchmark']} | {caps['semantic_findings_declared']} | {caps['gold_questions_declared']} | {caps['red_team_declared']} | {caps['weaviate_modes']} |"
        )
    return "\n".join(lines) + "\n"


def _failures_md(report: ProductReadinessReport) -> str:
    lines = ["# Known Failure Patterns", ""]
    if not report.failure_patterns:
        lines.append("No known failure patterns from available evidence.")
    for pattern in report.failure_patterns:
        lines.append(f"## {pattern.pattern}")
        lines.append(f"Affected domains: {len(pattern.affected_domains)}")
        for evidence in pattern.evidence:
            lines.append(f"- {evidence}")
    return "\n".join(lines) + "\n"


def _narrative_md(report: ProductReadinessReport) -> str:
    lines = ["# Demo Narrative", "", "Use the product demo to show three contrasts:", ""]
    for example in report.examples:
        lines.append(f"- `{example.dataset_id}` / {example.question}: baseline risk = {example.baseline_risk}; system behavior = {example.system_behavior}.")
    lines.append("")
    lines.append("The evidence console must state missing per-file evidence clearly instead of inventing pass rates.")
    return "\n".join(lines) + "\n"


__all__ = [
    "BaselineSystemExample",
    "CapabilityMatrix",
    "DomainEvidenceSummary",
    "FailurePatternSummary",
    "ProductReadinessReport",
    "build_product_readiness_report",
    "write_evidence_reports",
]
