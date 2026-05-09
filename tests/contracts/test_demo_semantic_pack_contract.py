from __future__ import annotations

import unittest

from contract_helpers import (
    assert_references_resolve,
    assert_required_card_lists,
    by_id,
    load_demo_semantic_pack,
)


class DemoSemanticPackContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.pack = load_demo_semantic_pack()

    def test_top_level_metadata_and_card_lists_exist(self) -> None:
        pack = self.pack
        self.assertEqual(pack["id"], "demo_company.revenue")
        self.assertEqual(pack["version"], "0.1.0")
        self.assertIn(pack["status"], {"draft", "reviewed", "approved"})
        self.assertEqual(pack["locale"], "ko-KR")
        self.assertTrue(pack["owners"])
        self.assertTrue(pack["source_refs"])
        self.assertTrue(pack["spaces"])
        assert_required_card_lists(pack)

    def test_table_cards_cover_required_phase0_fixture_entities(self) -> None:
        tables = by_id(self.pack["tables"])
        self.assertGreaterEqual(
            {table["physical_name"] for table in tables.values()},
            {"users", "payments", "campaigns"},
        )
        self.assertEqual(tables["table.users"]["role"], "dimension")
        self.assertEqual(tables["table.payments"]["role"], "fact")
        self.assertEqual(tables["table.campaigns"]["role"], "dimension")
        for table in tables.values():
            self.assertEqual(table["space_id"], "revenue")
            self.assertIn(table["status"], {"draft", "confirmed"})
            self.assertGreaterEqual(table["confidence"], 0.5)
            self.assertTrue(table["columns"])

    def test_required_phase0_entities_are_present(self) -> None:
        self.assertIn("metric.net_revenue", by_id(self.pack["metrics"]))
        self.assertIn("term.new_customer", by_id(self.pack["business_terms"]))
        self.assertIn("join.users_payments", by_id(self.pack["join_recipes"]))
        self.assertIn("verified_query.monthly_new_customer_revenue", by_id(self.pack["verified_queries"]))
        policy_roles = {role for policy in self.pack["policies"] for role in policy.get("applies_to", {}).get("roles", [])}
        self.assertIn("marketing_analyst", policy_roles)


    def test_demo_pack_validates_with_contract_package_when_available(self) -> None:
        try:
            import sys
            from pathlib import Path
            sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "semantic_contracts"))
            from semantic_contracts import validate_semantic_pack  # type: ignore
        except Exception as exc:  # pragma: no cover - dependency-free environments
            self.skipTest(f"semantic_contracts dependencies unavailable: {exc}")

        payload = {"semantic_pack": self.pack}
        result = validate_semantic_pack(payload)
        self.assertTrue(result.valid, [error.message for error in result.errors])

    def test_references_and_ids_are_internally_consistent(self) -> None:
        assert_references_resolve(self.pack)
