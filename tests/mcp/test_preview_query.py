from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import ModuleType
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "semantic_contracts"))
sys.path.insert(0, str(ROOT / "packages" / "semantic_registry"))
sys.path.insert(0, str(ROOT / "packages" / "semantic_mcp" / "src"))

if "semantic_registry.runtime" not in sys.modules:
    runtime_stub = ModuleType("semantic_registry.runtime")

    class _RuntimeGateStub:
        def __init__(self, *args, **kwargs) -> None:  # pragma: no cover - collection shim only
            pass

        @classmethod
        def from_packs(cls, *args, **kwargs):  # pragma: no cover - collection shim only
            return cls()

        def assess(self, *args, **kwargs):  # pragma: no cover - collection shim only
            return {"valid": False, "execution_allowed": False}

        def verify_sql(self, *args, **kwargs):  # pragma: no cover - collection shim only
            return {"valid": False, "execution_allowed": False}

    runtime_stub.AmbiguityGate = _RuntimeGateStub
    runtime_stub.PolicyVerifier = _RuntimeGateStub
    runtime_stub.SemanticVerifier = _RuntimeGateStub
    sys.modules["semantic_registry.runtime"] = runtime_stub

from semantic_mcp import inspect_registration_surface, preview_query  # noqa: E402
from semantic_mcp.tools.preview_query import PreviewRuntimeUnavailable  # noqa: E402


class PreviewQueryMcpToolTests(unittest.TestCase):
    def test_preview_query_is_registered_without_general_execution_tool(self) -> None:
        surface = inspect_registration_surface()

        self.assertIn("preview_query", surface["tools"])
        self.assertNotIn("execute_query", surface["tools"])

    def test_preview_query_requires_space_role_and_sql(self) -> None:
        for kwargs in (
            {"space_id": "", "sql": "SELECT 1", "role": "marketing_analyst"},
            {"space_id": "demo_company.revenue", "sql": "", "role": "marketing_analyst"},
            {"space_id": "demo_company.revenue", "sql": "SELECT 1", "role": ""},
        ):
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(ValueError):
                    preview_query(**kwargs)

    def test_mcp_preview_query_uses_internal_validation_and_explicit_row_limit(self) -> None:
        calls = []

        def fake_runner(**kwargs):
            calls.append(kwargs)
            return {
                "status": "ok",
                "valid": True,
                "preview_allowed": True,
                "columns": ["payment_id", "amount"],
                "rows": [{"payment_id": "p001", "amount": 10}, {"payment_id": "p002", "amount": 20}],
                "row_count": 2,
                "truncated": True,
                "audit_record": {"status": "success"},
            }

        with patch("semantic_mcp.tools.preview_query._load_registry_preview_query", return_value=(fake_runner, None)):
            response = preview_query(
                "demo_company.revenue",
                "SELECT payment_id, amount FROM payments ORDER BY payment_id",
                role="marketing_analyst",
                root=ROOT / "semantic_packs",
                fixture_root=ROOT / "examples" / "demo_data",
                max_rows=2,
            )

        self.assertTrue(response["valid"], response)
        self.assertTrue(response["preview_allowed"])
        self.assertTrue(response["limit_added"])
        self.assertEqual(response["limit"], 2)
        self.assertEqual(response["row_count"], 2)
        self.assertTrue(response["truncated"])
        self.assertEqual(response["execution_target"], "local_fixture_only")
        self.assertFalse(response["execution_allowed"])
        self.assertFalse(response["production_execution_allowed"])
        self.assertEqual(calls[0]["space_id"], "demo_company.revenue")
        self.assertEqual(calls[0]["role"], "marketing_analyst")
        self.assertEqual(calls[0]["max_rows"], 2)
        self.assertTrue(calls[0]["require_validation"])

    def test_preview_query_delegates_to_execution_runtime_with_validation_forced(self) -> None:
        calls = []

        def fake_runner(**kwargs):
            calls.append(kwargs)
            return {
                "status": "ok",
                "valid": True,
                "preview_allowed": True,
                "columns": ["payment_id"],
                "rows": [{"payment_id": "p001"}, {"payment_id": "p002"}],
                "row_count": 2,
                "truncated": True,
                "audit_record": {"status": "success"},
            }

        with patch("semantic_mcp.tools.preview_query._load_registry_preview_query", return_value=(fake_runner, None)):
            response = preview_query(
                "demo_company.revenue",
                "SELECT payment_id FROM payments ORDER BY payment_id",
                role="marketing_analyst",
                root=ROOT / "semantic_packs",
                max_rows=2,
                data_root=ROOT / "examples" / "demo_data",
                audit_root=ROOT / "runtime" / "mcp_preview_test_audit",
            )

        self.assertEqual(response["tool_name"], "preview_query")
        self.assertTrue(response["truncated"])
        self.assertEqual(response["row_count"], 2)
        self.assertFalse(response["production_execution_allowed"])
        self.assertEqual(calls[0]["space_id"], "demo_company.revenue")
        self.assertEqual(calls[0]["role"], "marketing_analyst")
        self.assertEqual(calls[0]["max_rows"], 2)
        self.assertTrue(calls[0]["require_validation"])

    def test_missing_registry_preview_runtime_reports_no_fallback(self) -> None:
        with patch(
            "semantic_mcp.tools.preview_query._load_registry_preview_query",
            side_effect=PreviewRuntimeUnavailable("No Registry preview runtime is available; no MCP fallback preview was run"),
        ):
            response = preview_query("demo_company.revenue", "SELECT payment_id FROM payments", role="marketing_analyst")

        self.assertEqual(response["status"], "error")
        self.assertFalse(response["preview_allowed"])
        self.assertFalse(response["truncated"])
        self.assertEqual(response["rows"], [])
        self.assertTrue(any("no fallback preview" in warning for warning in response["warnings"]))


if __name__ == "__main__":
    unittest.main()
