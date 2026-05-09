from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[2]
BUILDER_SRC = REPO_ROOT / "packages" / "semantic_builder" / "src"
if str(BUILDER_SRC) not in sys.path:
    sys.path.insert(0, str(BUILDER_SRC))

from semantic_builder.connectors import (  # noqa: E402
    ConnectorConfigurationError,
    ConnectorDependencyError,
    MySQLConnector,
    OracleConnector,
    UnsupportedConnectorError,
)


class OptionalDBConnectorTests(unittest.TestCase):
    def test_mysql_connector_missing_dependency_is_explicit(self) -> None:
        with patch(
            "semantic_builder.connectors.mysql_connector.importlib.import_module",
            side_effect=ModuleNotFoundError("pymysql"),
        ):
            with self.assertRaisesRegex(ConnectorDependencyError, "pymysql"):
                MySQLConnector("mysql://user:pass@localhost/demo")

    def test_mysql_connector_lists_tables_through_read_only_information_schema(self) -> None:
        connection = _RecordingConnection(
            [
                [
                    ("sales", "orders", "BASE TABLE", "Sales orders"),
                    ("sales", "order_view", "VIEW", "Order view"),
                ]
            ]
        )
        connector = MySQLConnector(connection_factory=lambda: connection)

        tables = connector.list_tables()

        self.assertTrue(connector.read_only)
        self.assertEqual("orders", tables[0].table_name)
        self.assertEqual("Sales orders", tables[0].comment)
        self.assertTrue(tables[1].is_view)
        executed_sql = connection.cursor_obj.executed[0][0]
        self.assertIn("FROM information_schema.tables", executed_sql)
        self.assertIn("table_comment", executed_sql)

    def test_mysql_connector_lists_columns_through_read_only_information_schema(self) -> None:
        connection = _RecordingConnection(
            [
                [
                    ("sales", "orders", "status", "varchar", "NO", 1, "Lifecycle status"),
                    ("sales", "orders", "amount", "decimal", "YES", 2, None),
                ]
            ]
        )
        connector = MySQLConnector(connection_factory=lambda: connection)

        columns = connector.list_columns("sales", "orders")

        self.assertEqual("status", columns[0].column_name)
        self.assertEqual("Lifecycle status", columns[0].comment)
        self.assertFalse(columns[0].is_nullable)
        self.assertIsNone(columns[1].comment)
        executed_sql, params = connection.cursor_obj.executed[0]
        self.assertIn("FROM information_schema.columns", executed_sql)
        self.assertIn("column_comment", executed_sql)
        self.assertEqual(("sales", "orders"), params)

    def test_oracle_connector_missing_connection_string_is_explicit(self) -> None:
        with patch(
            "semantic_builder.connectors.sql.importlib.import_module",
            side_effect=AssertionError("dependency import should not run before connection string validation"),
        ):
            with self.assertRaisesRegex(ConnectorConfigurationError, "non-empty connection string"):
                OracleConnector("")


if __name__ == "__main__":
    unittest.main()


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

    def cursor(self) -> _RecordingCursor:
        return self.cursor_obj

    def close(self) -> None:
        return None
