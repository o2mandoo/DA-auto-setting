"""Column profiling primitives for local file inputs.

Phase 4 profiling is intentionally conservative: it may emit safe categorical
examples for low-cardinality non-PII columns, but PII-like columns only expose
policy hints and pattern summaries. This prevents raw names, emails, or phone
numbers from leaking into generated Semantic Packs or intermediate artifacts.
The profiler also exposes a timeout budget so DB-backed callers can reuse the
same PII-safe profiling rules without letting a scan run unbounded.
"""

from __future__ import annotations

import math
import re
import time
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable, Mapping, Sequence

NULL_STRINGS = {"", "null", "none", "n/a", "na", "nan"}
LOW_CARDINALITY_LIMIT = 20
SAFE_TOP_N = 5

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_PHONE_RE = re.compile(r"(?:\+?\d[\d\s().-]{7,}\d)")
_DATE_FORMATS = ("%Y-%m-%d", "%Y/%m/%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S")

PII_NAME_HINTS = {
    "name",
    "full_name",
    "first_name",
    "last_name",
    "customer_name",
    "client_name",
    "employee_name",
    "staff_name",
    "member_name",
    "user_name",
    "username",
    "person",
    "contact",
    # Workbook admin/territory sheets often label human names by role rather
    # than with a literal *_name suffix; keep raw manager names out of drafts.
    "manager",
    "regional_manager",
}
PII_EMAIL_HINTS = {"email", "e_mail", "mail"}
PII_PHONE_HINTS = {"phone", "mobile", "telephone", "tel", "cell"}
PII_ADDRESS_HINTS = {"address", "street", "zipcode", "zip", "postal_code"}
PII_IDENTIFIER_HINTS = {"ssn", "resident", "passport", "driver_license", "national_id"}


@dataclass(frozen=True)
class PIIDetection:
    """PII classification without retaining matched raw values."""

    is_pii: bool
    categories: tuple[str, ...] = ()
    reasons: tuple[str, ...] = ()
    policy_hints: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "is_pii": self.is_pii,
            "categories": list(self.categories),
            "reasons": list(self.reasons),
            "policy_hints": list(self.policy_hints),
        }


@dataclass(frozen=True)
class ColumnProfile:
    """JSON-serializable column profile used by downstream draft builders."""

    name: str
    type_guess: str
    row_count: int
    null_count: int
    null_ratio: float
    cardinality_estimate: int
    pii: PIIDetection
    top_values: tuple[dict[str, Any], ...] = ()
    pattern_summary: dict[str, Any] = field(default_factory=dict)
    numeric_min: float | None = None
    numeric_max: float | None = None
    date_min: str | None = None
    date_max: str | None = None
    join_key_candidate: bool = False

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "name": self.name,
            "type_guess": self.type_guess,
            "row_count": self.row_count,
            "null_count": self.null_count,
            "null_ratio": self.null_ratio,
            "cardinality_estimate": self.cardinality_estimate,
            "pii": self.pii.to_dict(),
            "top_values": [dict(item) for item in self.top_values],
            "pattern_summary": dict(self.pattern_summary),
            "join_key_candidate": self.join_key_candidate,
        }
        if self.numeric_min is not None:
            payload["numeric_min"] = self.numeric_min
        if self.numeric_max is not None:
            payload["numeric_max"] = self.numeric_max
        if self.date_min is not None:
            payload["date_min"] = self.date_min
        if self.date_max is not None:
            payload["date_max"] = self.date_max
        return payload


@dataclass(frozen=True)
class SafeProfilerConfig:
    """Safe profiling knobs shared by file and DB-backed callers.

    timeout_ms exists so future database scanners can enforce bounded metadata
    and sample queries without inventing a separate timing policy.
    """

    timeout_ms: int | None = None
    top_n: int = SAFE_TOP_N
    low_cardinality_limit: int = LOW_CARDINALITY_LIMIT

    def to_dict(self) -> dict[str, Any]:
        return {
            "timeout_ms": self.timeout_ms,
            "top_n": self.top_n,
            "low_cardinality_limit": self.low_cardinality_limit,
        }


def profile_dataset(dataset: Any, *, config: SafeProfilerConfig | None = None) -> dict[str, Any]:
    """Profile a connector FileDataset-like object without importing connector code."""
    profiler_config = config or SafeProfilerConfig()
    deadline = _ProfilerDeadline(profiler_config.timeout_ms)
    deadline.check()
    table_name = getattr(dataset, "table_name")
    rows = tuple(getattr(dataset, "rows"))
    columns = tuple(getattr(dataset, "columns"))
    profile = {
        "table_name": table_name,
        "row_count": len(rows),
        "columns": [
            profile_column(column, (row.get(column) for row in rows), config=profiler_config).to_dict()
            for column in columns
        ],
    }
    sheet_name = getattr(dataset, "sheet_name", None)
    if sheet_name is not None:
        # Sheet name is structural workbook metadata, not a sampled cell value.
        profile["sheet_name"] = sheet_name
    return profile


def profile_rows(
    table_name: str,
    rows: Sequence[Mapping[str, Any]],
    *,
    config: SafeProfilerConfig | None = None,
) -> dict[str, Any]:
    """Profile table-shaped row dictionaries produced by local file connectors."""
    profiler_config = config or SafeProfilerConfig()
    deadline = _ProfilerDeadline(profiler_config.timeout_ms)
    deadline.check()
    columns: list[str] = []
    seen: set[str] = set()
    for row in rows:
        deadline.check()
        for column in row:
            if column not in seen:
                seen.add(column)
                columns.append(column)
    return {
        "table_name": table_name,
        "row_count": len(rows),
        "columns": [
            profile_column(column, (row.get(column) for row in rows), config=profiler_config).to_dict()
            for column in columns
        ],
    }


def profile_column(
    name: str,
    values: Iterable[Any],
    *,
    top_n: int = SAFE_TOP_N,
    config: SafeProfilerConfig | None = None,
) -> ColumnProfile:
    """Return a PII-safe profile for one column.

    Raw values are included only for low-cardinality non-PII columns. PII-like or
    high-cardinality columns receive pattern summaries instead, so downstream
    draft pack generation cannot accidentally persist raw sensitive values.
    """
    if config is None:
        profiler_config = SafeProfilerConfig(top_n=top_n)
    elif top_n != SAFE_TOP_N:
        profiler_config = SafeProfilerConfig(
            timeout_ms=config.timeout_ms,
            top_n=top_n,
            low_cardinality_limit=config.low_cardinality_limit,
        )
    else:
        profiler_config = config
    deadline = _ProfilerDeadline(profiler_config.timeout_ms)
    deadline.check()
    value_list = list(values)
    normalized = [_normalize_value(value) for value in value_list]
    deadline.check()
    present = [value for value in normalized if value is not None]
    pii = detect_pii(name, present)
    type_guess = _guess_type(present)
    counter = Counter(present)
    cardinality = len(counter)
    null_count = len(value_list) - len(present)
    row_count = len(value_list)
    numeric_values = [_to_decimal(value) for value in present]
    numeric_values = [value for value in numeric_values if value is not None]
    date_values = [_to_date(value) for value in present]
    date_values = [value for value in date_values if value is not None]

    safe_top_values: tuple[dict[str, Any], ...] = ()
    if not pii.is_pii and 0 < cardinality <= profiler_config.low_cardinality_limit:
        safe_top_values = tuple(
            {"value": value, "count": count} for value, count in counter.most_common(profiler_config.top_n)
        )

    # PII-classified columns must not expose raw extrema: min/max values can be
    # direct identifiers for numeric/date PII such as postal codes or birth dates.
    numeric_min = float(min(numeric_values)) if numeric_values and not pii.is_pii else None
    numeric_max = float(max(numeric_values)) if numeric_values and not pii.is_pii else None
    date_min = min(date_values).isoformat() if date_values and not pii.is_pii else None
    date_max = max(date_values).isoformat() if date_values and not pii.is_pii else None

    return ColumnProfile(
        name=name,
        type_guess=type_guess,
        row_count=row_count,
        null_count=null_count,
        null_ratio=_safe_ratio(null_count, row_count),
        cardinality_estimate=cardinality,
        pii=pii,
        top_values=safe_top_values,
        pattern_summary=_pattern_summary(name, present, pii, cardinality),
        numeric_min=numeric_min,
        numeric_max=numeric_max,
        date_min=date_min,
        date_max=date_max,
        join_key_candidate=_is_join_key_candidate(name, row_count, cardinality, null_count),
    )


@dataclass(frozen=True)
class _ProfilerDeadline:
    timeout_ms: int | None
    started_at: float = field(default_factory=time.perf_counter)

    def check(self) -> None:
        if self.timeout_ms is None:
            return
        if self.timeout_ms <= 0:
            raise TimeoutError("profile timeout_ms must be positive when configured")
        elapsed_ms = (time.perf_counter() - self.started_at) * 1000.0
        if elapsed_ms > self.timeout_ms:
            raise TimeoutError(f"profile exceeded timeout_ms={self.timeout_ms}")


def detect_pii(name: str, values: Sequence[str]) -> PIIDetection:
    """Detect likely PII from column names and value shapes without storing matches."""
    normalized_name = _normalize_column_name(name)
    categories: set[str] = set()
    reasons: list[str] = []

    def add(category: str, reason: str) -> None:
        categories.add(category)
        if reason not in reasons:
            reasons.append(reason)

    if _name_matches(normalized_name, PII_EMAIL_HINTS):
        add("email", "column_name")
    if _name_matches(normalized_name, PII_PHONE_HINTS):
        add("phone", "column_name")
    if _looks_like_person_name_column(normalized_name):
        add("person_name", "column_name")
    if _name_matches(normalized_name, PII_ADDRESS_HINTS):
        add("address", "column_name")
    if _name_matches(normalized_name, PII_IDENTIFIER_HINTS):
        add("government_identifier", "column_name")

    sample = values[: min(len(values), 50)]
    if sample and sum(1 for value in sample if _EMAIL_RE.match(value)) / len(sample) >= 0.5:
        add("email", "value_pattern")
    if sample and sum(1 for value in sample if _looks_like_phone(value)) / len(sample) >= 0.5:
        add("phone", "value_pattern")

    policy_hints: tuple[str, ...] = ()
    if categories:
        # This policy text is intentionally generic; never include matched raw PII.
        policy_hints = (
            "block_raw_values",
            "exclude_from_value_dictionary",
            "allow_only_aggregated_or_join-safe_usage",
        )
    return PIIDetection(
        is_pii=bool(categories),
        categories=tuple(sorted(categories)),
        reasons=tuple(reasons),
        policy_hints=policy_hints,
    )


def _normalize_value(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    text = str(value).strip()
    if text.lower() in NULL_STRINGS:
        return None
    return text


def _normalize_column_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.strip().lower()).strip("_")


def _name_matches(normalized_name: str, hints: set[str]) -> bool:
    tokens = set(filter(None, normalized_name.split("_")))
    return normalized_name in hints or bool(tokens & hints)


def _looks_like_person_name_column(normalized_name: str) -> bool:
    # A bare `name` column is likely personal in many business exports, but
    # domain nouns such as `product_name` or `sheet_name` are not PII. Keep this
    # narrower than token matching so realistic BI files do not over-block
    # ordinary catalog dimensions.
    if normalized_name in PII_NAME_HINTS:
        return True
    tokens = normalized_name.split("_")
    if not tokens or tokens[-1] != "name":
        return False
    return bool(set(tokens[:-1]) & {"customer", "client", "employee", "staff", "member", "user", "person", "contact"})


def _looks_like_phone(value: str) -> bool:
    # ISO-like dates contain 8 digits and hyphens, so exclude known date shapes
    # before applying the broad phone heuristic. This keeps normal date columns
    # usable for min/max profiling instead of incorrectly blocking them as PII.
    if _to_date(value) is not None:
        return False
    # Alphanumeric business identifiers such as `US-2022-103800` can contain
    # phone-length digit runs; do not classify them as phone numbers unless the
    # visible shape is phone-like punctuation plus digits only.
    if re.search(r"[A-Za-z]", value):
        return False
    digits = re.sub(r"\D", "", value)
    return 8 <= len(digits) <= 15 and bool(_PHONE_RE.search(value))


def _guess_type(values: Sequence[str]) -> str:
    if not values:
        return "unknown"
    if all(_to_decimal(value) is not None for value in values):
        return "number"
    if all(_to_date(value) is not None for value in values):
        return "date"
    lowered = {value.lower() for value in values}
    if lowered <= {"true", "false", "0", "1", "yes", "no", "y", "n"}:
        return "boolean"
    return "string"


def _to_decimal(value: str) -> Decimal | None:
    try:
        return Decimal(value.replace(",", ""))
    except (InvalidOperation, AttributeError):
        return None


def _to_date(value: str) -> date | None:
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def _safe_ratio(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return round(numerator / denominator, 4)


def _pattern_summary(name: str, values: Sequence[str], pii: PIIDetection, cardinality: int) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "non_null_count": len(values),
        "distinct_count": cardinality,
    }
    if not values:
        return summary
    lengths = [len(value) for value in values]
    summary.update(
        {
            "min_length": min(lengths),
            "max_length": max(lengths),
            "avg_length": round(sum(lengths) / len(lengths), 2),
        }
    )
    if pii.is_pii:
        summary["redaction"] = "raw_values_suppressed_for_pii"
    elif cardinality > LOW_CARDINALITY_LIMIT:
        summary["redaction"] = "raw_values_suppressed_for_high_cardinality"
    return summary


def _is_join_key_candidate(name: str, row_count: int, cardinality: int, null_count: int) -> bool:
    normalized = _normalize_column_name(name)
    if row_count == 0 or null_count:
        return False
    if normalized == "id" or normalized.endswith("_id") or normalized.endswith("id"):
        return cardinality == row_count
    return False
