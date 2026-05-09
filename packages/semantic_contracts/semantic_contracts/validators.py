"""Semantic Pack loading and validation helpers."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError as PydanticValidationError

from .errors import ErrorCode, ErrorSeverity, ValidationErrorDetail, ValidationResult
from .models import ColumnCard, SemanticPack, SemanticPackDocument


def load_pack_yaml(path: str | Path) -> SemanticPack:
    """Load a Semantic Pack YAML file and return its typed contract model."""

    pack_path = Path(path)
    try:
        payload = yaml.safe_load(pack_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ValueError(f"Invalid YAML in {pack_path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"Semantic Pack YAML must contain a mapping: {pack_path}")
    if "semantic_pack" in payload:
        return SemanticPackDocument.model_validate(payload).semantic_pack
    return SemanticPack.model_validate(payload)


def validate_semantic_pack(pack: SemanticPack | dict[str, Any]) -> ValidationResult:
    """Validate Semantic Pack shape, unique IDs, references, and PII value safety."""

    errors: list[ValidationErrorDetail] = []
    warnings: list[ValidationErrorDetail] = []

    if not isinstance(pack, SemanticPack):
        if isinstance(pack, dict):
            payload = pack.get("semantic_pack", pack)
            if isinstance(payload, dict):
                _collect_required_top_level_errors(payload, errors)
        try:
            if isinstance(pack, dict) and "semantic_pack" in pack:
                pack = SemanticPackDocument.model_validate(pack).semantic_pack
            else:
                pack = SemanticPack.model_validate(pack)
        except PydanticValidationError as exc:
            return ValidationResult.from_errors([
                ValidationErrorDetail(
                    code=ErrorCode.INVALID_MODEL,
                    message=str(exc),
                    path="semantic_pack",
                )
            ])

    _collect_duplicate_id_errors(pack, errors)
    _collect_reference_errors(pack, errors, warnings)
    _collect_pii_value_dictionary_errors(pack, errors)
    _collect_pii_policy_errors(pack, errors)
    return ValidationResult.from_errors(errors, warnings)


def _collect_required_top_level_errors(payload: dict[str, Any], errors: list[ValidationErrorDetail]) -> None:
    required = {
        "id",
        "version",
        "status",
        "title",
        "description",
        "locale",
        "owners",
        "source_refs",
        "spaces",
        "tables",
        "columns",
        "value_dictionaries",
        "metrics",
        "business_terms",
        "join_recipes",
        "policies",
        "verified_queries",
        "reverse_questions",
        "metadata",
    }
    for section in sorted(required - set(payload)):
        errors.append(ValidationErrorDetail(
            code=ErrorCode.INVALID_MODEL,
            message=f"Missing required Semantic Pack top-level section: {section}",
            path=f"semantic_pack.{section}",
        ))


def _collect_duplicate_id_errors(pack: SemanticPack, errors: list[ValidationErrorDetail]) -> None:
    seen: dict[str, str] = {}
    for path, ids in _iter_card_ids(pack):
        for card_id in ids:
            if card_id in seen:
                errors.append(ValidationErrorDetail(
                    code=ErrorCode.DUPLICATE_ID,
                    message=f"Duplicate Semantic Pack id: {card_id}",
                    path=path,
                    context={"first_path": seen[card_id]},
                ))
            else:
                seen[card_id] = path


def _iter_card_ids(pack: SemanticPack) -> Iterable[tuple[str, list[str]]]:
    yield "spaces", [item.id for item in pack.spaces]
    yield "tables", [item.id for item in pack.tables]
    yield "columns", [item.id for item in pack.columns]
    yield "value_dictionaries", [item.id for item in pack.value_dictionaries]
    yield "metrics", [item.id for item in pack.metrics]
    yield "business_terms", [item.id for item in pack.business_terms]
    yield "business_terms.ambiguity_rules", [rule.id for term in pack.business_terms for rule in term.ambiguity_rules]
    yield "join_recipes", [item.id for item in pack.join_recipes]
    yield "policies", [item.id for item in pack.policies]
    yield "verified_queries", [item.id for item in pack.verified_queries]
    yield "reverse_questions", [item.id for item in pack.reverse_questions]


def _collect_reference_errors(
    pack: SemanticPack,
    errors: list[ValidationErrorDetail],
    warnings: list[ValidationErrorDetail],
) -> None:
    space_ids = {space.id for space in pack.spaces}
    table_names = {table.physical_name for table in pack.tables}
    table_ids = {table.id for table in pack.tables}
    column_by_name = {_column_key(column.table, column.name): column for column in pack.columns}
    column_ids = {column.id for column in pack.columns}
    metric_ids = {metric.id for metric in pack.metrics}
    term_ids = {term.id for term in pack.business_terms}

    for table in pack.tables:
        if table.space_id not in space_ids:
            errors.append(_err(ErrorCode.UNKNOWN_SPACE, f"Unknown space_id {table.space_id}", "tables", table.id))
        for column_name in table.columns:
            if _column_key(table.physical_name, column_name) not in column_by_name:
                warnings.append(ValidationErrorDetail(
                    code=ErrorCode.UNKNOWN_COLUMN,
                    message=f"Table {table.physical_name} lists unknown column {column_name}",
                    path=f"tables.{table.id}.columns",
                    severity=ErrorSeverity.WARNING,
                ))

    for column in pack.columns:
        if column.table not in table_names:
            errors.append(_err(ErrorCode.UNKNOWN_TABLE, f"Column {column.id} references unknown table {column.table}", "columns", column.id))

    for dictionary in pack.value_dictionaries:
        if dictionary.table not in table_names:
            errors.append(_err(ErrorCode.UNKNOWN_TABLE, f"Value dictionary {dictionary.id} references unknown table {dictionary.table}", "value_dictionaries", dictionary.id))
        elif _column_key(dictionary.table, dictionary.column) not in column_by_name:
            errors.append(_err(ErrorCode.UNKNOWN_COLUMN, f"Value dictionary {dictionary.id} references unknown column {dictionary.table}.{dictionary.column}", "value_dictionaries", dictionary.id))

    for metric in pack.metrics:
        for table_name in metric.required_tables:
            if table_name not in table_names:
                errors.append(_err(ErrorCode.UNKNOWN_TABLE, f"Metric {metric.id} requires unknown table {table_name}", "metrics", metric.id))

    for term in pack.business_terms:
        for table_name in term.related_tables:
            if table_name not in table_names:
                errors.append(_err(ErrorCode.UNKNOWN_TABLE, f"Term {term.id} references unknown table {table_name}", "business_terms", term.id))
        for metric_id in term.related_metrics:
            if metric_id not in metric_ids:
                errors.append(_err(ErrorCode.UNKNOWN_METRIC, f"Term {term.id} references unknown metric {metric_id}", "business_terms", term.id))

    for join in pack.join_recipes:
        for table_name in (join.left_table, join.right_table):
            if table_name not in table_names:
                errors.append(_err(ErrorCode.UNKNOWN_TABLE, f"Join {join.id} references unknown table {table_name}", "join_recipes", join.id))

    for policy in pack.policies:
        for table_name in policy.allowed_tables:
            if table_name not in table_names:
                errors.append(_err(ErrorCode.UNKNOWN_TABLE, f"Policy {policy.id} allows unknown table {table_name}", "policies", policy.id))
        for column_ref in policy.blocked_columns:
            if column_ref not in column_ids and column_ref not in column_by_name:
                errors.append(_err(ErrorCode.UNKNOWN_COLUMN, f"Policy {policy.id} blocks unknown column {column_ref}", "policies", policy.id))

    for query in pack.verified_queries:
        for term_id in query.related_terms:
            if term_id not in term_ids:
                errors.append(_err(ErrorCode.UNKNOWN_TERM, f"Verified query {query.id} references unknown term {term_id}", "verified_queries", query.id))
        for metric_id in query.related_metrics:
            if metric_id not in metric_ids:
                errors.append(_err(ErrorCode.UNKNOWN_METRIC, f"Verified query {query.id} references unknown metric {metric_id}", "verified_queries", query.id))

    known_targets = table_ids | column_ids | metric_ids | term_ids
    for question in pack.reverse_questions:
        if question.target not in known_targets:
            errors.append(ValidationErrorDetail(
                code=ErrorCode.UNKNOWN_POLICY_REF,
                message=f"Reverse question {question.id} targets unknown card {question.target}",
                path="reverse_questions",
                context={"id": question.id},
            ))


def _collect_pii_value_dictionary_errors(pack: SemanticPack, errors: list[ValidationErrorDetail]) -> None:
    columns_by_key: dict[str, ColumnCard] = {_column_key(column.table, column.name): column for column in pack.columns}
    for dictionary in pack.value_dictionaries:
        column = columns_by_key.get(_column_key(dictionary.table, dictionary.column))
        if not column:
            continue
        if column.pii.is_candidate:
            errors.append(ValidationErrorDetail(
                code=ErrorCode.PII_RAW_VALUE_BLOCKED,
                message=f"PII candidate column {dictionary.table}.{dictionary.column} cannot define raw value dictionary entries",
                path=f"value_dictionaries.{dictionary.id}",
                context={"table": dictionary.table, "column": dictionary.column},
            ))
        if column.profile.top_values_safe is False and dictionary.values:
            errors.append(ValidationErrorDetail(
                code=ErrorCode.UNSAFE_VALUE_DICTIONARY,
                message=f"Column {dictionary.table}.{dictionary.column} is not marked top_values_safe",
                path=f"value_dictionaries.{dictionary.id}",
                context={"table": dictionary.table, "column": dictionary.column},
            ))


def _collect_pii_policy_errors(pack: SemanticPack, errors: list[ValidationErrorDetail]) -> None:
    policy_blocked_columns = {column for policy in pack.policies for column in policy.blocked_columns}
    for column in pack.columns:
        if not column.pii.is_candidate:
            continue
        key = _column_key(column.table, column.name)
        if key not in policy_blocked_columns and column.id not in policy_blocked_columns:
            errors.append(ValidationErrorDetail(
                code=ErrorCode.PII_RAW_VALUE_BLOCKED,
                message=f"PII candidate column {key} must be represented in policy blocked_columns",
                path=f"columns.{column.id}.pii",
                context={"table": column.table, "column": column.name},
            ))


def _column_key(table: str, column: str) -> str:
    return f"{table}.{column}"


def _err(code: ErrorCode, message: str, path: str, card_id: str) -> ValidationErrorDetail:
    return ValidationErrorDetail(code=code, message=message, path=path, context={"id": card_id})
