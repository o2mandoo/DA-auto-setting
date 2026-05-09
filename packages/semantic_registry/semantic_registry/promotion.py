"""Phase 6 promotion guards for explicit human-confirmed proposals."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Mapping

from semantic_contracts import ConfirmationStatus, PackProposal, PackStatus, ProposalStatus, SemanticPack


_EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.IGNORECASE)
_PHONE_RE = re.compile(r"(?<!\d)(?:\+?\d[\d\-\s().]{7,}\d)(?!\d)")
_SAFE_TOKEN_RE = re.compile(r"^[A-Za-z0-9_.:-]+$")
_VERSION_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)(?:[-+].*)?$")


class PromotionError(ValueError):
    """Raised when Phase 6 promotion would violate audit or safety rules."""


@dataclass(frozen=True)
class PromotionConfirmation:
    confirmation_id: str
    target_id: str
    status: str
    source_ref: str

    @classmethod
    def from_record(cls, record: "PromotionConfirmation | Mapping[str, Any]") -> "PromotionConfirmation":
        if isinstance(record, PromotionConfirmation):
            return record
        if not isinstance(record, Mapping):
            raise PromotionError("confirmation records must be mappings")
        source_ref = _safe_source_ref(record.get("source_ref"))
        confirmation = cls(
            confirmation_id=str(record.get("confirmation_id") or ""),
            target_id=str(record.get("target_id") or record.get("proposal_id") or ""),
            status=str(record.get("status") or ""),
            source_ref=source_ref,
        )
        confirmation._validate_safe()
        return confirmation

    def as_audit_dict(self) -> dict[str, str]:
        return {
            "confirmation_id": self.confirmation_id,
            "target_id": self.target_id,
            "status": self.status,
            "source_ref": self.source_ref,
        }

    def _validate_safe(self) -> None:
        for name, value in (
            ("confirmation_id", self.confirmation_id),
            ("target_id", self.target_id),
            ("status", self.status),
            ("source_ref", self.source_ref),
        ):
            if not value:
                raise PromotionError(f"confirmation {name} must not be blank")
            _reject_raw_pii(value)


@dataclass(frozen=True)
class PromotionResult:
    pack: SemanticPack
    source_version: str
    target_version: str
    confirmation_ids: tuple[str, ...]


def promote_pack(
    pack: SemanticPack,
    *,
    target_status: PackStatus | str,
    confirmations: list[PromotionConfirmation | Mapping[str, Any]],
    proposal_id: str,
    promoted_at: str | None = None,
) -> PromotionResult:
    """Return a promoted pack copy with audit metadata; never mutate input packs."""

    _reject_raw_pii(proposal_id)
    normalized_confirmations = _normalize_confirmations(confirmations, proposal_id=proposal_id)
    status = PackStatus(target_status)
    source_version = pack.version
    target_version = next_patch_version(pack.version) if pack.status == PackStatus.APPROVED else pack.version
    metadata = dict(pack.metadata)
    # Only safe identifiers/source refs are copied into audit metadata. Free-form
    # answers/rationales stay out of the pack to avoid raw PII propagation.
    metadata["last_promotion"] = {
        "proposal_id": proposal_id,
        "promoted_at": promoted_at,
        "source_status": pack.status.value,
        "target_status": status.value,
        "source_version": source_version,
        "target_version": target_version,
        "write_policy": "copy_on_write_no_approved_in_place_mutation",
        "confirmations": [confirmation.as_audit_dict() for confirmation in normalized_confirmations],
    }
    promoted_pack = pack.model_copy(deep=True, update={"status": status, "version": target_version, "metadata": metadata})
    return PromotionResult(
        pack=promoted_pack,
        source_version=source_version,
        target_version=target_version,
        confirmation_ids=tuple(confirmation.confirmation_id for confirmation in normalized_confirmations),
    )


def assert_approved_pack_update_allowed(
    original: SemanticPack,
    candidate: SemanticPack,
    *,
    confirmations: list[PromotionConfirmation | Mapping[str, Any]],
    proposal_id: str,
) -> None:
    """Block silent in-place mutation of approved packs; require versioned promotion."""

    _normalize_confirmations(confirmations, proposal_id=proposal_id)
    if original.status == PackStatus.APPROVED and candidate != original and candidate.version == original.version:
        raise PromotionError("approved pack mutation is blocked; create a versioned promotion path")


def next_patch_version(version: str) -> str:
    match = _VERSION_RE.match(version)
    if not match:
        raise PromotionError("version must be MAJOR.MINOR.PATCH")
    major, minor, patch = (int(part) for part in match.groups())
    return f"{major}.{minor}.{patch + 1}"


def promotion_path(pack_id: str, version: str) -> str:
    if not _SAFE_TOKEN_RE.match(pack_id) or not _SAFE_TOKEN_RE.match(version):
        raise PromotionError("pack_id and version must be safe path tokens")
    return f"{pack_id.replace('.', '_')}.v{version.replace('.', '_')}.yaml"


def require_explicit_confirmation(proposal: PackProposal) -> PackProposal:
    """Validate proposal preconditions without mutating an approved pack in place."""

    has_approval = any(confirmation.status == ConfirmationStatus.APPROVED for confirmation in proposal.confirmations)
    if not has_approval:
        raise ValueError("promotion requires an explicit approved confirmation record")
    if proposal.status not in {ProposalStatus.REVIEWED, ProposalStatus.APPROVED}:
        raise ValueError("promotion requires a reviewed or approved proposal status")
    return proposal


def promotion_manifest(proposal: PackProposal, *, next_version: str) -> dict[str, str]:
    """Create a deterministic version/proposal manifest; no query or DB execution."""

    require_explicit_confirmation(proposal)
    if not next_version or not next_version.strip():
        raise ValueError("next_version must not be blank")
    return {
        "pack_id": proposal.pack_id,
        "proposal_id": proposal.proposal_id,
        "target_ref": proposal.target_ref,
        "next_version": next_version,
        "mutation_mode": "versioned_proposal_only",
    }


def _normalize_confirmations(
    confirmations: list[PromotionConfirmation | Mapping[str, Any]],
    *,
    proposal_id: str,
) -> list[PromotionConfirmation]:
    if not confirmations:
        raise PromotionError("promotion requires at least one explicit confirmation")
    normalized = [PromotionConfirmation.from_record(record) for record in confirmations]
    for confirmation in normalized:
        status = confirmation.status.casefold()
        if status in {"rejected", "dismissed"}:
            raise PromotionError(f"cannot promote with {status} confirmation")
        if status not in {"confirmed", "approved", "reviewed"}:
            raise PromotionError(f"cannot promote with {status} confirmation")
        # Historical confirmation records may point at the originating
        # Phase 5 question/proposal id; Phase 6 audit keeps that safe id rather
        # than silently rewriting it during pack promotion.
    return normalized


def _safe_source_ref(source_ref: Any) -> str:
    if isinstance(source_ref, Mapping):
        ref_type = str(source_ref.get("type") or "")
        name = str(source_ref.get("name") or "")
        value = f"{ref_type}:{name}"
    else:
        value = str(source_ref or "")
    _reject_raw_pii(value)
    return value


def _reject_raw_pii(value: str) -> None:
    if _EMAIL_RE.search(value) or _PHONE_RE.search(value):
        raise PromotionError("promotion metadata must not contain raw PII")
