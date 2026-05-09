"""Eval helpers for MCP tool integration without MCP transport.

These helpers exercise the local function-level MCP tool surface directly so
eval and contract tests can verify behavior without starting stdio or pulling
in the official MCP runtime. If the optional preview surface is unavailable in
some environment, the fallback is explicit and recorded in the returned data
instead of being silent.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from . import inspect_registration_surface
from .tools import (
    list_semantic_spaces,
    plan_data_query,
    preview_query,
    resolve_business_terms,
    search_semantic_context,
    validate_sql,
)
from .tools.preview_query import PreviewRuntimeUnavailable

DEFAULT_EVAL_FIXTURE_ROOT = Path("examples") / "demo_data"


def build_search_semantic_context_eval(
    space_id: str,
    query: str,
    *,
    pack_root: str | Path,
) -> dict[str, Any]:
    """Return a local search probe without requiring MCP transport."""

    return search_semantic_context(
        space_id=space_id,
        query=query,
        filters={"backend": "keyword", "limit": 5},
        root=pack_root,
    )


def build_resolve_business_terms_eval(
    space_id: str,
    terms: list[str],
    *,
    pack_root: str | Path,
) -> dict[str, Any]:
    """Return a local business-term resolution probe."""

    return resolve_business_terms(space_id=space_id, terms=terms, root=pack_root)


def build_plan_data_query_eval(
    space_id: str,
    question: str,
    *,
    role: str,
    pack_root: str | Path,
) -> dict[str, Any]:
    """Return a local planning probe with execution disabled."""

    return plan_data_query(space_id=space_id, question=question, role=role, root=pack_root)


def build_validate_sql_eval(
    sql: str,
    *,
    space_id: str,
    role: str,
    pack_root: str | Path,
) -> dict[str, Any]:
    """Return a local SQL validation probe with no execution path."""

    return validate_sql(sql_or_space_id=space_id, sql=sql, role=role, root=pack_root)


def build_preview_query_eval(
    space_id: str,
    sql: str,
    *,
    role: str,
    pack_root: str | Path,
    fixture_root: str | Path = DEFAULT_EVAL_FIXTURE_ROOT,
    max_rows: int = 2,
) -> dict[str, Any]:
    """Return a local preview probe or an explicit fallback record."""

    try:
        response = preview_query(
            space_id,
            sql,
            role=role,
            root=pack_root,
            fixture_root=fixture_root,
            max_rows=max_rows,
        )
    except (PreviewRuntimeUnavailable, RuntimeError, ModuleNotFoundError) as exc:
        return {
            "available": False,
            "tool_name": "preview_query",
            "execution_allowed": False,
            "preview_allowed": False,
            "rows": [],
            "row_count": 0,
            "truncated": False,
            "warnings": [str(exc), "No preview fallback was used."],
            "fallback": "explicit_preview_runtime_unavailable",
        }

    response = dict(response)
    response.setdefault("tool_name", "preview_query")
    response["available"] = True
    return response


def build_mcp_eval_bundle(
    *,
    space_id: str,
    question: str,
    sql: str,
    role: str,
    terms: list[str],
    pack_root: str | Path,
    fixture_root: str | Path = DEFAULT_EVAL_FIXTURE_ROOT,
    max_rows: int = 2,
) -> dict[str, Any]:
    """Collect a deterministic, transport-free MCP eval bundle."""

    registration_surface = inspect_registration_surface()
    spaces = list_semantic_spaces(pack_root=pack_root)
    return {
        "registration_surface": registration_surface,
        "list_semantic_spaces": spaces,
        "search_semantic_context": build_search_semantic_context_eval(
            space_id=space_id,
            query=question,
            pack_root=pack_root,
        ),
        "resolve_business_terms": build_resolve_business_terms_eval(
            space_id=space_id,
            terms=terms,
            pack_root=pack_root,
        ),
        "plan_data_query": build_plan_data_query_eval(
            space_id=space_id,
            question=question,
            role=role,
            pack_root=pack_root,
        ),
        "validate_sql": build_validate_sql_eval(
            sql=sql,
            space_id=space_id,
            role=role,
            pack_root=pack_root,
        ),
        "preview_query": build_preview_query_eval(
            space_id=space_id,
            sql=sql,
            role=role,
            pack_root=pack_root,
            fixture_root=fixture_root,
            max_rows=max_rows,
        ),
        "execution_allowed": False,
        "transport_required": False,
    }


__all__ = [
    "DEFAULT_EVAL_FIXTURE_ROOT",
    "build_mcp_eval_bundle",
    "build_plan_data_query_eval",
    "build_preview_query_eval",
    "build_resolve_business_terms_eval",
    "build_search_semantic_context_eval",
    "build_validate_sql_eval",
]
