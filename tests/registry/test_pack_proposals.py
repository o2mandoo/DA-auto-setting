from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "semantic_contracts"))
sys.path.insert(0, str(ROOT / "packages" / "semantic_registry"))

from semantic_contracts import ConfirmationStatus, HumanConfirmation, ProposalStatus  # noqa: E402
from semantic_registry.proposals import (  # noqa: E402
    create_pack_proposal,
    file_evidence_ref,
    postgresql_evidence_ref,
    proposal_index_payload,
    record_confirmation,
)
from semantic_registry.promotion import promotion_manifest, require_explicit_confirmation  # noqa: E402


class PackProposalContractTests(unittest.TestCase):
    def test_file_and_postgresql_evidence_refs_are_safe_index_payloads(self) -> None:
        proposal = create_pack_proposal(
            proposal_id="prop_001",
            pack_id="demo_company.revenue",
            target_ref="metric.net_revenue",
            proposed_patch={"formula_sql": "sum(payments.amount) - sum(payments.refunded_amount)"},
            evidence_refs=[
                file_evidence_ref(
                    "file:demo:payments",
                    "examples/demo_data/payments.csv",
                    column_refs=["payments.amount", "payments.refunded_amount"],
                    row_locator_digest="sha256:abc123",
                ),
                postgresql_evidence_ref(
                    "pg:warehouse:payments",
                    database="warehouse",
                    schema_name="public",
                    table_name="payments",
                    column_refs=["payments.amount"],
                    query_fingerprint="sha256:def456",
                ),
            ],
            indexable_summary="net revenue proposal using safe column identifiers",
        )

        payload = proposal_index_payload(proposal)

        self.assertFalse(payload["vdb_implementation"])
        self.assertEqual([item["source_kind"] for item in payload["evidence_refs"]], ["file", "postgresql"])
        self.assertNotIn("proposed_patch", payload)
        self.assertEqual(proposal.status, ProposalStatus.DRAFT)

    def test_proposal_rejects_raw_pii_values_and_raw_value_keys(self) -> None:
        evidence = file_evidence_ref("file:demo", "examples/demo_data/users.csv")

        with self.assertRaises(ValueError):
            create_pack_proposal(
                proposal_id="prop_pii_email",
                pack_id="demo_company.revenue",
                target_ref="column.users.email",
                proposed_patch={"example": "customer@example.com"},
                evidence_refs=[evidence],
            )

        with self.assertRaises(ValueError):
            create_pack_proposal(
                proposal_id="prop_raw_values",
                pack_id="demo_company.revenue",
                target_ref="column.users.email",
                proposed_patch={"raw_values": ["blocked"]},
                evidence_refs=[evidence],
            )

    def test_evidence_metadata_rejects_raw_values(self) -> None:
        with self.assertRaises(ValueError):
            file_evidence_ref(
                "file:demo",
                "examples/demo_data/users.csv",
                metadata={"sample_values": ["010-1234-5678"]},
            )

    def test_promotion_requires_explicit_approved_confirmation(self) -> None:
        proposal = create_pack_proposal(
            proposal_id="prop_approved",
            pack_id="demo_company.revenue",
            target_ref="term.new_customer",
            proposed_patch={"definition": "first paid order within the selected period"},
            evidence_refs=[file_evidence_ref("file:demo:users", "examples/demo_data/users.csv")],
            status=ProposalStatus.REVIEWED,
        )

        with self.assertRaises(ValueError):
            require_explicit_confirmation(proposal)

        confirmed = record_confirmation(
            proposal,
            HumanConfirmation(
                confirmation_id="conf_001",
                proposal_id="prop_approved",
                status=ConfirmationStatus.APPROVED,
                reviewer="marketing_analyst",
                rationale="Reviewed against source column definitions",
            ),
        )

        manifest = promotion_manifest(confirmed, next_version="0.1.1")
        self.assertEqual(manifest["mutation_mode"], "versioned_proposal_only")
        self.assertEqual(manifest["proposal_id"], "prop_approved")

    def test_statuses_support_rejected_and_dismissed(self) -> None:
        rejected = create_pack_proposal(
            proposal_id="prop_rejected",
            pack_id="demo_company.revenue",
            target_ref="join.users_payments",
            proposed_patch={"reason": "duplicate hypothesis"},
            evidence_refs=[file_evidence_ref("file:demo", "examples/demo_data/payments.csv")],
            status=ProposalStatus.REJECTED,
        )
        dismissed_confirmation = HumanConfirmation(
            confirmation_id="conf_dismissed",
            proposal_id="prop_rejected",
            status=ConfirmationStatus.DISMISSED,
            reviewer="data_steward",
        )

        self.assertEqual(rejected.status.value, "rejected")
        self.assertEqual(dismissed_confirmation.status.value, "dismissed")


if __name__ == "__main__":
    unittest.main()
