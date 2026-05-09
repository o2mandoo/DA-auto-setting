"""MySQL adapter skeleton for Phase 10.

This module keeps the MySQL path explicit and non-silent. It is intentionally
not a fake scanner: callers must supply a connection string, the optional driver
must be installed, and even then the adapter only reports that the live scanning
path is not yet enabled in this phase.
"""

from __future__ import annotations

from .sql import OptionalDatabaseConnector


class MySQLConnector(OptionalDatabaseConnector):
    product_name = "MySQL"
    # The dependency label matches the current adapter tests so missing-driver
    # failures remain explicit instead of looking like a generic runtime import
    # error.
    driver_module = "pymysql"
    dependency_name = "pymysql"
