from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "semantic_contracts"))
sys.path.insert(0, str(ROOT / "packages" / "semantic_registry"))

from semantic_contracts import (  # noqa: E402
    AmbiguityRule,
    ColumnCard,
    ColumnProfile,
    PiiPolicy,
    RawValueStorage,
    ValueDictionary,
    ValueDictionaryEntry,
)
from semantic_registry import PackStore, SearchIndex, iter_pack_card_documents  # noqa: E402


class CardFlatteningTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.pack = PackStore(ROOT / "semantic_packs").load_pack("demo_company.revenue")

    def test_documents_cover_required_card_types_and_fields(self) -> None:
        pack = self.pack.model_copy(deep=True)
        pack.business_terms[0].ambiguity_rules.append(AmbiguityRule(
            id="ambiguity.new_customer.period_basis",
            target="term.new_customer",
            condition="new customer period is ambiguous",
            question="신규 고객 기간 기준을 first_paid_at으로 볼까요?",
            required_when="date_basis_missing",
            status="draft",
        ))

        documents = list(iter_pack_card_documents(pack, source_path="semantic_packs/demo_company/revenue.v0_1.yaml"))
        by_type = {document.card_type for document in documents}

        self.assertTrue({
            "table",
            "column",
            "value_dictionary",
            "metric",
            "business_term",
            "join_recipe",
            "policy",
            "verified_query",
            "ambiguity_rule",
        }.issubset(by_type))
        for document in documents:
            self.assertTrue(document.card_id)
            self.assertTrue(document.card_type)
            self.assertEqual(document.pack_id, "demo_company.revenue")
            self.assertTrue(document.space_id)
            self.assertTrue(document.status)
            self.assertTrue(document.text)
            self.assertIsInstance(document.metadata, dict)
            self.assertEqual(document.source_path, "semantic_packs/demo_company/revenue.v0_1.yaml")

    def test_safe_value_dictionary_values_are_indexed(self) -> None:
        documents = {document.card_id: document for document in iter_pack_card_documents(self.pack)}
        status_doc = documents["value_dict.payments.status"]

        self.assertIn("PAID", status_doc.text)
        self.assertIn("결제 완료", status_doc.text)
        self.assertTrue(status_doc.metadata["values_indexed"])
        self.assertFalse(status_doc.metadata["pii_raw_values_indexed"])

    def test_pii_value_dictionary_raw_values_are_not_indexed(self) -> None:
        pack = self.pack.model_copy(deep=True)
        pack.value_dictionaries.append(ValueDictionary(
            id="value_dict.users.email.synthetic_unsafe",
            table="users",
            column="email",
            values=[ValueDictionaryEntry(value="alice@example.com", label="Alice Email", status="draft")],
        ))

        documents = {document.card_id: document for document in iter_pack_card_documents(pack)}
        email_doc = documents["value_dict.users.email.synthetic_unsafe"]
        serialized_metadata = str(email_doc.metadata)

        self.assertIn("users email", email_doc.text)
        self.assertNotIn("alice@example.com", email_doc.text)
        self.assertNotIn("alice@example.com", serialized_metadata)
        self.assertFalse(email_doc.metadata["values_indexed"])
        self.assertFalse(email_doc.metadata["pii_raw_values_indexed"])

    def test_dormant_customer_query_finds_status_dictionary_when_fixture_has_it(self) -> None:
        pack = self.pack.model_copy(deep=True)
        users_table = next(table for table in pack.tables if table.physical_name == "users")
        users_table.columns.append("status")
        pack.columns.append(ColumnCard(
            id="column.users.status",
            table="users",
            name="status",
            data_type="string",
            semantic_type="status_code",
            description="Customer lifecycle status used for dormant-customer segmentation.",
            profile=ColumnProfile(top_values_safe=True),
            pii=PiiPolicy(raw_value_storage=RawValueStorage.ALLOWED),
            status="draft",
        ))
        pack.value_dictionaries.append(ValueDictionary(
            id="value_dict.users.status",
            table="users",
            column="status",
            values=[ValueDictionaryEntry(value="S", label="휴면 고객", description="Dormant customer", status="draft")],
        ))

        results = SearchIndex.from_pack(pack).search_cards("휴면 고객", card_types=["value_dictionary"], limit=3)

        self.assertEqual(results[0].card_id, "value_dict.users.status")
        self.assertIn("S", results[0].text)
        self.assertIn("휴면 고객", results[0].text)

    def test_ambiguous_revenue_query_finds_ambiguity_rule_when_fixture_has_it(self) -> None:
        pack = self.pack.model_copy(deep=True)
        pack.business_terms[1].ambiguity_rules.append(AmbiguityRule(
            id="ambiguity.net_revenue.refund_timing",
            target="term.net_revenue",
            condition="revenue query does not specify refund timing",
            question="순매출에서 환불은 결제월 기준인가요, 환불월 기준인가요?",
            required_when="refund_timing_missing",
            status="draft",
        ))

        results = SearchIndex.from_pack(pack).search_cards("환불 순매출 기준", card_types=["ambiguity_rule"], limit=3)

        self.assertEqual(results[0].card_id, "ambiguity.net_revenue.refund_timing")
        self.assertEqual(results[0].card_type, "ambiguity_rule")
        self.assertEqual(results[0].status, "draft")

    def test_search_index_uses_flattened_documents_and_status(self) -> None:
        results = SearchIndex.from_pack(self.pack).search_cards("순매출", limit=5)
        metric = next(result for result in results if result.card_id == "metric.net_revenue")

        self.assertEqual(metric.card_type, "metric")
        self.assertEqual(metric.status, "draft")
        self.assertIn("metric.net_revenue", metric.text)
        self.assertEqual(metric.metadata["label"], "순매출")


if __name__ == "__main__":
    unittest.main()
