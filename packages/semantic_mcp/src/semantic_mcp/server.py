"""Import-time-safe MCP stdio server wrapper.

Function-level tools can be tested without the MCP SDK. Launching stdio requires
the official SDK and raises an explicit dependency error if it is missing; this
avoids silently shipping a fake MCP runtime.
"""

from __future__ import annotations

import sys
from typing import Any

_MISSING_MCP_MESSAGE = (
    "The official MCP Python SDK is required to launch semantic-mcp. "
    "Install the package declared by packages/semantic_mcp/pyproject.toml "
    "(modelcontextprotocol/python-sdk; import path mcp.server.fastmcp.FastMCP)."
)

REGISTERED_TOOLS = (
    "list_semantic_spaces",
    "search_semantic_context",
    "resolve_business_terms",
    "plan_data_query",
    "validate_sql",
    "preview_query",
    "record_feedback",
    "compare_baseline_vs_system_sql",
)

REGISTERED_RESOURCES = (
    "semantic://packs",
    "semantic://packs/{pack_id}",
    "semantic://packs/{pack_id}/terms",
    "semantic://packs/{pack_id}/metrics",
    "semantic://packs/{pack_id}/policies",
    "semantic://packs/{pack_id}/verified-queries",
)

REGISTERED_PROMPTS = ("answer_with_semantic_pack",)


def create_server() -> Any:
    """Create and register the local stdio MCP server surface."""

    try:
        from mcp.server.fastmcp import FastMCP
    except ModuleNotFoundError as exc:  # pragma: no cover - depends on local SDK install.
        raise RuntimeError(_MISSING_MCP_MESSAGE) from exc

    from .resources import (
        build_pack_resource,
        build_packs_resource,
        get_pack_metrics,
        get_pack_policies,
        get_pack_terms,
        get_pack_verified_queries,
    )
    from .tools import (
        list_semantic_spaces,
        plan_data_query,
        preview_query,
        record_feedback,
        compare_baseline_vs_system_sql,
        resolve_business_terms,
        search_semantic_context,
        validate_sql,
    )
    from .prompts import get_prompt

    server = FastMCP("semantic-data-context")

    # Register only deterministic metadata/validation tools. Query execution,
    # BI rendering, database connectors, and hidden LLM calls are intentionally absent.
    for tool in (
        list_semantic_spaces,
        search_semantic_context,
        resolve_business_terms,
        plan_data_query,
        validate_sql,
        preview_query,
        record_feedback,
        compare_baseline_vs_system_sql,
    ):
        server.tool()(tool)

    @server.resource("semantic://packs")
    def packs_resource() -> dict[str, Any]:
        return build_packs_resource()

    @server.resource("semantic://packs/{pack_id}")
    def pack_resource(pack_id: str) -> dict[str, Any]:
        return build_pack_resource(pack_id)

    @server.resource("semantic://packs/{pack_id}/terms")
    def terms_resource(pack_id: str) -> dict[str, Any]:
        return get_pack_terms(pack_id)

    @server.resource("semantic://packs/{pack_id}/metrics")
    def metrics_resource(pack_id: str) -> dict[str, Any]:
        return get_pack_metrics(pack_id)

    @server.resource("semantic://packs/{pack_id}/policies")
    def policies_resource(pack_id: str) -> dict[str, Any]:
        return get_pack_policies(pack_id)

    @server.resource("semantic://packs/{pack_id}/verified-queries")
    def verified_queries_resource(pack_id: str) -> dict[str, Any]:
        return get_pack_verified_queries(pack_id)

    @server.prompt()
    def answer_with_semantic_pack() -> str:
        """Prompt contract for source-grounded semantic-pack answers."""

        prompt = get_prompt("answer_with_semantic_pack")
        return str(prompt["template"])

    return server


def inspect_registration_surface() -> dict[str, Any]:
    """Return deterministic registration expectations without requiring MCP SDK.

    This is validation-only evidence for local tests; it does not instantiate a
    fake server or perform hidden fallback registration.
    """

    return {
        "tools": list(REGISTERED_TOOLS),
        "resources": list(REGISTERED_RESOURCES),
        "prompts": list(REGISTERED_PROMPTS),
        "registered_tools": list(REGISTERED_TOOLS),
        "registered_resources": list(REGISTERED_RESOURCES),
        "registered_prompts": list(REGISTERED_PROMPTS),
        "execution_allowed": False,
        "production_execution_allowed": False,
        "mcp_sdk_required_for_stdio": True,
        "stdio_requires_official_mcp_sdk": True,
        "no_execute_query_tool": True,
        "preview_scope": "local/demo/test",
    }


def run_stdio() -> None:
    """Run the MCP stdio server when the official SDK is installed."""

    create_server().run(transport="stdio")


def main() -> int:
    """Console entrypoint for ``semantic-mcp``."""

    try:
        run_stdio()
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":  # pragma: no cover - console path.
    raise SystemExit(main())
