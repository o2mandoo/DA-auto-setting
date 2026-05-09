"""Oracle adapter skeleton for Phase 10.

Oracle support is intentionally explicit and read-only. The adapter refuses to
pretend that missing configuration or missing dependencies are usable live
scanner paths.
"""

from __future__ import annotations

from .sql import OptionalDatabaseConnector


class OracleConnector(OptionalDatabaseConnector):
    product_name = "Oracle"
    driver_module = "oracledb"
    dependency_name = "oracledb"
