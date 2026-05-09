"""Metadata provenance and gap helpers for Builder/Scanner artifacts.

Real DB comments are product-usable draft evidence. Missing comments become
metadata gaps. Synthetic fixture comments are explicitly test-only and must not
be confused with approved semantic truth.
"""

from __future__ import annotations

from typing import Any, Mapping

TEST_ONLY_SYNTHETIC_METADATA_MARKER = "TEST_ONLY_SYNTHETIC_METADATA"
ABSTRACT_COLUMN_NAMES = {"status", "state", "type", "code", "category", "segment", "channel"}
DATE_HINTS = ("date", "dt", "day", "time", "created", "updated", "paid", "signup", "started")
METRIC_HINTS = ("amount", "revenue", "sales", "profit", "cost", "price", "total", "qty", "quantity", "count")


def classify_comment(comment: str | None) -> str:
    text = str(comment or "").strip()
    if not text:
        return "no_comment"
    if TEST_ONLY_SYNTHETIC_METADATA_MARKER in text:
        return "test_only_synthetic_comment"
    return "real_db_comment"


def provenance_for_comment(
    comment: str | None,
    *,
    source_detail: str,
    confidence: float | None = None,
) -> dict[str, Any]:
    source = classify_comment(comment)
    payload = {
        "metadata_source": source,
        "source_detail": source_detail,
        "confidence": confidence,
        "status": "draft",
        "is_test_only": source == "test_only_synthetic_comment",
        "can_use_for_text2sql": source == "real_db_comment",
        "requires_human_confirmation": source != "human_confirmed",
    }
    if source == "no_comment":
        payload["metadata_gap_reason"] = "missing_db_comment"
    return {key: value for key, value in payload.items() if value is not None}


def no_comment_gap(target: str, *, reason: str, severity: str = "medium", expected_answer_type: str = "text") -> dict[str, Any]:
    return {
        "target": target,
        "metadata_source": "no_comment",
        "metadata_gap_reason": reason,
        "severity": severity,
        "expected_answer_type": expected_answer_type,
        "requires_human_confirmation": True,
    }


def column_gap_candidates(column: Mapping[str, Any]) -> list[dict[str, Any]]:
    table = str(column.get("table_name") or column.get("table") or "unknown_table")
    name = str(column.get("column_name") or column.get("name") or "unknown_column")
    target = f"column.{table}.{name}"
    gaps: list[dict[str, Any]] = []
    source = _metadata_source(column)
    if source == "no_comment":
        gaps.append(no_comment_gap(target, reason="missing_column_comment"))
    lowered = name.casefold()
    if source == "no_comment" and lowered in ABSTRACT_COLUMN_NAMES:
        gaps.append(no_comment_gap(target, reason="abstract_column_without_comment", severity="high", expected_answer_type="value_dictionary"))
    if bool((column.get("pii") or {}).get("is_pii")):
        gaps.append(no_comment_gap(target, reason="pii_policy_needs_confirmation", severity="high", expected_answer_type="policy"))
    if column.get("join_key_candidate") or lowered == "id" or lowered.endswith("_id"):
        gaps.append(no_comment_gap(target, reason="join_key_ambiguity", expected_answer_type="join_recipe"))
    return _dedupe_gaps(gaps)


def table_gap_candidates(record: Mapping[str, Any]) -> list[dict[str, Any]]:
    table = str(record.get("table_name") or record.get("name") or "unknown_table")
    columns = list(record.get("columns") or [])
    gaps: list[dict[str, Any]] = []
    if _metadata_source(record) == "no_comment":
        gaps.append(no_comment_gap(f"table.{table}", reason="missing_table_comment", expected_answer_type="table_purpose"))
    date_columns = [_column_name(column) for column in columns if _looks_date(column)]
    if len(date_columns) >= 2:
        gaps.append(no_comment_gap(f"table.{table}", reason="multiple_candidate_date_columns", severity="high", expected_answer_type="date_basis"))
    metric_columns = [_column_name(column) for column in columns if _looks_metric(column)]
    if len(metric_columns) >= 2:
        gaps.append(no_comment_gap(f"table.{table}", reason="multiple_metric_like_numeric_columns", severity="high", expected_answer_type="metric_definition"))
    return _dedupe_gaps(gaps)


def attach_metadata_gaps(record: dict[str, Any]) -> dict[str, Any]:
    enriched = dict(record)
    columns = []
    for column in enriched.get("columns", []) or []:
        column_payload = dict(column)
        existing = list(column_payload.get("metadata_gaps") or [])
        column_payload["metadata_gaps"] = _dedupe_gaps([*existing, *column_gap_candidates(column_payload)])
        columns.append(column_payload)
    enriched["columns"] = columns
    existing_table_gaps = list(enriched.get("metadata_gaps") or [])
    enriched["metadata_gaps"] = _dedupe_gaps([*existing_table_gaps, *table_gap_candidates(enriched)])
    return enriched


def _metadata_source(value: Mapping[str, Any]) -> str:
    provenance = value.get("metadata_provenance") or []
    if isinstance(provenance, Mapping):
        provenance = [provenance]
    for item in provenance:
        if isinstance(item, Mapping) and item.get("metadata_source"):
            return str(item["metadata_source"])
    return str(value.get("metadata_source") or "no_comment")


def _column_name(column: Mapping[str, Any]) -> str:
    return str(column.get("column_name") or column.get("name") or "")


def _looks_date(column: Mapping[str, Any]) -> bool:
    name = _column_name(column).casefold()
    return str(column.get("type_guess") or column.get("column_type") or "").casefold() in {"date", "timestamp"} or any(h in name for h in DATE_HINTS)


def _looks_metric(column: Mapping[str, Any]) -> bool:
    name = _column_name(column).casefold()
    dtype = str(column.get("type_guess") or column.get("column_type") or "").casefold()
    return dtype in {"number", "numeric", "integer", "decimal", "double precision"} or any(h in name for h in METRIC_HINTS)


def _dedupe_gaps(gaps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str]] = set()
    result: list[dict[str, Any]] = []
    for gap in gaps:
        key = (str(gap.get("target")), str(gap.get("metadata_gap_reason")))
        if key in seen:
            continue
        seen.add(key)
        result.append(gap)
    return result


__all__ = [
    "TEST_ONLY_SYNTHETIC_METADATA_MARKER",
    "attach_metadata_gaps",
    "classify_comment",
    "column_gap_candidates",
    "no_comment_gap",
    "provenance_for_comment",
    "table_gap_candidates",
]
