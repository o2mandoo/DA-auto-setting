from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "semantic_contracts"))
sys.path.insert(0, str(ROOT / "packages" / "semantic_registry"))

from semantic_registry.query_planner import QueryPlanner  # noqa: E402
from semantic_registry.runtime import AmbiguityGate, PolicyVerifier, SemanticVerifier  # noqa: E402
from semantic_registry.store import PackStore  # noqa: E402


class PolicySemanticVerifierTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.pack_root = ROOT / "semantic_packs"
        cls.pack = PackStore(cls.pack_root).load_pack("demo_company.revenue")
        cls.planner = QueryPlanner.from_pack(cls.pack)
        cls.policy = PolicyVerifier.from_packs([cls.pack])
        cls.semantic = SemanticVerifier.from_packs([cls.pack])

    def test_ambiguity_gate_requires_clarification_when_plan_has_reverse_questions(self) -> None:
        plan = self.planner.plan("신규 고객 순매출", role="marketing_analyst")

        verdict = AmbiguityGate().assess(plan)

        self.assertTrue(verdict["requires_clarification"])
        self.assertFalse(verdict["execution_allowed"])
        self.assertIn("rq.new_customer.date_basis", [item["id"] for item in verdict["ambiguities"]])

    def test_policy_verifier_blocks_policy_blocked_columns_without_execution(self) -> None:
        verdict = self.policy.verify_sql(
            "SELECT users.email FROM users",
            role="marketing_analyst",
        )

        self.assertEqual(verdict["verifier"], "policy")
        self.assertFalse(verdict["valid"])
        self.assertFalse(verdict["execution_allowed"])
        self.assertTrue(any("users.email" in error for error in verdict["errors"]))

    def test_semantic_verifier_accepts_new_customer_date_basis(self) -> None:
        plan = self.planner.plan("월별 신규 고객 순매출", role="marketing_analyst")
        sql = """
            SELECT DATE_TRUNC('month', users.first_paid_at), SUM(payments.amount)
            FROM users JOIN payments ON users.user_id = payments.user_id
            WHERE users.first_paid_at >= :start_date
              AND users.first_paid_at < :end_date
              AND payments.status = 'PAID'
            GROUP BY 1
        """

        verdict = self.semantic.verify_sql(sql, plan=plan, role="marketing_analyst")

        self.assertTrue(verdict["valid"], verdict)
        self.assertFalse(verdict["execution_allowed"])

    def test_missing_required_business_term_condition_is_rejected(self) -> None:
        plan = self.planner.plan("월별 신규 고객 순매출", role="marketing_analyst")
        sql = """
            SELECT DATE_TRUNC('month', payments.paid_at), SUM(payments.amount)
            FROM users JOIN payments ON users.user_id = payments.user_id
            WHERE payments.status = 'PAID'
            GROUP BY 1
        """

        verdict = self.semantic.verify_sql(sql, plan=plan, role="marketing_analyst")

        self.assertFalse(verdict["valid"], verdict)
        self.assertFalse(verdict["execution_allowed"])
        self.assertTrue(any("missing required business-term condition columns" in error for error in verdict["errors"]))

    def test_wrong_date_basis_is_caught_by_semantic_verifier(self) -> None:
        plan = self.planner.plan("월별 신규 고객 순매출", role="marketing_analyst")
        wrong_sql = """
            SELECT DATE_TRUNC('month', payments.paid_at), SUM(payments.amount)
            FROM users JOIN payments ON users.user_id = payments.user_id
            WHERE payments.paid_at >= :start_date
              AND payments.paid_at < :end_date
              AND payments.status = 'PAID'
            GROUP BY 1
        """

        verdict = self.semantic.verify_sql(wrong_sql, plan=plan, role="marketing_analyst")

        self.assertFalse(verdict["valid"])
        self.assertFalse(verdict["execution_allowed"])
        self.assertTrue(any("Wrong date basis" in error for error in verdict["errors"]))
        self.assertTrue(any("users.first_paid_at" in error for error in verdict["errors"]))


if __name__ == "__main__":
    unittest.main()
