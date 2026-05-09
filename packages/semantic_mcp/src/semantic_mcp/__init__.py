"""Semantic MCP function-level surface.

Importing this package is dependency-light: the MCP SDK and contract/runtime
dependencies are imported lazily only when a function-level tool is accessed or
when the stdio transport is started.
"""

_TOOL_EXPORTS = {
    "list_semantic_spaces",
    "search_semantic_context",
    "resolve_business_terms",
    "plan_data_query",
    "preview_query",
    "validate_sql",
    "record_feedback",
}

__version__ = "0.1.0"

__all__ = [
    "__version__",
    "create_server",
    "inspect_registration_surface",
    "list_semantic_spaces",
    "main",
    "search_semantic_context",
    "resolve_business_terms",
    "plan_data_query",
    "preview_query",
    "run_stdio",
    "validate_sql",
    "record_feedback",
]


def __getattr__(name: str):
    """Lazily expose tool functions so server imports remain dependency-safe."""

    if name in _TOOL_EXPORTS:
        from . import tools

        return getattr(tools, name)
    if name in {"create_server", "inspect_registration_surface", "main", "run_stdio"}:
        from . import server

        return getattr(server, name)
    raise AttributeError(f"module 'semantic_mcp' has no attribute {name!r}")
