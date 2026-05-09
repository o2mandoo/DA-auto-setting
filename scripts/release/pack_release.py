#!/usr/bin/env python3
"""Build a minimal release packet from existing repo evidence.

This script is intentionally lightweight:
- it does not invent evidence,
- it does not run product workflows,
- it only packages existing source-of-truth artifacts into a versioned
  release directory.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "reports" / "release"


@dataclass(frozen=True)
class EvidenceFile:
    name: str
    path: Path
    required: bool = False


EVIDENCE_FILES: tuple[EvidenceFile, ...] = (
    EvidenceFile("pr0_pr7_index", REPO_ROOT / "reports" / "productization" / "PR0_PR7_EVIDENCE_INDEX.md", True),
    EvidenceFile("readiness_matrix", REPO_ROOT / "reports" / "productization" / "PRODUCTION_READINESS_MATRIX.md", True),
    EvidenceFile("risk_register", REPO_ROOT / "reports" / "productization" / "PRODUCTION_RISK_REGISTER.md", True),
    EvidenceFile("dependency_snapshot", REPO_ROOT / "reports" / "productization" / "PR1_PIP_FREEZE.txt", False),
    EvidenceFile("db_fixture_readonly", REPO_ROOT / "reports" / "productization" / "PR4_DB_FIXTURE_READONLY_EVIDENCE.md", False),
    EvidenceFile("comment_mode_rules", REPO_ROOT / "docs" / "product" / "METADATA_PROVENANCE_RULES.md", False),
    EvidenceFile("sql_comparison", REPO_ROOT / "reports" / "productization" / "phase15_sql_comparison_engine.md", False),
    EvidenceFile("n8n_readiness", REPO_ROOT / "reports" / "productization" / "phase20_n8n_readiness_report.md", False),
)


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def git_commit(root: Path) -> str:
    try:
        return (
            subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True)
            .strip()
        )
    except Exception:
        return "unknown"


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def evidence_status(path: Path) -> str:
    return "present" if path.exists() else "missing"


def build_manifest(release_id: str, output_dir: Path, root: Path) -> dict[str, Any]:
    inputs: list[dict[str, Any]] = []
    missing_required: list[str] = []
    missing_optional: list[str] = []

    for item in EVIDENCE_FILES:
        status = evidence_status(item.path)
        target = "required" if item.required else "optional"
        inputs.append(
            {
                "name": item.name,
                "path": str(item.path.relative_to(root)),
                "status": status,
                "required": item.required,
            }
        )
        if status == "missing":
            if item.required:
                missing_required.append(str(item.path.relative_to(root)))
            else:
                missing_optional.append(str(item.path.relative_to(root)))

    summary_sources = {
        "pr0_pr7_index": str((root / "reports" / "productization" / "PR0_PR7_EVIDENCE_INDEX.md").relative_to(root)),
        "readiness_matrix": str((root / "reports" / "productization" / "PRODUCTION_READINESS_MATRIX.md").relative_to(root)),
        "risk_register": str((root / "reports" / "productization" / "PRODUCTION_RISK_REGISTER.md").relative_to(root)),
    }

    return {
        "release_id": release_id,
        "generated_at": iso_now(),
        "git_commit": git_commit(root),
        "output_dir": str(output_dir.relative_to(root)),
        "status": "complete" if not missing_required else "partial",
        "missing_required_evidence": missing_required,
        "missing_optional_evidence": missing_optional,
        "evidence_inputs": inputs,
        "summary_sources": summary_sources,
    }


def render_summary(manifest: dict[str, Any]) -> str:
    lines = [
        f"# Release Packet — {manifest['release_id']}",
        "",
        f"Generated at: {manifest['generated_at']}",
        f"Git commit: {manifest['git_commit']}",
        f"Status: {manifest['status']}",
        "",
        "## Included source evidence",
    ]
    for item in manifest["evidence_inputs"]:
        marker = "required" if item["required"] else "optional"
        lines.append(f"- {item['name']}: {item['path']} ({item['status']}, {marker})")
    lines.extend(
        [
            "",
            "## Missing evidence",
            *(f"- {item}" for item in (manifest["missing_required_evidence"] + manifest["missing_optional_evidence"]) or ["- none"]),
        ]
    )
    return "\n".join(lines) + "\n"


def render_known_limitations(manifest: dict[str, Any]) -> str:
    missing = manifest["missing_required_evidence"] + manifest["missing_optional_evidence"]
    lines = [
        "# Known Limitations",
        "",
        "- The packet only packages existing repo evidence; it does not generate new proof.",
        "- No product execution is performed by this script.",
        "- Missing evidence is reported explicitly rather than inferred.",
    ]
    if missing:
        lines.extend(["", "## Missing evidence", *[f"- {item}" for item in missing]])
    return "\n".join(lines) + "\n"


def render_support_matrix(root: Path) -> str:
    matrix = read_text(root / "reports" / "productization" / "PRODUCTION_READINESS_MATRIX.md")
    return (
        "# Support Matrix\n\n"
        "This packet reuses the repository readiness matrix as the support-level source of truth.\n\n"
        "Primary source: `reports/productization/PRODUCTION_READINESS_MATRIX.md`\n\n"
        "Selected support-level excerpts are preserved in the source document.\n\n"
        "## Source snapshot\n\n"
        "```text\n"
        + "\n".join(matrix.splitlines()[:40])
        + "\n```\n"
    )


def render_release_manifest(manifest: dict[str, Any]) -> str:
    return json.dumps(manifest, indent=2, sort_keys=True) + "\n"


def pack_release(release_id: str, output_root: Path = DEFAULT_OUTPUT_ROOT, root: Path = REPO_ROOT) -> Path:
    output_dir = output_root / release_id
    output_dir.mkdir(parents=True, exist_ok=True)

    manifest = build_manifest(release_id, output_dir, root)
    (output_dir / "release_manifest.json").write_text(render_release_manifest(manifest), encoding="utf-8")
    (output_dir / "release_summary.md").write_text(render_summary(manifest), encoding="utf-8")
    (output_dir / "known_limitations.md").write_text(render_known_limitations(manifest), encoding="utf-8")
    (output_dir / "support_matrix.md").write_text(render_support_matrix(root), encoding="utf-8")
    return output_dir


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release-id", required=True, help="Versioned release identifier, e.g. release-20260509")
    parser.add_argument(
        "--output-root",
        default=str(DEFAULT_OUTPUT_ROOT),
        help="Output directory root for release packets (default: reports/release)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    output_dir = pack_release(args.release_id, Path(args.output_root), REPO_ROOT)
    print(f"release packet written to {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
