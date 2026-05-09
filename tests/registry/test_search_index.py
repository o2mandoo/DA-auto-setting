from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "semantic_contracts"))
sys.path.insert(0, str(ROOT / "packages" / "semantic_registry"))

from semantic_registry import CardRegistry, PackStore, SearchIndex, resolve_terms, search_cards  # noqa: E402


class SearchIndexTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.pack = PackStore(ROOT / "semantic_packs").load_pack("demo_company.revenue")
        cls.index = SearchIndex.from_pack(cls.pack)

    def test_search_finds_korean_metric_label(self) -> None:
        results = self.index.search_cards("순매출", limit=5)
        ids = [result.card_id for result in results]

        self.assertIn("metric.net_revenue", ids)
        self.assertTrue(all(result.score > 0 for result in results))

    def test_search_finds_english_business_term_alias(self) -> None:
        results = self.index.search_cards("new customer", card_types=["business_terms"], limit=5)

        self.assertEqual(results[0].card_id, "term.new_customer")
        self.assertEqual(results[0].card_type, "business_term")

    def test_search_can_filter_tables_columns_policies_and_queries(self) -> None:
        self.assertEqual(
            self.index.search_cards("Payments", card_types=["table"], limit=1)[0].card_id,
            "table.payments",
        )
        self.assertEqual(
            self.index.search_cards("refund_amount", card_types=["columns"], limit=1)[0].card_id,
            "column.payments.refund_amount",
        )
        self.assertEqual(
            self.index.search_cards("marketing_analyst", card_types=["policy"], limit=1)[0].card_id,
            "policy.marketing_safe_revenue",
        )
        self.assertEqual(
            self.index.search_cards("월별 신규 고객", card_types=["verified_queries"], limit=1)[0].card_id,
            "verified_query.monthly_new_customer_revenue",
        )

    def test_limit_and_blank_query_are_respected(self) -> None:
        self.assertEqual(self.index.search_cards("", limit=10), [])
        self.assertEqual(len(self.index.search_cards("revenue", limit=2)), 2)
        self.assertEqual(self.index.search_cards("revenue", limit=0), [])


    def test_resolve_terms_matches_id_label_and_alias(self) -> None:
        response = resolve_terms(["신규 고객", "net revenue", "missing term"], root=ROOT / "semantic_packs")

        resolved_ids = [term.term_id for term in response.resolved_terms]
        self.assertEqual(resolved_ids, ["term.new_customer", "term.net_revenue"])
        self.assertEqual(response.resolved_terms[0].sql_condition, "users.first_paid_at >= {start_date} AND users.first_paid_at < {end_date}")
        self.assertEqual(response.unresolved_terms, ["missing term"])


    def test_card_registry_resolve_terms_matches_id_label_and_alias(self) -> None:
        response = CardRegistry.from_pack(self.pack).resolve_terms(["신규 고객", "net revenue", "missing term"])

        self.assertEqual([term.term_id for term in response.resolved_terms], ["term.new_customer", "term.net_revenue"])
        self.assertEqual(response.unresolved_terms, ["missing term"])

    def test_resolve_terms_can_scope_to_pack_id(self) -> None:
        response = resolve_terms(["new_customer"], space_id="demo_company.revenue", root=ROOT / "semantic_packs")

        self.assertEqual([term.term_id for term in response.resolved_terms], ["term.new_customer"])

    def test_module_level_search_loads_local_packs(self) -> None:
        results = search_cards("net revenue", card_types=["metrics"], root=ROOT / "semantic_packs")
        ids = [result.card_id for result in results]

        self.assertIn("metric.net_revenue", ids)


if __name__ == "__main__":
    unittest.main()
