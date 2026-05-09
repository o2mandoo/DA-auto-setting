"""MCP-facing query planning adapter over the Registry QueryPlanner.

This module is intentionally thin: the Registry owns Phase 3 planning policy,
while MCP only serializes the validation-only result for external clients.
There is no SQL generation, SQL execution, LLM fallback, or VDB lookup here.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from semantic_registry.query_planner import plan_data_query as registry_plan_data_query
from semantic_registry.store import DEFAULT_PACK_ROOT


def plan_data_query(
    space_id: str,
    question: str,
    role: str | None = None,
    pack_root: str | Path = DEFAULT_PACK_ROOT,
    root: str | Path | None = None,
) -> dict[str, Any]:
    """Return a Registry-backed, metadata-only query plan."""

    effective_root = root if root is not None else pack_root
    return registry_plan_data_query(
        space_id=space_id,
        question=question,
        role=role,
        pack_root=effective_root,
    ).model_dump(mode="json")


__all__ = ["plan_data_query"]
