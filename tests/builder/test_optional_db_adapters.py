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
            "semantic_builder.connectors.sql.importlib.import_module",
            side_effect=ModuleNotFoundError("pymysql"),
        ):
            with self.assertRaisesRegex(ConnectorDependencyError, "pymysql"):
                MySQLConnector("mysql://user:pass@localhost/demo")

    def test_mysql_list_tables_keeps_view_flags_visible_without_faking_success(self) -> None:
        with patch("semantic_builder.connectors.sql.importlib.import_module", return_value=object()):
            with self.assertRaisesRegex(UnsupportedConnectorError, "include_views=True"):
                MySQLConnector("mysql://user:pass@localhost/demo").list_tables(
                    schema="sales",
                    table_allowlist=["orders"],
                    include_views=True,
                    include_materialized_views=True,
                )

    def test_oracle_connector_missing_connection_string_is_explicit(self) -> None:
        with patch(
            "semantic_builder.connectors.sql.importlib.import_module",
            side_effect=AssertionError("dependency import should not run before connection string validation"),
        ):
            with self.assertRaisesRegex(ConnectorConfigurationError, "non-empty connection string"):
                OracleConnector("")


if __name__ == "__main__":
    unittest.main()
