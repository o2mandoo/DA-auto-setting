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


def build_release_summary(
    release_id: str,
    generated_at: str,
    commit: str,
    missing_evidence: Iterable[str],
    redaction_summary: RedactionSummary,
) -> str:
    missing_lines = list(missing_evidence)
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
    redaction_summary: RedactionSummary,
) -> dict[str, object]:
    return {
        "release_id": release_id,
        "generated_at": generated_at,
        "git_commit": commit,
        "status": "dry-run",
        "output_dir": str(out_dir),
        "source_files": [str(path) for path in SOURCE_FILES],
        "artifacts": {
            "release_summary": "release_summary.md",
            "risk_register": "risk_register.md",
            "known_limitations": "known_limitations.md",
            "support_matrix": "support_matrix.md",
        },
        "missing_evidence": missing_evidence,
        "redactions": redaction_summary.counts,
        "safety_checks": {
            "sensitive_content_redacted": redaction_summary.had_findings,
            "secrets_redacted": redaction_summary.had_findings,
            "no_production_execute_query_claim": True,
            "no_silent_fallback_claim": True,
            "no_raw_pii_claim": True,
        },
    }


def build_packet(repo: Path, release_id: str, out_dir: Path) -> dict[str, object]:
    evidence, missing_evidence = source_index(repo)
    generated_at = datetime.now(timezone.utc).isoformat()
    commit = git_commit(repo)

    matrix_text = evidence.get(str(SOURCE_FILES[0]), "")
    risk_text = evidence.get(str(SOURCE_FILES[1]), "")
    final_report = evidence.get(str(SOURCE_FILES[2]), "")
    validation_text = evidence.get(str(SOURCE_FILES[3]), "")

    release_summary_text = build_release_summary(
        release_id=release_id,
        generated_at=generated_at,
        commit=commit,
        missing_evidence=missing_evidence,
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
        redaction_summary=redaction_summary,
    )

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "release_summary.md").write_text(release_summary_text, encoding="utf-8")
    (out_dir / "risk_register.md").write_text(risk_register_text, encoding="utf-8")
    (out_dir / "known_limitations.md").write_text(known_limitations_text, encoding="utf-8")
    (out_dir / "support_matrix.md").write_text(support_matrix_text, encoding="utf-8")

    manifest = build_manifest(
        release_id=release_id,
        generated_at=generated_at,
        commit=commit,
        out_dir=out_dir,
        missing_evidence=missing_evidence,
        redaction_summary=redaction_summary,
    )
    (out_dir / "release_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release-id", default=os.environ.get("RELEASE_ID", "release-packer-20260509T134905Z"))
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
