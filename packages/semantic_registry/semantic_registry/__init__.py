"""Local Semantic Registry APIs."""

from importlib import import_module
from typing import Any

from .cards import CardDocument, CardRegistry, RegistryCard, iter_pack_card_documents, iter_pack_cards
from .feedback import FeedbackReceipt, FeedbackStore, save_feedback
from .query_planner import QueryPlanner, load_space_packs, plan_data_query
from .search import CardSearchResult, SearchIndex, resolve_terms, search_cards
from .sql_guard import SQLGuard, validate_sql
from .store import (
    PackStore,
    PackSummary,
    SpaceSummary,
    inspect_all,
    list_packs,
    list_spaces,
    load_pack,
    load_packs,
)

__all__ = [
    "CardDocument",
    "CardRegistry",
    "CardSearchResult",
    "FeedbackReceipt",
    "FeedbackStore",
    "PackStore",
    "PackSummary",
    "QueryPlanner",
    "RegistryCard",
    "SQLGuard",
    "SearchIndex",
    "SpaceSummary",
    "inspect_all",
    "iter_pack_card_documents",
    "iter_pack_cards",
    "load_space_packs",
    "list_packs",
    "list_spaces",
    "resolve_terms",
    "load_pack",
    "load_packs",
    "plan_data_query",
    "save_feedback",
    "search_cards",
    "validate_sql",
]

# Phase 6 proposal/promotion modules are implemented by separate team lanes.
# Resolve only the public integration symbols lazily so this package can import
# during merge ordering gaps without widening the MCP surface or executing SQL.
_PHASE6_EXPLICIT_EXPORTS = {
    "proposals": (
        "create_pack_proposal",
        "file_evidence_ref",
        "has_explicit_approval",
        "postgresql_evidence_ref",
        "proposal_index_payload",
        "record_confirmation",
    ),
    "promotion": (
        "PromotionConfirmation",
        "PromotionError",
        "PromotionResult",
        "assert_approved_pack_update_allowed",
        "next_patch_version",
        "promote_pack",
        "promotion_manifest",
        "promotion_path",
        "require_explicit_confirmation",
    ),
}


def _phase6_export_names() -> tuple[str, ...]:
    names: list[str] = []
    for module_name, explicit_names in _PHASE6_EXPLICIT_EXPORTS.items():
        try:
            module = import_module(f"{__name__}.{module_name}")
        except ModuleNotFoundError as exc:
            if exc.name == f"{__name__}.{module_name}":
                continue
            raise
        module_names = tuple(getattr(module, "__all__", explicit_names))
        names.extend(name for name in explicit_names if name in module_names or hasattr(module, name))
    return tuple(names)


__all__.extend(name for name in _phase6_export_names() if name not in __all__)


def __getattr__(name: str) -> Any:
    for module_name, explicit_names in _PHASE6_EXPLICIT_EXPORTS.items():
        if name not in explicit_names:
            continue
        try:
            module = import_module(f"{__name__}.{module_name}")
        except ModuleNotFoundError as exc:
            if exc.name == f"{__name__}.{module_name}":
                continue
            raise
        module_names = tuple(getattr(module, "__all__", explicit_names))
        if name in module_names or hasattr(module, name):
            value = getattr(module, name)
            globals()[name] = value
            return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(_phase6_export_names()))
