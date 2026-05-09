"""Connector API for the Semantic Builder local-file MVP and DB adapter stubs.

Phase 10 keeps database support explicitly read-only and non-silent. The file
connectors remain the primary MVP surface; MySQL and Oracle are only exposed as
adapter skeletons with explicit unsupported / missing-dependency errors until a
safe scanner lane is wired in.
"""

from .db import DBConnector, SafeScanConfig, UnsupportedConnectorError
from .sql import ConnectorConfigurationError, ConnectorDependencyError
from .files import (
    FileDataset,
    MissingConnectorDependency,
    UnsupportedFileType,
    load_file,
    load_file_datasets,
    scan_source,
)
from .mysql_connector import MySQLConnector
from .oracle_connector import OracleConnector
from .postgres_connector import PostgresConnector

__all__ = [
    "DBConnector",
    "ConnectorConfigurationError",
    "ConnectorDependencyError",
    "FileDataset",
    "MissingConnectorDependency",
    "MySQLConnector",
    "OracleConnector",
    "PostgresConnector",
    "SafeScanConfig",
    "UnsupportedFileType",
    "UnsupportedConnectorError",
    "load_file",
    "load_file_datasets",
    "scan_source",
]
