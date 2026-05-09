"""Safe local preview query execution for demo datasets only.

Phase 9 permits a narrow ``preview_query`` capability. This module validates SQL
with the Semantic Pack guard before any local execution, runs only against files
under ``examples/demo_data`` (or an explicitly supplied local data root), and
records an audit entry for both successful and failed previews. It deliberately
has no production database connector and no production query-runner alias.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import time
from typing import Any, Iterable
from uuid import uuid4

from semantic_contracts import SqlGuardResult
from semantic_registry.sql_guard import validate_sql
from semantic_registry.store import DEFAULT_PACK_ROOT

_DEFAULT_DATA_ROOT = Path("examples") / "demo_data"
_DEFAULT_MAX_ROWS = 100
_DEFAULT_TIMEOUT_MS = 1_000


@dataclass(frozen=True)
class PreviewRequest:
    """Input envelope for a local preview.

    ``validation_id`` is optional because this service can validate internally;
    the preview still fails closed when validation errors are found. Paths are
    local roots, not credentials or remote connection strings.
    """

    sql: str
    space_id: str = "demo_company.revenue"
    user_role: str | None = None
    pack_root: str | Path = DEFAULT_PACK_ROOT
    data_root: str | Path = _DEFAULT_DATA_ROOT
    max_rows: int = _DEFAULT_MAX_ROWS
    timeout_ms: int = _DEFAULT_TIMEOUT_MS
    validation_id: str | None = None


@dataclass(frozen=True)
class PreviewAuditRecord:
    """PII-safe audit metadata for one preview attempt.

    The audit stores a SQL fingerprint instead of raw SQL so failed previews can
    be traced without logging literal values or sensitive projections.
    """

    audit_id: str
    created_at: str
    space_id: str
    user_role: str | None
    validation_id: str
    ok: bool
    sql_fingerprint: str
    row_count: int = 0
    truncated: bool = False
    failure_reason: str | None = None
    referenced_tables: list[str] = field(default_factory=list)
    referenced_columns: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class PreviewResult:
    """Structured preview response returned to MCP/tool layers."""

    ok: bool
    audit_id: str
    columns: list[str] = field(default_factory=list)
    rows: list[dict[str, Any]] = field(default_factory=list)
    row_count: int = 0
    truncated: bool = False
    validation: SqlGuardResult | None = None
    error: str | None = None


class InMemoryPreviewAuditLog:
    """Simple append-only audit sink for tests and local previews.

    Production audit storage is outside Phase 9; this sink makes the safety
    contract executable without introducing a service, database, or network
    dependency.
    """

    def __init__(self) -> None:
        self.records: list[PreviewAuditRecord] = []

    def append(self, record: PreviewAuditRecord) -> PreviewAuditRecord:
        self.records.append(record)
        return record


class SafePreviewEngine:
    """Validate and preview SELECT SQL against local demo files only."""

    def __init__(self, audit_log: InMemoryPreviewAuditLog | None = None) -> None:
        self.audit_log = audit_log or InMemoryPreviewAuditLog()

    def preview(self, request: PreviewRequest) -> PreviewResult:
        audit_id = f"preview-{uuid4()}"
        validation_id = request.validation_id or f"sql_guard:{_sql_fingerprint(request.sql)[:12]}"
        validation: SqlGuardResult | None = None
        started = time.monotonic()

        try:
            _validate_request_limits(request)
            validation = validate_sql(
                request.sql,
                space_id=request.space_id,
                role=request.user_role,
                pack_root=request.pack_root,
            )
            if not validation.valid:
                return self._failure_result(
                    audit_id=audit_id,
                    request=request,
                    validation_id=validation_id,
                    validation=validation,
                    failure_reason="; ".join(validation.errors) or "SQL validation failed before preview.",
                )

            rows, columns, truncated = self._execute_local_preview(request, started=started)
            row_count = len(rows)
            self._write_audit(
                audit_id=audit_id,
                request=request,
                validation_id=validation_id,
                ok=True,
                validation=validation,
                row_count=row_count,
                truncated=truncated,
            )
            return PreviewResult(
                ok=True,
                audit_id=audit_id,
                columns=columns,
                rows=rows,
                row_count=row_count,
                truncated=truncated,
                validation=validation,
            )
        except Exception as exc:  # noqa: BLE001 - failed previews must be audited, not leaked silently.
            return self._failure_result(
                audit_id=audit_id,
                request=request,
                validation_id=validation_id,
                validation=validation,
                failure_reason=str(exc),
            )

    def _execute_local_preview(self, request: PreviewRequest, *, started: float) -> tuple[list[dict[str, Any]], list[str], bool]:
        clean_sql = _single_statement_sql(request.sql)
        data_root = Path(request.data_root)
        if not data_root.exists():
            raise ValueError(f"Local preview data root does not exist: {data_root}")

        connection = sqlite3.connect(":memory:")
        connection.row_factory = sqlite3.Row
        try:
            _load_local_demo_tables(connection, data_root)
            deadline = started + (request.timeout_ms / 1000)

            def _timeout_guard() -> int:
                return 1 if time.monotonic() > deadline else 0

            # SQLite progress handler is the stdlib timeout guard available for
            # local previews; it avoids introducing DuckDB or external services.
            connection.set_progress_handler(_timeout_guard, 1_000)
            bounded_sql = f"SELECT * FROM ({clean_sql}) AS preview_subquery LIMIT {request.max_rows + 1}"
            cursor = connection.execute(bounded_sql)
            try:
                fetched = cursor.fetchall()
                columns = [description[0] for description in (cursor.description or [])]
            finally:
                cursor.close()
        finally:
            connection.close()

        truncated = len(fetched) > request.max_rows
        visible_rows = fetched[: request.max_rows]
        rows = [{column: row[column] for column in columns} for row in visible_rows]
        return rows, columns, truncated

    def _failure_result(
        self,
        *,
        audit_id: str,
        request: PreviewRequest,
        validation_id: str,
        validation: SqlGuardResult | None,
        failure_reason: str,
    ) -> PreviewResult:
        self._write_audit(
            audit_id=audit_id,
            request=request,
            validation_id=validation_id,
            ok=False,
            validation=validation,
            failure_reason=failure_reason,
        )
        return PreviewResult(ok=False, audit_id=audit_id, validation=validation, error=failure_reason)

    def _write_audit(
        self,
        *,
        audit_id: str,
        request: PreviewRequest,
        validation_id: str,
        ok: bool,
        validation: SqlGuardResult | None,
        row_count: int = 0,
        truncated: bool = False,
        failure_reason: str | None = None,
    ) -> None:
        referenced_tables = list(validation.referenced_tables) if validation is not None else []
        referenced_columns = list(validation.referenced_columns) if validation is not None else []
        self.audit_log.append(
            PreviewAuditRecord(
                audit_id=audit_id,
                created_at=datetime.now(UTC).isoformat(),
                space_id=request.space_id,
                user_role=request.user_role,
                validation_id=validation_id,
                ok=ok,
                sql_fingerprint=_sql_fingerprint(request.sql),
                row_count=row_count,
                truncated=truncated,
                failure_reason=failure_reason,
                referenced_tables=referenced_tables,
                referenced_columns=referenced_columns,
            )
        )


def preview_query(
    sql: str,
    *,
    space_id: str = "demo_company.revenue",
    user_role: str | None = None,
    pack_root: str | Path = DEFAULT_PACK_ROOT,
    data_root: str | Path = _DEFAULT_DATA_ROOT,
    max_rows: int = _DEFAULT_MAX_ROWS,
    timeout_ms: int = _DEFAULT_TIMEOUT_MS,
    audit_log: InMemoryPreviewAuditLog | None = None,
) -> PreviewResult:
    """Convenience local preview API; validates before touching demo data."""

    engine = SafePreviewEngine(audit_log=audit_log)
    return engine.preview(
        PreviewRequest(
            sql=sql,
            space_id=space_id,
            user_role=user_role,
            pack_root=pack_root,
            data_root=data_root,
            max_rows=max_rows,
            timeout_ms=timeout_ms,
        )
    )


def _validate_request_limits(request: PreviewRequest) -> None:
    if request.max_rows < 1:
        raise ValueError("max_rows must be at least 1")
    if request.timeout_ms < 1:
        raise ValueError("timeout_ms must be at least 1")


def _single_statement_sql(sql: str) -> str:
    stripped = sql.strip().rstrip(";").strip()
    if not stripped:
        raise ValueError("SQL must not be blank")
    return stripped


def _sql_fingerprint(sql: str) -> str:
    return hashlib.sha256(sql.encode("utf-8")).hexdigest()


def _load_local_demo_tables(connection: sqlite3.Connection, data_root: Path) -> None:
    loaded = False
    for csv_path in sorted(data_root.glob("*.csv")):
        _load_csv_table(connection, csv_path)
        loaded = True
    for json_path in sorted(data_root.glob("*.json")):
        _load_json_table(connection, json_path)
        loaded = True
    if not loaded:
        raise ValueError(f"No CSV/JSON demo data files found for local preview: {data_root}")


def _load_csv_table(connection: sqlite3.Connection, path: Path) -> None:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        columns = list(reader.fieldnames or [])
    _create_and_insert(connection, _safe_table_name(path), columns, rows)


def _load_json_table(connection: sqlite3.Connection, path: Path) -> None:
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, list):
        raise ValueError(f"JSON preview table must be a list of objects: {path}")
    rows = [row for row in payload if isinstance(row, dict)]
    columns = sorted({str(key) for row in rows for key in row})
    _create_and_insert(connection, _safe_table_name(path), columns, rows)


def _create_and_insert(connection: sqlite3.Connection, table_name: str, columns: list[str], rows: Iterable[dict[str, Any]]) -> None:
    if not columns:
        return
    quoted_columns = ", ".join(_quote_identifier(column) for column in columns)
    connection.execute(f"CREATE TABLE {_quote_identifier(table_name)} ({quoted_columns})")
    placeholders = ", ".join("?" for _ in columns)
    insert_sql = f"INSERT INTO {_quote_identifier(table_name)} ({quoted_columns}) VALUES ({placeholders})"
    connection.executemany(insert_sql, [[row.get(column) for column in columns] for row in rows])


def _safe_table_name(path: Path) -> str:
    table_name = path.stem
    if not re.match(r"^[A-Za-z_]\w*$", table_name):
        raise ValueError(f"Unsafe local preview table name: {table_name}")
    return table_name


def _quote_identifier(identifier: str) -> str:
    if not re.match(r"^[A-Za-z_]\w*$", identifier):
        raise ValueError(f"Unsafe local preview identifier: {identifier}")
    return f'"{identifier}"'
