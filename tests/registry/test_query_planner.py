from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "semantic_contracts"))
sys.path.insert(0, str(ROOT / "packages" / "semantic_registry"))

from semantic_contracts.mcp_tool_contracts import PlanDataQueryResponse  # noqa: E402
from semantic_registry.query_planner import QueryPlanner, plan_data_query  # noqa: E402
from semantic_registry.store import PackStore  # noqa: E402


class QueryPlannerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.pack_root = ROOT / "semantic_packs"
        cls.pack = PackStore(cls.pack_root).load_pack("demo_company.revenue")
        cls.planner = QueryPlanner.from_pack(cls.pack)

    def test_korean_new_customer_net_revenue_question_returns_structured_plan(self) -> None:
        response = self.planner.plan("지난달 신규 고객 순매출을 보여줘", role="marketing_analyst")

        self.assertIsInstance(response, PlanDataQueryResponse)
        self.assertEqual(response.intent, "semantic_context_query_plan")
        self.assertFalse(response.execution_allowed)
        self.assertEqual(response.required_terms, ["term.new_customer"])
        self.assertEqual(response.required_metrics, ["metric.net_revenue"])
        self.assertEqual(response.candidate_tables, ["users", "payments"])
        self.assertEqual(response.join_recipes, ["join.users_payments"])
        self.assertIn("users.first_paid_at >= {start_date} AND users.first_paid_at < {end_date}", response.filters)
        self.assertIn("payments.status = 'PAID'", response.filters)
        self.assertTrue(any("SQL execution is out of scope" in note for note in response.policy_notes))

    def test_plan_includes_pack_reverse_questions_as_ambiguities(self) -> None:
        response = self.planner.plan("신규 고객 순매출", role="marketing_analyst")

        ambiguity_ids = [ambiguity.id for ambiguity in response.ambiguities]
        self.assertIn("rq.new_customer.date_basis", ambiguity_ids)
        self.assertIn("rq.net_revenue.refund_timing", ambiguity_ids)

    def test_role_policy_filters_disallowed_candidate_tables(self) -> None:
        # Unknown roles have no matching allow-list policy in the demo pack; the
        # planner therefore keeps semantic candidates but emits no role notes.
        unknown_role_response = self.planner.plan("신규 고객 순매출", role="unknown_role")
        analyst_response = self.planner.plan("신규 고객 순매출", role="marketing_analyst")

        self.assertEqual(unknown_role_response.candidate_tables, ["users", "payments"])
        self.assertEqual(unknown_role_response.policy_notes, [])
        self.assertEqual(analyst_response.candidate_tables, ["users", "payments"])
        self.assertTrue(analyst_response.policy_notes)

    def test_module_level_plan_data_query_loads_space_from_actual_registry_package_path(self) -> None:
        response = plan_data_query(
            "demo_company.revenue",
            "월별 신규 고객 순매출",
            role="marketing_analyst",
            root=self.pack_root,
        )

        self.assertEqual(response.required_terms, ["term.new_customer"])
        self.assertIn("metric.net_revenue", response.required_metrics)
        self.assertFalse(response.execution_allowed)

    def test_unknown_question_returns_empty_validation_only_plan(self) -> None:
        response = self.planner.plan("완전히 새로운 질문", role="marketing_analyst")

        self.assertEqual(response.required_terms, [])
        self.assertEqual(response.required_metrics, [])
        self.assertEqual(response.candidate_tables, [])
        self.assertEqual(response.join_recipes, [])
        self.assertFalse(response.execution_allowed)


if __name__ == "__main__":
    unittest.main()
