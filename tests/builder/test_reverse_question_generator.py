from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BUILDER_SRC = REPO_ROOT / "packages" / "semantic_builder" / "src"
if str(BUILDER_SRC) not in sys.path:
    sys.path.insert(0, str(BUILDER_SRC))

from semantic_builder.inference.reverse_questions import (  # noqa: E402
    generate_reverse_questions,
    write_onboarding_questions_jsonl,
)


class ReverseQuestionGeneratorTests(unittest.TestCase):
    def test_generates_questions_for_date_metric_join_and_pii_uncertainty(self) -> None:
        questions = generate_reverse_questions(
            [
                {
                    "table_name": "payments",
                    "path": "examples/demo_data/payments.json",
                    "columns": [
                        {"name": "user_id", "type_guess": "string", "join_key_candidate": True, "pii": {"is_pii": False}},
                        {"name": "paid_at", "type_guess": "date", "pii": {"is_pii": False}},
                        {"name": "settled_at", "type_guess": "date", "pii": {"is_pii": False}},
                        {"name": "amount", "type_guess": "number", "pii": {"is_pii": False}},
                        {
                            "name": "customer_email",
                            "type_guess": "string",
                            "pii": {"is_pii": True, "categories": ["email"]},
                            "top_values": [{"value": "ada@example.com", "count": 1}],
                        },
                    ],
                }
            ]
        )

        by_category = {question["category"] for question in questions}
        self.assertIn("ambiguous_date_basis", by_category)
        self.assertIn("metric_definition", by_category)
        self.assertIn("join_relationship", by_category)
        self.assertIn("pii_policy", by_category)
        serialized = json.dumps(questions, ensure_ascii=False)
        self.assertNotIn("ada@example.com", serialized)
        self.assertIn("payments.customer_email", serialized)
        for question in questions:
            self.assertEqual("open", question["status"])
            self.assertTrue(question["evidence"], question)
            self.assertTrue(all(item["safe_reference"] for item in question["evidence"]))

    def test_empty_profiles_create_missing_evidence_question(self) -> None:
        questions = generate_reverse_questions([])

        self.assertEqual(1, len(questions))
        self.assertEqual("missing_evidence", questions[0]["category"])
        self.assertEqual("source_profiles", questions[0]["target"])

    def test_accepts_postgresql_origin_references_without_db_execution(self) -> None:
        questions = generate_reverse_questions(
            [
                {
                    "table_name": "orders",
                    "schema_name": "analytics",
                    "source_ref": {"type": "postgresql", "name": "warehouse.analytics.orders"},
                    "columns": [
                        {"name": "order_date", "type_guess": "date", "pii": {"is_pii": False}},
                        {"name": "ship_date", "type_guess": "date", "pii": {"is_pii": False}},
                    ],
                }
            ]
        )

        date_question = next(question for question in questions if question["category"] == "ambiguous_date_basis")
        self.assertEqual("postgresql", date_question["evidence"][0]["source_type"])
        self.assertEqual("orders", date_question["evidence"][0]["table"])

    def test_hypothesis_uncertainties_and_low_confidence_become_questions(self) -> None:
        questions = generate_reverse_questions(
            [],
            hypotheses=[
                {
                    "id": "metric.net_revenue",
                    "confidence": 0.42,
                    "uncertainties": [
                        {"type": "date_basis", "reason": "date basis is unclear"},
                        "join relationship needs confirmation",
                    ],
                    "evidence": [{"type": "profile", "table": "payments", "column": "amount"}],
                }
            ],
        )

        categories = [question["category"] for question in questions]
        self.assertIn("low_confidence", categories)
        self.assertIn("ambiguous_date_basis", categories)
        self.assertIn("join_relationship", categories)

    def test_jsonl_writer_redacts_accidental_pii_strings(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "onboarding_questions.jsonl"
            write_onboarding_questions_jsonl(
                [
                    {
                        "id": "rq.test",
                        "target": "column.users.email",
                        "question": "Can alice@example.com be used?",
                        "reason": "call +82-10-1234-5678",
                    }
                ],
                out,
            )

            text = out.read_text(encoding="utf-8")
        self.assertIn("[REDACTED_EMAIL]", text)
        self.assertIn("[REDACTED_PHONE]", text)
        self.assertNotIn("alice@example.com", text)
        self.assertNotIn("1234-5678", text)


if __name__ == "__main__":
    unittest.main()
