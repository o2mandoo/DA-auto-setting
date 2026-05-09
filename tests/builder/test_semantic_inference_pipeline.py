from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[2]
BUILDER_SRC = REPO_ROOT / "packages" / "semantic_builder" / "src"
if str(BUILDER_SRC) not in sys.path:
    sys.path.insert(0, str(BUILDER_SRC))

from semantic_builder.cli import main as builder_main  # noqa: E402
from semantic_builder.inference import (  # noqa: E402
    LocalProviderConfig,
    LocalSemanticInferenceProvider,
    generate_semantic_inference,
    load_inference_provider_config,
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
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            profiles = tmp / "column_profiles.jsonl"
            profiles.write_text(
                json.dumps(
                    {
                        "table_name": "orders",
                        "row_count": 1,
                        "columns": [],
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            with patch("semantic_builder.cli.LocalSemanticInferenceProvider") as mock_provider:
                mock_provider.side_effect = ValueError("local semantic inference provider requires explicit enabled=True config")
                with self.assertRaisesRegex(ValueError, "enabled=True"):
                    builder_main(
                        [
                            "infer-semantics",
                            "--profiles",
                            str(profiles),
                            "--hypotheses-out",
                            str(tmp / "semantic_hypotheses.jsonl"),
                            "--questions-out",
                            str(tmp / "onboarding_questions.jsonl"),
                            "--provider",
                            "local",
                            "--local-model",
                            "local-test",
                            "--local-endpoint",
                            "http://127.0.0.1:11434",
                        ]
                    )

    def test_cli_honors_explicit_provider_selection_flags_and_env(self) -> None:
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
                            }
                        ],
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )

            env = {
                "SEMANTIC_BUILDER_PROVIDER": "local",
                "SEMANTIC_BUILDER_LOCAL_ENABLED": "true",
                "SEMANTIC_BUILDER_LOCAL_MODEL": "local-test",
                "SEMANTIC_BUILDER_LOCAL_ENDPOINT": "http://127.0.0.1:11434",
            }
            with patch.dict(os.environ, env, clear=False):
                with patch("semantic_builder.cli.LocalSemanticInferenceProvider") as mock_provider:
                    provider_instance = mock_provider.return_value
                    provider_instance.infer.return_value = {
                        "hypotheses": [
                            {
                                "status": "draft",
                                "kind": "table",
                                "table": "orders",
                                "source": "openai-compatible-local-http",
                            }
                        ],
                        "onboarding_questions": [
                            {
                                "status": "open",
                                "kind": "question",
                                "question": "Test question for local provider",
                                "source": "openai-compatible-local-http",
                            }
                        ],
                    }
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
                    )
                    mock_provider.assert_called_once()
                    config = mock_provider.call_args.args[0]
                    provider_name = config.provider if hasattr(config, "provider") else config.model
                    self.assertEqual(provider_name, "local-test")
                    self.assertEqual(config.endpoint, "http://127.0.0.1:11434")

            with patch("semantic_builder.cli.LocalSemanticInferenceProvider") as mock_provider:
                provider_instance = mock_provider.return_value
                provider_instance.infer.return_value = {
                    "hypotheses": [
                        {
                            "status": "draft",
                            "kind": "table",
                            "table": "orders",
                            "source": "openai-compatible-local-http",
                        }
                    ],
                    "onboarding_questions": [
                        {
                            "status": "open",
                            "kind": "question",
                            "question": "Test question for local provider",
                            "source": "openai-compatible-local-http",
                        }
                    ],
                }
                builder_main(
                    [
                        "infer-semantics",
                        "--profiles",
                        str(profiles),
                        "--hypotheses-out",
                        str(hypotheses),
                        "--questions-out",
                        str(questions),
                        "--provider",
                        "local",
                        "--local-enabled",
                        "--local-model",
                        "local-test",
                        "--local-endpoint",
                        "http://127.0.0.1:11434",
                    ]
                )
                mock_provider.assert_called_once()
                config = mock_provider.call_args.args[0]
                provider_name = config.provider if hasattr(config, "provider") else config.model
                self.assertEqual(provider_name, "local-test")
                self.assertEqual(config.endpoint, "http://127.0.0.1:11434")

    def test_provider_config_loads_supported_env_fields(self) -> None:
        env = {
            "SDC_LLM_ENABLED": "1",
            "SDC_LLM_PROVIDER": "openai-compatible",
            "SDC_LLM_ENDPOINT": "http://localhost:11434/v1",
            "SDC_LLM_BASE_URL": "http://localhost:11434",
            "SDC_LLM_MODEL": "qwen2.5:7b",
            "SDC_LLM_API_KEY": "secret-placeholder",
            "SDC_LLM_TIMEOUT": "30",
            "SDC_LLM_MAX_TOKENS": "512",
            "SDC_LLM_TEMPERATURE": "0.2",
        }

        config = load_inference_provider_config(env)

        self.assertTrue(config.enabled)
        self.assertEqual("openai-compatible", config.provider)
        self.assertEqual("http://localhost:11434/v1", config.endpoint)
        self.assertEqual("http://localhost:11434", config.base_url)
        self.assertEqual("qwen2.5:7b", config.model)
        self.assertEqual("secret-placeholder", config.api_key)
        self.assertEqual(30, config.timeout)
        self.assertEqual(512, config.max_tokens)
        self.assertAlmostEqual(0.2, config.temperature)

    def test_provider_config_normalizes_endpoint_to_base_url_when_missing(self) -> None:
        config = load_inference_provider_config({"SDC_LLM_BASE_URL": "http://localhost:11434"})
        self.assertEqual("http://localhost:11434", config.base_url)

    def test_local_provider_build_request_sanitizes_profile_records_and_requests_json(self) -> None:
        provider = LocalSemanticInferenceProvider(
            LocalProviderConfig(enabled=True, provider="local-http", model="qwen2.5:7b", endpoint="http://localhost:11434/v1")
        )
        request = provider.build_request(
            [
                {
                    "table_name": "users",
                    "source_ref": {"type": "postgresql", "name": "warehouse.public.users"},
                    "columns": [
                        {
                            "name": "email",
                            "type_guess": "string",
                            "pii": {"is_pii": True, "categories": ["email"]},
                            "top_values": [{"value": "ada@example.com", "count": 1}],
                            "numeric_min": 1,
                            "numeric_max": 2,
                        }
                    ],
                }
            ]
        )

        self.assertEqual({"type": "json_object"}, request["response_format"])
        self.assertIn("strict JSON", request["instructions"])
        self.assertEqual("local-http", request["provider"])
        self.assertEqual("qwen2.5:7b", request["model"])
        self.assertNotIn("ada@example.com", json.dumps(request, ensure_ascii=False))
        self.assertEqual([], request["profile_records"][0]["columns"][0]["top_values"])
        self.assertNotIn("numeric_min", request["profile_records"][0]["columns"][0])
        self.assertNotIn("numeric_max", request["profile_records"][0]["columns"][0])

    def test_local_provider_parse_response_requires_json_object_with_expected_keys(self) -> None:
        provider = LocalSemanticInferenceProvider(LocalProviderConfig(enabled=True))

        parsed = provider.parse_response(
            json.dumps(
                {
                    "hypotheses": [{"id": "hyp.table.users", "status": "draft"}],
                    "onboarding_questions": [{"id": "question.users.email", "status": "open"}],
                }
            )
        )

        self.assertEqual(["hyp.table.users"], [item["id"] for item in parsed["hypotheses"]])
        self.assertEqual(["question.users.email"], [item["id"] for item in parsed["onboarding_questions"]])

        with self.assertRaisesRegex(ValueError, "valid JSON"):
            provider.parse_response("{not-json")
        with self.assertRaisesRegex(ValueError, "must contain hypotheses and onboarding_questions arrays"):
            provider.parse_response({"hypotheses": {}, "onboarding_questions": []})


if __name__ == "__main__":
    unittest.main()
