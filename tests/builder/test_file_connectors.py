from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[2]
LOCAL_SUPERSTORE_XLS = REPO_ROOT / "docs" / "reference" / "test_datasets" / "tableau_superstore" / "Sample - Superstore.xls"
BUILDER_SRC = REPO_ROOT / "packages" / "semantic_builder" / "src"
if str(BUILDER_SRC) not in sys.path:
    sys.path.insert(0, str(BUILDER_SRC))

from semantic_builder.connectors import (  # noqa: E402
    MissingConnectorDependency,
    UnsupportedFileType,
    load_file,
    load_file_datasets,
    scan_source,
)


class FileConnectorTests(unittest.TestCase):
    def test_scan_demo_data_loads_csv_json_and_xlsx_tables(self) -> None:
        datasets = scan_source(REPO_ROOT / "examples" / "demo_data")
        by_name = {dataset.table_name: dataset for dataset in datasets}

        self.assertEqual({"payments", "subscriptions", "users"}, set(by_name))
        self.assertEqual("csv", by_name["users"].file_format)
        self.assertEqual(("user_id", "email", "signup_date", "country", "marketing_channel"), by_name["users"].columns)
        self.assertEqual(4, by_name["users"].row_count)
        self.assertEqual("json", by_name["payments"].file_format)
        self.assertIn("amount", by_name["payments"].columns)
        self.assertEqual(4, by_name["payments"].row_count)
        self.assertEqual("xlsx", by_name["subscriptions"].file_format)
        self.assertEqual(
            ("subscription_id", "user_id", "plan", "started_at", "monthly_amount", "status"),
            by_name["subscriptions"].columns,
        )
        self.assertEqual(4, by_name["subscriptions"].row_count)

    def test_xlsx_file_is_loaded_when_openpyxl_is_available(self) -> None:
        dataset = load_file(REPO_ROOT / "examples" / "demo_data" / "subscriptions.xlsx")

        self.assertEqual("subscriptions", dataset.table_name)
        self.assertEqual("xlsx", dataset.file_format)
        self.assertEqual("pro", dataset.rows[0]["plan"])
        self.assertEqual(49.0, dataset.rows[0]["monthly_amount"])

    def test_xls_superstore_file_is_loaded_when_xlrd_is_available(self) -> None:
        if not LOCAL_SUPERSTORE_XLS.exists():
            self.skipTest(f"local-only Superstore XLS is not tracked in git: {LOCAL_SUPERSTORE_XLS}")
        dataset = load_file(LOCAL_SUPERSTORE_XLS)

        self.assertEqual("sample_superstore_orders", dataset.table_name)
        self.assertEqual("Orders", dataset.sheet_name)
        self.assertEqual("xls", dataset.file_format)
        self.assertEqual(10194, dataset.row_count)
        self.assertIn("Order ID", dataset.columns)
        self.assertIn("Customer Name", dataset.columns)
        self.assertIn("Sales", dataset.columns)
        self.assertEqual("US-2022-103800", dataset.rows[0]["Order ID"])

    def test_xls_superstore_scans_all_non_empty_sheets_with_metadata(self) -> None:
        if not LOCAL_SUPERSTORE_XLS.exists():
            self.skipTest(f"local-only Superstore XLS is not tracked in git: {LOCAL_SUPERSTORE_XLS}")
        datasets = load_file_datasets(LOCAL_SUPERSTORE_XLS)
        by_name = {dataset.table_name: dataset for dataset in datasets}

        self.assertEqual({"sample_superstore_orders", "sample_superstore_people", "sample_superstore_returns"}, set(by_name))
        self.assertEqual("Orders", by_name["sample_superstore_orders"].sheet_name)
        self.assertEqual("People", by_name["sample_superstore_people"].sheet_name)
        self.assertEqual("Returns", by_name["sample_superstore_returns"].sheet_name)
        self.assertEqual(4, by_name["sample_superstore_people"].row_count)
        scan_record = by_name["sample_superstore_returns"].to_scan_record()
        self.assertEqual("Returns", scan_record["sheet_name"])
        self.assertEqual("sample_superstore_returns", scan_record["table_name"])

    def test_json_object_with_single_list_is_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "orders.json"
            path.write_text('{"records":[{"id":1,"status":"new"}]}', encoding="utf-8")

            dataset = load_file(path)

        self.assertEqual("orders", dataset.table_name)
        self.assertEqual(("id", "status"), dataset.columns)
        self.assertEqual(1, dataset.row_count)

    def test_jsonl_blank_lines_are_ignored_and_columns_remain_stable(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "events.jsonl"
            path.write_text(
                '{"event_id":"e1","status":"new"}\n\n{"event_id":"e2","status":"done","amount":10}\n',
                encoding="utf-8",
            )

            dataset = load_file(path)

        self.assertEqual("events", dataset.table_name)
        self.assertEqual("jsonl", dataset.file_format)
        self.assertEqual(("event_id", "status", "amount"), dataset.columns)
        self.assertEqual(2, dataset.row_count)

    def test_jsonl_non_object_record_is_rejected_explicitly(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "events.jsonl"
            path.write_text('{"event_id":"e1"}\n["not", "an", "object"]\n', encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "JSONL record .* must be an object"):
                load_file(path)

    def test_xlsx_missing_dependency_is_explicit(self) -> None:
        # Optional XLSX support must fail loudly instead of silently faking spreadsheet reads.
        with patch("semantic_builder.connectors.files.importlib.import_module", side_effect=ModuleNotFoundError("openpyxl")):
            with self.assertRaisesRegex(MissingConnectorDependency, "openpyxl"):
                load_file(Path("demo.xlsx"))

    def test_xls_missing_dependency_is_explicit(self) -> None:
        # Legacy XLS support must also fail loudly instead of pretending Superstore coverage.
        with patch("semantic_builder.connectors.files.importlib.import_module", side_effect=ModuleNotFoundError("xlrd")):
            with self.assertRaisesRegex(MissingConnectorDependency, "xlrd"):
                load_file(Path("demo.xls"))

    def test_unsupported_source_type_rejects_db_like_inputs(self) -> None:
        # Phase 4 is file-only: no DB connectors, credentials, or execute_query path belong here.
        with self.assertRaisesRegex(UnsupportedFileType, "CSV, JSON, JSONL, XLS, and XLSX"):
            load_file(Path("warehouse.postgresql"))


if __name__ == "__main__":
    unittest.main()
