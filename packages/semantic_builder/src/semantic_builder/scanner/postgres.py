"""PostgreSQL safe scanner built on the read-only connector contract."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

from semantic_builder.connectors.db import ColumnMetadata, DBConnector, SafeScanConfig, TableMetadata


@dataclass
class PostgresScanner:
    """Bounded read-only scanner for PostgreSQL-backed semantic packs."""

    connector: DBConnector
    config: SafeScanConfig | None = None

    def scan(self) -> dict[str, Any]:
        config = self.config or SafeScanConfig()
        tables = list(self.connector.list_tables(config))
        tables = self._filter_allowed_tables(tables, config)
        report_tables: list[dict[str, Any]] = []
        for table in tables:
            columns = list(self.connector.list_columns(table.schema_name, table.table_name, config))
            column_payloads: list[dict[str, Any]] = []
            for column in columns:
                column_payloads.append(self._profile_column(table, column, config))
            report_tables.append(
                {
                    "schema_name": table.schema_name,
                    "table_name": table.table_name,
                    "qualified_name": f"{table.schema_name}.{table.table_name}",
                    "table_type": table.table_type,
                    "is_view": table.is_view,
                    "is_materialized_view": table.is_materialized_view,
                    "columns": column_payloads,
                }
            )
        return {
            "connector": "postgres",
            "config": config.to_dict(),
            "tables": report_tables,
        }

    def _filter_allowed_tables(self, tables: Sequence[TableMetadata], config: SafeScanConfig) -> list[TableMetadata]:
        """Apply the allowlist at the scanner boundary as a safety backstop.

        The connector is expected to honor the allowlist, but the scanner keeps a
        second read-only filter so a misbehaving connector cannot accidentally
        profile a table that the scan config excluded.
        """

        allowed = config.select_tables(
            [
                {
                    "schema": table.schema_name,
                    "table_name": table.table_name,
                    "kind": table.table_type,
                }
                for table in tables
            ]
        )
        allowed_keys = {(record["schema"], record["table_name"], record["kind"]) for record in allowed}
        return [
            table
            for table in tables
            if (table.schema_name, table.table_name, table.table_type) in allowed_keys
        ]

    def _profile_column(self, table: TableMetadata, column: ColumnMetadata, config: SafeScanConfig) -> dict[str, Any]:
        profile = dict(self.connector.profile_column(table.schema_name, table.table_name, column.column_name, config))
        profile.setdefault("name", column.column_name)
        profile.setdefault("type_guess", column.data_type)
        profile.setdefault("row_count", 0)
        profile.setdefault("null_count", 0)
        profile.setdefault("null_ratio", 0.0)
        profile.setdefault("cardinality_estimate", 0)
        profile.setdefault("top_values", [])
        profile.setdefault("pattern_summary", {})
        profile["schema_name"] = table.schema_name
        profile["table_name"] = table.table_name
        profile["qualified_name"] = f"{table.schema_name}.{table.table_name}"
        profile["column_name"] = column.column_name
        profile["column_type"] = column.data_type
        profile["is_nullable"] = column.is_nullable
        profile["ordinal_position"] = column.ordinal_position
        return profile


def scan_postgres_database(connector: DBConnector, *, config: SafeScanConfig | None = None) -> dict[str, Any]:
    """Convenience wrapper for callers that prefer a functional API."""

    return PostgresScanner(connector=connector, config=config).scan()
