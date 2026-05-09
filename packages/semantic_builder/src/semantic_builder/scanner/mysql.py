"""MySQL safe scanner built on the read-only connector contract."""

from __future__ import annotations

from typing import Any

from semantic_builder.connectors.db import DBConnector, SafeScanConfig

from .postgres import PostgresScanner


class MySQLScanner(PostgresScanner):
    """Bounded read-only scanner for MySQL-backed semantic packs.

    MySQL catalog reads are owned by ``MySQLConnector``. This scanner keeps the
    shared metadata/provenance/gap behavior from ``PostgresScanner`` while
    labeling evidence as MySQL so source details stay backend-faithful.
    """

    def __init__(self, connector: DBConnector, config: SafeScanConfig | None = None) -> None:
        super().__init__(
            connector=connector,
            config=config,
            connector_name="mysql",
            source_detail_prefix="mysql",
        )


def scan_mysql_database(connector: DBConnector, *, config: SafeScanConfig | None = None) -> dict[str, Any]:
    """Convenience wrapper for MySQL connectors that implement DBConnector."""

    return MySQLScanner(connector=connector, config=config).scan()


__all__ = ["MySQLScanner", "scan_mysql_database"]
