"""Deterministic MCP tool functions over the local Semantic Registry.

The tool layer returns plain JSON-compatible dictionaries so the MCP server can
adapt them without leaking Pydantic objects. It intentionally performs no SQL
execution, no database access, no vector search, and no LLM calls; Phase 2 is a
local interface over already-validated Semantic Pack metadata.
"""

from __future__ import annotations

from pathlib import Path
import re
from typing import Any, Iterable, Mapping

from semantic_contracts.mcp_tool_contracts import (
    FeedbackReceipt as ContractFeedbackReceipt,
    ListSemanticSpacesResponse,
    PlannedAmbiguity,
    RecordFeedbackResponse,
    SearchFilters,
)
from semantic_registry.feedback import FeedbackStore
from semantic_registry.runtime import AmbiguityGate, PolicyVerifier, SemanticVerifier
from semantic_registry.search import resolve_terms as registry_resolve_terms
from semantic_registry.store import DEFAULT_PACK_ROOT, PackStore

from .plan_query import plan_data_query as registry_backed_plan_data_query
from .preview_query import preview_query as registry_backed_preview_query
from .search_context import search_semantic_context as registry_backed_search_semantic_context
from .validate_sql import validate_sql as registry_backed_validate_sql

DEFAULT_FEEDBACK_ROOT = Path(".runtime") / "feedback"
_CARD_TYPE_ALIASES = {
    "business_terms": "business_term",
    "terms": "business_term",
    "metrics": "metric",
    "tables": "table",
    "columns": "column",
    "join_recipes": "join_recipe",
    "policies": "policy",
    "verified_queries": "verified_query",
    "value_dictionaries": "value_dictionary",
    "reverse_questions": "reverse_question",
}


def list_semantic_spaces(pack_root: str | Path = DEFAULT_PACK_ROOT, root: str | Path | None = None) -> dict[str, Any]:
    """Return local semantic spaces as a structured dict."""

    if root is not None:
        pack_root = root
    spaces = [
        {"space_id": space.space_id, "title": space.title, "version": space.version, "status": space.status}
        for space in PackStore(pack_root).list_spaces()
    ]
    return _dump(ListSemanticSpacesResponse(spaces=spaces))


def search_semantic_context(
    space_id: str,
    query: str,
    filters: Mapping[str, Any] | SearchFilters | None = None,
    pack_root: str | Path = DEFAULT_PACK_ROOT,
    root: str | Path | None = None,
    backend: str | None = None,
) -> dict[str, Any]:
    """Search Semantic Pack cards through an explicitly selected backend."""

    return registry_backed_search_semantic_context(
        space_id=space_id,
        query=query,
        filters=dict(filters or {}) if not isinstance(filters, SearchFilters) else filters.model_dump(mode="json"),
        pack_root=pack_root,
        root=root,
        backend=backend,
    )


def resolve_business_terms(
    space_id: str,
    terms: Iterable[str],
    pack_root: str | Path = DEFAULT_PACK_ROOT,
    root: str | Path | None = None,
) -> dict[str, Any]:
    """Resolve terms by id, label, or alias using local registry cards only."""

    pack_root = root if root is not None else pack_root
    packs = _load_space_packs(space_id, pack_root)
    response = registry_resolve_terms(terms, pack=packs[0] if len(packs) == 1 else None, space_id=space_id, root=pack_root)
    if len(packs) > 1:
        # The registry convenience API resolves one pack or reloads by id; for
        # semantic-space aliases spanning multiple packs, resolve deterministically here.
        from semantic_registry.cards import CardRegistry  # local import keeps tool startup lean.

        cards = [card for pack in packs for card in CardRegistry.from_pack(pack).cards]
        response = CardRegistry(cards).resolve_terms(terms)
    return _dump(response)


def plan_data_query(
    space_id: str,
    question: str,
    role: str | None = None,
    pack_root: str | Path = DEFAULT_PACK_ROOT,
    root: str | Path | None = None,
) -> dict[str, Any]:
    """Create a metadata-only query plan through the Registry owner."""

    return registry_backed_plan_data_query(
        space_id=space_id,
        question=question,
        role=role,
        pack_root=pack_root,
        root=root,
    )


def explain_query_plan(
    space_id: str,
    question: str,
    role: str | None = None,
    pack_root: str | Path = DEFAULT_PACK_ROOT,
    root: str | Path | None = None,
) -> dict[str, Any]:
    """Return a validation-only plan plus ambiguity-gate status.

    This is an explanatory MCP surface only: it never drafts, previews, or
    executes SQL, and it preserves planner ambiguities for the caller to ask.
    """

    plan = plan_data_query(space_id=space_id, question=question, role=role, pack_root=pack_root, root=root)
    return {
        "space_id": space_id,
        "question": question,
        "role": role,
        "plan": plan,
        "ambiguity_gate": AmbiguityGate().assess(plan),
        "execution_allowed": False,
    }


def validate_semantic_sql(
    space_id: str,
    question: str,
    sql: str,
    role: str | None = None,
    pack_root: str | Path = DEFAULT_PACK_ROOT,
    root: str | Path | None = None,
) -> dict[str, Any]:
    """Run policy and semantic verification for a SQL draft without executing it."""

    effective_root = root if root is not None else pack_root
    packs = _load_space_packs(space_id, effective_root)
    plan = plan_data_query(space_id=space_id, question=question, role=role, pack_root=effective_root)
    policy_verdict = PolicyVerifier.from_packs(packs).verify_sql(sql, role=role)
    semantic_verdict = SemanticVerifier.from_packs(packs).verify_sql(sql, plan=plan, role=role)
    return {
        "space_id": space_id,
        "question": question,
        "role": role,
        "policy_verdict": policy_verdict,
        "semantic_verdict": semantic_verdict,
        "valid": bool(policy_verdict["valid"] and semantic_verdict["valid"]),
        "execution_allowed": False,
    }


def answer_with_semantic_pack(
    space_id: str,
    question: str,
    role: str | None = None,
    pack_root: str | Path = DEFAULT_PACK_ROOT,
) -> dict[str, Any]:
    """Return deterministic prompt context for an answer model, not an answer."""

    plan = plan_data_query(space_id=space_id, question=question, role=role, pack_root=pack_root)
    search = search_semantic_context(space_id=space_id, query=question, filters={"limit": 5}, pack_root=pack_root)
    return {
        "prompt_name": "answer_with_semantic_pack",
        "space_id": space_id,
        "question": question,
        "role": role,
        "instructions": [
            "Answer only from the supplied semantic context.",
            "Do not expose blocked PII columns or raw values.",
            "Do not execute SQL; provide validation/planning guidance only.",
            "Ask the listed ambiguity questions before treating the plan as final.",
        ],
        "semantic_context": search["results"],
        "plan": plan,
        "execution_allowed": False,
    }


def preview_query(
    space_id: str,
    sql: str,
    role: str,
    pack_root: str | Path = DEFAULT_PACK_ROOT,
    root: str | Path | None = None,
    fixture_root: str | Path = Path("examples") / "demo_data",
    max_rows: int | None = None,
    data_root: str | Path | None = None,
    audit_root: str | Path | None = None,
) -> dict[str, Any]:
    """Run a validation-gated local preview through the Registry runtime."""

    return registry_backed_preview_query(
        space_id=space_id,
        sql=sql,
        role=role,
        pack_root=pack_root,
        root=root,
        fixture_root=fixture_root,
        max_rows=max_rows,
        data_root=data_root,
        audit_root=audit_root,
    )


def validate_sql(
    sql_or_space_id: str,
    sql: str | None = None,
    role: str | None = None,
    pack_root: str | Path = DEFAULT_PACK_ROOT,
    root: str | Path | None = None,
    space_id: str | None = None,
) -> dict[str, Any]:
    """Validate SQL text through the Registry SQLGuard without executing it."""

    return registry_backed_validate_sql(
        sql_or_space_id=sql_or_space_id,
        sql=sql,
        role=role,
        pack_root=pack_root,
        root=root,
        space_id=space_id,
    )




def compare_baseline_vs_system_sql(
    space_id: str,
    question: str,
    baseline_sql: str | None,
    system_sql: str | None,
    role: str | None = "marketing_analyst",
    pack_root: str | Path = DEFAULT_PACK_ROOT,
    root: str | Path | None = None,
) -> dict[str, Any]:
    """Compare baseline and Semantic Pack SQL drafts without executing either."""

    from semantic_registry.product.comparison import compare_baseline_vs_system_sql as compare_sql

    effective_root = root if root is not None else pack_root
    return compare_sql(
        question=question,
        baseline_sql=baseline_sql,
        system_sql=system_sql,
        space_id=space_id,
        role=role,
        pack_root=effective_root,
    ).to_dict()


def record_feedback(
    space_id: str,
    feedback_type: str,
    message: str,
    card_id: str | None = None,
    source: str | None = None,
    feedback_root: str | Path = DEFAULT_FEEDBACK_ROOT,
) -> dict[str, Any]:
    """Append PII-checked feedback to local JSONL storage."""

    receipt = FeedbackStore(feedback_root).record_feedback(
        {
            "space_id": space_id,
            "card_id": card_id,
            "feedback_type": feedback_type,
            "message": message,
            "source": source,
        },
        space_id=space_id,
    )
    return _dump(RecordFeedbackResponse(receipt=ContractFeedbackReceipt(feedback_id=receipt.feedback_id)))


def inspect_all(pack_root: str | Path = DEFAULT_PACK_ROOT) -> dict[str, Any]:
    """Expose deterministic local pack/card counts for smoke tests."""

    return PackStore(pack_root).inspect_all()


def _load_space_packs(space_id: str, pack_root: str | Path) -> list[Any]:
    store = PackStore(pack_root)
    packs = store.load_packs()
    selected = [
        pack
        for pack in packs
        if pack.id == space_id or any(getattr(space, "space_id", getattr(space, "id", None)) == space_id for space in pack.spaces)
    ]
    if not selected:
        raise KeyError(f"Unknown semantic space: {space_id}")
    return selected


def _coerce_search_filters(filters: Mapping[str, Any] | SearchFilters | None) -> SearchFilters:
    if filters is None:
        return SearchFilters()
    if isinstance(filters, SearchFilters):
        return filters
    return SearchFilters(**dict(filters))


def _normalize_card_type(value: str) -> str:
    lowered = value.strip().casefold()
    return _CARD_TYPE_ALIASES.get(lowered, lowered)


def _normalize_text(value: str) -> str:
    return value.casefold().replace("_", " ").replace(".", " ").replace("-", " ")


def _matches_question(question_norm: str, candidates: Iterable[str | None]) -> bool:
    for candidate in candidates:
        if not candidate:
            continue
        normalized = _normalize_text(str(candidate))
        if normalized and normalized in question_norm:
            return True
    return False


def _unique(values: Iterable[Any]) -> list[Any]:
    seen: set[Any] = set()
    result: list[Any] = []
    for value in values:
        if value is None or value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _payload_by_id(packs: Iterable[Any], card_type: str, card_id: str) -> Any | None:
    attr = {
        "business_term": "business_terms",
        "metric": "metrics",
    }.get(card_type)
    if not attr:
        return None
    for pack in packs:
        for item in getattr(pack, attr):
            if item.id == card_id:
                return item
    return None


def _select_join_recipes(packs: Iterable[Any], tables: Iterable[str]) -> list[str]:
    table_set = set(tables)
    if len(table_set) < 2:
        return []
    selected: list[str] = []
    for pack in packs:
        for join in pack.join_recipes:
            if join.left_table in table_set and join.right_table in table_set:
                selected.append(join.id)
    return _unique(selected)


def _policy_notes_for_role(packs: Iterable[Any], role: str | None) -> list[str]:
    notes: list[str] = []
    for pack in packs:
        for policy in pack.policies:
            if role is None or role in policy.applies_to.roles:
                notes.extend(policy.notes)
    return _unique(notes)


def _policy_limits_for_role(packs: Iterable[Any], role: str | None) -> tuple[set[str], set[str]]:
    allowed_tables: set[str] = set()
    blocked_columns: set[str] = set()
    for pack in packs:
        for policy in pack.policies:
            if role is not None and role not in policy.applies_to.roles:
                continue
            allowed_tables.update(policy.allowed_tables)
            blocked_columns.update(column.casefold() for column in policy.blocked_columns)
    return allowed_tables, blocked_columns


def _collect_ambiguities(packs: Iterable[Any], target_ids: set[str], terms: Iterable[Any]) -> list[PlannedAmbiguity]:
    ambiguities: list[PlannedAmbiguity] = []
    for term in terms:
        for rule in term.ambiguity_rules:
            ambiguities.append(PlannedAmbiguity(id=rule.id, target=rule.target, question=rule.question, reason=rule.condition))
    for pack in packs:
        for reverse_question in pack.reverse_questions:
            if reverse_question.target in target_ids:
                ambiguities.append(PlannedAmbiguity(
                    id=reverse_question.id,
                    target=reverse_question.target,
                    question=reverse_question.question,
                    reason=reverse_question.reason,
                ))
    deduped: list[PlannedAmbiguity] = []
    seen: set[tuple[str | None, str]] = set()
    for ambiguity in ambiguities:
        key = (ambiguity.id, ambiguity.question)
        if key not in seen:
            seen.add(key)
            deduped.append(ambiguity)
    return deduped


def _has_multiple_statements(sql: str) -> bool:
    statements = [part.strip() for part in sql.split(";") if part.strip()]
    return len(statements) > 1


def _extract_referenced_tables(sql: str) -> list[str]:
    matches = re.findall(r"(?is)\b(?:from|join)\s+([a-zA-Z_][\w.]*)(?:\s+as)?(?:\s+[a-zA-Z_]\w*)?", sql)
    return _unique(match.split(".")[-1].casefold() for match in matches)


def _extract_referenced_columns(sql: str) -> list[str]:
    return _unique(match.casefold() for match in re.findall(r"\b([a-zA-Z_]\w*\.[a-zA-Z_]\w*)\b", sql))


def _blocked_column_hits(sql: str, blocked_columns: Iterable[str]) -> list[str]:
    normalized = sql.casefold()
    hits = []
    for column in sorted(set(blocked_columns)):
        table, _, name = column.partition(".")
        patterns = [rf"\b{re.escape(table)}\s*\.\s*{re.escape(name)}\b", rf"\b{re.escape(name)}\b"]
        if any(re.search(pattern, normalized) for pattern in patterns):
            hits.append(column)
    return hits


def _dump(model: Any) -> dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump(mode="json")
    return dict(model)


__all__ = [
    "answer_with_semantic_pack",
    "explain_query_plan",
    "inspect_all",
    "list_semantic_spaces",
    "plan_data_query",
    "preview_query",
    "record_feedback",
    "resolve_business_terms",
    "search_semantic_context",
    "validate_semantic_sql",
    "validate_sql",
]
