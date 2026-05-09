from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BUILDER_SRC = REPO_ROOT / "packages" / "semantic_builder" / "src"
if str(BUILDER_SRC) not in sys.path:
    sys.path.insert(0, str(BUILDER_SRC))

from semantic_builder.connectors import PostgresConnector, SafeScanConfig  # noqa: E402


class _DummyCursor:
    def execute(self, sql: str, params: tuple[object, ...] = ()) -> None:  # pragma: no cover - helper only
        self.sql = sql
        self.params = params

    def fetchall(self) -> list[tuple[object, ...]]:  # pragma: no cover - helper only
        return [(1, 1)]

    def fetchone(self) -> tuple[object, ...]:  # pragma: no cover - helper only
        return (1, 1)

    def close(self) -> None:  # pragma: no cover - helper only
        return None


class _DummyConnection:
    def cursor(self) -> _DummyCursor:  # pragma: no cover - helper only
        return _DummyCursor()

    def close(self) -> None:  # pragma: no cover - helper only
        return None


class DBConnectorContractTests(unittest.TestCase):
    def test_safe_scan_config_exposes_allowlist_aliases_and_limits(self) -> None:
        config = SafeScanConfig(
            schemas=("public", "analytics"),
            tables=("public.users",),
            max_tables=3,
            max_columns=7,
            max_sample_rows=2,
            timeout_ms=2500,
            low_cardinality_threshold=4,
            pii_policy="block_raw_values",
        )

        self.assertEqual(("public", "analytics"), config.schemas)
        self.assertEqual(("public.users",), config.tables)
        self.assertEqual(config.schemas, config.schemas_allowlist)
        self.assertEqual(config.tables, config.tables_allowlist)
        payload = config.to_dict()
        self.assertEqual(["public", "analytics"], payload["schemas"])
        self.assertEqual(["public.users"], payload["tables"])
        self.assertEqual(["public", "analytics"], payload["schemas_allowlist"])
        self.assertEqual(["public.users"], payload["tables_allowlist"])

    def test_safe_scan_config_caps_table_selection_at_max_tables(self) -> None:
        config = SafeScanConfig(max_tables=2)
        tables = (
            {"schema": "public", "table_name": "users", "kind": "table"},
            {"schema": "public", "table_name": "payments", "kind": "table"},
            {"schema": "analytics", "table_name": "events", "kind": "table"},
            {"schema": "analytics", "table_name": "sessions", "kind": "view"},
        )

        selected = config.select_tables(tables)

        self.assertEqual(2, len(selected))
        self.assertEqual(("users", "payments"), tuple(record["table_name"] for record in selected))

    def test_postgres_connector_matches_read_only_contract_shape(self) -> None:
        connector = PostgresConnector(connection_factory=_DummyConnection)

        self.assertTrue(connector.read_only)
        self.assertTrue(callable(connector.connect))
        self.assertTrue(callable(connector.list_schemas))
        self.assertTrue(callable(connector.list_tables))
        self.assertTrue(callable(connector.list_columns))
        self.assertTrue(callable(connector.sample_rows))
        self.assertTrue(callable(connector.profile_column))
        self.assertIsNotNone(connector.connect())
        connector.close()

    def test_postgres_connector_requires_connection_string_without_factory(self) -> None:
        connector = PostgresConnector()

        with self.assertRaisesRegex(ValueError, "connection string"):
            connector.connect()

    def test_safe_scan_config_rejects_invalid_limits(self) -> None:
        with self.assertRaisesRegex(ValueError, "max_tables"):
            SafeScanConfig(max_tables=0)
        with self.assertRaisesRegex(ValueError, "timeout_ms"):
            SafeScanConfig(timeout_ms=0)


if __name__ == "__main__":
    unittest.main()
