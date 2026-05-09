from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "semantic_contracts"))
sys.path.insert(0, str(ROOT / "packages" / "semantic_registry"))

from semantic_registry.runtime import DomainQueryPlanner, SqlDraftGenerator, SqlDraftSource  # noqa: E402
from semantic_registry.store import PackStore  # noqa: E402


class SqlGenerationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.pack_root = ROOT / "semantic_packs"
        cls.pack = PackStore(cls.pack_root).load_pack("demo_company.revenue")
        cls.planner = DomainQueryPlanner.from_packs([cls.pack])
        cls.generator = SqlDraftGenerator.from_packs([cls.pack])

    def test_verified_query_template_is_preferred_over_rule_sql(self) -> None:
        plan = self.planner.plan("월별 신규 고객 순매출을 보여줘", role="marketing_analyst")

        draft = self.generator.draft(plan, role="marketing_analyst")

        self.assertEqual(draft.source, SqlDraftSource.VERIFIED_QUERY_TEMPLATE)
        self.assertEqual(draft.selected_verified_query, "verified_query.monthly_new_customer_revenue")
        self.assertIn("users.first_paid_at >= {start_date}", draft.sql)
        self.assertIn("payments.status = 'PAID'", draft.sql)
        self.assertFalse(draft.execution_allowed)
        self.assertGreaterEqual(draft.confidence, 0.9)

    def test_ambiguous_plan_does_not_generate_sql(self) -> None:
        plan = self.planner.plan("신규 고객 순매출", role="marketing_analyst")

        draft = self.generator.draft(plan, role="marketing_analyst")

        self.assertIsNone(draft.sql)
        self.assertEqual(draft.source, SqlDraftSource.NONE)
        self.assertIn("sql_draft_not_allowed", draft.warnings)
        self.assertFalse(draft.execution_allowed)


if __name__ == "__main__":
    unittest.main()
