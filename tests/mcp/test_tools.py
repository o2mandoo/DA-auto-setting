from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "semantic_contracts"))
sys.path.insert(0, str(ROOT / "packages" / "semantic_registry"))
sys.path.insert(0, str(ROOT / "packages" / "semantic_mcp" / "src"))

from semantic_mcp import (  # noqa: E402
    list_semantic_spaces,
    plan_data_query,
    record_feedback,
    resolve_business_terms,
    search_semantic_context,
    validate_sql,
)


class SemanticMcpToolTests(unittest.TestCase):
    def test_list_semantic_spaces_returns_demo_pack_summary(self) -> None:
        response = list_semantic_spaces(ROOT / "semantic_packs")
        spaces_by_id = {space["space_id"]: space for space in response["spaces"]}

        # Phase 4 may generate additional draft packs in the same semantic_packs
        # root, so this contract checks the canonical demo pack by id rather
        # than depending on discovery order.
        self.assertIn("demo_company.revenue", spaces_by_id)
        self.assertEqual(spaces_by_id["demo_company.revenue"]["status"], "approved")

    def test_search_semantic_context_scopes_to_pack_and_normalizes_scores(self) -> None:
        response = search_semantic_context(
            "demo_company.revenue",
            "순매출",
            filters={"card_types": ["metrics"], "limit": 3},
            root=ROOT / "semantic_packs",
        )

        self.assertGreaterEqual(len(response["results"]), 1)
        self.assertEqual(response["results"][0]["card_id"], "metric.net_revenue")
        self.assertLessEqual(response["results"][0]["score"], 1.0)
        missing = search_semantic_context("missing.pack", "순매출", root=ROOT / "semantic_packs")
        self.assertEqual(missing["results"], [])
        self.assertTrue(any("Unknown semantic space" in warning for warning in missing["warnings"]))

    def test_resolve_business_terms_matches_id_label_and_alias(self) -> None:
        response = resolve_business_terms(
            "demo_company.revenue",
            ["신규 고객", "net revenue", "missing"],
            root=ROOT / "semantic_packs",
        )

        self.assertEqual([item["term_id"] for item in response["resolved_terms"]], ["term.new_customer", "term.net_revenue"])
        self.assertEqual(response["unresolved_terms"], ["missing"])

    def test_plan_data_query_is_validation_only_and_pack_backed(self) -> None:
        response = plan_data_query(
            "demo_company.revenue",
            "월별 신규 고객 순매출",
            role="marketing_analyst",
            root=ROOT / "semantic_packs",
        )

        self.assertFalse(response["execution_allowed"])
        self.assertIn("term.new_customer", response["required_terms"])
        self.assertIn("metric.net_revenue", response["required_metrics"])
        self.assertIn("payments", response["candidate_tables"])
        self.assertIn("join.users_payments", response["join_recipes"])
        self.assertTrue(any("SQL execution is out of scope" in note for note in response["policy_notes"]))

    def test_validate_sql_blocks_non_select_multi_statement_and_pii(self) -> None:
        safe = validate_sql(
            "SELECT users.user_id, SUM(payments.amount) FROM users JOIN payments ON users.user_id = payments.user_id GROUP BY users.user_id;",
            space_id="demo_company.revenue",
            role="marketing_analyst",
            root=ROOT / "semantic_packs",
        )
        blocked = validate_sql(
            "SELECT users.email FROM users",
            space_id="demo_company.revenue",
            role="marketing_analyst",
            root=ROOT / "semantic_packs",
        )
        multi = validate_sql(
            "SELECT users.user_id FROM users; SELECT payments.amount FROM payments",
            space_id="demo_company.revenue",
            role="marketing_analyst",
            root=ROOT / "semantic_packs",
        )
        destructive = validate_sql(
            "DELETE FROM users",
            space_id="demo_company.revenue",
            role="marketing_analyst",
            root=ROOT / "semantic_packs",
        )

        self.assertTrue(safe["valid"], safe)
        self.assertFalse(safe["execution_allowed"])
        self.assertFalse(blocked["valid"])
        self.assertTrue(any("users.email" in error for error in blocked["errors"]))
        self.assertFalse(multi["valid"])
        self.assertFalse(destructive["valid"])

    def test_record_feedback_appends_local_jsonl_and_rejects_pii(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            response = record_feedback(
                "demo_company.revenue",
                "confirmation",
                "net revenue definition is correct",
                card_id="metric.net_revenue",
                source="unit-test",
                feedback_root=Path(tmp) / "feedback",
            )

            self.assertTrue(response["receipt"]["accepted"])
            self.assertTrue(response["receipt"]["stored"])
            self.assertTrue((Path(tmp) / "feedback" / "demo_company.revenue.jsonl").exists())

            with self.assertRaises(ValueError):
                record_feedback(
                    "demo_company.revenue",
                    "correction",
                    "contact user@example.com",
                    feedback_root=Path(tmp) / "feedback",
                )


if __name__ == "__main__":
    unittest.main()
