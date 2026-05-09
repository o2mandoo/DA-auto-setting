from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "semantic_contracts"))

from semantic_contracts import (  # noqa: E402
    BusinessTerm,
    ColumnCard,
    JoinRecipe,
    Metric,
    Policy,
    SemanticPack,
    TableCard,
    ValidationResult,
    VerifiedQuery,
    validate_semantic_pack,
)


def valid_pack() -> dict:
    return {
        "semantic_pack": {
            "id": "demo_company.revenue",
            "version": "0.1.0",
            "status": "draft",
            "title": "Demo Company Revenue Context",
            "description": "Revenue/customer/campaign semantic context for demo use.",
            "locale": "ko-KR",
            "owners": [{"role": "data_owner", "name": "Demo Data Team"}],
            "source_refs": [{"type": "file", "name": "demo_source", "safe_reference": True}],
            "spaces": [{"id": "revenue", "title": "Revenue Analysis"}],
            "tables": [
                {
                    "id": "table.users",
                    "space_id": "revenue",
                    "physical_name": "users",
                    "title": "Users",
                    "description": "Customer dimension table.",
                    "role": "dimension",
                    "grain": "one row per user",
                    "primary_key": "user_id",
                    "columns": ["user_id", "email", "first_paid_at"],
                    "pii_level": "high",
                    "status": "confirmed",
                    "confidence": 0.95,
                },
                {
                    "id": "table.payments",
                    "space_id": "revenue",
                    "physical_name": "payments",
                    "title": "Payments",
                    "description": "Payment fact table.",
                    "role": "fact",
                    "grain": "one row per payment",
                    "primary_key": "payment_id",
                    "columns": ["payment_id", "user_id", "amount", "paid_at", "status"],
                    "pii_level": "none",
                    "status": "confirmed",
                    "confidence": 0.95,
                },
                {
                    "id": "table.campaigns",
                    "space_id": "revenue",
                    "physical_name": "campaigns",
                    "title": "Campaigns",
                    "description": "Marketing campaign dimension table.",
                    "role": "dimension",
                    "grain": "one row per campaign",
                    "primary_key": "campaign_id",
                    "columns": ["campaign_id"],
                    "pii_level": "none",
                    "status": "confirmed",
                    "confidence": 0.9,
                },
            ],
            "columns": [
                {
                    "id": "column.users.user_id",
                    "table": "users",
                    "name": "user_id",
                    "data_type": "integer",
                    "nullable": False,
                    "semantic_type": "identifier",
                    "description": "Stable user identifier.",
                    "profile": {"null_ratio": 0.0, "cardinality": 1000, "top_values_safe": False},
                    "pii": {"is_candidate": False, "raw_value_storage": "allowed"},
                    "status": "confirmed",
                    "confidence": 0.99,
                },
                {
                    "id": "column.users.email",
                    "table": "users",
                    "name": "email",
                    "data_type": "string",
                    "nullable": False,
                    "semantic_type": "email",
                    "description": "User email; policy-blocked PII.",
                    "profile": {"null_ratio": 0.0, "cardinality": 1000, "top_values_safe": False},
                    "pii": {"is_candidate": True, "raw_value_storage": "blocked"},
                    "status": "confirmed",
                    "confidence": 0.99,
                },
                {
                    "id": "column.users.first_paid_at",
                    "table": "users",
                    "name": "first_paid_at",
                    "data_type": "timestamp",
                    "nullable": True,
                    "semantic_type": "first_payment_timestamp",
                    "description": "First successful payment timestamp.",
                    "profile": {"null_ratio": 0.2, "cardinality": 800, "top_values_safe": False},
                    "pii": {"is_candidate": False, "raw_value_storage": "allowed"},
                    "status": "confirmed",
                    "confidence": 0.9,
                },
                {
                    "id": "column.payments.payment_id",
                    "table": "payments",
                    "name": "payment_id",
                    "data_type": "integer",
                    "nullable": False,
                    "semantic_type": "identifier",
                    "description": "Stable payment identifier.",
                    "pii": {"is_candidate": False, "raw_value_storage": "allowed"},
                    "status": "confirmed",
                },
                {
                    "id": "column.payments.user_id",
                    "table": "payments",
                    "name": "user_id",
                    "data_type": "integer",
                    "nullable": False,
                    "semantic_type": "foreign_key",
                    "description": "User foreign key.",
                    "pii": {"is_candidate": False, "raw_value_storage": "allowed"},
                    "status": "confirmed",
                },
                {
                    "id": "column.payments.amount",
                    "table": "payments",
                    "name": "amount",
                    "data_type": "numeric",
                    "nullable": False,
                    "semantic_type": "money",
                    "description": "Paid amount.",
                    "pii": {"is_candidate": False, "raw_value_storage": "allowed"},
                    "status": "confirmed",
                },
                {
                    "id": "column.payments.paid_at",
                    "table": "payments",
                    "name": "paid_at",
                    "data_type": "timestamp",
                    "nullable": False,
                    "semantic_type": "payment_timestamp",
                    "description": "Payment timestamp.",
                    "pii": {"is_candidate": False, "raw_value_storage": "allowed"},
                    "status": "confirmed",
                },
                {
                    "id": "column.payments.status",
                    "table": "payments",
                    "name": "status",
                    "data_type": "string",
                    "nullable": False,
                    "semantic_type": "status_code",
                    "description": "Payment lifecycle status.",
                    "profile": {"null_ratio": 0.0, "cardinality": 3, "top_values_safe": True},
                    "pii": {"is_candidate": False, "raw_value_storage": "allowed"},
                    "status": "confirmed",
                },
                {
                    "id": "column.campaigns.campaign_id",
                    "table": "campaigns",
                    "name": "campaign_id",
                    "data_type": "integer",
                    "nullable": False,
                    "semantic_type": "identifier",
                    "description": "Stable campaign identifier.",
                    "pii": {"is_candidate": False, "raw_value_storage": "allowed"},
                    "status": "confirmed",
                },
            ],
            "value_dictionaries": [
                {
                    "id": "value_dict.payments.status",
                    "table": "payments",
                    "column": "status",
                    "values": [{"value": "PAID", "label": "Paid", "source": "human", "status": "confirmed"}],
                }
            ],
            "metrics": [
                {
                    "id": "metric.net_revenue",
                    "name": "net_revenue",
                    "label": "순매출",
                    "description": "Gross payment amount minus refunds and discounts.",
                    "formula_sql": "payments.amount - payments.refund_amount - payments.discount_amount",
                    "date_basis": "payments.paid_at",
                    "required_tables": ["payments"],
                    "default_filters": ["payments.status = 'PAID'"],
                    "status": "confirmed",
                    "owner": "finance",
                }
            ],
            "business_terms": [
                {
                    "id": "term.new_customer",
                    "term": "신규 고객",
                    "aliases": ["new customer"],
                    "definition": "First paid date falls within the analysis period.",
                    "sql_condition": "users.first_paid_at >= {start_date} AND users.first_paid_at < {end_date}",
                    "related_tables": ["users", "payments"],
                    "related_metrics": ["metric.net_revenue"],
                    "ambiguity_policy": "ask_if_date_basis_missing",
                    "status": "confirmed",
                }
            ],
            "join_recipes": [
                {
                    "id": "join.users_payments",
                    "left_table": "users",
                    "right_table": "payments",
                    "join_type": "one_to_many",
                    "condition": "users.user_id = payments.user_id",
                    "recommended": True,
                    "warnings": ["Use user_id, not email, for joins."],
                }
            ],
            "policies": [
                {
                    "id": "policy.marketing_safe_revenue",
                    "applies_to": {"roles": ["marketing_analyst"]},
                    "allowed_tables": ["users", "payments", "campaigns"],
                    "blocked_columns": ["users.email"],
                    "notes": ["Aggregated revenue is allowed; raw PII is blocked."],
                }
            ],
            "verified_queries": [
                {
                    "id": "verified_query.monthly_new_customer_revenue",
                    "question": "월별 신규 고객 순매출을 보여줘",
                    "sql": "SELECT DATE_TRUNC('month', first_paid_at), SUM(net_revenue) FROM demo_revenue_view GROUP BY 1",
                    "related_terms": ["term.new_customer"],
                    "related_metrics": ["metric.net_revenue"],
                    "status": "confirmed",
                }
            ],
            "reverse_questions": [],
            "metadata": {"created_at": "2026-05-08", "updated_at": "2026-05-08"},
        }
    }


class SemanticPackModelTests(unittest.TestCase):
    def test_valid_pack_builds_core_models(self) -> None:
        payload = valid_pack()["semantic_pack"]
        pack = SemanticPack.model_validate(payload)
        result = validate_semantic_pack(valid_pack())

        self.assertIsInstance(pack, SemanticPack)
        self.assertTrue(result.valid, result.errors)
        self.assertIsInstance(pack.tables[0], TableCard)
        self.assertIsInstance(pack.columns[1], ColumnCard)
        self.assertIsInstance(pack.business_terms[0], BusinessTerm)
        self.assertIsInstance(pack.metrics[0], Metric)
        self.assertIsInstance(pack.join_recipes[0], JoinRecipe)
        self.assertIsInstance(pack.policies[0], Policy)
        self.assertIsInstance(pack.verified_queries[0], VerifiedQuery)
        self.assertEqual(pack.policies[0].applies_to.roles, ["marketing_analyst"])

    def test_invalid_pack_validation_reports_model_errors(self) -> None:
        data = valid_pack()
        data["semantic_pack"]["columns"][1]["pii"]["raw_value_storage"] = "allowed"

        result = validate_semantic_pack(data)

        self.assertIsInstance(result, ValidationResult)
        self.assertFalse(result.valid)
        self.assertIn("PII candidate", _messages(result))

    def test_invalid_pack_rejects_value_dictionary_for_pii_column(self) -> None:
        data = valid_pack()
        data["semantic_pack"]["value_dictionaries"].append(
            {
                "id": "value_dict.users.email",
                "table": "users",
                "column": "email",
                "values": [{"value": "person@example.com", "label": "Example"}],
            }
        )

        result = validate_semantic_pack(data)

        self.assertFalse(result.valid)
        self.assertIn("cannot define raw value dictionary", _messages(result))

    def test_required_top_level_sections_are_enforced(self) -> None:
        data = valid_pack()
        del data["semantic_pack"]["policies"]

        result = validate_semantic_pack(data)

        self.assertFalse(result.valid)
        self.assertIn("semantic_pack.policies", [error.path for error in result.errors])

    def test_policy_must_represent_blocked_pii_columns(self) -> None:
        data = valid_pack()
        data["semantic_pack"]["policies"][0]["blocked_columns"] = []

        result = validate_semantic_pack(data)

        self.assertFalse(result.valid)
        self.assertIn("must be represented in policy blocked_columns", _messages(result))


def _messages(result: ValidationResult) -> str:
    return "\n".join(error.message for error in result.errors)


if __name__ == "__main__":
    unittest.main()
