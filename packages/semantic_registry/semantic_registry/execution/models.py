"""Registry helpers for Phase 9 safe preview execution contracts.

The helpers derive policy-shaped metadata from already-loaded Semantic Packs.
They do not execute SQL, open databases, or perform preview adapter work.
"""

from __future__ import annotations

from typing import Iterable

from semantic_contracts import ExecutionPolicy, SemanticPack


def execution_policy_from_packs(
    packs: Iterable[SemanticPack],
    *,
    role: str | None = None,
    default_max_preview_rows: int = 100,
) -> ExecutionPolicy:
    """Build a conservative ExecutionPolicy from matching Semantic Pack policies."""

    allowed_tables: set[str] = set()
    blocked_columns: set[str] = set()
    max_preview_row_caps: list[int] = []
    for pack in packs:
        for policy in pack.policies:
            if role is not None and role not in policy.applies_to.roles:
                continue
            allowed_tables.update(policy.allowed_tables)
            blocked_columns.update(policy.blocked_columns)
            # The semantic pack model defaults this field to 100, so only treat
            # it as policy-authored when the source data explicitly set it.
            fields_set = getattr(policy, "model_fields_set", None) or getattr(policy, "__pydantic_fields_set__", set())
            if "max_preview_rows" in fields_set:
                max_preview_row_caps.append(int(policy.max_preview_rows))
            else:
                max_preview_row_caps.append(default_max_preview_rows)
    # No matching role means no table access; downstream guard/preview lanes can
    # block deterministically instead of silently widening permissions.
    # When policies do match, keep the preview cap policy-derived so a lower cap
    # cannot be widened back to the module default during normalization.
    max_rows = min(max_preview_row_caps) if max_preview_row_caps else min(default_max_preview_rows, 1)
    return ExecutionPolicy(
        role=role,
        allowed_tables=sorted(allowed_tables),
        blocked_columns=sorted(blocked_columns),
        max_preview_rows=max_rows,
    )


__all__ = ["execution_policy_from_packs"]
