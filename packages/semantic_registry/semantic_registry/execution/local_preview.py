"""File-backed local preview adapter for Phase 9 demo data.

This module is intentionally scoped to local/demo preview. It never opens an
external database and exposes no production query runner;
callers must run SQL guard/policy validation before invoking the adapter.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
import json
from pathlib import Path
import re
import sqlite3
from typing import Any


@dataclass(frozen=True)
class DemoTable:
    name: str
    source_path: Path
    columns: tuple[str, ...]
    rows: tuple[dict[str, Any], ...]


@dataclass(frozen=True)
class DemoDataRegistry:
    """Table registry built from local CSV/JSON fixtures.

    XLSX is deliberately not parsed here to avoid adding runtime dependencies in
    the preview lane; unsupported files are recorded so callers can report the
    limitation instead of silently pretending the source was registered.
    """

    tables: dict[str, DemoTable] = field(default_factory=dict)
    skipped_sources: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_demo_dir(cls, demo_dir: str | Path) -> "DemoDataRegistry":
        root = Path(demo_dir)
        tables: dict[str, DemoTable] = {}
        skipped: dict[str, str] = {}
        for path in sorted(root.iterdir() if root.exists() else []):
            if not path.is_file():
                continue
            table_name = _safe_table_name(path.stem)
            try:
                if path.suffix.casefold() == ".csv":
                    tables[table_name] = _load_csv_table(table_name, path)
                elif path.suffix.casefold() == ".json":
                    tables[table_name] = _load_json_table(table_name, path)
                else:
                    skipped[path.name] = f"unsupported preview fixture type: {path.suffix}"
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                skipped[path.name] = str(exc)
        return cls(tables=tables, skipped_sources=skipped)


@dataclass(frozen=True)
class PreviewResult:
    columns: list[str]
    rows: list[dict[str, Any]]
    row_count: int
    returned_count: int
    truncated: bool
    applied_limit: int
    registered_tables: list[str]
    skipped_sources: dict[str, str] = field(default_factory=dict)


class LocalPreviewAdapter:
    """Run bounded SELECT previews over registered local fixture files only."""

    def __init__(self, registry: DemoDataRegistry, *, max_rows: int = 50) -> None:
        if max_rows < 1:
            raise ValueError("max_rows must be positive")
        self.registry = registry
        self.max_rows = max_rows

    @classmethod
    def from_demo_dir(cls, demo_dir: str | Path, *, max_rows: int = 50) -> "LocalPreviewAdapter":
        return cls(DemoDataRegistry.from_demo_dir(demo_dir), max_rows=max_rows)

    def preview(self, sql: str, *, limit: int | None = None) -> PreviewResult:
        """Return rows/columns/count for a bounded local SELECT preview.

        This adapter is a final local preview step, not a safety gate. It still
        rejects non-SELECT and multi-statement SQL as defense-in-depth, but PII
        and role policy checks belong to the SQL guard/audit lane.
        """

        requested_limit = self.max_rows if limit is None else min(_positive_limit(limit), self.max_rows)
        normalized = _normalize_preview_sql(sql)
        base_sql, sql_limit = _split_final_limit(normalized)
        effective_limit = min(requested_limit, sql_limit) if sql_limit is not None else requested_limit
        probe_limit = effective_limit if sql_limit is not None and sql_limit <= effective_limit else effective_limit + 1
        count_sql = _count_sql(base_sql, sql_limit)
        preview_sql = f"SELECT * FROM ({base_sql}) AS _preview_rows LIMIT {probe_limit}"

        # sqlite3's context manager does not close the connection; close
        # explicitly so local preview verification remains warning-free.
        connection = sqlite3.connect(":memory:")
        connection.row_factory = sqlite3.Row
        try:
            self._register_tables(connection)
            count_cursor = connection.execute(count_sql)
            try:
                row_count = int(count_cursor.fetchone()[0])
            finally:
                count_cursor.close()
            cursor = connection.execute(preview_sql)
            try:
                fetched = cursor.fetchall()
                cursor_columns = [description[0] for description in (cursor.description or [])]
            finally:
                cursor.close()
        finally:
            connection.close()

        truncated = len(fetched) > effective_limit or row_count > effective_limit
        visible = fetched[:effective_limit]
        columns = cursor_columns or _columns_from_cursorless_sql(base_sql, self.registry.tables)
        rows = [{column: row[column] for column in row.keys()} for row in visible]
        return PreviewResult(
            columns=columns,
            rows=rows,
            row_count=row_count,
            returned_count=len(rows),
            truncated=truncated,
            applied_limit=effective_limit,
            registered_tables=sorted(self.registry.tables),
            skipped_sources=dict(self.registry.skipped_sources),
        )

    def _register_tables(self, connection: sqlite3.Connection) -> None:
        for table in self.registry.tables.values():
            quoted_table = _quote_identifier(table.name)
            column_defs = ", ".join(f"{_quote_identifier(column)} TEXT" for column in table.columns)
            connection.execute(f"CREATE TABLE {quoted_table} ({column_defs})")
            if not table.rows:
                continue
            placeholders = ", ".join("?" for _ in table.columns)
            column_list = ", ".join(_quote_identifier(column) for column in table.columns)
            values = [[_to_sqlite_value(row.get(column)) for column in table.columns] for row in table.rows]
            connection.executemany(f"INSERT INTO {quoted_table} ({column_list}) VALUES ({placeholders})", values)


def _load_csv_table(table_name: str, path: Path) -> DemoTable:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        columns = tuple(_safe_column_name(column) for column in (reader.fieldnames or ()))
        rows = tuple({_safe_column_name(key): value for key, value in row.items()} for row in reader)
    if not columns:
        raise ValueError("CSV preview source has no header")
    return DemoTable(name=table_name, source_path=path, columns=columns, rows=rows)


def _load_json_table(table_name: str, path: Path) -> DemoTable:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list) or not all(isinstance(item, dict) for item in payload):
        raise ValueError("JSON preview source must be a list of objects")
    columns = tuple(dict.fromkeys(str(key) for row in payload for key in row.keys()))
    if not columns:
        raise ValueError("JSON preview source has no object columns")
    rows = tuple({column: row.get(column) for column in columns} for row in payload)
    return DemoTable(name=table_name, source_path=path, columns=columns, rows=rows)


def _normalize_preview_sql(sql: str) -> str:
    stripped = sql.strip().rstrip(";").strip()
    if not stripped:
        raise ValueError("preview SQL must be non-empty")
    # Defense-in-depth only: policy/PII validation is performed before preview.
    if ";" in _strip_string_literals(stripped):
        raise ValueError("preview SQL must contain a single statement")
    if not re.match(r"(?is)^\s*(select|with)\b", stripped):
        raise ValueError("preview SQL must be a SELECT/WITH statement")
    return stripped


def _split_final_limit(sql: str) -> tuple[str, int | None]:
    match = re.search(r"(?is)\s+limit\s+(\d+)\s*$", sql)
    if match is None:
        return sql, None
    return sql[: match.start()].strip(), int(match.group(1))


def _count_sql(base_sql: str, sql_limit: int | None) -> str:
    limited = f"{base_sql} LIMIT {sql_limit}" if sql_limit is not None else base_sql
    return f"SELECT COUNT(*) FROM ({limited}) AS _preview_count"


def _columns_from_cursorless_sql(base_sql: str, tables: dict[str, DemoTable]) -> list[str]:
    # Empty result sets still need stable column metadata for simple table scans.
    match = re.search(r"(?is)^\s*select\s+\*\s+from\s+([a-zA-Z_][\w]*)\b", base_sql)
    if match and match.group(1) in tables:
        return list(tables[match.group(1)].columns)
    return []


def _strip_string_literals(sql: str) -> str:
    return re.sub(r"'(?:''|[^'])*'|\"(?:\"\"|[^\"])*\"", "''", sql)


def _positive_limit(value: int) -> int:
    if value < 1:
        raise ValueError("limit must be positive")
    return value


def _safe_table_name(name: str) -> str:
    safe = re.sub(r"\W+", "_", name.strip().casefold()).strip("_")
    if not safe or not re.match(r"^[a-z_]", safe):
        safe = f"table_{safe}"
    return safe


def _safe_column_name(name: str) -> str:
    safe = re.sub(r"\W+", "_", str(name).strip()).strip("_")
    if not safe or not re.match(r"^[A-Za-z_]", safe):
        safe = f"column_{safe}"
    return safe


def _quote_identifier(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def _to_sqlite_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (str, int, float)):
        return value
    return str(value)
