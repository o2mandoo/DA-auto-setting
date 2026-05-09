"""Shared DB connector contracts for Phase 10 safe scanning.

This module only defines interfaces and limit controls. It does not open
connections, execute SQL, or collect raw values; later scanner implementations
must stay read-only and respect these constraints.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol, Sequence, runtime_checkable


class UnsupportedConnectorError(RuntimeError):
    """Raised when a connector backend is intentionally unavailable."""


class MissingConnectorDependency(RuntimeError):
    """Raised when an optional connector dependency is not installed."""


@runtime_checkable
class DBConnector(Protocol):
    """Read-only database connector contract for safe metadata scanning."""

    read_only: bool

    def connect(self) -> "DBConnector":
        """Open or refresh the underlying connection without changing state."""

    def list_schemas(self, config: "SafeScanConfig | None" = None) -> Sequence["SchemaMetadata"]:
        """Return schema names visible to the read-only connector."""

    def list_tables(self, config: "SafeScanConfig | None" = None) -> Sequence["TableMetadata"]:
        """Return table/view metadata records, optionally scoped to safe limits."""

    def list_columns(
        self,
        schema: str,
        table: str,
        config: "SafeScanConfig | None" = None,
    ) -> Sequence["ColumnMetadata"]:
        """Return column metadata records for one table."""

    def sample_rows(
        self,
        schema: str,
        table: str,
        columns: Sequence[str] | None = None,
        *,
        config: "SafeScanConfig | None" = None,
    ) -> Sequence[Mapping[str, Any]]:
        """Return bounded sample rows for safe profiling."""

    def profile_column(
        self,
        schema: str,
        table: str,
        column: str,
        config: "SafeScanConfig | None" = None,
    ) -> Mapping[str, Any]:
        """Return a PII-safe column profile payload."""

    def close(self) -> None:
        """Release any held connection resources."""


@dataclass(frozen=True, slots=True)
class SafeScanConfig:
    """Read-only scan guardrails for DB-backed connector and scanner flows."""

    schemas: tuple[str, ...] = field(default_factory=tuple)
    tables: tuple[str, ...] = field(default_factory=tuple)
    max_tables: int = 25
    max_columns: int = 100
    max_sample_rows: int = 10
    timeout_ms: int = 5000
    low_cardinality_threshold: int = 20
    pii_policy: str = "block_raw_values"

    def __post_init__(self) -> None:
        object.__setattr__(self, "schemas", _normalize_allowlist(self.schemas))
        object.__setattr__(self, "tables", _normalize_allowlist(self.tables))
        for field_name in ("max_tables", "max_columns", "max_sample_rows", "timeout_ms", "low_cardinality_threshold"):
            value = getattr(self, field_name)
            if value <= 0:
                raise ValueError(f"{field_name} must be greater than zero")
        if not self.pii_policy.strip():
            raise ValueError("pii_policy must not be empty")

    def is_schema_allowed(self, schema: str) -> bool:
        """Return whether one schema is in the allowlist."""
        return not self.schemas or schema in self.schemas

    @property
    def schemas_allowlist(self) -> tuple[str, ...]:
        """Compatibility alias for the Phase 10 prompt wording."""
        return self.schemas

    @property
    def tables_allowlist(self) -> tuple[str, ...]:
        """Compatibility alias for the Phase 10 prompt wording."""
        return self.tables

    def is_table_allowed(self, schema: str, table: str) -> bool:
        """Return whether one table or view is in the allowlist."""
        if self.tables:
            candidates = {table, f"{schema}.{table}" if schema else table}
            return bool(candidates & set(self.tables))
        return self.is_schema_allowed(schema)

    def select_tables(self, tables: Sequence[Mapping[str, Any]]) -> tuple[dict[str, Any], ...]:
        """Apply allowlists, dedupe, and max_tables while preserving order."""
        selected: list[dict[str, Any]] = []
        seen: set[tuple[str, str, str]] = set()
        for record in tables:
            schema = str(record.get("schema", "")).strip()
            table = str(record.get("table_name") or record.get("name") or "").strip()
            kind = str(record.get("kind") or "table").strip()
            if not table or not self.is_schema_allowed(schema) or not self.is_table_allowed(schema, table):
                continue
            key = (schema, table, kind)
            if key in seen:
                continue
            seen.add(key)
            selected.append(dict(record))
            if len(selected) >= self.max_tables:
                break
        return tuple(selected)

    def limit_columns(self, columns: Sequence[Mapping[str, Any]]) -> tuple[dict[str, Any], ...]:
        """Deduplicate and clamp a table's columns to max_columns."""
        selected: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()
        for record in columns:
            schema = str(record.get("schema", "")).strip()
            column = str(record.get("name") or record.get("column_name") or "").strip()
            if not column:
                continue
            key = (schema, column)
            if key in seen:
                continue
            seen.add(key)
            selected.append(dict(record))
            if len(selected) >= self.max_columns:
                break
        return tuple(selected)

    def sample_row_limit(self, requested_limit: int | None = None) -> int:
        """Clamp requested sample sizes to the configured safe maximum."""
        if requested_limit is None:
            return self.max_sample_rows
        return max(0, min(requested_limit, self.max_sample_rows))

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable snapshot for reports and CLI payloads."""
        return {
            "schemas": list(self.schemas),
            "tables": list(self.tables),
            "schemas_allowlist": list(self.schemas),
            "tables_allowlist": list(self.tables),
            "max_tables": self.max_tables,
            "max_columns": self.max_columns,
            "max_sample_rows": self.max_sample_rows,
            "timeout_ms": self.timeout_ms,
            "low_cardinality_threshold": self.low_cardinality_threshold,
            "pii_policy": self.pii_policy,
        }


@dataclass(frozen=True, slots=True)
class SchemaMetadata:
    """Schema metadata record returned by safe DB scanners."""

    name: str

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name}


@dataclass(frozen=True, slots=True)
class TableMetadata:
    """Table or view metadata record returned by safe DB scanners."""

    schema_name: str
    table_name: str
    table_type: str = "TABLE"
    is_view: bool = False
    is_materialized_view: bool = False
    row_count_estimate: int | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "schema": self.schema_name,
            "table_name": self.table_name,
            "kind": self.table_type,
            "is_view": self.is_view,
            "is_materialized_view": self.is_materialized_view,
        }
        if self.row_count_estimate is not None:
            payload["row_count_estimate"] = self.row_count_estimate
        return payload


@dataclass(frozen=True, slots=True)
class ColumnMetadata:
    """Column metadata record returned by safe DB scanners."""

    schema_name: str
    table_name: str
    column_name: str
    data_type: str
    is_nullable: bool
    ordinal_position: int
    is_pii: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema_name,
            "table_name": self.table_name,
            "name": self.column_name,
            "data_type": self.data_type,
            "is_nullable": self.is_nullable,
            "ordinal_position": self.ordinal_position,
            "is_pii": self.is_pii,
        }


def _normalize_allowlist(values: Sequence[str]) -> tuple[str, ...]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        cleaned.append(text)
    return tuple(cleaned)
