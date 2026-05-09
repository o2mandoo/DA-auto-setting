"""Product-external DB fixture comment mode helpers.

This module is for experiments only. Synthetic comments generated here are
fixture-only, carry TEST_ONLY_SYNTHETIC_METADATA, and must never be treated as
approved product truth.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import StrEnum
from pathlib import Path
from typing import Any, Mapping

import yaml

TEST_ONLY_MARKER = "TEST_ONLY_SYNTHETIC_METADATA"


class FixtureCommentMode(StrEnum):
    NO_COMMENTS = "no_comments"
    REAL_COMMENTS = "real_comments"
    SYNTHETIC_COMMENTS = "synthetic_comments"


@dataclass(frozen=True)
class FixtureTablePlan:
    schema_name: str
    table_name: str
    columns: list[str]
    mode: FixtureCommentMode
    table_comment: str | None = None
    column_comments: dict[str, str] = field(default_factory=dict)
    is_test_only: bool = False

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["mode"] = self.mode.value
        return payload


def load_fixture_manifest(path: str | Path) -> dict[str, Any]:
    payload = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("fixture manifest must be a mapping")
    return payload


def build_fixture_table_plan(
    *,
    dataset_id: str,
    schema_name: str,
    table_name: str,
    columns: list[str],
    mode: FixtureCommentMode | str,
    real_comments: Mapping[str, Any] | None = None,
) -> FixtureTablePlan:
    comment_mode = FixtureCommentMode(mode)
    if not schema_name.startswith("semantic_fixture_"):
        raise ValueError("fixture schemas must use semantic_fixture_* prefix")
    if not columns:
        raise ValueError("fixture table plan requires at least one column")
    if comment_mode == FixtureCommentMode.NO_COMMENTS:
        return FixtureTablePlan(schema_name=schema_name, table_name=table_name, columns=columns, mode=comment_mode)
    if comment_mode == FixtureCommentMode.REAL_COMMENTS:
        comments = dict(real_comments or {})
        return FixtureTablePlan(
            schema_name=schema_name,
            table_name=table_name,
            columns=columns,
            mode=comment_mode,
            table_comment=comments.get("table"),
            column_comments={column: str(comments.get("columns", {}).get(column)) for column in columns if comments.get("columns", {}).get(column)},
            is_test_only=False,
        )
    return FixtureTablePlan(
        schema_name=schema_name,
        table_name=table_name,
        columns=columns,
        mode=comment_mode,
        table_comment=f"{TEST_ONLY_MARKER}: fixture-only synthetic fixture comment for {dataset_id}.{table_name}",
        column_comments={column: f"{TEST_ONLY_MARKER}: fixture-only synthetic fixture meaning for {table_name}.{column}" for column in columns},
        is_test_only=True,
    )


def fixture_mode_summary(plans: list[FixtureTablePlan]) -> dict[str, Any]:
    return {
        "fixture_only": True,
        "not_product_runtime": True,
        "modes": sorted({plan.mode.value for plan in plans}),
        "tables": [plan.to_dict() for plan in plans],
        "synthetic_truth_blocked": all(_synthetic_plan_is_test_only(plan) for plan in plans),
    }


def _synthetic_plan_is_test_only(plan: FixtureTablePlan) -> bool:
    if not plan.is_test_only:
        return True
    if TEST_ONLY_MARKER not in (plan.table_comment or ""):
        return False
    if not plan.column_comments:
        return False
    return all(TEST_ONLY_MARKER in comment for comment in plan.column_comments.values())


__all__ = ["FixtureCommentMode", "FixtureTablePlan", "TEST_ONLY_MARKER", "build_fixture_table_plan", "fixture_mode_summary", "load_fixture_manifest"]
