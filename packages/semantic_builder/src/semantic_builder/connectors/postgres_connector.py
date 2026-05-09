"""Read-only PostgreSQL connector for the Phase 10 safe scanner.

The connector only exposes metadata and bounded sample/profile queries. It
quotes identifiers so reserved words and case-sensitive names stay usable, and
it refuses to pretend that a connection exists when the driver or DSN is
missing.
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Callable, Mapping, Sequence

from semantic_builder.profiler import profile_column as profile_safe_column

from .db import ColumnMetadata, SafeScanConfig, SchemaMetadata, TableMetadata, UnsupportedConnectorError


@dataclass
class PostgresConnector:
    """Small read-only PostgreSQL adapter used by the safe scanner."""

    # The protocol contract requires an explicit read-only flag so contract
    # checks can distinguish safe metadata scanners from any future writer.
    read_only: bool = True
    dsn: str | None = None
    connection_factory: Callable[[], Any] | None = None
    connection: Any | None = None
    _driver_name: str | None = field(default=None, init=False, repr=False)

    def connect(self) -> Any:
        if self.connection is not None:
            return self.connection
        if self.connection_factory is not None:
            self.connection = self.connection_factory()
            self._driver_name = "factory"
            return self.connection
        if not self.dsn:
            raise ValueError("PostgreSQL connection string is required")
        self.connection = self._connect_with_optional_driver()
        return self.connection

    def close(self) -> None:
        if self.connection is None:
            return
        close = getattr(self.connection, "close", None)
        if callable(close):
            close()
        self.connection = None

    def list_schemas(self, config: SafeScanConfig | None = None) -> Sequence[SchemaMetadata]:
        rows = self._fetchall(
            """
            SELECT schema_name
            FROM information_schema.schemata
            WHERE schema_name NOT IN ('information_schema', 'pg_catalog')
            ORDER BY schema_name
            """
        )
        schemas = [SchemaMetadata(name=str(row[0])) for row in rows]
        if config and config.schemas:
            allowed = set(config.schemas)
            return [schema for schema in schemas if schema.name in allowed]
        return schemas

    def list_tables(self, config: SafeScanConfig | None = None) -> Sequence[TableMetadata]:
        rows = self._fetchall(
            """
            SELECT t.table_schema, t.table_name, t.table_type, obj_description(c.oid, 'pg_class') AS comment
            FROM information_schema.tables t
            LEFT JOIN pg_catalog.pg_namespace n ON n.nspname = t.table_schema
            LEFT JOIN pg_catalog.pg_class c ON c.relnamespace = n.oid AND c.relname = t.table_name
            WHERE t.table_schema NOT IN ('information_schema', 'pg_catalog')
            UNION ALL
            SELECT m.schemaname AS table_schema, m.matviewname AS table_name, 'MATERIALIZED VIEW' AS table_type, obj_description(c.oid, 'pg_class') AS comment
            FROM pg_matviews m
            LEFT JOIN pg_catalog.pg_namespace n ON n.nspname = m.schemaname
            LEFT JOIN pg_catalog.pg_class c ON c.relnamespace = n.oid AND c.relname = m.matviewname
            WHERE m.schemaname NOT IN ('information_schema', 'pg_catalog')
            ORDER BY 1, 2, 3
            """
        )
        tables = [
            TableMetadata(
                schema_name=str(row[0]),
                table_name=str(row[1]),
                table_type=str(row[2]),
                is_view=str(row[2]) == "VIEW",
                is_materialized_view=str(row[2]) == "MATERIALIZED VIEW",
                comment=str(row[3]) if len(row) > 3 and row[3] is not None else None,
            )
            for row in rows
        ]
        if config is not None:
            selected = config.select_tables(
                [
                    {
                        "schema": table.schema_name,
                        "table_name": table.table_name,
                        "kind": table.table_type,
                    }
                    for table in tables
                ]
            )
            selected_names = {(record["schema"], record["table_name"], record["kind"]) for record in selected}
            tables = [
                table
                for table in tables
                if (table.schema_name, table.table_name, table.table_type) in selected_names
            ]
        if config and config.max_tables is not None:
            return tables[: config.max_tables]
        return tables

    def list_columns(self, schema_name: str, table_name: str, config: SafeScanConfig | None = None) -> Sequence[ColumnMetadata]:
        rows = self._fetchall(
            """
            SELECT c.table_schema, c.table_name, c.column_name, c.data_type, c.is_nullable, c.ordinal_position,
                   col_description(pc.oid, c.ordinal_position) AS comment
            FROM information_schema.columns c
            LEFT JOIN pg_catalog.pg_namespace n ON n.nspname = c.table_schema
            LEFT JOIN pg_catalog.pg_class pc ON pc.relnamespace = n.oid AND pc.relname = c.table_name
            WHERE c.table_schema = %s AND c.table_name = %s
            ORDER BY c.ordinal_position
            """,
            (schema_name, table_name),
        )
        columns = [
            ColumnMetadata(
                schema_name=str(row[0]),
                table_name=str(row[1]),
                column_name=str(row[2]),
                data_type=str(row[3]),
                is_nullable=str(row[4]).upper() == "YES",
                ordinal_position=int(row[5]),
                comment=str(row[6]) if len(row) > 6 and row[6] is not None else None,
            )
            for row in rows
        ]
        if config and config.max_columns is not None:
            return columns[: config.max_columns]
        return columns

    def sample_rows(
        self,
        schema_name: str,
        table_name: str,
        columns: Sequence[str] | None = None,
        config: SafeScanConfig | None = None,
    ) -> Sequence[Mapping[str, Any]]:
        selected_columns = list(columns or ())
        if not selected_columns:
            selected_columns = [column.column_name for column in self.list_columns(schema_name, table_name, config)]
        limit = config.sample_row_limit() if config else 5
        sql = f"SELECT {', '.join(_quote_identifier(column) for column in selected_columns)} FROM {self._qualified_name(schema_name, table_name)} LIMIT %s"
        rows = self._fetchall(sql, (limit,))
        return [dict(zip(selected_columns, row, strict=False)) for row in rows]

    def profile_column(
        self,
        schema_name: str,
        table_name: str,
        column_name: str,
        config: SafeScanConfig | None = None,
    ) -> Mapping[str, Any]:
        scan_config = config or SafeScanConfig()
        row_totals = self._fetchone(
            f"""
            SELECT COUNT(*) AS row_count,
                   COUNT({self._qualified_column(schema_name, table_name, column_name)}) AS non_null_count
            FROM {self._qualified_name(schema_name, table_name)}
            """
        )
        total_rows = int(row_totals[0]) if row_totals else 0
        non_null_count = int(row_totals[1]) if row_totals else 0
        non_null_values = self._fetchall(
            f"""
            SELECT {self._qualified_column(schema_name, table_name, column_name)} AS value,
                   COUNT(*) AS count
            FROM {self._qualified_name(schema_name, table_name)}
            WHERE {self._qualified_column(schema_name, table_name, column_name)} IS NOT NULL
            GROUP BY 1
            ORDER BY 2 DESC, 1 ASC
            LIMIT %s
            """,
            (scan_config.low_cardinality_threshold + 1,),
        )
        distinct_count = len(non_null_values)
        if distinct_count > scan_config.low_cardinality_threshold:
            return {
                "name": column_name,
                "row_count": total_rows,
                "null_count": total_rows - non_null_count,
                "null_ratio": round((total_rows - non_null_count) / total_rows, 4) if total_rows else 0.0,
                "cardinality_estimate": distinct_count,
                "type_guess": "unknown",
                "top_values": [],
                "pattern_summary": {
                    "non_null_count": non_null_count,
                    "distinct_count": distinct_count,
                    "redaction": "raw_values_suppressed_for_high_cardinality",
                },
            }

        expanded_values = [
            value
            for value, count in non_null_values
            for _ in range(int(count))
            if value is not None
        ]
        profile = profile_safe_column(column_name, expanded_values, top_n=scan_config.max_sample_rows).to_dict()
        profile["row_count"] = total_rows
        profile["null_count"] = total_rows - non_null_count
        profile["null_ratio"] = round((total_rows - non_null_count) / total_rows, 4) if total_rows else 0.0
        profile["cardinality_estimate"] = distinct_count
        profile["type_guess"] = _guess_db_type(profile, non_null_values)
        return profile

    def _connect_with_optional_driver(self) -> Any:
        for module_name in ("psycopg", "psycopg2"):
            try:
                driver = importlib.import_module(module_name)
            except ModuleNotFoundError:
                continue
            self._driver_name = module_name
            connect = getattr(driver, "connect", None)
            if callable(connect):
                return connect(self.dsn)
        raise UnsupportedConnectorError(
            "PostgreSQL scanner requires optional dependency 'psycopg' or 'psycopg2'. "
            "Install one of them or provide a test connection_factory."
        )

    def _fetchall(self, sql: str, params: Sequence[Any] | None = None) -> list[tuple[Any, ...]]:
        connection = self.connect()
        cursor = connection.cursor()
        try:
            cursor.execute(sql, params or ())
            rows = cursor.fetchall()
        finally:
            close = getattr(cursor, "close", None)
            if callable(close):
                close()
        return [tuple(row) for row in rows]

    def _fetchone(self, sql: str, params: Sequence[Any] | None = None) -> tuple[Any, ...] | None:
        connection = self.connect()
        cursor = connection.cursor()
        try:
            cursor.execute(sql, params or ())
            row = cursor.fetchone()
        finally:
            close = getattr(cursor, "close", None)
            if callable(close):
                close()
        return tuple(row) if row is not None else None

    def _qualified_name(self, schema_name: str, table_name: str) -> str:
        return f"{_quote_identifier(schema_name)}.{_quote_identifier(table_name)}"

    def _qualified_column(self, schema_name: str, table_name: str, column_name: str) -> str:
        _ = schema_name, table_name
        return _quote_identifier(column_name)

def _quote_identifier(value: str) -> str:
    escaped = value.replace('"', '""')
    return f'"{escaped}"'


def _guess_db_type(profile: Mapping[str, Any], distinct_rows: Sequence[tuple[Any, ...]]) -> str:
    values = [row[0] for row in distinct_rows if row]
    if not values:
        return "unknown"
    if all(_to_decimal(value) is not None for value in values if value is not None):
        return "number"
    return str(profile.get("type_guess") or "string")


def _to_decimal(value: Any) -> Decimal | None:
    try:
        return Decimal(str(value).replace(",", ""))
    except Exception:
        return None
