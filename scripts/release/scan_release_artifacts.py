#!/usr/bin/env python3
"""Fail-closed scan for release artifacts and n8n workflow safety.

This script codifies the release artifact scans that were previously run as
manual `rg` commands during PR-7 verification. It is CI-safe, deterministic, and
reports every finding instead of falling back to a warning-only path.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parents[2]

RELEASE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("openai_key", re.compile(r"sk-[A-Za-z0-9]{20,}")),
    ("aws_access_key_id", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("password_in_url", re.compile(r"password@", re.IGNORECASE)),
    ("client_secret", re.compile(r"client_secret", re.IGNORECASE)),
    (
        "named_secret_assignment",
        re.compile(
            r"(?i)\b(password|secret|token|api[_-]?key|client_secret|aws_secret_access_key)\b\s*[:=]\s*[^\s,'\"`]+"
        ),
    ),
    ("bearer_token", re.compile(r"Bearer\s+[A-Za-z0-9._~+/=-]+", re.IGNORECASE)),
    ("postgres_dsn", re.compile(r"\bpostgres(?:ql)?://", re.IGNORECASE)),
    ("mysql_dsn", re.compile(r"\bmysql://", re.IGNORECASE)),
    ("local_user_path", re.compile(r"/Users/[^\s\"'`<>]+")),
    ("worker_id", re.compile(r"\bworker-\d+\b")),
    ("leader_id", re.compile(r"\bleader-fixed\b")),
    ("email", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")),
)

WORKFLOW_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("postgres_dsn", re.compile(r"\bpostgres(?:ql)?://", re.IGNORECASE)),
    ("mysql_dsn", re.compile(r"\bmysql://", re.IGNORECASE)),
    ("mongodb_dsn", re.compile(r"\bmongodb://", re.IGNORECASE)),
    ("password_literal", re.compile(r"password", re.IGNORECASE)),
    ("secret_literal", re.compile(r"secret", re.IGNORECASE)),
    ("token_literal", re.compile(r"token", re.IGNORECASE)),
    ("api_key_literal", re.compile(r"api[_-]?key", re.IGNORECASE)),
    ("authorization_literal", re.compile(r"authorization", re.IGNORECASE)),
    ("bearer_literal", re.compile(r"bearer\s+", re.IGNORECASE)),
    ("sql_connector_node", re.compile(r"n8n-nodes-base\.(postgres|mysql|mssql|sqlite|mariadb|oracledb|snowflake)", re.IGNORECASE)),
)

EXECUTE_QUERY_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("execute_query_def", re.compile(r"def\s+execute_query\b")),
    ("execute_query_call", re.compile(r"execute_query\(")),
    ("execute_query_route", re.compile(r"/api/" + "execute_query")),
)


@dataclass(frozen=True)
class Finding:
    category: str
    pattern: str
    path: str
    line: int
    text: str

    def to_dict(self) -> dict[str, object]:
        return {
            "category": self.category,
            "pattern": self.pattern,
            "path": self.path,
            "line": self.line,
            "text": self.text,
        }


def iter_text_files(root: Path) -> Iterable[Path]:
    if not root.exists():
        raise FileNotFoundError(f"scan root does not exist: {root}")
    for path in sorted(root.rglob("*")):
        if path.is_file():
            yield path


def display_path(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def scan_text_files(root: Path, patterns: tuple[tuple[str, re.Pattern[str]], ...], category: str) -> list[Finding]:
    findings: list[Finding] = []
    for path in iter_text_files(root):
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            continue
        for lineno, line in enumerate(lines, start=1):
            for name, pattern in patterns:
                if pattern.search(line):
                    findings.append(Finding(category, name, display_path(path), lineno, line.strip()[:240]))
    return findings


def scan_execution_surface(roots: Iterable[Path]) -> list[Finding]:
    findings: list[Finding] = []
    for root in roots:
        if not root.exists():
            continue
        for path in iter_text_files(root):
            if ".git" in path.parts or ".omx" in path.parts:
                continue
            try:
                lines = path.read_text(encoding="utf-8").splitlines()
            except UnicodeDecodeError:
                continue
            for lineno, line in enumerate(lines, start=1):
                # Documentation/tests may mention execute_query as a forbidden term. Only implementation-like
                # definitions, calls, or route strings fail this scan.
                for name, pattern in EXECUTE_QUERY_PATTERNS:
                    if pattern.search(line):
                        findings.append(Finding("execute_query_surface", name, display_path(path), lineno, line.strip()[:240]))
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release-dir", default="reports/release/release-test")
    parser.add_argument("--workflow-dir", default="n8n/workflows")
    parser.add_argument("--json", action="store_true", help="Print machine-readable result")
    args = parser.parse_args()

    release_dir = (REPO_ROOT / args.release_dir).resolve()
    workflow_dir = (REPO_ROOT / args.workflow_dir).resolve()

    findings: list[Finding] = []
    findings.extend(scan_text_files(release_dir, RELEASE_PATTERNS, "release_artifact_sensitive_content"))
    findings.extend(scan_text_files(workflow_dir, WORKFLOW_PATTERNS, "n8n_workflow_unsafe_content"))
    findings.extend(scan_execution_surface([REPO_ROOT / "packages", REPO_ROOT / "scripts", REPO_ROOT / "n8n", REPO_ROOT / "tests"]))

    result = {
        "status": "failed" if findings else "passed",
        "release_dir": display_path(release_dir),
        "workflow_dir": display_path(workflow_dir),
        "finding_count": len(findings),
        "findings": [finding.to_dict() for finding in findings],
    }
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    elif findings:
        for finding in findings:
            print(f"{finding.category}:{finding.pattern}:{finding.path}:{finding.line}: {finding.text}")
    else:
        print("release artifact scan: PASS")
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
