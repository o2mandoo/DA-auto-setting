from __future__ import annotations

import unittest

from semantic_contracts import ConfirmationStatus, HumanConfirmation, ProposalStatus
from semantic_registry.proposals import create_pack_proposal, file_evidence_ref, record_confirmation
from semantic_registry.promotion import promotion_manifest, require_explicit_confirmation


class PackPromotionGuardTests(unittest.TestCase):
    def _proposal(self, *, status: ProposalStatus = ProposalStatus.REVIEWED):
        return create_pack_proposal(
            proposal_id="prop_001",
            pack_id="demo_company.revenue",
            target_ref="metric.net_revenue",
            proposed_patch={"formula_sql": "sum(payments.amount) - sum(payments.refunded_amount)"},
            evidence_refs=[
                file_evidence_ref(
                    "file:phase5:hypotheses",
                    "runtime/phase5_leader_eval/superstore/semantic_hypotheses.jsonl",
                    column_refs=["payments.amount", "payments.refunded_amount"],
                )
            ],
            status=status,
            indexable_summary="net revenue proposal using safe column identifiers",
        )

    def test_promotion_requires_explicit_approved_confirmation(self) -> None:
        proposal = self._proposal()

        with self.assertRaisesRegex(ValueError, "explicit approved confirmation"):
            require_explicit_confirmation(proposal)

        confirmed = record_confirmation(
            proposal,
            HumanConfirmation(
                confirmation_id="conf_001",
                proposal_id="prop_001",
                status=ConfirmationStatus.APPROVED,
                reviewer="data_steward",
                rationale="Reviewed source refs only",
            ),
        )

        self.assertIs(require_explicit_confirmation(confirmed), confirmed)

    def test_promotion_manifest_requires_reviewed_or_approved_proposal_status(self) -> None:
        draft = record_confirmation(
            self._proposal(status=ProposalStatus.DRAFT),
            HumanConfirmation(
                confirmation_id="conf_001",
                proposal_id="prop_001",
                status=ConfirmationStatus.APPROVED,
                reviewer="data_steward",
            ),
        )

        with self.assertRaisesRegex(ValueError, "reviewed or approved proposal status"):
            promotion_manifest(draft, next_version="0.1.1")

    def test_promotion_manifest_is_versioned_proposal_only(self) -> None:
        confirmed = record_confirmation(
            self._proposal(status=ProposalStatus.APPROVED),
            HumanConfirmation(
                confirmation_id="conf_001",
                proposal_id="prop_001",
                status=ConfirmationStatus.APPROVED,
                reviewer="data_steward",
            ),
        )

        manifest = promotion_manifest(confirmed, next_version="0.1.1")

        self.assertEqual(
            manifest,
            {
                "pack_id": "demo_company.revenue",
                "proposal_id": "prop_001",
                "target_ref": "metric.net_revenue",
                "next_version": "0.1.1",
                "mutation_mode": "versioned_proposal_only",
            },
        )

    def test_confirmation_proposal_mismatch_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "proposal_id must match"):
            record_confirmation(
                self._proposal(),
                HumanConfirmation(
                    confirmation_id="conf_bad",
                    proposal_id="other_proposal",
                    status=ConfirmationStatus.APPROVED,
                    reviewer="data_steward",
                ),
            )

    def test_confirmation_text_rejects_raw_pii(self) -> None:
        with self.assertRaisesRegex(ValueError, "raw PII"):
            record_confirmation(
                self._proposal(),
                HumanConfirmation(
                    confirmation_id="conf_bad",
                    proposal_id="prop_001",
                    status=ConfirmationStatus.APPROVED,
                    reviewer="data_steward",
                    rationale="contact owner@example.com",
                ),
            )


if __name__ == "__main__":
    unittest.main()
