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

    def test_local_provider_missing_endpoint_or_model_errors_explicitly(self) -> None:
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
            hypotheses = tmp / "semantic_hypotheses.jsonl"
            questions = tmp / "onboarding_questions.jsonl"

            with self.assertRaisesRegex(ValueError, "requires an endpoint"):
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
                    ]
                )

    def test_local_provider_invalid_response_is_explicit_failure_without_mock_fallback(self) -> None:
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

            with patch("semantic_builder.cli.LocalSemanticInferenceProvider") as mock_provider:
                mock_provider.return_value.infer.return_value = {"hypotheses": "not-a-list", "onboarding_questions": []}
                with self.assertRaisesRegex(ValueError, "explicit semantic inference provider .* failed"):
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
                self.assertFalse(hypotheses.exists(), "explicit local failure must not write fallback mock output")

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


if __name__ == "__main__":
    unittest.main()
