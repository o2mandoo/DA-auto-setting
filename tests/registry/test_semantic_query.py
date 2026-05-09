from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "semantic_contracts"))
sys.path.insert(0, str(ROOT / "packages" / "semantic_registry"))

from semantic_registry.store import PackStore  # noqa: E402
from semantic_registry.retrieval import analyze_semantic_query  # noqa: E402


class SemanticQueryUnderstandingTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.pack = PackStore(ROOT / "semantic_packs").load_pack("demo_company.revenue")

    def test_aliases_terms_metrics_patterns_and_questions_are_explained(self) -> None:
        understanding = analyze_semantic_query([self.pack], "첫 결제 고객의 net revenue")
        payload = understanding.as_dict()

        self.assertIn("term.new_customer", [item["card_id"] for item in payload["matched_terms"]])
        self.assertIn("term.net_revenue", [item["card_id"] for item in payload["matched_terms"]])
        self.assertIn("metric.net_revenue", [item["card_id"] for item in payload["matched_metrics"]])
        self.assertIn(
            {"card_id": "term.new_customer", "alias": "첫 결제 고객"},
            payload["aliases_used"],
        )
        self.assertIn(
            "verified_query.monthly_new_customer_revenue",
            [item["card_id"] for item in payload["verified_query_matches"]],
        )
        self.assertIn("rq.new_customer.date_basis", [item["card_id"] for item in payload["reverse_question_candidates"]])
        self.assertIn("ambiguity.new_customer.date_basis", [item["card_id"] for item in payload["ambiguity_candidates"]])
        self.assertEqual(payload["warnings"], [])

    def test_unknown_domain_phrase_is_not_overmatched_to_generic_customer_token(self) -> None:
        understanding = analyze_semantic_query([self.pack], "휴면 고객")
        payload = understanding.as_dict()

        self.assertEqual(payload["matched_terms"], [])
        self.assertEqual(payload["matched_metrics"], [])
        self.assertEqual(payload["unknown_terms"], ["휴면 고객"])
        self.assertIn("unknown_or_low_confidence_domain_term", payload["warnings"])
        self.assertIn("no_semantic_pack_match", payload["warnings"])

    def test_business_term_can_surface_related_metric_without_llm_or_db_call(self) -> None:
        understanding = analyze_semantic_query([self.pack], "실매출 기준")
        payload = understanding.as_dict()

        self.assertIn("term.net_revenue", [item["card_id"] for item in payload["matched_terms"]])
        related_metric = {
            item["card_id"]: item["match_kind"]
            for item in payload["matched_metrics"]
        }
        self.assertEqual(related_metric["metric.net_revenue"], "related_term")


if __name__ == "__main__":
    unittest.main()
