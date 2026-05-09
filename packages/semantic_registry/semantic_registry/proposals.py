"""Phase 6 local proposal helpers for human confirmation workflows."""

from __future__ import annotations

from typing import Any

from semantic_contracts import (
    ConfirmationStatus,
    EvidenceRef,
    HumanConfirmation,
    PackProposal,
    ProposalStatus,
    SourceKind,
)


def file_evidence_ref(
    reference_id: str,
    file_path: str,
    *,
    sheet_name: str | None = None,
    column_refs: list[str] | None = None,
    row_locator_digest: str | None = None,
    notes: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> EvidenceRef:
    """Build a PII-safe file-origin pointer; never include raw cell values."""

    return EvidenceRef(
        source_kind=SourceKind.FILE,
        reference_id=reference_id,
        file_path=file_path,
        sheet_name=sheet_name,
        column_refs=list(column_refs or []),
        row_locator_digest=row_locator_digest,
        notes=notes,
        metadata=dict(metadata or {}),
    )


def postgresql_evidence_ref(
    reference_id: str,
    *,
    table_name: str | None = None,
    schema_name: str | None = None,
    database: str | None = None,
    column_refs: list[str] | None = None,
    row_locator_digest: str | None = None,
    query_fingerprint: str | None = None,
    notes: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> EvidenceRef:
    """Build a future PostgreSQL-origin pointer without storing row values."""

    return EvidenceRef(
        source_kind=SourceKind.POSTGRESQL,
        reference_id=reference_id,
        database=database,
        schema_name=schema_name,
        table_name=table_name,
        column_refs=list(column_refs or []),
        row_locator_digest=row_locator_digest,
        query_fingerprint=query_fingerprint,
        notes=notes,
        metadata=dict(metadata or {}),
    )


def create_pack_proposal(
    *,
    proposal_id: str,
    pack_id: str,
    target_ref: str,
    proposed_patch: dict[str, Any],
    evidence_refs: list[EvidenceRef],
    change_type: str = "update",
    status: ProposalStatus = ProposalStatus.DRAFT,
    created_by: str | None = None,
    created_at: str | None = None,
    indexable_summary: str | None = None,
) -> PackProposal:
    """Create a local proposal record; callers must persist it explicitly."""

    return PackProposal(
        proposal_id=proposal_id,
        pack_id=pack_id,
        target_ref=target_ref,
        proposed_patch=dict(proposed_patch),
        evidence_refs=list(evidence_refs),
        change_type=change_type,  # type: ignore[arg-type]
        status=status,
        created_by=created_by,
        created_at=created_at,
        indexable_summary=indexable_summary,
    )


def record_confirmation(
    proposal: PackProposal,
    confirmation: HumanConfirmation,
) -> PackProposal:
    """Return a new proposal record with appended confirmation, no pack mutation."""

    if confirmation.proposal_id != proposal.proposal_id:
        raise ValueError("confirmation proposal_id must match proposal")
    return proposal.model_copy(update={"confirmations": [*proposal.confirmations, confirmation]})


def proposal_index_payload(proposal: PackProposal) -> dict[str, object]:
    """Return a safe text-search payload; this is not a VDB/Weaviate client."""

    return {
        "proposal_id": proposal.proposal_id,
        "pack_id": proposal.pack_id,
        "target_ref": proposal.target_ref,
        "change_type": proposal.change_type,
        "status": proposal.status.value,
        "indexable_summary": proposal.indexable_summary,
        "evidence_refs": [
            {
                "source_kind": evidence.source_kind.value,
                "reference_id": evidence.reference_id,
                "file_path": evidence.file_path,
                "database": evidence.database,
                "schema_name": evidence.schema_name,
                "table_name": evidence.table_name,
                "column_refs": list(evidence.column_refs),
                "row_locator_digest": evidence.row_locator_digest,
                "query_fingerprint": evidence.query_fingerprint,
            }
            for evidence in proposal.evidence_refs
        ],
        "vdb_implementation": False,
    }


def has_explicit_approval(proposal: PackProposal) -> bool:
    return any(confirmation.status == ConfirmationStatus.APPROVED for confirmation in proposal.confirmations)
