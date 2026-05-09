from __future__ import annotations

import sys
import unittest
from pathlib import Path

from pydantic import ValidationError

REPO_ROOT = Path(__file__).resolve().parents[2]
BUILDER_SRC = REPO_ROOT / "packages" / "semantic_builder" / "src"
CONTRACTS_SRC = REPO_ROOT / "packages" / "semantic_contracts"
for path in (BUILDER_SRC, CONTRACTS_SRC):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from semantic_builder.inference import (  # noqa: E402
    ColumnHypothesis,
    ConfidenceLevel,
    EvidenceReference,
    TableHypothesis,
    Uncertainty,
)


class SemanticHypothesisModelTests(unittest.TestCase):
    def test_table_hypothesis_is_draft_and_requires_evidence(self) -> None:
        evidence = EvidenceReference(
            source_type="file",
            source_name="demo_profiles",
            artifact_type="profile_record",
            file_path="runtime/demo/column_profiles.jsonl",
            table_name="payments",
            record_index=1,
            json_pointer="/columns/0",
        )

        hypothesis = TableHypothesis(
            id="hyp.table.payments",
            title="Payments",
            table_name="payments",
            confidence=ConfidenceLevel.MEDIUM,
            evidence=[evidence],
            uncertainties=[Uncertainty(code="needs_owner_review", message="Table role needs business confirmation.")],
        )

        self.assertEqual("draft", hypothesis.status)
        self.assertEqual("table", hypothesis.kind)
        self.assertEqual("medium", hypothesis.confidence)
        self.assertEqual("file", hypothesis.evidence[0].source_type)

        with self.assertRaises(ValidationError):
            TableHypothesis(id="hyp.table.missing", table_name="missing", evidence=[])

    def test_evidence_reference_supports_future_postgresql_origin_without_raw_values(self) -> None:
        evidence = EvidenceReference(
            source_type="postgresql",
            source_name="warehouse_profile",
            artifact_type="column_profile",
            schema_name="public",
            table_name="payments",
            column_name="amount",
            json_pointer="/columns/amount",
        )

        self.assertTrue(evidence.safe_reference)
        self.assertTrue(evidence.pii_safe)
        self.assertFalse(evidence.raw_value_included)
        self.assertEqual("postgresql", evidence.source_type)

    def test_evidence_reference_rejects_raw_or_unsafe_payloads(self) -> None:
        with self.assertRaises(ValidationError):
            EvidenceReference(
                source_type="file",
                source_name="demo_profiles",
                artifact_type="profile_record",
                file_path="runtime/demo/column_profiles.jsonl",
                raw_value_included=True,
            )

        with self.assertRaises(ValidationError):
            EvidenceReference(
                source_type="file",
                source_name="demo_profiles",
                artifact_type="profile_record",
                file_path="runtime/demo/column_profiles.jsonl",
                raw_value="ada@example.com",
            )

    def test_pii_column_hypothesis_forces_blocked_raw_value_storage(self) -> None:
        evidence = EvidenceReference(
            source_type="file",
            source_name="demo_profiles",
            artifact_type="column_profile",
            file_path="runtime/demo/column_profiles.jsonl",
            table_name="users",
            column_name="email",
        )

        hypothesis = ColumnHypothesis(
            id="hyp.column.users.email",
            table_name="users",
            column_name="email",
            pii_candidate=True,
            evidence=[evidence],
        )
        self.assertEqual("blocked", hypothesis.raw_value_storage)

        with self.assertRaises(ValidationError):
            ColumnHypothesis(
                id="hyp.column.users.email",
                table_name="users",
                column_name="email",
                pii_candidate=True,
                raw_value_storage="allowed",
                evidence=[evidence],
            )


if __name__ == "__main__":
    unittest.main()
