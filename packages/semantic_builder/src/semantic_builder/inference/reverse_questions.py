"""PII-safe reverse question generation for semantic inference drafts.

Phase 5 does not confirm business meaning. This module turns profile metadata
and draft uncertainty into onboarding questions so a domain owner can resolve
ambiguity explicitly. It never uses sampled raw PII values and does not call an
LLM, external database, MCP runtime, VDB, or query execution path.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

EMAIL_RE = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")
PHONE_RE = re.compile(r"(?:\+?\d[\d\s().-]{7,}\d)")
DATE_NAME_HINTS = ("date", "dt", "day", "time", "created", "updated", "paid", "signup", "started")
METRIC_NAME_HINTS = (
    "amount",
    "revenue",
    "sales",
    "price",
    "cost",
    "profit",
    "margin",
    "quantity",
    "qty",
    "count",
    "total",
    "fee",
)
GENERIC_NAME_HINTS = {"status", "type", "category", "code", "name", "description", "value"}


@dataclass(frozen=True)
class EvidenceReference:
    """Source pointer that is safe for file-origin and future PostgreSQL records."""

    source_type: str
    table: str | None = None
    column: str | None = None
    source_name: str | None = None
    sheet_name: str | None = None
    safe_reference: bool = True

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"source_type": self.source_type, "safe_reference": self.safe_reference}
        if self.table:
            payload["table"] = self.table
        if self.column:
            payload["column"] = self.column
        if self.source_name:
            payload["source_name"] = self.source_name
        if self.sheet_name:
            payload["sheet_name"] = self.sheet_name
        return payload


@dataclass(frozen=True)
class ReverseQuestion:
    """Draft onboarding question; status remains open until a human answers."""

    id: str
    target: str
    question: str
    reason: str
    category: str
    status: str = "open"
    priority: str = "medium"
    evidence: tuple[EvidenceReference, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "target": self.target,
            "question": _redact_text(self.question),
            "reason": _redact_text(self.reason),
            "category": self.category,
            "status": self.status,
            "priority": self.priority,
            "evidence": [item.to_dict() for item in self.evidence],
        }


def generate_reverse_questions(
    profile_records: Iterable[Mapping[str, Any]],
    hypotheses: Iterable[Mapping[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Generate specific, evidence-backed onboarding questions.

    Inputs are metadata-only profile/hypothesis records. The generator ignores
    sampled ``top_values`` so stale profiles cannot leak raw PII into questions.
    """
    records = [dict(record) for record in profile_records]
    questions: list[ReverseQuestion] = []

    if not records:
        questions.append(
            _question(
                category="missing_evidence",
                target="source_profiles",
                question=(
                    "No profile records were available. Which source tables should be included "
                    "before semantic inference starts?"
                ),
                reason="The inference input was empty, so business terms or metrics cannot be inferred safely.",
                priority="high",
                evidence=(),
            )
        )
        # Keep this question and still convert any supplied hypothesis
        # uncertainty at the shared merge point below.

    for record in records:
        table = _safe_identifier(record.get("table_name") or record.get("name") or "unknown_table")
        columns = [_column_dict(column) for column in record.get("columns", []) if isinstance(column, Mapping)]
        table_evidence = (_evidence(record, table=table),)

        if not columns:
            questions.append(
                _question(
                    category="missing_evidence",
                    target=f"table.{table}",
                    question=f"Table `{table}` has no profiled columns. Should this source be excluded or rescanned?",
                    reason="A table-level profile without columns is insufficient for safe semantic draft generation.",
                    priority="high",
                    evidence=table_evidence,
                )
            )
            continue

        date_columns = [_safe_identifier(column.get("name")) for column in columns if _is_date_column(column)]
        if len(date_columns) >= 2:
            questions.append(
                _question(
                    category="ambiguous_date_basis",
                    target=f"table.{table}",
                    question=(
                        f"For `{table}` time-based reporting, which date column should be the default basis: "
                        f"{_join_names(date_columns)}?"
                    ),
                    reason="Multiple date-like columns were detected, so period filters could produce different results.",
                    priority="high",
                    evidence=tuple(_evidence(record, table=table, column=column) for column in date_columns),
                )
            )

        metric_columns = [_safe_identifier(column.get("name")) for column in columns if _is_metric_candidate(column)]
        for column_name in metric_columns:
            questions.append(
                _question(
                    category="metric_definition",
                    target=f"column.{table}.{column_name}",
                    question=(
                        f"Should `{table}.{column_name}` become a business metric, and what filters, aggregation, "
                        "currency/unit, and date basis define it?"
                    ),
                    reason="Numeric or metric-like columns are only candidates until a domain owner confirms business semantics.",
                    priority="medium",
                    evidence=(_evidence(record, table=table, column=column_name),),
                )
            )

        join_columns = [_safe_identifier(column.get("name")) for column in columns if _is_join_candidate(column)]
        for column_name in join_columns:
            questions.append(
                _question(
                    category="join_relationship",
                    target=f"column.{table}.{column_name}",
                    question=(
                        f"Does `{table}.{column_name}` join to another profiled table, and if so what is the "
                        "cardinality and trusted join condition?"
                    ),
                    reason="Join-key-shaped columns were detected, but inferred joins require human confirmation.",
                    priority="medium",
                    evidence=(_evidence(record, table=table, column=column_name),),
                )
            )

        for column in columns:
            column_name = _safe_identifier(column.get("name"))
            evidence = (_evidence(record, table=table, column=column_name),)
            if _is_pii_column(column):
                questions.append(
                    _question(
                        category="pii_policy",
                        target=f"column.{table}.{column_name}",
                        question=(
                            f"Column `{table}.{column_name}` is PII-like. Which roles may use it, and should all raw "
                            "values remain blocked from dictionaries, prompts, logs, and future indexes?"
                        ),
                        reason="PII-like profile metadata requires explicit policy confirmation without exposing raw values.",
                        priority="high",
                        evidence=evidence,
                    )
                )
            if _has_weak_evidence(column):
                questions.append(
                    _question(
                        category="missing_evidence",
                        target=f"column.{table}.{column_name}",
                        question=(
                            f"What business meaning should `{table}.{column_name}` carry, and is additional sample-free "
                            "documentation needed to confirm it?"
                        ),
                        reason="The profile has weak evidence such as high nulls, high cardinality, or a generic column name.",
                        priority="medium",
                        evidence=evidence,
                    )
                )

    questions.extend(_questions_from_hypotheses(hypotheses or ()))
    return [question.to_dict() for question in _dedupe(questions)]


def write_onboarding_questions_jsonl(questions: Iterable[Mapping[str, Any]], path: str | Path) -> None:
    """Write onboarding questions as JSONL, preserving PII redaction at the boundary."""
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as handle:
        for question in questions:
            safe_question = _sanitize_mapping(question)
            handle.write(json.dumps(safe_question, ensure_ascii=False, sort_keys=True) + "\n")


def _questions_from_hypotheses(hypotheses: Iterable[Mapping[str, Any]]) -> list[ReverseQuestion]:
    questions: list[ReverseQuestion] = []
    for hypothesis in hypotheses:
        target = _safe_target(str(hypothesis.get("target") or hypothesis.get("id") or "hypothesis"))
        confidence = hypothesis.get("confidence")
        uncertainties = hypothesis.get("uncertainties") or hypothesis.get("uncertainty") or []
        if isinstance(uncertainties, Mapping):
            uncertainties = [uncertainties]
        if _is_low_confidence(confidence):
            questions.append(
                _question(
                    category="low_confidence",
                    target=target,
                    question=f"What evidence would confirm or reject draft hypothesis `{target}`?",
                    reason=f"The hypothesis confidence is low ({confidence}).",
                    priority="high",
                    evidence=_hypothesis_evidence(hypothesis),
                )
            )
        for uncertainty in uncertainties:
            label = _uncertainty_label(uncertainty)
            category = _uncertainty_category(label)
            questions.append(
                _question(
                    category=category,
                    target=target,
                    question=f"For `{target}`, how should this uncertainty be resolved: {label}?",
                    reason="Draft semantic inference reported unresolved uncertainty that must not be auto-approved.",
                    priority="high" if category in {"pii_policy", "ambiguous_date_basis"} else "medium",
                    evidence=_hypothesis_evidence(hypothesis),
                )
            )
    return questions


def _question(
    *,
    category: str,
    target: str,
    question: str,
    reason: str,
    evidence: Sequence[EvidenceReference],
    priority: str,
) -> ReverseQuestion:
    safe_target = _safe_target(target)
    digest = hashlib.sha1(f"{category}|{safe_target}|{question}".encode("utf-8")).hexdigest()[:10]
    return ReverseQuestion(
        id=f"rq.{category}.{digest}",
        target=safe_target,
        question=question,
        reason=reason,
        category=category,
        priority=priority,
        evidence=tuple(evidence),
    )


def _dedupe(questions: Sequence[ReverseQuestion]) -> list[ReverseQuestion]:
    seen: set[tuple[str, str, str]] = set()
    unique: list[ReverseQuestion] = []
    for question in questions:
        key = (question.category, question.target, question.question)
        if key in seen:
            continue
        seen.add(key)
        unique.append(question)
    return unique


def _column_dict(column: Mapping[str, Any]) -> dict[str, Any]:
    # Copy only metadata fields used for question generation; raw top_values are
    # intentionally ignored because they may contain stale PII from old profiles.
    return {
        "name": column.get("name"),
        "type_guess": column.get("type_guess"),
        "null_ratio": column.get("null_ratio"),
        "cardinality_estimate": column.get("cardinality_estimate"),
        "join_key_candidate": column.get("join_key_candidate"),
        "pii": dict(column.get("pii") or {}),
    }


def _evidence(record: Mapping[str, Any], *, table: str, column: str | None = None) -> EvidenceReference:
    source_ref = record.get("source_ref") if isinstance(record.get("source_ref"), Mapping) else {}
    source_type = str(source_ref.get("type") or record.get("source_type") or _infer_source_type(record))
    source_name = source_ref.get("name") or record.get("source_name") or record.get("path")
    return EvidenceReference(
        source_type=_safe_identifier(source_type),
        table=table,
        column=_safe_identifier(column) if column else None,
        source_name=_safe_source_name(source_name),
        sheet_name=_safe_source_name(record.get("sheet_name")),
        safe_reference=True,
    )


def _hypothesis_evidence(hypothesis: Mapping[str, Any]) -> tuple[EvidenceReference, ...]:
    evidence_items = hypothesis.get("evidence") or hypothesis.get("source_refs") or []
    if isinstance(evidence_items, Mapping):
        evidence_items = [evidence_items]
    refs: list[EvidenceReference] = []
    for item in evidence_items:
        if not isinstance(item, Mapping):
            continue
        refs.append(
            EvidenceReference(
                source_type=_safe_identifier(item.get("source_type") or item.get("type") or "profile"),
                table=_safe_identifier(item.get("table")) if item.get("table") else None,
                column=_safe_identifier(item.get("column")) if item.get("column") else None,
                source_name=_safe_source_name(item.get("source_name") or item.get("name")),
                sheet_name=_safe_source_name(item.get("sheet_name")),
                safe_reference=True,
            )
        )
    return tuple(refs)


def _infer_source_type(record: Mapping[str, Any]) -> str:
    if record.get("postgresql") or record.get("schema_name"):
        return "postgresql"
    return "file"


def _is_date_column(column: Mapping[str, Any]) -> bool:
    name = _safe_identifier(column.get("name"))
    return column.get("type_guess") == "date" or any(hint in name for hint in DATE_NAME_HINTS)


def _is_metric_candidate(column: Mapping[str, Any]) -> bool:
    name = _safe_identifier(column.get("name"))
    return column.get("type_guess") == "number" or any(hint in name for hint in METRIC_NAME_HINTS)


def _is_join_candidate(column: Mapping[str, Any]) -> bool:
    name = _safe_identifier(column.get("name"))
    return bool(column.get("join_key_candidate")) or name == "id" or name.endswith("_id")


def _is_pii_column(column: Mapping[str, Any]) -> bool:
    pii = column.get("pii") or {}
    return bool(isinstance(pii, Mapping) and pii.get("is_pii"))


def _has_weak_evidence(column: Mapping[str, Any]) -> bool:
    name = _safe_identifier(column.get("name"))
    null_ratio = _safe_float(column.get("null_ratio"))
    cardinality = _safe_int(column.get("cardinality_estimate"))
    return null_ratio >= 0.5 or cardinality >= 1000 or name in GENERIC_NAME_HINTS


def _is_low_confidence(confidence: Any) -> bool:
    if confidence is None:
        return False
    try:
        return float(confidence) < 0.6
    except (TypeError, ValueError):
        return str(confidence).lower() in {"low", "draft_low"}


def _uncertainty_label(uncertainty: Any) -> str:
    if isinstance(uncertainty, Mapping):
        return _redact_text(str(uncertainty.get("question") or uncertainty.get("reason") or uncertainty.get("type") or "unspecified"))
    return _redact_text(str(uncertainty))


def _uncertainty_category(label: str) -> str:
    lowered = label.lower()
    if "date" in lowered or "period" in lowered:
        return "ambiguous_date_basis"
    if "join" in lowered or "relationship" in lowered:
        return "join_relationship"
    if "pii" in lowered or "policy" in lowered or "blocked" in lowered:
        return "pii_policy"
    if "metric" in lowered or "aggregation" in lowered or "filter" in lowered:
        return "metric_definition"
    return "low_confidence"


def _safe_identifier(value: Any) -> str:
    text = _redact_text(str(value or "").strip().lower())
    safe = re.sub(r"[^0-9a-zA-Z_]+", "_", text).strip("_")
    return safe or "unknown"


def _safe_target(target: str) -> str:
    redacted = _redact_text(target)
    return re.sub(r"[^0-9A-Za-z_./-]+", "_", redacted).strip("_") or "unknown"


def _safe_source_name(value: Any) -> str | None:
    if value in (None, ""):
        return None
    # Keep only structural source identifiers such as paths/table source names;
    # redact any accidental credential or PII-shaped value.
    return _redact_text(str(value))


def _join_names(values: Sequence[str]) -> str:
    return ", ".join(f"`{value}`" for value in values)


def _safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _safe_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _sanitize_mapping(value: Mapping[str, Any]) -> dict[str, Any]:
    return {str(key): _sanitize_value(item) for key, item in value.items()}


def _sanitize_value(value: Any) -> Any:
    if isinstance(value, str):
        return _redact_text(value)
    if isinstance(value, Mapping):
        return _sanitize_mapping(value)
    if isinstance(value, list):
        return [_sanitize_value(item) for item in value]
    return value


def _redact_text(text: str) -> str:
    return PHONE_RE.sub("[REDACTED_PHONE]", EMAIL_RE.sub("[REDACTED_EMAIL]", text))
