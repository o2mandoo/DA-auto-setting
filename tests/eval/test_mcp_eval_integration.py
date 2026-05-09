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

from semantic_mcp import inspect_registration_surface  # noqa: E402
from semantic_mcp.eval_helpers import (  # noqa: E402
    build_mcp_eval_bundle,
    build_preview_query_eval,
)


class McpEvalIntegrationTests(unittest.TestCase):
    def test_eval_bundle_uses_local_tool_functions_without_transport(self) -> None:
        with patch(
            "semantic_mcp.eval_helpers.preview_query",
            return_value={
                "tool_name": "preview_query",
                "available": True,
                "execution_allowed": False,
                "preview_allowed": True,
                "rows": [{"payment_id": "p001"}],
                "row_count": 1,
                "truncated": False,
                "warnings": ["mocked transport"],
                "limit": 2,
            },
        ):
            bundle = build_mcp_eval_bundle(
                space_id="demo_company.revenue",
                question="월별 신규 고객 순매출",
                sql="SELECT users.user_id, SUM(payments.amount) FROM users JOIN payments ON users.user_id = payments.user_id GROUP BY users.user_id",
                role="marketing_analyst",
                terms=["신규 고객", "net revenue"],
                pack_root=ROOT / "semantic_packs",
                fixture_root=ROOT / "examples" / "demo_data",
                max_rows=2,
            )

        self.assertFalse(bundle["execution_allowed"])
        self.assertFalse(bundle["transport_required"])
        self.assertIn("search_semantic_context", bundle)
        self.assertIn("resolve_business_terms", bundle)
        self.assertIn("plan_data_query", bundle)
        self.assertIn("validate_sql", bundle)
        self.assertIn("preview_query", bundle)
        self.assertTrue(bundle["preview_query"]["available"])
        self.assertEqual(bundle["preview_query"]["warnings"], ["mocked transport"])
        self.assertTrue(bundle["plan_data_query"]["required_terms"])
        self.assertTrue(bundle["validate_sql"]["valid"])
        self.assertIn("preview_query", inspect_registration_surface()["tools"])
        self.assertNotIn("execute_query", inspect_registration_surface()["tools"])

    def test_preview_eval_reports_explicit_fallback_when_preview_runtime_is_missing(self) -> None:
        with patch(
            "semantic_mcp.eval_helpers.preview_query",
            side_effect=RuntimeError("No preview runtime is installed; no preview fallback was run"),
        ):
            response = build_preview_query_eval(
                "demo_company.revenue",
                "SELECT payment_id FROM payments ORDER BY payment_id",
                role="marketing_analyst",
                pack_root=ROOT / "semantic_packs",
                fixture_root=ROOT / "examples" / "demo_data",
                max_rows=2,
            )

        self.assertFalse(response["available"])
        self.assertFalse(response["preview_allowed"])
        self.assertEqual(response["rows"], [])
        self.assertEqual(response["fallback"], "explicit_preview_runtime_unavailable")
        self.assertTrue(any("No preview fallback" in warning for warning in response["warnings"]))


if __name__ == "__main__":
    unittest.main()
