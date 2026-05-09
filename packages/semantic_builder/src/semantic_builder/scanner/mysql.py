"""MySQL safe scanner built on the read-only connector contract.

MySQL scanning shares the generic DB scanner behavior with PostgreSQL, but it
must label connector/report provenance as MySQL so callers cannot mistake a
MySQL validation path for a PostgreSQL fallback.
"""

from __future__ import annotations

from typing import Any

from semantic_builder.connectors.db import DBConnector, SafeScanConfig
from semantic_builder.scanner.postgres import PostgresScanner


class MySQLScanner(PostgresScanner):
    """Bounded read-only scanner for MySQL-backed semantic packs.

    The connector is responsible for reading MySQL catalog comments; this class
    preserves the same provenance semantics while labeling evidence as MySQL.
    """

    connector_name = "mysql"
    source_detail_prefix = "mysql"


def scan_mysql_database(connector: DBConnector, *, config: SafeScanConfig | None = None) -> dict[str, Any]:
    """Convenience wrapper for MySQL connectors that implement DBConnector."""

    return MySQLScanner(connector=connector, config=config).scan()


__all__ = ["MySQLScanner", "scan_mysql_database"]
