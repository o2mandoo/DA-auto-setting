#!/usr/bin/env python3
"""Print and validate the repository's clone-ready setup path.

This helper is intentionally offline-safe: it only checks for local docs and
template files and prints the canonical setup commands for the repository.
"""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    env_example = ROOT / ".env.example"
    setup_doc = ROOT / "docs" / "setup" / "DEVELOPMENT.md"

    missing = [path for path in (env_example, setup_doc) if not path.exists()]
    if missing:
        for path in missing:
            print(f"missing: {path.relative_to(ROOT)}")
        return 1

    print("clone-ready setup checks: PASS")
    print(f"- found {env_example.relative_to(ROOT)}")
    print(f"- found {setup_doc.relative_to(ROOT)}")
    print()
    print("canonical local setup commands:")
    print("  cp .env.example .env")
    print(
        "  export PYTHONPATH=packages/semantic_contracts:packages/semantic_builder/src:"
        "packages/semantic_registry:packages/semantic_mcp/src:/tmp/semantic-data-context-deps"
    )
    print("  python3 scripts/demo/run_local_demo.py")
    print("  python3 -m unittest tests.builder.test_semantic_inference_pipeline -v")
    print("  python3 -m unittest discover -s tests/security -v")
    print("  python3 -m unittest discover -s tests/registry -v")
    print("  python3 -m unittest discover -s tests/mcp -v")
    print()
    print("optional paths:")
    print("  python3 -m unittest tests.integration.test_weaviate_live_optional -v")
    print("  use SEMANTIC_POSTGRES_* only for read-only fixture scanning")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
