#!/usr/bin/env python3
"""Build a redacted release packet from repository evidence.

The packet is intentionally local-first and evidence-driven:
- it surfaces the production readiness matrix
- it includes the risk register
- it includes known limitations
- it redacts secret-like and PII-like values before writing outputs

This utility is designed for dry-run / release-packet generation, not for
claiming production readiness.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, NamedTuple


REDACTION_PLACEHOLDERS = {
    "email": "<redacted_email>",
    "credentials": "<redacted_credentials>",
    "openai_key": "<redacted_openai_key>",
    "aws_access_key_id": "<redacted_aws_access_key_id>",
    "secret_value": "<redacted_secret>",
    "token_value": "<redacted_token>",
}

REDACTION_PATTERNS: list[tuple[str, re.Pattern[str], str | None]] = [
    ("email", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"), REDACTION_PLACEHOLDERS["email"]),
    ("local_path", re.compile(r"(?P<path>/Users/[^\s\"'`<>]+)"), "<redacted_local_path>"),
    ("worker_id", re.compile(r"\bworker-\d+\b"), "<redacted_worker_id>"),
    ("leader_id", re.compile(r"\bleader-fixed\b"), "<redacted_worker_id>"),
    (
        "url_credentials",
        re.compile(r"(?P<scheme>\b[a-zA-Z][a-zA-Z0-9+.-]*://)(?P<userinfo>[^/\s@]+@)"),
        None,
    ),
    ("openai_key", re.compile(r"\bsk-[A-Za-z0-9]{20,}\b"), REDACTION_PLACEHOLDERS["openai_key"]),
    ("aws_access_key_id", re.compile(r"\bAKIA[0-9A-Z]{16}\b"), REDACTION_PLACEHOLDERS["aws_access_key_id"]),
    (
        "named_secret",
        re.compile(
            r"(?i)\b(password|secret|token|api[_-]?key|client_secret|aws_secret_access_key)\b(\s*[:=]\s*)([^\s,'\"`]+)"
        ),
        None,
    ),
    ("bearer_token", re.compile(r"(?i)\bBearer\s+[A-Za-z0-9\-._~+/]+=*"), "Bearer " + REDACTION_PLACEHOLDERS["token_value"]),
]

SOURCE_FILES: tuple[Path, ...] = (
    Path("reports/productization/PRODUCTION_READINESS_MATRIX.md"),
    Path("reports/productization/PRODUCTION_RISK_REGISTER.md"),
    Path("reports/final/final_integration_report.md"),
    Path("docs/execution/VALIDATION_DATASETS.md"),
)

READINESS_MATRIX_SOURCE = Path("reports/productization/PRODUCTION_READINESS_MATRIX.md")
EVIDENCE_INDEX_SOURCE = Path("reports/productization/PR0_PR7_EVIDENCE_INDEX.md")
API_MCP_N8N_SOURCE_FILES: tuple[Path, ...] = (
    Path("docs/product/PRODUCT_MODES.md"),
    Path("docs/product/BASELINE_COMPARISON_SPEC.md"),
    Path("docs/product/METADATA_PROVENANCE_RULES.md"),
    Path("docs/api/PRODUCT_API.md"),
    Path("reports/productization/PR2_HTTP_ADAPTER_EVIDENCE.md"),
    Path("reports/productization/PR3_MCP_SAFE_RUNTIME_EVIDENCE.md"),
    Path("reports/productization/phase20_n8n_readiness_report.md"),
)
TEST_EVIDENCE_REFERENCES: tuple[Path, ...] = (
    Path("tests/release/test_build_release_packet.py"),
    Path("Makefile"),
)

METADATA_PROVENANCE_RULES: tuple[dict[str, object], ...] = (
    {
        "source": "real_db_comment",
        "product_usable": True,
        "rule": "Real DB table/column comments are product-usable context only with preserved provenance/status.",
    },
    {
        "source": "no_comment",
        "product_usable": False,
        "rule": "Missing comments are metadata gaps and must trigger reverse questions instead of hallucinated semantics.",
    },
    {
        "source": "test_only_synthetic_comment",
        "product_usable": False,
        "rule": "Synthetic comments are fixture-only and must never become product truth or human-approved context automatically.",
    },
    {
        "source": "sidecar_metadata",
        "product_usable": True,
        "rule": "Sidecar metadata can be used only with explicit source attribution and status.",
    },
    {
        "source": "llm_hypothesis",
        "product_usable": False,
        "rule": "LLM hypotheses remain draft context until review/promotion.",
    },
    {
        "source": "human_confirmed",
        "product_usable": True,
        "rule": "Human-confirmed context can be used as approved semantic truth within pack policy boundaries.",
    },
    {
        "source": "verified_query",
        "product_usable": True,
        "rule": "Verified queries can be used as high-confidence examples but do not authorize production SQL execution.",
    },
)

SUPPORT_LEVELS: tuple[dict[str, str], ...] = (
    {
        "surface": "Semantic Pack contracts",
        "support_level": "supported_local_validation",
        "evidence_status": "present",
        "evidence": "reports/productization/PRODUCTION_READINESS_MATRIX.md",
        "limitation": "Schema freeze and external-adapter versioning remain release-gated.",
    },
    {
        "surface": "Local Registry and MCP interface",
        "support_level": "supported_local_validation",
        "evidence_status": "present",
        "evidence": "reports/productization/PR3_MCP_SAFE_RUNTIME_EVIDENCE.md",
        "limitation": "MCP requires the official SDK/runtime; no production SQL execution surface is supported.",
    },
    {
        "surface": "Optional local HTTP adapter",
        "support_level": "partial_local_adapter",
        "evidence_status": "present",
        "evidence": "reports/productization/PR2_HTTP_ADAPTER_EVIDENCE.md",
        "limitation": "Adapter is local/demo scoped and does not make the repo production-server ready.",
    },
    {
        "surface": "PostgreSQL fixture/read-only metadata",
        "support_level": "fixture_readonly_validation",
        "evidence_status": "present",
        "evidence": "reports/productization/PR4_DB_FIXTURE_READONLY_EVIDENCE.md",
        "limitation": "Metadata scan/profile/demo validation only; no production execution claim.",
    },
    {
        "surface": "MySQL fixture/read-only metadata",
        "support_level": "fixture_readonly_validation",
        "evidence_status": "present",
        "evidence": "reports/productization/PR4_DB_FIXTURE_READONLY_EVIDENCE.md",
        "limitation": "No fallback to PostgreSQL/DuckDB/SQLite/cached JSON/synthetic comments.",
    },
    {
        "surface": "Weaviate retrieval backend",
        "support_level": "optional_evidence_gated",
        "evidence_status": "present_or_explicit_skip",
        "evidence": "reports/productization/PR5_SEMANTIC_RETRIEVAL_EVIDENCE.md",
        "limitation": "Selected Weaviate must fail visibly if unavailable; keyword fallback is not allowed after explicit selection.",
    },
    {
        "surface": "n8n orchestration",
        "support_level": "demo_orchestration_only",
        "evidence_status": "present",
        "evidence": "reports/productization/pr6_n8n_live_runtime_smoke.md",
        "limitation": "n8n is not source of truth, must not execute SQL, and must keep backend/comment warnings visible.",
    },
    {
        "surface": "Oracle",
        "support_level": "unsupported",
        "evidence_status": "no_release_evidence",
        "evidence": "reports/productization/PRODUCTION_READINESS_MATRIX.md",
        "limitation": "Unsupported backends must fail explicitly; no fake Oracle fixture behavior is allowed.",
    },
    {
        "surface": "Production execute_query",
        "support_level": "forbidden",
        "evidence_status": "prohibited_by_contract",
        "evidence": "docs/product/PRODUCTION_MODE_ADR.md",
        "limitation": "No route, MCP tool, handler, workflow, or documentation may promote production SQL execution.",
    },
)

EVIDENCE_GATES: tuple[dict[str, object], ...] = (
    {
        "gate": "PR-0 production boundary and readiness baseline",
        "paths": (
            "docs/product/PRODUCTION_MODE_ADR.md",
            "reports/productization/PRODUCTION_READINESS_MATRIX.md",
            "reports/productization/PRODUCTION_RISK_REGISTER.md",
        ),
    },
    {
        "gate": "PR-1 clean clone package baseline",
        "paths": (
            "reports/productization/PR1_CLEAN_CLONE_EVIDENCE.md",
            "reports/productization/PR1_FINAL_VERIFIER_EVIDENCE.md",
            "reports/productization/PR1_PIP_FREEZE.txt",
        ),
    },
    {
        "gate": "PR-2 optional local HTTP adapter",
        "paths": (
            "reports/productization/PR2_HTTP_ADAPTER_EVIDENCE.md",
            "docs/api/PRODUCT_API.md",
            "docs/api/OPENAPI_LIKE.yaml",
        ),
    },
    {
        "gate": "PR-3 MCP + safe query runtime hardening",
        "paths": (
            "reports/productization/PR3_MCP_SAFE_RUNTIME_EVIDENCE.md",
            "docs/product/PRODUCT_MODES.md",
        ),
    },
    {
        "gate": "PR-4 DB fixture/read-only evidence",
        "paths": (
            "reports/productization/PR4_DB_FIXTURE_READONLY_EVIDENCE.md",
            "reports/reality/postgres_live_fixture_evidence.json",
            "reports/reality/mysql_live_fixture_evidence.json",
        ),
    },
    {
        "gate": "PR-5 retrieval/Weaviate optional evidence",
        "paths": (
            "reports/productization/PR5_PRECHECK_DB_CORPUS_EVIDENCE.md",
            "reports/productization/PR5_SEMANTIC_RETRIEVAL_EVIDENCE.md",
        ),
    },
    {
        "gate": "PR-6 n8n workflow smoke",
        "paths": (
            "reports/productization/phase20_n8n_readiness_report.md",
            "reports/productization/final_n8n_readiness_evaluate_after_comment_rules.md",
        ),
        "external_missing": ("live imported n8n workflow smoke output",),
    },
    {
        "gate": "PR-7 CI, observability, release packet",
        "paths": (
            ".github/workflows/packaging-clean-clone.yml",
            "scripts/release/build_release_packet.py",
            "tests/release/test_build_release_packet.py",
        ),
        "external_missing": ("live CI run log", "signed or promoted release candidate approval"),
    },
)


class RedactionSummary(NamedTuple):
    counts: dict[str, int]
    had_findings: bool


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def git_commit(root: Path) -> str:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return "unknown"
    return completed.stdout.strip() or "unknown"


def extract_markdown_section(text: str, heading: str) -> str:
    pattern = re.compile(rf"^##\s+{re.escape(heading)}\s*$", re.MULTILINE)
    match = pattern.search(text)
    if not match:
        return ""
    start = match.start()
    rest = text[match.end() :]
    next_heading = re.search(r"^##\s+", rest, re.MULTILINE)
    end = match.end() + (next_heading.start() if next_heading else len(rest))
    return text[start:end].strip() + "\n"


def redact_text(text: str) -> tuple[str, RedactionSummary]:
    counts: dict[str, int] = {}
    redacted = text

    def bump(name: str, amount: int) -> None:
        if amount:
            counts[name] = counts.get(name, 0) + amount

    for name, pattern, replacement in REDACTION_PATTERNS:
        if name == "url_credentials":
            redacted, count = pattern.subn(lambda m: f"{m.group('scheme')}{REDACTION_PLACEHOLDERS['credentials']}@", redacted)
            bump("credentials", count)
            continue
        if name == "named_secret":
            def repl(match: re.Match[str]) -> str:
                key = match.group(1).lower().replace("-", "_")
                if key == "aws_secret_access_key":
                    placeholder = REDACTION_PLACEHOLDERS["secret_value"]
                elif "token" in key:
                    placeholder = REDACTION_PLACEHOLDERS["token_value"]
                else:
                    placeholder = REDACTION_PLACEHOLDERS["secret_value"]
                return f"{match.group(1)}{match.group(2)}{placeholder}"

            redacted, count = pattern.subn(repl, redacted)
            bump("secret_value", count)
            continue
        redacted, count = pattern.subn(replacement or "", redacted)
        bump(name, count)

    return redacted, RedactionSummary(counts=counts, had_findings=bool(counts))


def merge_counts(*summaries: RedactionSummary) -> RedactionSummary:
    counts: dict[str, int] = {}
    for summary in summaries:
        for key, value in summary.counts.items():
            counts[key] = counts.get(key, 0) + value
    return RedactionSummary(counts=counts, had_findings=bool(counts))


def source_index(root: Path) -> tuple[dict[str, str], list[str]]:
    indexed: dict[str, str] = {}
    missing: list[str] = []
    for relative in SOURCE_FILES:
        path = root / relative
        if path.exists():
            indexed[str(relative)] = read_text(path)
        else:
            missing.append(str(relative))
    return indexed, missing


def build_dependency_snapshot(root: Path) -> tuple[str, bool]:
    try:
        completed = subprocess.run(
            [sys.executable, "-m", "pip", "freeze"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        return f"# dependency snapshot unavailable\n\nReason: {exc.__class__.__name__}\n", False
    return completed.stdout.rstrip() + "\n", True


def build_source_reference_block(title: str, source_paths: Iterable[Path], root: Path, missing: list[str]) -> str:
    lines = [f"# {title}", ""]
    paths = list(source_paths)
    for source_path in paths:
        rel = str(source_path)
        if (root / source_path).exists():
            lines.append(f"- {rel}")
        else:
            missing.append(rel)
            lines.append(f"- {rel} (missing)")
    lines.append("")
    return "\n".join(lines)


def build_api_mcp_n8n_summary(root: Path, missing: list[str]) -> str:
    lines = [
        "# API / MCP / n8n Surface Summary",
        "",
        "This summary is assembled from current repo evidence and keeps explicit source references.",
        "",
        "## Source references",
    ]
    for source_path in API_MCP_N8N_SOURCE_FILES:
        rel = str(source_path)
        if (root / source_path).exists():
            lines.append(f"- {rel}")
        else:
            missing.append(rel)
            lines.append(f"- {rel} (missing)")
    lines.extend(
        [
            "",
            "## Summary",
            "",
            "- Product API and MCP surfaces remain validation-first and do not expose production execute_query.",
            "- Baseline versus system SQL comparison is profile-only and non-executing.",
            "- n8n workflow evidence remains orchestration-only and must surface backend/comment warnings explicitly.",
        ]
    )
    return "\n".join(lines) + "\n"


def build_test_evidence() -> str:
    lines = [
        "# Test Evidence",
        "",
        "## References",
    ]
    for ref in TEST_EVIDENCE_REFERENCES:
        lines.append(f"- {ref}")
    lines.extend(
        [
            "",
            "## Suggested verification commands",
            "",
            "- `make PYTHON=python3 release-pack RELEASE_ID=<id> RELEASE_OUT=reports/release`",
            "- `make release-test`",
            "",
            "These commands are representative release-smoke evidence references; execution results are captured by the worker run.",
        ]
    )
    return "\n".join(lines) + "\n"




def build_structured_support_matrix() -> str:
    lines = [
        "## Structured support levels",
        "",
        "| Surface | Support level | Evidence status | Evidence | Limitation |",
        "|---|---|---|---|---|",
    ]
    for item in SUPPORT_LEVELS:
        lines.append(
            "| {surface} | `{support_level}` | {evidence_status} | {evidence} | {limitation} |".format(**item)
        )
    lines.append("")
    return "\n".join(lines)


def build_evidence_coverage(root: Path) -> list[dict[str, object]]:
    coverage: list[dict[str, object]] = []
    for gate in EVIDENCE_GATES:
        paths = [Path(str(path)) for path in gate["paths"]]  # type: ignore[index]
        present_paths = [str(path) for path in paths if (root / path).exists()]
        missing_paths = [str(path) for path in paths if not (root / path).exists()]
        external_missing = list(gate.get("external_missing", ()))  # type: ignore[union-attr]
        if missing_paths:
            status = "partial" if present_paths else "missing"
        elif external_missing:
            status = "partial"
        else:
            status = "present"
        coverage.append(
            {
                "gate": gate["gate"],
                "status": status,
                "present_paths": present_paths,
                "missing_paths": missing_paths,
                "external_missing": external_missing,
            }
        )
    return coverage


def build_missing_gate_evidence(coverage: Iterable[dict[str, object]]) -> list[dict[str, str]]:
    missing: list[dict[str, str]] = []
    for item in coverage:
        missing_paths = [str(path) for path in item.get("missing_paths", [])]
        external_missing = [str(entry) for entry in item.get("external_missing", [])]
        if not missing_paths and not external_missing:
            continue
        needed = []
        if missing_paths:
            needed.append("missing files: " + ", ".join(missing_paths))
        if external_missing:
            needed.append("missing external/live evidence: " + ", ".join(external_missing))
        missing.append(
            {
                "gate": str(item["gate"]),
                "status": str(item["status"]),
                "evidence_needed": "; ".join(needed),
            }
        )
    return missing


def build_safety_proof(redaction_summary: RedactionSummary) -> dict[str, dict[str, object]]:
    return {
        "no_production_execute_query": {
            "status": "prohibited",
            "evidence": ["docs/product/PRODUCTION_MODE_ADR.md", "reports/productization/PRODUCTION_READINESS_MATRIX.md"],
        },
        "no_silent_fallback": {
            "status": "prohibited",
            "evidence": ["reports/productization/PRODUCTION_READINESS_MATRIX.md", "reports/productization/PR5_SEMANTIC_RETRIEVAL_EVIDENCE.md"],
        },
        "no_raw_pii_artifacts": {
            "status": "redacted_or_blocked",
            "redaction_findings": redaction_summary.counts,
        },
        "no_unsupported_db_claim": {
            "status": "oracle_unsupported",
            "evidence": ["reports/productization/PRODUCTION_READINESS_MATRIX.md"],
        },
        "no_synthetic_metadata_as_product_truth": {
            "status": "fixture_only",
            "evidence": ["docs/product/METADATA_PROVENANCE_RULES.md", "reports/productization/PR4_DB_FIXTURE_READONLY_EVIDENCE.md"],
        },
    }


def build_release_summary(
    release_id: str,
    generated_at: str,
    commit: str,
    missing_evidence: Iterable[str],
    missing_gates: Iterable[dict[str, str]],
    redaction_summary: RedactionSummary,
) -> str:
    missing_lines = list(missing_evidence)
    gate_lines = list(missing_gates)
    lines = [
        f"# Release Packet: {release_id}",
        "",
        f"- generated_at: {generated_at}",
        f"- git_commit: {commit}",
        "- status: dry-run release packet",
        "",
        "## Evidence snapshot",
        "",
        "- Production readiness matrix included.",
        "- Risk register included.",
        "- Known limitations included.",
        "- Support matrix included.",
        "- Secret-like and PII-like values are redacted before writing packet files.",
        "",
        "## Missing evidence",
        "",
    ]
    if missing_lines:
        lines.extend(f"- {item}" for item in missing_lines)
    else:
        lines.append("- none")
    lines.extend(
        [
            "",
            "## Missing gate evidence",
            "",
        ]
    )
    if gate_lines:
        lines.extend(f"- {item['gate']}: {item['evidence_needed']}" for item in gate_lines)
    else:
        lines.append("- none")
    lines.extend(
        [
            "",
            "## Redaction summary",
            "",
        ]
    )
    if redaction_summary.counts:
        for key, count in sorted(redaction_summary.counts.items()):
            lines.append(f"- {key}: {count}")
    else:
        lines.append("- none")
    return "\n".join(lines).rstrip() + "\n"


def build_manifest(
    release_id: str,
    generated_at: str,
    commit: str,
    out_dir: Path,
    missing_evidence: list[str],
    missing_gates: list[dict[str, str]],
    evidence_coverage: list[dict[str, object]],
    redaction_summary: RedactionSummary,
    dependency_snapshot_present: bool,
) -> dict[str, object]:
    coverage_counts = {
        status: sum(1 for item in evidence_coverage if item["status"] == status)
        for status in ("present", "partial", "missing")
    }
    return {
        "release_id": release_id,
        "generated_at": generated_at,
        "git_commit": commit,
        "status": "dry-run",
        "output_dir": str(Path("reports") / "release" / release_id),
        "source_files": [str(path) for path in SOURCE_FILES],
        "artifacts": {
            "release_summary": "release_summary.md",
            "readiness_matrix": "readiness_matrix.md",
            "risk_register": "risk_register.md",
            "known_limitations": "known_limitations.md",
            "support_matrix": "support_matrix.md",
            "dependency_snapshot": "dependency_snapshot.txt",
            "evidence_index": "evidence_index.md",
            "api_mcp_n8n_surface_summary": "api_mcp_n8n_surface_summary.md",
            "test_evidence": "test_evidence.md",
        },
        "missing_evidence": missing_evidence,
        "missing_gate_evidence": missing_gates,
        "evidence_coverage": evidence_coverage,
        "evidence_coverage_summary": coverage_counts,
        "metadata_provenance_rules": list(METADATA_PROVENANCE_RULES),
        "support_levels": list(SUPPORT_LEVELS),
        "test_status": {
            "status": "not_run_by_packer",
            "release_test_command": "make release-test",
            "note": "The release packer records test references; verifier lanes must attach real command output.",
        },
        "risk_summary": {
            "source": str(SOURCE_FILES[1]),
            "status": "included" if str(SOURCE_FILES[1]) not in missing_evidence else "missing",
        },
        "redactions": redaction_summary.counts,
        "safety_checks": {
            "sensitive_content_redacted": redaction_summary.had_findings,
            "secrets_redacted": redaction_summary.had_findings,
            "no_production_execute_query_claim": True,
            "no_silent_fallback_claim": True,
            "no_raw_pii_claim": True,
            "dependency_snapshot_present": dependency_snapshot_present,
        },
        "safety_proof": build_safety_proof(redaction_summary),
    }


def build_packet(repo: Path, release_id: str, out_dir: Path) -> dict[str, object]:
    evidence, missing_evidence = source_index(repo)
    generated_at = datetime.now(timezone.utc).isoformat()
    commit = git_commit(repo)
    dependency_snapshot_text, dependency_snapshot_present = build_dependency_snapshot(repo)
    dependency_snapshot_text, dependency_redactions = redact_text(dependency_snapshot_text)
    evidence_coverage = build_evidence_coverage(repo)
    missing_gate_evidence = build_missing_gate_evidence(evidence_coverage)

    matrix_text = evidence.get(str(SOURCE_FILES[0]), "")
    risk_text = evidence.get(str(SOURCE_FILES[1]), "")
    final_report = evidence.get(str(SOURCE_FILES[2]), "")
    validation_text = evidence.get(str(SOURCE_FILES[3]), "")

    release_summary_text = build_release_summary(
        release_id=release_id,
        generated_at=generated_at,
        commit=commit,
        missing_evidence=missing_evidence,
        missing_gates=missing_gate_evidence,
        redaction_summary=RedactionSummary(counts={}, had_findings=False),
    )
    risk_register_text, risk_redactions = redact_text(risk_text)
    known_limitations_source = "\n".join(
        section
        for section in (
            extract_markdown_section(final_report, "Known limitations"),
            extract_markdown_section(validation_text, "Current known limitations"),
        )
        if section
    )
    known_limitations_text, limitation_redactions = redact_text(known_limitations_source)
    support_matrix_source = "\n".join(
        section
        for section in (
            extract_markdown_section(matrix_text, "Support matrix"),
            build_structured_support_matrix(),
            extract_markdown_section(matrix_text, "Non-negotiable safety gates"),
        )
        if section
    )
    support_matrix_text, support_redactions = redact_text(support_matrix_source)
    redaction_summary = merge_counts(risk_redactions, limitation_redactions, support_redactions)
    release_summary_text = build_release_summary(
        release_id=release_id,
        generated_at=generated_at,
        commit=commit,
        missing_evidence=missing_evidence,
        missing_gates=missing_gate_evidence,
        redaction_summary=redaction_summary,
    )
    readiness_matrix_raw = read_text(repo / READINESS_MATRIX_SOURCE)
    readiness_matrix_text, readiness_redactions = redact_text(readiness_matrix_raw)
    evidence_index_raw = read_text(repo / EVIDENCE_INDEX_SOURCE) if (repo / EVIDENCE_INDEX_SOURCE).exists() else build_source_reference_block("Evidence Index", [EVIDENCE_INDEX_SOURCE], repo, missing_evidence)
    evidence_index_text, evidence_redactions = redact_text(evidence_index_raw)
    api_mcp_n8n_summary_raw = build_api_mcp_n8n_summary(repo, missing_evidence)
    api_mcp_n8n_summary_text, api_redactions = redact_text(api_mcp_n8n_summary_raw)
    test_evidence_raw = build_test_evidence()
    test_evidence_text, test_redactions = redact_text(test_evidence_raw)
    redaction_summary = merge_counts(
        risk_redactions,
        limitation_redactions,
        support_redactions,
        dependency_redactions,
        readiness_redactions,
        evidence_redactions,
        api_redactions,
        test_redactions,
    )
    release_summary_text = build_release_summary(
        release_id=release_id,
        generated_at=generated_at,
        commit=commit,
        missing_evidence=missing_evidence,
        missing_gates=missing_gate_evidence,
        redaction_summary=redaction_summary,
    )

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "release_summary.md").write_text(release_summary_text, encoding="utf-8")
    (out_dir / "readiness_matrix.md").write_text(readiness_matrix_text, encoding="utf-8")
    (out_dir / "risk_register.md").write_text(risk_register_text, encoding="utf-8")
    (out_dir / "known_limitations.md").write_text(known_limitations_text, encoding="utf-8")
    (out_dir / "support_matrix.md").write_text(support_matrix_text, encoding="utf-8")
    (out_dir / "dependency_snapshot.txt").write_text(dependency_snapshot_text, encoding="utf-8")
    (out_dir / "evidence_index.md").write_text(evidence_index_text, encoding="utf-8")
    (out_dir / "api_mcp_n8n_surface_summary.md").write_text(api_mcp_n8n_summary_text, encoding="utf-8")
    (out_dir / "test_evidence.md").write_text(test_evidence_text, encoding="utf-8")

    manifest = build_manifest(
        release_id=release_id,
        generated_at=generated_at,
        commit=commit,
        out_dir=out_dir,
        missing_evidence=missing_evidence,
        missing_gates=missing_gate_evidence,
        evidence_coverage=evidence_coverage,
        redaction_summary=redaction_summary,
        dependency_snapshot_present=dependency_snapshot_present,
    )
    (out_dir / "release_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--release-id",
        default=os.environ.get("RELEASE_ID") or f"release-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
    )
    parser.add_argument(
        "--out",
        default=str(repo_root() / "reports" / "release"),
        help="Output root directory. The release ID will be appended beneath this directory.",
    )
    parser.add_argument(
        "--repo-root",
        default=str(repo_root()),
        help="Repository root used to read source evidence.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo = Path(args.repo_root).resolve()
    out_root = Path(args.out).resolve()
    out_dir = out_root / args.release_id
    manifest = build_packet(repo=repo, release_id=args.release_id, out_dir=out_dir)
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
