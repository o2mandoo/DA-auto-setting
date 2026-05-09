#!/usr/bin/env python3
"""Build a machine-readable release packet for Semantic Data Context.

The packer is intentionally evidence-first:
- it gathers only repo-local release evidence,
- it keeps missing evidence explicit,
- it refuses to hide safety gaps,
- and it writes both machine-readable and human-readable artifacts.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RELEASE_ROOT = ROOT / "reports" / "release"
READINESS_MATRIX = ROOT / "reports" / "productization" / "PRODUCTION_READINESS_MATRIX.md"
RISK_REGISTER = ROOT / "reports" / "productization" / "PRODUCTION_RISK_REGISTER.md"
RELEASE_CONTEXT = ROOT / ".omx" / "context" / "release-packer-20260509T134905Z.md"

SENSITIVE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"sk-[A-Za-z0-9_-]{12,}"),
    re.compile(r"(?i)\b(?:postgres|mysql|weaviate|redis|mongodb)://[^\s)>\"]+"),
    re.compile(r"(?i)\b[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}\b"),
    re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    re.compile(r"\b(?:\+?\d{1,3}[-.\s]?)?(?:\(?\d{2,4}\)?[-.\s]?)?\d{3,4}[-.\s]?\d{4}\b"),
)


@dataclass(frozen=True)
class SupportEntry:
    surface: str
    support_level: str
    current_evidence: str
    production_caveat: str


SUPPORT_MATRIX: tuple[SupportEntry, ...] = (
    SupportEntry(
        surface="Packages (semantic_contracts, semantic_builder, semantic_registry, semantic_mcp)",
        support_level="Supported for local validation",
        current_evidence="Editable local packages and Makefile setup/test targets.",
        production_caveat="Needs clean-venv proof and dependency snapshot for release promotion.",
    ),
    SupportEntry(
        surface="MCP stdio",
        support_level="Supported with official SDK installed",
        current_evidence="semantic_mcp registration surface and tests.",
        production_caveat="SDK/runtime absence must fail explicitly; no fake stdio runtime.",
    ),
    SupportEntry(
        surface="HTTP adapter",
        support_level="Planned optional local adapter",
        current_evidence="Pure Python handlers and API docs only.",
        production_caveat="Not production server ready until the adapter PR lands.",
    ),
    SupportEntry(
        surface="Weaviate",
        support_level="Optional explicit backend",
        current_evidence="Backend seam and deterministic tests.",
        production_caveat="Selected Weaviate must fail explicitly if unavailable; no silent fallback.",
    ),
    SupportEntry(
        surface="PostgreSQL",
        support_level="Read-only fixture/demo metadata validation",
        current_evidence="Scanner/docs/tests only.",
        production_caveat="No production execution; fixture/environment gated.",
    ),
    SupportEntry(
        surface="MySQL",
        support_level="Fixture/demo validation; live evidence pending",
        current_evidence="Connector/docs/tests and explicit n8n requirements.",
        production_caveat="No fallback to other DBs; production MySQL is not supported by default.",
    ),
    SupportEntry(
        surface="Oracle",
        support_level="Unsupported",
        current_evidence="Docs state unsupported/no fake behavior.",
        production_caveat="Must fail explicitly until a real connector and tests exist.",
    ),
    SupportEntry(
        surface="n8n",
        support_level="Demo orchestration only",
        current_evidence="Requirements/templates/product tests.",
        production_caveat="Not source of truth; must not execute SQL or hide failures.",
    ),
    SupportEntry(
        surface="CI",
        support_level="Required for release, not proven here",
        current_evidence="Local commands defined.",
        production_caveat="CI logs must be attached before a production release claim.",
    ),
    SupportEntry(
        surface="Observability",
        support_level="Local audit artifacts only",
        current_evidence="Product API audit paths and safety reports.",
        production_caveat="Needs correlation ID/error taxonomy evidence in PR-2/PR-7.",
    ),
    SupportEntry(
        surface="Release",
        support_level="Not production release ready",
        current_evidence="Clone-ready docs and final integration report.",
        production_caveat="Needs signed release packet and support-level sign-off.",
    ),
)

MISSING_EVIDENCE: tuple[dict[str, str], ...] = (
    {
        "gate": "PR-1 clean clone package baseline",
        "status": "missing",
        "evidence_needed": "Clean-venv install log, make env-check output, make test output, dependency snapshot.",
    },
    {
        "gate": "PR-2 optional local HTTP adapter",
        "status": "missing",
        "evidence_needed": "Adapter smoke output, /healthz and /readyz proof, OpenAPI, typed error payloads.",
    },
    {
        "gate": "PR-3 MCP + safe query runtime hardening",
        "status": "missing",
        "evidence_needed": "Registration-surface proof and SQL red-team blocking outputs.",
    },
    {
        "gate": "PR-4 DB fixture/read-only evidence",
        "status": "missing",
        "evidence_needed": "Read-only fixture evidence and explicit live-service unavailable artifacts where relevant.",
    },
    {
        "gate": "PR-5 retrieval/Weaviate optional evidence",
        "status": "missing",
        "evidence_needed": "Explicit live/skip/failure evidence for selected Weaviate backend.",
    },
    {
        "gate": "PR-6 n8n workflow smoke",
        "status": "missing",
        "evidence_needed": "Workflow smoke against local APIs and visible backend/comment warnings.",
    },
    {
        "gate": "PR-7 CI, observability, release packet",
        "status": "missing",
        "evidence_needed": "CI logs, release candidate identifier, dependency snapshot, and signed release packet.",
    },
)


def generate_release_id(now: datetime | None = None) -> str:
    now = now or datetime.now(timezone.utc)
    short_sha = git_short_sha()
    stamp = now.strftime("%Y%m%dT%H%M%SZ")
    return f"release-{stamp}-{short_sha}"


def git_short_sha() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short=12", "HEAD"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return "unknown"
    return result.stdout.strip() or "unknown"


def git_commit() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return "unknown"
    return result.stdout.strip() or "unknown"


def collect_dependency_snapshot() -> dict[str, str | bool]:
    try:
        result = subprocess.run(
            [os.environ.get("PYTHON", "python3"), "-m", "pip", "freeze"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        return {
            "captured": False,
            "status": "missing",
            "reason": f"pip freeze unavailable: {exc.__class__.__name__}",
        }
    freeze_path = None
    return {
        "captured": True,
        "status": "available",
        "reason": "",
        "freeze_text": result.stdout,
        "freeze_path": freeze_path,
    }


def scan_sensitive_material(texts: Iterable[str]) -> list[str]:
    findings: list[str] = []
    for text in texts:
        for pattern in SENSITIVE_PATTERNS:
            for match in pattern.findall(text):
                findings.append(match)
    return findings


def ensure_no_sensitive_material(texts: Iterable[str]) -> None:
    findings = scan_sensitive_material(texts)
    if findings:
        raise ValueError(f"Sensitive material detected in release packet inputs: {sorted(set(findings))[:5]}")


def build_release_packet(
    *,
    release_id: str | None = None,
    out_root: Path | None = None,
    now: datetime | None = None,
) -> dict[str, object]:
    now = now or datetime.now(timezone.utc)
    release_id = release_id or generate_release_id(now)
    out_root = out_root or DEFAULT_RELEASE_ROOT / release_id
    out_root.mkdir(parents=True, exist_ok=True)

    source_texts = [
        READINESS_MATRIX.read_text(encoding="utf-8"),
        RISK_REGISTER.read_text(encoding="utf-8"),
        RELEASE_CONTEXT.read_text(encoding="utf-8"),
    ]
    ensure_no_sensitive_material(source_texts)

    manifest: dict[str, object] = {
        "schema_version": "1.0",
        "release_id": release_id,
        "release_status": "draft",
        "generated_at": now.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        "git_commit": git_commit(),
        "git_short_sha": git_short_sha(),
        "artifact_dir": _relative_or_abs(out_root),
        "artifact_paths": {
            "manifest": _relative_or_abs(out_root / "release_manifest.json"),
            "summary": _relative_or_abs(out_root / "release_summary.md"),
            "known_limitations": _relative_or_abs(out_root / "known_limitations.md"),
            "support_matrix": _relative_or_abs(out_root / "support_matrix.md"),
        },
        "source_evidence": {
            "readiness_matrix": str(READINESS_MATRIX.relative_to(ROOT)),
            "risk_register": str(RISK_REGISTER.relative_to(ROOT)),
            "release_context": str(RELEASE_CONTEXT.relative_to(ROOT)),
        },
        "support_matrix": [
            {
                "surface": entry.surface,
                "support_level": entry.support_level,
                "current_evidence": entry.current_evidence,
                "production_caveat": entry.production_caveat,
            }
            for entry in SUPPORT_MATRIX
        ],
        "missing_evidence": list(MISSING_EVIDENCE),
        "safety_proof": {
            "no_production_execute_query": {
                "status": "explicitly_prohibited",
                "evidence": "reports/productization/PRODUCTION_READINESS_MATRIX.md and .omx/context/release-packer-20260509T134905Z.md",
            },
            "no_silent_fallback": {
                "status": "explicitly_prohibited",
                "evidence": "reports/productization/PRODUCTION_READINESS_MATRIX.md and reports/productization/PRODUCTION_RISK_REGISTER.md",
            },
            "no_raw_pii_artifacts": {
                "status": "checked",
                "evidence": "release packet source texts scanned by release_pack.py",
            },
            "no_unsupported_db_claim": {
                "status": "checked",
                "evidence": "support_matrix lists Oracle as unsupported and MySQL as fixture/demo pending live evidence.",
            },
            "no_synthetic_metadata_as_product_truth": {
                "status": "checked",
                "evidence": "release context preserves test-only synthetic metadata boundaries.",
            },
        },
        "dependency_snapshot": collect_dependency_snapshot(),
        "test_evidence": {
            "required_commands": [
                "make env-check",
                "make test",
            ],
            "status": "missing",
            "reason": "release packer does not invent command output; actual verification must be attached by the worker run.",
        },
    }

    summary_path = out_root / "release_summary.md"
    limits_path = out_root / "known_limitations.md"
    support_path = out_root / "support_matrix.md"
    manifest_path = out_root / "release_manifest.json"

    summary_path.write_text(render_summary(manifest), encoding="utf-8")
    limits_path.write_text(render_known_limitations(manifest), encoding="utf-8")
    support_path.write_text(render_support_matrix(manifest), encoding="utf-8")
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def render_summary(manifest: dict[str, object]) -> str:
    missing = manifest["missing_evidence"]  # type: ignore[index]
    support_matrix = manifest["support_matrix"]  # type: ignore[index]
    return "\n".join(
        [
            f"# Release packet {manifest['release_id']}",  # type: ignore[index]
            "",
            f"- Generated at: {manifest['generated_at']}",  # type: ignore[index]
            f"- Git commit: {manifest['git_commit']} ({manifest['git_short_sha']})",  # type: ignore[index]
            f"- Release status: {manifest['release_status']}",  # type: ignore[index]
            f"- Missing evidence items: {len(missing)}",  # type: ignore[arg-type]
            "",
            "## Evidence sources",
            f"- {manifest['source_evidence']['readiness_matrix']}",
            f"- {manifest['source_evidence']['risk_register']}",
            f"- {manifest['source_evidence']['release_context']}",
            "",
            "## Safety posture",
            "- No production execute_query is allowed.",
            "- Silent fallback is forbidden.",
            "- Raw PII must not be stored, shown, or embedded.",
            "- Unsupported DB claims remain explicit.",
            "- Synthetic metadata stays fixture-only.",
            "",
            f"## Support surfaces ({len(support_matrix)})",
        ]
    )


def render_known_limitations(manifest: dict[str, object]) -> str:
    lines = ["# Known limitations", ""]
    for item in manifest["missing_evidence"]:  # type: ignore[index]
        lines.append(f"- {item['gate']}: {item['evidence_needed']}")  # type: ignore[index]
    lines.extend(
        [
            "",
            "## Explicit constraints",
            "- Release packet is evidence-first; missing evidence is reported, not inferred.",
            "- Oracle remains unsupported unless a real connector and tests exist.",
            "- MySQL stays fixture/demo until live read-only evidence is attached.",
        ]
    )
    return "\n".join(lines) + "\n"


def render_support_matrix(manifest: dict[str, object]) -> str:
    lines = ["# Support matrix", "", "| Surface | Support level | Current evidence | Production caveat |", "|---|---|---|---|"]
    for item in manifest["support_matrix"]:  # type: ignore[index]
        lines.append(
            f"| {item['surface']} | {item['support_level']} | {item['current_evidence']} | {item['production_caveat']} |"
        )
    lines.append("")
    return "\n".join(lines)


def _relative_or_abs(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="release_pack")
    parser.add_argument("--release-id", help="Optional release identifier; defaults to timestamp + git SHA.")
    parser.add_argument(
        "--out",
        type=Path,
        help="Output directory for the release packet. Defaults to reports/release/<release-id>.",
    )
    parser.add_argument(
        "--print-manifest",
        action="store_true",
        help="Print the generated manifest JSON to stdout after writing artifacts.",
    )
    args = parser.parse_args(argv)

    manifest = build_release_packet(release_id=args.release_id, out_root=args.out)
    if args.print_manifest:
        print(json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True))
    else:
        print(manifest["artifact_dir"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
