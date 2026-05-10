#!/usr/bin/env python3
"""Fail if local-only validation datasets or dataset inventories are tracked by git."""

from __future__ import annotations

import subprocess
import sys
PROHIBITED_PREFIXES = (
    "docs/reference/test_datasets/",
    "semantic_packs/sinagong_tableau_2026/",
    "reports/benchmarks/",
)

PROHIBITED_FILES = {
    "docs/execution/VALIDATION_DATASETS.md",
    "docs/execution/DATASET_BENCHMARKS.md",
    "eval/datasets/tableau_superstore.yaml",
    "eval/datasets/sinagong_tableau_2026.yaml",
    "reports/final/20_domain_benchmark_summary.json",
    "reports/final/20_domain_benchmark_summary.md",
    "reports/final/final_capability_matrix.md",
    "reports/final/known_failure_patterns.md",
    "reports/final/demo_narrative.md",
}


def tracked_files() -> list[str]:
    completed = subprocess.run(
        ["git", "ls-files", "-z"],
        check=True,
        capture_output=True,
        text=False,
    )
    return [item.decode("utf-8") for item in completed.stdout.split(b"\0") if item]


def main() -> int:
    violations = []
    for path in tracked_files():
        if path in PROHIBITED_FILES or any(path.startswith(prefix) for prefix in PROHIBITED_PREFIXES):
            violations.append(path)

    if violations:
        print("ERROR: local-only test datasets or dataset inventories are tracked by git.", file=sys.stderr)
        print("These files must stay local/ignored; use aggregate redacted evidence instead.", file=sys.stderr)
        for path in violations:
            print(f"- {path}", file=sys.stderr)
        return 1

    print("dataset git guard: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
