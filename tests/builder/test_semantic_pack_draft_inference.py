from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
BUILDER_SRC = REPO_ROOT / "packages" / "semantic_builder" / "src"
CONTRACTS_SRC = REPO_ROOT / "packages" / "semantic_contracts"
for path in (BUILDER_SRC, CONTRACTS_SRC):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from semantic_builder.builder import attach_inference_artifacts_to_draft_pack, build_semantic_pack_draft  # noqa: E402
from semantic_builder.cli import main as builder_main  # noqa: E402
from semantic_builder.connectors import scan_source  # noqa: E402
from semantic_builder.profiler import profile_dataset  # noqa: E402
from semantic_contracts import validate_semantic_pack  # noqa: E402


class SemanticPackDraftInferenceTests(unittest.TestCase):
    def test_inference_artifacts_attach_as_draft_metadata_without_contract_breakage_or_pii(self) -> None:
        document = build_semantic_pack_draft(
            [
                {
                    "table_name": "users",
                    "row_count": 1,
                    "columns": [
                        {
                            "name": "email",
                            "type_guess": "string",
                            "null_count": 0,
                            "null_ratio": 0.0,
                            "cardinality_estimate": 1,
                            "top_values": [{"value": "ada@example.com", "count": 1}],
                            "pii": {"is_pii": True, "categories": ["email"]},
                        }
                    ],
                }
            ]
        )

        enriched = attach_inference_artifacts_to_draft_pack(
            document,
            semantic_hypotheses=[
                {
                    "id": "hyp.column.users.email",
                    "kind": "column",
                    "target": "column.users.email",
                    "status": "approved",
                    "confidence": "low",
                    "raw_values": ["ada@example.com"],
                    "evidence": [{"source_ref": {"type": "postgresql", "name": "public.users", "safe_reference": True}}],
                    "rationale": "Email value ada@example.com must never be persisted raw.",
                }
            ],
            onboarding_questions=[
                {
                    "id": "rq.users.email.policy",
                    "target": "column.users.email",
                    "question": "Should ada@example.com-like identifiers remain blocked for analysts?",
                    "status": "answered",
                    "answer": "no auto-confirmation in Phase 5",
                }
            ],
        )

        result = validate_semantic_pack(enriched)
        self.assertTrue(result.valid, result.errors)
        pack = enriched["semantic_pack"]
        self.assertEqual("draft", pack["status"])
        proposals = pack["metadata"]["phase5_semantic_inference"]
        self.assertTrue(proposals["proposals_only"])
        self.assertFalse(proposals["auto_promoted"])
        self.assertEqual("draft", proposals["semantic_hypotheses"][0]["status"])
        self.assertEqual("open", proposals["onboarding_questions"][0]["status"])
        serialized = json.dumps(enriched, ensure_ascii=False)
        self.assertNotIn("ada@example.com", serialized)
        self.assertNotIn("raw_values", serialized)
        self.assertIn("postgresql", serialized)

    def test_inference_artifacts_reject_non_draft_pack(self) -> None:
        document = build_semantic_pack_draft([])
        document["semantic_pack"]["status"] = "approved"

        with self.assertRaisesRegex(ValueError, "only be attached to draft packs"):
            attach_inference_artifacts_to_draft_pack(
                document,
                semantic_hypotheses=[{"id": "hyp.table.users", "status": "draft"}],
            )

    def test_cli_build_pack_attaches_phase5_artifact_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            datasets = scan_source(REPO_ROOT / "examples" / "demo_data")
            profiles_path = tmp / "column_profiles.jsonl"
            hypotheses_path = tmp / "semantic_hypotheses.jsonl"
            questions_path = tmp / "onboarding_questions.jsonl"
            draft_path = tmp / "semantic_pack.draft.yaml"

            with profiles_path.open("w", encoding="utf-8") as handle:
                for dataset in datasets:
                    handle.write(json.dumps(profile_dataset(dataset), ensure_ascii=False, sort_keys=True) + "\n")
            hypotheses_path.write_text(
                json.dumps(
                    {
                        "id": "hyp.metric.net_revenue",
                        "kind": "metric",
                        "target": "metric.net_revenue",
                        "status": "draft",
                        "confidence": "low",
                        "uncertainties": [{"reason": "date basis missing"}],
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )
            questions_path.write_text(
                json.dumps(
                    {
                        "id": "rq.metric.net_revenue.date_basis",
                        "target": "metric.net_revenue",
                        "question": "Which date column defines monthly revenue?",
                        "status": "open",
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )

            self.assertEqual(
                0,
                builder_main(
                    [
                        "build-pack",
                        "--profiles",
                        str(profiles_path),
                        "--out",
                        str(draft_path),
                        "--semantic-hypotheses",
                        str(hypotheses_path),
                        "--onboarding-questions",
                        str(questions_path),
                    ]
                ),
            )

            document = yaml.safe_load(draft_path.read_text(encoding="utf-8"))
            result = validate_semantic_pack(document)
            self.assertTrue(result.valid, result.errors)
            metadata = document["semantic_pack"]["metadata"]["phase5_semantic_inference"]
            self.assertEqual("draft", metadata["semantic_hypotheses"][0]["status"])
            self.assertEqual("open", metadata["onboarding_questions"][0]["status"])
            self.assertTrue(metadata["proposals_only"])


if __name__ == "__main__":
    unittest.main()
