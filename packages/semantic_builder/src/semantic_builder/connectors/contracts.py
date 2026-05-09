"""Shared connector contracts for the Phase 10 safe-scanner package.

The contract layer keeps metadata shapes separate from the live connector
implementations. It deliberately does not open connections, execute SQL, or
collect raw values; those boundaries stay in the specific connector modules.
"""

from __future__ import annotations

from dataclasses import dataclass

from .db import DBConnector, SafeScanConfig, UnsupportedConnectorError


@dataclass(frozen=True, slots=True)
class SchemaMetadata:
    """Schema-level metadata surfaced by safe DB scanners."""

    name: str


@dataclass(frozen=True, slots=True)
class TableMetadata:
    """Table or view metadata surfaced by safe DB scanners."""

    schema_name: str
    table_name: str
    table_type: str
    is_view: bool = False
    is_materialized_view: bool = False


@dataclass(frozen=True, slots=True)
class ColumnMetadata:
    """Column-level metadata surfaced by safe DB scanners."""

    schema_name: str
    table_name: str
    column_name: str
    data_type: str
    is_nullable: bool
    ordinal_position: int


__all__ = [
    "ColumnMetadata",
    "DBConnector",
    "SafeScanConfig",
    "SchemaMetadata",
    "TableMetadata",
    "UnsupportedConnectorError",
]
