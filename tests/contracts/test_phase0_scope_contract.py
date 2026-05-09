from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
BUILDER_PACKAGE_DIR = ROOT / "packages" / "semantic_builder"
FORBIDDEN_BUILDER_IMPORTS = (
    # Phase 4 authorizes local file-input Builder code only; external runtime
    # surfaces remain out of scope for safety and reproducibility.
    "mcp",
    "psycopg",
    "psycopg2",
    "pymysql",
    "mysql",
    "cx_Oracle",
    "oracledb",
    "sqlalchemy",
    "openai",
    "anthropic",
    "chromadb",
    "faiss",
    "weaviate",
)


class Phase0ScopeContractTest(unittest.TestCase):
    def test_builder_does_not_introduce_forbidden_runtime_integrations(self) -> None:
        if not BUILDER_PACKAGE_DIR.exists():
            return

        forbidden_hits: list[tuple[Path, str]] = []
        for path in BUILDER_PACKAGE_DIR.rglob("*.py"):
            if "__pycache__" in path.parts:
                continue
            text = path.read_text(encoding="utf-8")
            for package_name in FORBIDDEN_BUILDER_IMPORTS:
                import_needles = (f"import {package_name}", f"from {package_name}")
                if any(needle in text for needle in import_needles):
                    forbidden_hits.append((path, package_name))

        self.assertEqual(
            forbidden_hits,
            [],
            "Builder may only use local file inputs in this phase; no MCP, DB, LLM, or VDB imports",
        )

    def test_no_execute_query_runtime_exists(self) -> None:
        runtime_hits: list[Path] = []
        for root in (ROOT / "packages", ROOT / "tests"):
            if not root.exists():
                continue
            for path in root.rglob("*.py"):
                text = path.read_text(encoding="utf-8")
                needle_def = "def " + "execute_query"
                needle_call = "execute" + "_query("
                if needle_def in text or needle_call in text:
                    runtime_hits.append(path)
        self.assertEqual(runtime_hits, [], "Current phase must not define or call execute_query")
