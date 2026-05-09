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

from semantic_builder.cli import main as builder_main  # noqa: E402
from semantic_builder.inference import (  # noqa: E402
    LocalProviderConfig,
    LocalSemanticInferenceProvider,
    generate_semantic_inference,
)


class SemanticInferencePipelineTests(unittest.TestCase):
    def test_mock_provider_generates_draft_hypotheses_and_questions(self) -> None:
        profiles = [
            {
                "table_name": "payments",
                "row_count": 2,
                "source_ref": {"type": "postgresql", "name": "warehouse.public.payments"},
                "columns": [
                    {
                        "name": "payment_id",
                        "type_guess": "string",
                        "null_ratio": 0.0,
                        "cardinality_estimate": 2,
                        "join_key_candidate": True,
                        "pii": {"is_pii": False, "categories": []},
                    },
                    {
                        "name": "amount",
                        "type_guess": "number",
                        "null_ratio": 0.0,
                        "cardinality_estimate": 2,
                        "numeric_min": 10.0,
                        "numeric_max": 20.0,
                        "pii": {"is_pii": False, "categories": []},
                    },
                    {
                        "name": "paid_at",
                        "type_guess": "date",
                        "null_ratio": 0.0,
                        "cardinality_estimate": 2,
                        "date_min": "2026-01-01",
                        "date_max": "2026-01-02",
                        "pii": {"is_pii": False, "categories": []},
                    },
                ],
            }
        ]

        result = generate_semantic_inference(profiles)

        self.assertTrue(result["hypotheses"])
        self.assertTrue(result["onboarding_questions"])
        self.assertTrue(all(item["status"] == "draft" for item in result["hypotheses"]))
        self.assertTrue(all(item["evidence"] for item in result["hypotheses"]))
        self.assertIn("postgresql", json.dumps(result, ensure_ascii=False))
        metric = next(item for item in result["hypotheses"] if item["kind"] == "metric")
        self.assertIn("confirm_date_basis", metric["uncertainties"])
        self.assertTrue(any("date column" in item["question"] for item in result["onboarding_questions"]))

    def test_pii_values_are_defensively_suppressed_from_hypotheses_and_questions(self) -> None:
        profiles = [
            {
                "table_name": "users",
                "row_count": 2,
                "columns": [
                    {
                        "name": "email",
                        "type_guess": "string",
                        "null_ratio": 0.0,
                        "cardinality_estimate": 2,
                        "top_values": [{"value": "ada@example.com", "count": 1}],
                        "pii": {"is_pii": True, "categories": ["email"]},
                    },
                    {
                        "name": "customer_name",
                        "type_guess": "string",
                        "null_ratio": 0.0,
                        "cardinality_estimate": 2,
                        "top_values": [{"value": "Ada Lovelace", "count": 1}],
                        "pii": {"is_pii": True, "categories": ["person_name"]},
                    },
                ],
            }
        ]

        result = generate_semantic_inference(profiles)
        serialized = json.dumps(result, ensure_ascii=False)

        self.assertNotIn("ada@example.com", serialized)
        self.assertNotIn("Ada Lovelace", serialized)
        self.assertIn("raw_values", serialized)
        self.assertIn("blocked", serialized)
        self.assertTrue(any(item["kind"] == "policy" for item in result["hypotheses"]))

    def test_cli_writes_semantic_hypotheses_and_onboarding_questions_jsonl(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            profiles = tmp / "column_profiles.jsonl"
            hypotheses = tmp / "semantic_hypotheses.jsonl"
            questions = tmp / "onboarding_questions.jsonl"
            profiles.write_text(
                json.dumps(
                    {
                        "table_name": "orders",
                        "row_count": 1,
                        "columns": [
                            {
                                "name": "order_id",
                                "type_guess": "string",
                                "null_ratio": 0.0,
                                "cardinality_estimate": 1,
                                "join_key_candidate": True,
                                "pii": {"is_pii": False, "categories": []},
                            },
                            {
                                "name": "sales",
                                "type_guess": "number",
                                "null_ratio": 0.0,
                                "cardinality_estimate": 1,
                                "numeric_min": 10.0,
                                "numeric_max": 10.0,
                                "pii": {"is_pii": False, "categories": []},
                            },
                        ],
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )

            self.assertEqual(
                0,
                builder_main(
                    [
                        "infer-semantics",
                        "--profiles",
                        str(profiles),
                        "--hypotheses-out",
                        str(hypotheses),
                        "--questions-out",
                        str(questions),
                    ]
                ),
            )

            hypothesis_rows = [json.loads(line) for line in hypotheses.read_text(encoding="utf-8").splitlines()]
            question_rows = [json.loads(line) for line in questions.read_text(encoding="utf-8").splitlines()]
            self.assertTrue(hypothesis_rows)
            self.assertTrue(question_rows)
            self.assertTrue(all(row["status"] == "draft" for row in hypothesis_rows))
            self.assertTrue(all(row["status"] == "open" for row in question_rows))

    def test_identifier_columns_with_order_prefix_are_not_treated_as_dates(self) -> None:
        result = generate_semantic_inference(
            [
                {
                    "table_name": "orders",
                    "row_count": 1,
                    "columns": [
                        {
                            "name": "order_id",
                            "type_guess": "string",
                            "null_ratio": 0.0,
                            "cardinality_estimate": 1,
                            "join_key_candidate": True,
                            "pii": {"is_pii": False, "categories": []},
                        },
                        {
                            "name": "order_date",
                            "type_guess": "date",
                            "null_ratio": 0.0,
                            "cardinality_estimate": 1,
                            "pii": {"is_pii": False, "categories": []},
                        },
                        {
                            "name": "sales",
                            "type_guess": "number",
                            "null_ratio": 0.0,
                            "cardinality_estimate": 1,
                            "numeric_min": 10.0,
                            "numeric_max": 10.0,
                            "pii": {"is_pii": False, "categories": []},
                        },
                    ],
                }
            ]
        )

        order_id = next(
            item for item in result["hypotheses"] if item["kind"] == "column" and item["payload"]["column"] == "order_id"
        )
        self.assertEqual("identifier", order_id["payload"]["semantic_type"])
        self.assertNotIn("confirm_date_basis", order_id["uncertainties"])

        metric = next(item for item in result["hypotheses"] if item["kind"] == "metric")
        self.assertEqual(["order_date"], metric["payload"]["candidate_date_columns"])

    def test_local_provider_requires_explicit_config_and_is_not_silent_fallback(self) -> None:
        with self.assertRaisesRegex(ValueError, "enabled=True"):
            LocalSemanticInferenceProvider()
        with self.assertRaisesRegex(NotImplementedError, "not implemented"):
            LocalSemanticInferenceProvider(LocalProviderConfig(enabled=True, model="local-test")).infer([])

    def test_local_provider_config_normalizes_env_and_config_aliases(self) -> None:
        config = LocalProviderConfig.from_mapping(
            {
                "enabled": "true",
                "provider": "openai-compatible",
                "base_url": "http://localhost:11434",
                "model": "qwen2.5:7b",
                "api_key": "secret-token",
                "timeout_ms": "2500",
                "max_tokens": "1024",
                "temperature": "0.2",
            }
        )

        self.assertTrue(config.enabled)
        self.assertEqual("openai-compatible", config.provider)
        self.assertEqual("http://localhost:11434", config.endpoint)
        self.assertEqual("http://localhost:11434", config.base_url)
        self.assertEqual("qwen2.5:7b", config.model)
        self.assertEqual("secret-token", config.api_key)
        self.assertEqual(2500.0, config.timeout)
        self.assertEqual(1024, config.max_tokens)
        self.assertEqual(0.2, config.temperature)

    def test_local_provider_config_reads_sdc_llm_env(self) -> None:
        config = LocalProviderConfig.from_env(
            {
                "SDC_LLM_ENABLED": "1",
                "SDC_LLM_PROVIDER": "openai-compatible",
                "SDC_LLM_ENDPOINT": "http://localhost:8000/v1",
                "SDC_LLM_MODEL": "gpt-4.1-mini",
                "SDC_LLM_API_KEY": "env-token",
                "SDC_LLM_TIMEOUT": "3.5",
                "SDC_LLM_MAX_TOKENS": "2048",
                "SDC_LLM_TEMPERATURE": "0.4",
            }
        )

        self.assertTrue(config.enabled)
        self.assertEqual("openai-compatible", config.provider)
        self.assertEqual("http://localhost:8000/v1", config.endpoint)
        self.assertEqual("gpt-4.1-mini", config.model)
        self.assertEqual("env-token", config.api_key)
        self.assertEqual(3.5, config.timeout)
        self.assertEqual(2048, config.max_tokens)
        self.assertEqual(0.4, config.temperature)

    def test_local_provider_config_rejects_invalid_numeric_fields(self) -> None:
        with self.assertRaisesRegex(ValueError, "timeout"):
            LocalProviderConfig.from_mapping({"enabled": True, "timeout": 0})
        with self.assertRaisesRegex(ValueError, "max_tokens"):
            LocalProviderConfig.from_mapping({"enabled": True, "max_tokens": 0})
        with self.assertRaisesRegex(ValueError, "temperature"):
            LocalProviderConfig.from_mapping({"enabled": True, "temperature": 2.5})


if __name__ == "__main__":
    unittest.main()
