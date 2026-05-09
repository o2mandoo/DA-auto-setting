from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "semantic_contracts"))
sys.path.insert(0, str(ROOT / "packages" / "semantic_registry"))

from semantic_registry.runtime import DomainQueryPlanner, plan_domain_query  # noqa: E402
from semantic_registry.store import PackStore  # noqa: E402


class DomainQueryPlannerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.pack_root = ROOT / "semantic_packs"
        cls.pack = PackStore(cls.pack_root).load_pack("demo_company.revenue")
        cls.planner = DomainQueryPlanner.from_packs([cls.pack])

    def test_plans_new_customer_net_revenue_with_verified_template_preference(self) -> None:
        plan = self.planner.plan("월별 신규 고객 순매출을 보여줘", role="marketing_analyst")

        self.assertEqual(plan.required_terms, ["term.new_customer"])
        self.assertEqual(plan.required_metrics, ["metric.net_revenue"])
        self.assertEqual(plan.candidate_tables, ["users", "payments"])
        self.assertEqual(plan.join_recipes, ["join.users_payments"])
        self.assertEqual(plan.selected_verified_query, "verified_query.monthly_new_customer_revenue")
        self.assertIn("verified_query.monthly_new_customer_revenue", plan.used_cards)
        self.assertGreaterEqual(plan.confidence, 0.85)
        self.assertFalse(plan.execution_allowed if hasattr(plan, "execution_allowed") else False)

    def test_ambiguous_question_does_not_allow_sql_draft(self) -> None:
        plan = self.planner.plan("신규 고객 순매출", role="marketing_analyst")

        self.assertFalse(plan.sql_draft_allowed)
        self.assertIn("clarification_required_before_sql_draft", plan.warnings)

    def test_module_api_loads_space_from_pack_root(self) -> None:
        plan = plan_domain_query(
            "demo_company.revenue",
            "월별 신규 고객 순매출",
            role="marketing_analyst",
            pack_root=self.pack_root,
        )

        self.assertEqual(plan.selected_verified_query, "verified_query.monthly_new_customer_revenue")
        self.assertFalse(plan.execution_allowed if hasattr(plan, "execution_allowed") else False)


if __name__ == "__main__":
    unittest.main()
