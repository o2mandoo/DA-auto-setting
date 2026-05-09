"""Semantic Builder package for local file-only draft pack generation.

Phase 4 deliberately stays local-file based: no database execution, no MCP
runtime, no VDB, and no LLM calls are exposed from this package boundary.
"""

from semantic_builder.builder import build_semantic_pack_draft

__version__ = "0.1.0"

__all__ = ["__version__", "build_semantic_pack_draft"]
