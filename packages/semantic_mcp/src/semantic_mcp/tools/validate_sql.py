"""MCP-facing SQL validation adapter over the Registry SQLGuard.

The guard remains validation-only. It never opens a database connection and
always returns ``execution_allowed=false`` so clients cannot confuse validation
with query execution.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from semantic_registry.sql_guard import validate_sql as registry_validate_sql
from semantic_registry.store import DEFAULT_PACK_ROOT


def validate_sql(
    sql_or_space_id: str,
    sql: str | None = None,
    role: str | None = None,
    pack_root: str | Path = DEFAULT_PACK_ROOT,
    root: str | Path | None = None,
    space_id: str | None = None,
) -> dict[str, Any]:
    """Validate SQL against Semantic Pack policies without executing it."""

    effective_root = root if root is not None else pack_root
    if sql is None:
        sql_text = sql_or_space_id
        effective_space_id = space_id or "revenue"
    else:
        sql_text = sql
        effective_space_id = space_id or sql_or_space_id
    return registry_validate_sql(
        sql_text,
        space_id=effective_space_id,
        role=role,
        pack_root=effective_root,
    ).model_dump(mode="json")


__all__ = ["validate_sql"]
