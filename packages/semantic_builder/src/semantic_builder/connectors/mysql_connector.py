"""Read-only MySQL connector for safe metadata scanning.

The connector exposes only catalog metadata and bounded sample/profile reads.
It does not provide a general SQL execution surface and refuses to hide missing
driver/configuration failures behind fallback backends.
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Callable, Mapping, Sequence
from urllib.parse import unquote, urlparse

from semantic_builder.profiler import profile_column as profile_safe_column

from .db import ColumnMetadata, SafeScanConfig, SchemaMetadata, TableMetadata
from .sql import ConnectorConfigurationError, ConnectorDependencyError


@dataclass
class MySQLConnector:
    """Small read-only MySQL adapter used by the safe scanner."""

    dsn: str | None = None
    connection_factory: Callable[[], Any] | None = None
    connection: Any | None = None
    read_only: bool = True
    _driver_name: str | None = field(default=None, init=False, repr=False)

    def connect(self) -> Any:
        if self.connection is not None:
            return self.connection
        if self.connection_factory is not None:
            self.connection = self.connection_factory()
            self._driver_name = "factory"
            return self.connection
        if not self.dsn or not str(self.dsn).strip():
            raise ConnectorConfigurationError("MySQL connector is not configured; provide a non-empty connection string before scanning.")
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
            WHERE schema_name NOT IN ('information_schema', 'mysql', 'performance_schema', 'sys')
            ORDER BY schema_name
            """
        )
        schemas = [SchemaMetadata(name=str(_row_value(row, 0, "schema_name"))) for row in rows]
        if config and config.schemas:
            allowed = set(config.schemas)
            return [schema for schema in schemas if schema.name in allowed]
        return schemas

    def list_tables(self, config: SafeScanConfig | None = None) -> Sequence[TableMetadata]:
        rows = self._fetchall(
            """
            SELECT table_schema, table_name, table_type, table_comment
            FROM information_schema.tables
            WHERE table_schema NOT IN ('information_schema', 'mysql', 'performance_schema', 'sys')
            ORDER BY table_schema, table_name, table_type
            """
        )
        tables = [
            TableMetadata(
                schema_name=str(_row_value(row, 0, "table_schema")),
                table_name=str(_row_value(row, 1, "table_name")),
                table_type=str(_row_value(row, 2, "table_type")),
                is_view=str(_row_value(row, 2, "table_type")).upper() == "VIEW",
                is_materialized_view=False,
                comment=_optional_text(_row_value(row, 3, "table_comment")),
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
            tables = [table for table in tables if (table.schema_name, table.table_name, table.table_type) in selected_names]
        if config and config.max_tables is not None:
            return tables[: config.max_tables]
        return tables

    def list_columns(self, schema_name: str, table_name: str, config: SafeScanConfig | None = None) -> Sequence[ColumnMetadata]:
        rows = self._fetchall(
            """
            SELECT table_schema, table_name, column_name, data_type, is_nullable, ordinal_position, column_comment
            FROM information_schema.columns
            WHERE table_schema = %s AND table_name = %s
            ORDER BY ordinal_position
            """,
            (schema_name, table_name),
        )
        columns = [
            ColumnMetadata(
                schema_name=str(_row_value(row, 0, "table_schema")),
                table_name=str(_row_value(row, 1, "table_name")),
                column_name=str(_row_value(row, 2, "column_name")),
                data_type=str(_row_value(row, 3, "data_type")),
                is_nullable=str(_row_value(row, 4, "is_nullable")).upper() == "YES",
                ordinal_position=int(_row_value(row, 5, "ordinal_position")),
                comment=_optional_text(_row_value(row, 6, "column_comment")),
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
        return [dict(zip(selected_columns, [_row_value(row, index) for index in range(len(selected_columns))], strict=False)) for row in rows]

    def profile_column(
        self,
        schema_name: str,
        table_name: str,
        column_name: str,
        config: SafeScanConfig | None = None,
    ) -> Mapping[str, Any]:
        scan_config = config or SafeScanConfig()
        column_ref = self._qualified_column(schema_name, table_name, column_name)
        table_ref = self._qualified_name(schema_name, table_name)
        row_totals = self._fetchone(
            f"""
            SELECT COUNT(*) AS row_count,
                   COUNT({column_ref}) AS non_null_count
            FROM {table_ref}
            """
        )
        total_rows = int(_row_value(row_totals, 0, "row_count")) if row_totals else 0
        non_null_count = int(_row_value(row_totals, 1, "non_null_count")) if row_totals else 0
        non_null_values = self._fetchall(
            f"""
            SELECT {column_ref} AS value,
                   COUNT(*) AS count
            FROM {table_ref}
            WHERE {column_ref} IS NOT NULL
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
            _row_value(row, 0, "value")
            for row in non_null_values
            for _ in range(int(_row_value(row, 1, "count")))
            if _row_value(row, 0, "value") is not None
        ]
        profile = profile_safe_column(column_name, expanded_values, top_n=scan_config.max_sample_rows).to_dict()
        profile["row_count"] = total_rows
        profile["null_count"] = total_rows - non_null_count
        profile["null_ratio"] = round((total_rows - non_null_count) / total_rows, 4) if total_rows else 0.0
        profile["cardinality_estimate"] = distinct_count
        profile["type_guess"] = _guess_db_type(profile, non_null_values)
        return profile

    def _connect_with_optional_driver(self) -> Any:
        try:
            driver = importlib.import_module("pymysql")
        except ModuleNotFoundError as exc:
            raise ConnectorDependencyError(
                "MySQL input requires optional dependency 'pymysql'. Install it or skip MySQL sources explicitly."
            ) from exc
        self._driver_name = "pymysql"
        connect = getattr(driver, "connect", None)
        if not callable(connect):
            raise ConnectorDependencyError("MySQL optional dependency 'pymysql' does not expose connect().")
        return connect(**_connect_kwargs(self.dsn or ""))

    def _fetchall(self, sql: str, params: Sequence[Any] | None = None) -> list[Any]:
        connection = self.connect()
        cursor = connection.cursor()
        try:
            cursor.execute(sql, params or ())
            return list(cursor.fetchall())
        finally:
            close = getattr(cursor, "close", None)
            if callable(close):
                close()

    def _fetchone(self, sql: str, params: Sequence[Any] | None = None) -> Any | None:
        connection = self.connect()
        cursor = connection.cursor()
        try:
            cursor.execute(sql, params or ())
            return cursor.fetchone()
        finally:
            close = getattr(cursor, "close", None)
            if callable(close):
                close()

    def _qualified_name(self, schema_name: str, table_name: str) -> str:
        return f"{_quote_identifier(schema_name)}.{_quote_identifier(table_name)}"

    def _qualified_column(self, schema_name: str, table_name: str, column_name: str) -> str:
        _ = schema_name, table_name
        return _quote_identifier(column_name)


def _connect_kwargs(dsn: str) -> dict[str, Any]:
    parsed = urlparse(dsn)
    if parsed.scheme and parsed.scheme not in {"mysql", "mysql+pymysql"}:
        raise ConnectorConfigurationError("MySQL connector requires a mysql:// or mysql+pymysql:// connection string.")
    if not parsed.hostname:
        raise ConnectorConfigurationError("MySQL connector requires a host in the connection string.")
    kwargs: dict[str, Any] = {
        "host": parsed.hostname,
        "user": unquote(parsed.username or ""),
        "password": unquote(parsed.password or ""),
        "database": unquote(parsed.path.lstrip("/")) if parsed.path else "",
        "port": parsed.port or 3306,
        "read_timeout": 5,
        "write_timeout": 5,
    }
    return kwargs


def _quote_identifier(value: str) -> str:
    escaped = value.replace("`", "``")
    return f"`{escaped}`"


def _row_value(row: Any, index: int, key: str | None = None) -> Any:
    if row is None:
        return None
    if isinstance(row, Mapping):
        if key and key in row:
            return row[key]
        if key and key.upper() in row:
            return row[key.upper()]
        values = list(row.values())
        return values[index] if index < len(values) else None
    return row[index]


def _optional_text(value: Any) -> str | None:
    text = "" if value is None else str(value).strip()
    return text or None


def _guess_db_type(profile: Mapping[str, Any], distinct_rows: Sequence[Any]) -> str:
    values = [_row_value(row, 0, "value") for row in distinct_rows]
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
