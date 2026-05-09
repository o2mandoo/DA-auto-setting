from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BUILDER_SRC = REPO_ROOT / "packages" / "semantic_builder" / "src"
if str(BUILDER_SRC) not in sys.path:
    sys.path.insert(0, str(BUILDER_SRC))

from semantic_builder.connectors.db import ColumnMetadata, SafeScanConfig, TableMetadata  # noqa: E402
from semantic_builder.connectors.postgres_connector import PostgresConnector  # noqa: E402
from semantic_builder.scanner import PostgresScanner  # noqa: E402


class _RecordingCursor:
    def __init__(self, responses: list[list[tuple[object, ...]]]) -> None:
        self.responses = responses
        self.executed: list[tuple[str, tuple[object, ...]]] = []
        self._current: list[tuple[object, ...]] = []

    def execute(self, sql: str, params: tuple[object, ...] = ()) -> None:
        self.executed.append((sql, params))
        if not self.responses:
            raise AssertionError(f"Unexpected query: {sql}")
        self._current = self.responses.pop(0)

    def fetchall(self) -> list[tuple[object, ...]]:
        return list(self._current)

    def fetchone(self) -> tuple[object, ...] | None:
        return self._current[0] if self._current else None

    def close(self) -> None:
        return None


class _RecordingConnection:
    def __init__(self, responses: list[list[tuple[object, ...]]]) -> None:
        self.cursor_obj = _RecordingCursor(responses)
        self.closed = False

    def cursor(self) -> _RecordingCursor:
        return self.cursor_obj

    def close(self) -> None:
        self.closed = True


class _ScannerConnector:
    def __init__(self) -> None:
        self.profile_calls: list[tuple[str, str, str]] = []
        self.column_calls: list[tuple[str, str]] = []

    def connect(self):  # pragma: no cover - scanner never needs a live connection in this test
        return self

    def close(self) -> None:  # pragma: no cover - helper only
        return None

    def list_schemas(self, config: SafeScanConfig | None = None):
        return []

    def list_tables(self, config: SafeScanConfig | None = None):
        tables = [
            TableMetadata(schema_name="public", table_name="users", table_type="BASE TABLE"),
            TableMetadata(schema_name="public", table_name="audit_log", table_type="BASE TABLE"),
        ]
        return tables

    def list_columns(self, schema_name: str, table_name: str, config: SafeScanConfig | None = None):
        self.column_calls.append((schema_name, table_name))
        return [
            ColumnMetadata(
                schema_name=schema_name,
                table_name=table_name,
                column_name="status",
                data_type="text",
                is_nullable=False,
                ordinal_position=1,
            )
        ]

    def sample_rows(self, schema_name: str, table_name: str, columns=None, config: SafeScanConfig | None = None):
        return []

    def profile_column(self, schema_name: str, table_name: str, column_name: str, config: SafeScanConfig | None = None):
        self.profile_calls.append((schema_name, table_name, column_name))
        return {
            "name": column_name,
            "row_count": 3,
            "null_count": 0,
            "null_ratio": 0.0,
            "cardinality_estimate": 2,
            "type_guess": "string",
            "top_values": [{"value": "PAID", "count": 2}, {"value": "PENDING", "count": 1}],
            "pattern_summary": {"non_null_count": 3, "distinct_count": 2},
        }


class PostgresScannerTests(unittest.TestCase):
    def test_low_cardinality_status_profiles_top_values_without_leaking_raw_values(self) -> None:
        connection = _RecordingConnection(
            [
                [(4, 4)],
                [("PAID", 2), ("PENDING", 1)],
            ]
        )
        connector = PostgresConnector(connection_factory=lambda: connection)

        profile = connector.profile_column(
            "Sales Data",
            "Order Detail",
            "status",
            SafeScanConfig(max_sample_rows=3, low_cardinality_threshold=5),
        )

        self.assertEqual(4, profile["row_count"])
        self.assertEqual(0, profile["null_count"])
        self.assertEqual(0.0, profile["null_ratio"])
        self.assertEqual(2, profile["cardinality_estimate"])
        self.assertEqual("string", profile["type_guess"])
        self.assertEqual({"value": "PAID", "count": 2}, profile["top_values"][0])
        self.assertNotIn("raw_values_suppressed_for_high_cardinality", profile["pattern_summary"].get("redaction", ""))

        executed_sql = [sql for sql, _ in connection.cursor_obj.executed]
        self.assertIn('FROM "Sales Data"."Order Detail"', executed_sql[0])
        self.assertIn('COUNT("status")', executed_sql[0])
        self.assertIn('GROUP BY 1', executed_sql[1])

    def test_reserved_words_and_case_sensitive_names_are_scanner_safe(self) -> None:
        connector = _ScannerConnector()
        scanner = PostgresScanner(
            connector=connector,
            config=SafeScanConfig(tables=("public.users",), max_tables=10, max_columns=10),
        )

        report = scanner.scan()

        self.assertEqual("postgres", report["connector"])
        self.assertEqual(1, len(report["tables"]))
        self.assertEqual([("public", "users")], connector.column_calls)
        self.assertEqual([("public", "users", "status")], connector.profile_calls)
        self.assertEqual("users", report["tables"][0]["table_name"])
        self.assertEqual("status", report["tables"][0]["columns"][0]["name"])

    def test_table_allowlist_excludes_non_allowed_tables_before_scanning(self) -> None:
        connector = _ScannerConnector()
        scanner = PostgresScanner(
            connector=connector,
            config=SafeScanConfig(tables=("public.users",), max_tables=10, max_columns=10),
        )

        report = scanner.scan()

        self.assertEqual(1, len(report["tables"]))
        self.assertEqual([("public", "users")], connector.column_calls)
        self.assertEqual([("public", "users", "status")], connector.profile_calls)
        self.assertEqual("users", report["tables"][0]["table_name"])
        self.assertNotIn("audit_log", {table["table_name"] for table in report["tables"]})


if __name__ == "__main__":
    unittest.main()
