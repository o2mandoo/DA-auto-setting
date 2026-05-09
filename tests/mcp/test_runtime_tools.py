from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "semantic_contracts"))
sys.path.insert(0, str(ROOT / "packages" / "semantic_registry"))
sys.path.insert(0, str(ROOT / "packages" / "semantic_mcp" / "src"))

from semantic_mcp.tools import explain_query_plan, validate_semantic_sql  # noqa: E402


class RuntimeMcpToolTests(unittest.TestCase):
    def test_explain_query_plan_exposes_ambiguity_gate_and_no_execution(self) -> None:
        response = explain_query_plan(
            "demo_company.revenue",
            "신규 고객 순매출",
            role="marketing_analyst",
            root=ROOT / "semantic_packs",
        )

        self.assertFalse(response["execution_allowed"])
        self.assertTrue(response["ambiguity_gate"]["requires_clarification"])
        self.assertIn("term.new_customer", response["plan"]["required_terms"])

    def test_validate_semantic_sql_runs_policy_and_semantic_verifiers(self) -> None:
        response = validate_semantic_sql(
            "demo_company.revenue",
            "월별 신규 고객 순매출",
            """
            SELECT DATE_TRUNC('month', payments.paid_at), SUM(payments.amount)
            FROM users JOIN payments ON users.user_id = payments.user_id
            WHERE payments.paid_at >= :start_date
              AND payments.paid_at < :end_date
              AND payments.status = 'PAID'
            GROUP BY 1
            """,
            role="marketing_analyst",
            root=ROOT / "semantic_packs",
        )

        self.assertFalse(response["execution_allowed"])
        self.assertTrue(response["policy_verdict"]["valid"])
        self.assertFalse(response["semantic_verdict"]["valid"])
        self.assertFalse(response["valid"])
        self.assertTrue(any("Wrong date basis" in error for error in response["semantic_verdict"]["errors"]))


if __name__ == "__main__":
    unittest.main()
