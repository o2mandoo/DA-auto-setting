"""Stdlib-only Semantic Pack contract helpers for Phase 0 tests.

These helpers intentionally avoid importing product packages. Phase 0 verifier tests
should prove the demo Semantic Pack shape and guardrail representation without
requiring Registry, MCP, Builder, or third-party runtime dependencies.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEMO_PACK_PATH = ROOT / "semantic_packs" / "demo_company" / "revenue.v0_1.yaml"

CARD_LIST_KEYS = (
    "tables",
    "columns",
    "value_dictionaries",
    "metrics",
    "business_terms",
    "join_recipes",
    "policies",
    "verified_queries",
    "reverse_questions",
)


def load_structured_yaml(path: Path) -> dict[str, Any]:
    """Load a YAML file using PyYAML when present, with JSON fallback.

    The demo pack may be represented as JSON-compatible YAML so the Phase 0
    contract tests stay runnable in a clean stdlib-only environment.
    """
    text = path.read_text(encoding="utf-8")
    if not text.strip():
        raise AssertionError(f"{path} is empty")

    try:  # optional dependency; tests do not require it
        import yaml  # type: ignore
    except Exception:
        return json.loads(text)

    loaded = yaml.safe_load(text)
    if not isinstance(loaded, dict):
        raise AssertionError(f"{path} did not load as a mapping")
    return loaded


def load_demo_semantic_pack() -> dict[str, Any]:
    payload = load_structured_yaml(DEMO_PACK_PATH)
    if "semantic_pack" not in payload:
        raise AssertionError("demo pack must use top-level semantic_pack key")
    pack = payload["semantic_pack"]
    if not isinstance(pack, dict):
        raise AssertionError("semantic_pack must be a mapping")
    return pack


def by_id(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for item in items:
        item_id = item.get("id")
        if not isinstance(item_id, str) or not item_id:
            raise AssertionError(f"item missing string id: {item!r}")
        if item_id in indexed:
            raise AssertionError(f"duplicate id: {item_id}")
        indexed[item_id] = item
    return indexed


def assert_required_card_lists(pack: dict[str, Any]) -> None:
    for key in CARD_LIST_KEYS:
        value = pack.get(key)
        if not isinstance(value, list) or not value:
            raise AssertionError(f"semantic_pack.{key} must be a non-empty list")


def assert_references_resolve(pack: dict[str, Any]) -> None:
    tables_by_id = by_id(pack["tables"])
    table_names = {table["physical_name"] for table in tables_by_id.values()}
    column_names = {f"{column['table']}.{column['name']}" for column in pack["columns"]}
    metric_ids = set(by_id(pack["metrics"]).keys())
    term_ids = set(by_id(pack["business_terms"]).keys())

    for column in pack["columns"]:
        if column.get("table") not in table_names:
            raise AssertionError(f"column references unknown table: {column}")

    for value_dict in pack["value_dictionaries"]:
        ref = f"{value_dict.get('table')}.{value_dict.get('column')}"
        if ref not in column_names:
            raise AssertionError(f"value dictionary references unknown column: {ref}")

    for join in pack["join_recipes"]:
        if join.get("left_table") not in table_names:
            raise AssertionError(f"join references unknown left_table: {join}")
        if join.get("right_table") not in table_names:
            raise AssertionError(f"join references unknown right_table: {join}")
        if " = " not in join.get("condition", ""):
            raise AssertionError(f"join condition must be explicit equality: {join}")

    for term in pack["business_terms"]:
        for table in term.get("related_tables", []):
            if table not in table_names:
                raise AssertionError(f"business term references unknown table: {term}")
        for metric_id in term.get("related_metrics", []):
            if metric_id not in metric_ids:
                raise AssertionError(f"business term references unknown metric: {term}")

    for query in pack["verified_queries"]:
        for metric_id in query.get("related_metrics", []):
            if metric_id not in metric_ids:
                raise AssertionError(f"verified query references unknown metric: {query}")
        for term_id in query.get("related_terms", []):
            if term_id not in term_ids:
                raise AssertionError(f"verified query references unknown term: {query}")
