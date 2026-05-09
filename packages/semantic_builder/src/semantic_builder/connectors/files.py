"""Local file connectors for Phase 4 Semantic Builder.

This module intentionally reads only local CSV/JSON/XLS/XLSX files. DB connector
contracts live in :mod:`semantic_builder.connectors.db`, so this file remains
file-only and must not grow any networked or SQL-executing behavior.
"""

from __future__ import annotations

import csv
import importlib
import itertools
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

from .db import MissingConnectorDependency

SUPPORTED_SUFFIXES = {".csv", ".json", ".jsonl", ".xls", ".xlsx"}


class UnsupportedFileType(ValueError):
    """Raised when a file source is outside the Phase 4 file-only scope."""


@dataclass(frozen=True)
class FileDataset:
    """In-memory table-shaped view of one local demo data file or workbook sheet."""

    path: Path
    table_name: str
    file_format: str
    columns: tuple[str, ...]
    rows: tuple[dict[str, Any], ...]
    sheet_name: str | None = None

    @property
    def row_count(self) -> int:
        return len(self.rows)

    def to_scan_record(self) -> dict[str, Any]:
        """Return a JSON-serializable scan summary for downstream workers."""
        record = {
            "source_type": "file",
            "path": str(self.path),
            "table_name": self.table_name,
            "format": self.file_format,
            "columns": list(self.columns),
            "row_count": self.row_count,
        }
        if self.sheet_name is not None:
            # Sheet metadata lets the profile CLI re-load the exact worksheet
            # instead of accidentally profiling every sheet for every scan row.
            record["sheet_name"] = self.sheet_name
        return record


def scan_source(source: str | Path) -> list[FileDataset]:
    """Scan a file or directory and load supported local file datasets."""
    source_path = Path(source)
    if source_path.is_dir():
        files = sorted(
            path
            for path in source_path.rglob("*")
            if path.is_file() and path.suffix.lower() in SUPPORTED_SUFFIXES
        )
    else:
        files = [source_path]
    datasets: list[FileDataset] = []
    for path in files:
        datasets.extend(load_file_datasets(path))
    return datasets


def load_file(path: str | Path) -> FileDataset:
    """Load a supported local file as a deterministic primary dataset.

    Multi-sheet Excel workbooks are fully exposed through scan_source() and
    load_file_datasets().  This compatibility wrapper returns the first
    non-empty worksheet so older single-table callers keep working.
    """
    datasets = load_file_datasets(path)
    if not datasets:
        file_path = Path(path)
        suffix = file_path.suffix.lower()
        return FileDataset(
            path=file_path,
            table_name=_table_name_from_path(file_path),
            file_format=suffix.removeprefix("."),
            columns=(),
            rows=(),
        )
    return datasets[0]


def load_file_datasets(path: str | Path) -> list[FileDataset]:
    """Load all table datasets represented by one supported local file."""
    file_path = Path(path)
    suffix = file_path.suffix.lower()
    file_format = suffix.removeprefix(".")
    if suffix == ".csv":
        rows = _read_csv(file_path)
        return [_dataset_from_rows(file_path, _table_name_from_path(file_path), file_format, rows)]
    if suffix == ".json":
        rows = _read_json(file_path)
        return [_dataset_from_rows(file_path, _table_name_from_path(file_path), file_format, rows)]
    if suffix == ".jsonl":
        rows = _read_jsonl(file_path)
        return [_dataset_from_rows(file_path, _table_name_from_path(file_path), file_format, rows)]
    if suffix == ".xls":
        return _read_xls_datasets(file_path)
    if suffix == ".xlsx":
        return _read_xlsx_datasets(file_path)
    raise UnsupportedFileType(
        f"Unsupported file type {suffix!r}; Phase 4 supports CSV, JSON, JSONL, XLS, and XLSX only."
    )


def _dataset_from_rows(
    path: Path,
    table_name: str,
    file_format: str,
    rows: Sequence[dict[str, Any]],
    *,
    sheet_name: str | None = None,
) -> FileDataset:
    return FileDataset(
        path=path,
        table_name=table_name,
        file_format=file_format,
        columns=_columns_from_rows(rows),
        rows=tuple(rows),
        sheet_name=sheet_name,
    )


def _read_csv(path: Path) -> list[dict[str, Any]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _read_json(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    return _records_from_json_payload(payload, path)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            record = json.loads(line)
            if not isinstance(record, dict):
                raise ValueError(f"JSONL record at {path}:{line_number} must be an object")
            rows.append(dict(record))
    return rows


def _read_xlsx(path: Path) -> list[dict[str, Any]]:
    """Compatibility helper returning the primary XLSX worksheet rows."""
    datasets = _read_xlsx_datasets(path)
    return list(datasets[0].rows) if datasets else []


def _read_xlsx_datasets(path: Path) -> list[FileDataset]:
    # XLSX is optional to keep the MVP lightweight; failures are explicit so we
    # never pretend spreadsheet coverage passed when openpyxl is unavailable.
    try:
        openpyxl = importlib.import_module("openpyxl")
    except ModuleNotFoundError as exc:
        raise MissingConnectorDependency(
            "XLSX input requires optional dependency 'openpyxl'. Install it or skip XLSX sources explicitly."
        ) from exc

    workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        sheet_rows: list[tuple[str, list[dict[str, Any]]]] = []
        for worksheet in workbook.worksheets:
            rows = _rows_from_values(worksheet.iter_rows(values_only=True))
            if rows:
                sheet_rows.append((str(worksheet.title), rows))
        return _excel_datasets_from_sheet_rows(path, "xlsx", sheet_rows)
    finally:
        workbook.close()


def _read_xls(path: Path) -> list[dict[str, Any]]:
    """Compatibility helper returning the primary XLS worksheet rows."""
    datasets = _read_xls_datasets(path)
    return list(datasets[0].rows) if datasets else []


def _read_xls_datasets(path: Path) -> list[FileDataset]:
    # Legacy .xls support is required for Tableau Sample Superstore validation.
    # Keep the dependency explicit so we do not silently skip or fake legacy
    # workbook coverage when xlrd is missing.
    try:
        xlrd = importlib.import_module("xlrd")
    except ModuleNotFoundError as exc:
        raise MissingConnectorDependency(
            "XLS input requires optional dependency 'xlrd'. Install it or skip XLS sources explicitly."
        ) from exc

    workbook = xlrd.open_workbook(str(path), on_demand=True)
    try:
        sheet_rows: list[tuple[str, list[dict[str, Any]]]] = []
        for worksheet in workbook.sheets():
            if worksheet.nrows == 0:
                continue
            header_row = worksheet.row_values(0)
            value_rows = (
                [
                    _xls_cell_value(xlrd, cell, workbook.datemode)
                    for cell in worksheet.row(row_index)
                ]
                for row_index in range(1, worksheet.nrows)
            )
            rows = _rows_from_values(itertools.chain((header_row,), value_rows))
            if rows:
                sheet_rows.append((str(worksheet.name), rows))
        return _excel_datasets_from_sheet_rows(path, "xls", sheet_rows)
    finally:
        workbook.release_resources()


def _rows_from_values(values_iter: Iterable[Sequence[Any]]) -> list[dict[str, Any]]:
    """Convert worksheet values into rows, skipping sheets with no data rows.

    The first row is treated as the header to keep Phase 4 deterministic and
    local-only; there is no heuristic table detection or hidden SQL execution.
    """
    iterator = iter(values_iter)
    for header_row in iterator:
        if _row_has_value(header_row):
            break
    else:
        return []
    headers = [_normalize_header(value, index) for index, value in enumerate(header_row)]
    rows: list[dict[str, Any]] = []
    for values in iterator:
        if not _row_has_value(values):
            continue
        rows.append({header: value for header, value in zip(headers, values)})
    return rows


def _row_has_value(values: Sequence[Any]) -> bool:
    return any(value is not None and str(value).strip() != "" for value in values)


def _excel_datasets_from_sheet_rows(
    path: Path, file_format: str, sheet_rows: Sequence[tuple[str, list[dict[str, Any]]]]
) -> list[FileDataset]:
    workbook_name = _table_name_from_path(path)
    multiple_sheets = len(sheet_rows) > 1
    used_names: dict[str, int] = {}
    datasets: list[FileDataset] = []
    for sheet_name, rows in sheet_rows:
        base_name = workbook_name
        if multiple_sheets:
            base_name = f"{workbook_name}_{_safe_table_token(sheet_name)}"
        table_name = _dedupe_table_name(base_name, used_names)
        datasets.append(
            _dataset_from_rows(
                path,
                table_name,
                file_format,
                rows,
                sheet_name=sheet_name,
            )
        )
    return datasets


def _dedupe_table_name(table_name: str, used_names: dict[str, int]) -> str:
    count = used_names.get(table_name, 0) + 1
    used_names[table_name] = count
    if count == 1:
        return table_name
    return f"{table_name}_{count}"


def _xls_cell_value(xlrd: Any, cell: Any, datemode: int) -> Any:
    if cell.ctype == xlrd.XL_CELL_EMPTY:
        return None
    if cell.ctype == xlrd.XL_CELL_DATE:
        try:
            value = xlrd.xldate.xldate_as_datetime(cell.value, datemode)
        except Exception:
            # Preserve the raw numeric serial only when xlrd itself cannot
            # decode it; this fallback is explicit and still local/read-only.
            return cell.value
        if value.time().isoformat() == "00:00:00":
            return value.date().isoformat()
        return value.isoformat()
    if cell.ctype == xlrd.XL_CELL_BOOLEAN:
        return bool(cell.value)
    if cell.ctype == xlrd.XL_CELL_NUMBER and float(cell.value).is_integer():
        return int(cell.value)
    return cell.value


def _records_from_json_payload(payload: Any, path: Path) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        records = payload
    elif isinstance(payload, dict):
        list_values = [value for value in payload.values() if isinstance(value, list)]
        if len(list_values) != 1:
            raise ValueError(
                f"JSON file {path} must contain a list of objects or exactly one top-level list value"
            )
        records = list_values[0]
    else:
        raise ValueError(f"JSON file {path} must contain table-shaped objects")

    if not all(isinstance(record, dict) for record in records):
        raise ValueError(f"JSON file {path} must contain only object records")
    return [dict(record) for record in records]


def _columns_from_rows(rows: Sequence[dict[str, Any]]) -> tuple[str, ...]:
    columns: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for column in row:
            if column not in seen:
                seen.add(column)
                columns.append(column)
    return tuple(columns)


def _normalize_header(value: Any, index: int) -> str:
    if value is None or str(value).strip() == "":
        return f"column_{index + 1}"
    return str(value).strip()


def _table_name_from_path(path: Path) -> str:
    # Keep generated table names deterministic and shell/path safe for draft packs.
    return _safe_table_token(path.stem)


def _safe_table_token(value: str) -> str:
    token = re.sub(r"[^0-9A-Za-z_]+", "_", value.strip().lower()).strip("_")
    return token or "table"
