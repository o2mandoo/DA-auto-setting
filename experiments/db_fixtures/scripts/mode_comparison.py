"""Compare DB comment fixture modes without silently substituting a backend.

The comparison is product-external evidence for the onboarding/demo harness. It
does not execute SQL and it does not promote fixture metadata into product
truth. If live DB execution is later requested, it must go through the explicit
backend-specific fixture safety gate; no backend silently substitutes for another.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping
import argparse
import json

from semantic_builder.metadata import attach_metadata_gaps, provenance_for_comment

from .fixture_modes import FixtureCommentMode, TEST_ONLY_MARKER, build_fixture_table_plan
from .mysql_fixture_loader import build_mysql_sql_plan
from .postgres_fixture_loader import build_postgres_sql_plan


@dataclass(frozen=True)
class FixtureModeComparison:
    mode: str
    backend: str
    available: bool
    table_name: str
    useful_metadata_coverage: float
    reverse_question_count: int
    text2sql_context_available: bool
    pack_draft_quality: str
    runtime_warnings: list[str]
    baseline_vs_system_sql_difference: str
    sql_comment_statements: int
    notes: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def compare_comment_modes(
    *,
    dataset_id: str,
    schema_name: str,
    table_name: str,
    columns: list[str],
    real_comments: Mapping[str, Any] | None = None,
    backend: str = "postgres",
) -> list[FixtureModeComparison]:
    """Return deterministic mode comparisons for no/real/synthetic comments.

    ``real_comments`` must be source/manifest-provided. When it is absent, the
    real-comment mode is marked unavailable instead of fabricating comments.
    """

    if not columns:
        raise ValueError("columns must not be empty")
    normalized_backend = _normalize_backend(backend)
    modes = [
        FixtureCommentMode.NO_COMMENTS,
        FixtureCommentMode.REAL_COMMENTS,
        FixtureCommentMode.SYNTHETIC_COMMENTS,
    ]
    return [
        _compare_one_mode(
            dataset_id=dataset_id,
            schema_name=schema_name,
            table_name=table_name,
            columns=columns,
            mode=mode,
            real_comments=real_comments,
            backend=normalized_backend,
        )
        for mode in modes
    ]


def write_comment_mode_comparison(path: str | Path, comparisons: list[FixtureModeComparison]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps({"comparisons": [comparison.to_dict() for comparison in comparisons]}, ensure_ascii=False, indent=2)
        + "\n",
        encoding="utf-8",
    )


def _compare_one_mode(
    *,
    dataset_id: str,
    schema_name: str,
    table_name: str,
    columns: list[str],
    mode: FixtureCommentMode,
    real_comments: Mapping[str, Any] | None,
    backend: str,
) -> FixtureModeComparison:
    real_available = _has_real_comments(real_comments)
    available = mode != FixtureCommentMode.REAL_COMMENTS or real_available
    effective_comments = real_comments if available and mode == FixtureCommentMode.REAL_COMMENTS else None
    plan = build_fixture_table_plan(
        dataset_id=dataset_id,
        schema_name=schema_name,
        table_name=table_name,
        columns=columns,
        mode=mode,
        real_comments=effective_comments,
    )
    sql_plan = _build_sql_plan(plan, backend=backend)
    table_comment = plan.table_comment
    column_comments = plan.column_comments
    record = _record_for_mode(table_name=table_name, columns=columns, table_comment=table_comment, column_comments=column_comments)
    warning_set: set[str] = set()
    reverse_questions = 0
    if mode == FixtureCommentMode.NO_COMMENTS:
        warning_set.add("metadata_gap_not_context_truth")
        reverse_questions = _gap_count(record)
    elif mode == FixtureCommentMode.REAL_COMMENTS and available:
        warning_set.add("comment_only_draft_context")
        reverse_questions = _gap_count(record)
    elif mode == FixtureCommentMode.REAL_COMMENTS and not available:
        warning_set.add("real_comments_manifest_missing")
        reverse_questions = _gap_count(_record_for_mode(table_name=table_name, columns=columns, table_comment=None, column_comments={}))
    else:
        warning_set.add("test_only_synthetic_metadata_excluded")

    coverage = _coverage(columns=columns, table_comment=table_comment, column_comments=column_comments)
    product_context = available and mode == FixtureCommentMode.REAL_COMMENTS and coverage > 0
    if mode == FixtureCommentMode.SYNTHETIC_COMMENTS:
        # Synthetic comments can be present in fixture SQL, but product context
        # coverage remains zero because they are explicitly test-only.
        coverage = 0.0
        product_context = False
    if not available:
        coverage = 0.0
        product_context = False

    return FixtureModeComparison(
        mode=mode.value,
        backend=backend,
        available=available,
        table_name=table_name,
        useful_metadata_coverage=coverage,
        reverse_question_count=reverse_questions,
        text2sql_context_available=product_context,
        pack_draft_quality=_quality_label(mode=mode, available=available, coverage=coverage, reverse_questions=reverse_questions),
        runtime_warnings=sorted(warning_set),
        baseline_vs_system_sql_difference=_baseline_difference(mode=mode, available=available),
        sql_comment_statements=_count_comment_statements(sql_plan.statements, backend=backend),
        notes=_notes(mode=mode, available=available),
    )


def _normalize_backend(backend: str) -> str:
    normalized = backend.strip().casefold()
    if normalized in {"postgres", "postgresql"}:
        return "postgres"
    if normalized == "mysql":
        return "mysql"
    raise ValueError(f"unsupported fixture backend: {backend}; expected postgres or mysql")


def _build_sql_plan(plan, *, backend: str):
    if backend == "postgres":
        return build_postgres_sql_plan(plan)
    if backend == "mysql":
        return build_mysql_sql_plan(plan)
    raise ValueError(f"unsupported fixture backend: {backend}")


def _count_comment_statements(statements: list[str], *, backend: str) -> int:
    if backend == "postgres":
        return sum(1 for statement in statements if statement.startswith("COMMENT ON "))
    if backend == "mysql":
        return sum(statement.count(" COMMENT") for statement in statements if statement.startswith("CREATE TABLE "))
    return 0


def _record_for_mode(
    *,
    table_name: str,
    columns: list[str],
    table_comment: str | None,
    column_comments: Mapping[str, str],
) -> dict[str, Any]:
    record = {
        "table_name": table_name,
        "metadata_provenance": [provenance_for_comment(table_comment, source_detail=f"fixture:{table_name}")],
        "columns": [
            {
                "table_name": table_name,
                "column_name": column,
                "type_guess": _type_guess(column),
                "metadata_provenance": [
                    provenance_for_comment(column_comments.get(column), source_detail=f"fixture:{table_name}.{column}")
                ],
                "pii": {"is_pii": _is_possible_pii(column)},
            }
            for column in columns
        ],
    }
    return attach_metadata_gaps(record)


def _has_real_comments(real_comments: Mapping[str, Any] | None) -> bool:
    if not real_comments:
        return False
    if real_comments.get("table"):
        return True
    columns = real_comments.get("columns") or {}
    return any(bool(value) for value in columns.values())


def _coverage(*, columns: list[str], table_comment: str | None, column_comments: Mapping[str, str]) -> float:
    denominator = len(columns) + 1
    numerator = (1 if table_comment else 0) + sum(1 for column in columns if column_comments.get(column))
    return round(numerator / denominator, 4)


def _gap_count(record: Mapping[str, Any]) -> int:
    count = len(record.get("metadata_gaps") or [])
    count += sum(len(column.get("metadata_gaps") or []) for column in record.get("columns") or [])
    return count


def _type_guess(column: str) -> str:
    lowered = column.casefold()
    if any(token in lowered for token in ("date", "dt", "day", "time", "created", "updated")):
        return "date"
    if any(token in lowered for token in ("amount", "revenue", "sales", "profit", "cost", "price", "qty", "count")):
        return "number"
    return "string"


def _is_possible_pii(column: str) -> bool:
    lowered = column.casefold()
    return any(token in lowered for token in ("email", "phone", "name", "customer"))


def _quality_label(*, mode: FixtureCommentMode, available: bool, coverage: float, reverse_questions: int) -> str:
    if mode == FixtureCommentMode.SYNTHETIC_COMMENTS:
        return "debug_upper_bound_fixture_only"
    if not available:
        return "unavailable_real_comment_manifest_missing"
    if coverage > 0 and reverse_questions <= 2:
        return "comment_context_available_with_review"
    if reverse_questions > 0:
        return "gap_driven_onboarding_required"
    return "minimal_context"


def _baseline_difference(*, mode: FixtureCommentMode, available: bool) -> str:
    if mode == FixtureCommentMode.NO_COMMENTS:
        return "baseline_sql_has_no_domain_context; system_should_surface_reverse_questions_before_sql"
    if mode == FixtureCommentMode.REAL_COMMENTS and available:
        return "system_can_use_real_comment_draft_context_with_warning; baseline_sql_cannot_explain_source"
    if mode == FixtureCommentMode.REAL_COMMENTS:
        return "real_comment_mode_unavailable; system_must_not_fabricate_context"
    return "synthetic_comments_help_fixture_debug_only; system_must_exclude_from_product_context"


def _notes(*, mode: FixtureCommentMode, available: bool) -> list[str]:
    if mode == FixtureCommentMode.SYNTHETIC_COMMENTS:
        return [f"all generated comments include {TEST_ONLY_MARKER}", "fixture-only annotations are excluded from product truth"]
    if mode == FixtureCommentMode.REAL_COMMENTS and not available:
        return ["source manifest did not provide real comments/descriptions", "no synthetic fallback was used"]
    if mode == FixtureCommentMode.NO_COMMENTS:
        return ["absence is represented as metadata gaps, not a scanner failure"]
    return ["real comments are usable draft semantic evidence and still require review before approval"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compare DB fixture comment modes.")
    parser.add_argument("--dataset-id", required=True)
    parser.add_argument("--schema", required=True)
    parser.add_argument("--table", required=True)
    parser.add_argument("--columns", required=True, help="Comma-separated column names")
    parser.add_argument("--out", required=True)
    parser.add_argument("--backend", choices=("postgres", "mysql"), default="postgres")
    args = parser.parse_args(argv)
    comparisons = compare_comment_modes(
        dataset_id=args.dataset_id,
        schema_name=args.schema,
        table_name=args.table,
        columns=[column.strip() for column in args.columns.split(",") if column.strip()],
        backend=args.backend,
    )
    write_comment_mode_comparison(args.out, comparisons)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["FixtureModeComparison", "compare_comment_modes", "write_comment_mode_comparison"]
