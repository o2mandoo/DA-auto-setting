"""Optional SQL database connector stubs for Phase 10.

These adapters deliberately do not pretend to support live scanning without a
verified local fixture. They only surface explicit configuration/dependency
errors so downstream code never mistakes an incomplete adapter for a working
scanner.
"""

from __future__ import annotations

import importlib
from typing import Any, Iterable

from .db import MissingConnectorDependency, UnsupportedConnectorError


class ConnectorConfigurationError(UnsupportedConnectorError):
    """Raised when an optional DB adapter is missing required configuration."""


class ConnectorDependencyError(MissingConnectorDependency):
    """Raised when an optional DB adapter dependency cannot be imported."""


class OptionalDatabaseConnector:
    """Shared skeleton for optional DB adapters.

    Subclasses provide product-specific module names and dependency labels. The
    adapter remains non-operational until a validated scanner implementation is
    added later, so these methods only validate configuration and dependency
    availability before refusing to fake a successful scan.
    """

    product_name = "database"
    driver_module = ""
    dependency_name = ""

    def __init__(self, connection_string: str | None = None, **settings: Any) -> None:
        self.connection_string = connection_string
        self.settings = settings
        self._driver = None
        # Validate eagerly so missing configuration/dependency errors surface
        # before any code can mistake the adapter for a usable scanner.
        self._require_configuration()
        self._require_dependency()

    def connect(self) -> None:
        self._require_configuration()
        self._require_dependency()
        raise UnsupportedConnectorError(
            f"{self.product_name} adapter skeleton is installed, but live scanning is intentionally disabled until a vetted fixture is available."
        )

    def list_schemas(self) -> list[dict[str, Any]]:
        self._require_ready("schema listing")
        raise UnsupportedConnectorError(self._not_available("schema listing"))

    def list_tables(
        self,
        *,
        schema: str | None = None,
        table_allowlist: Iterable[str] | None = None,
        include_views: bool = False,
        include_materialized_views: bool = False,
    ) -> list[dict[str, Any]]:
        self._require_configuration()
        self._require_dependency()
        allowlist = None if table_allowlist is None else list(table_allowlist)
        raise UnsupportedConnectorError(
            self._not_available(
                "table listing",
                details=(
                    f"schema={schema!r}, allowlist={allowlist!r}, "
                    f"include_views={include_views}, include_materialized_views={include_materialized_views}"
                ),
            )
        )

    def list_columns(self, table_name: str, *, schema: str | None = None) -> list[dict[str, Any]]:
        self._require_ready("column listing")
        raise UnsupportedConnectorError(
            self._not_available("column listing", details=f"schema={schema!r}, table_name={table_name!r}")
        )

    def sample_rows(
        self,
        table_name: str,
        *,
        schema: str | None = None,
        max_rows: int = 5,
    ) -> list[dict[str, Any]]:
        self._require_ready("row sampling")
        raise UnsupportedConnectorError(
            self._not_available(
                "row sampling",
                details=f"schema={schema!r}, table_name={table_name!r}, max_rows={max_rows}",
            )
        )

    def profile_column(
        self,
        table_name: str,
        column_name: str,
        *,
        schema: str | None = None,
        low_cardinality_threshold: int = 50,
    ) -> dict[str, Any]:
        self._require_ready("column profiling")
        raise UnsupportedConnectorError(
            self._not_available(
                "column profiling",
                details=(
                    f"schema={schema!r}, table_name={table_name!r}, column_name={column_name!r}, "
                    f"low_cardinality_threshold={low_cardinality_threshold}"
                ),
            )
        )

    def close(self) -> None:
        self._driver = None

    def _require_configuration(self) -> None:
        if not self.connection_string or not str(self.connection_string).strip():
            raise ConnectorConfigurationError(
                f"{self.product_name} connector is not configured; provide a non-empty connection string before scanning."
            )

    def _require_dependency(self) -> None:
        if self._driver is not None:
            return
        try:
            self._driver = importlib.import_module(self.driver_module)
        except ModuleNotFoundError as exc:
            raise ConnectorDependencyError(
                f"{self.product_name} input requires optional dependency {self.dependency_name!r}. Install it or skip {self.product_name} sources explicitly."
            ) from exc

    def _require_ready(self, action: str) -> None:
        self._require_configuration()
        self._require_dependency()
        raise UnsupportedConnectorError(self._not_available(action))

    def _not_available(self, action: str, *, details: str | None = None) -> str:
        message = (
            f"{self.product_name} adapter skeleton does not support {action} in Phase 10; "
            "it refuses to fake success for a live database scan."
        )
        if details:
            message = f"{message} ({details})"
        return message
