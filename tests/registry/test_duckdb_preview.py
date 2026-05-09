from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "semantic_registry"))

from semantic_registry.execution import LocalPreviewAdapter  # noqa: E402


class LocalPreviewAdapterTest(unittest.TestCase):
    def test_registers_demo_csv_and_json_sources(self) -> None:
        adapter = LocalPreviewAdapter.from_demo_dir(ROOT / "examples" / "demo_data", max_rows=10)

        result = adapter.preview("SELECT user_id, country FROM users ORDER BY user_id")

        self.assertEqual(result.registered_tables, ["payments", "users"])
        self.assertIn("subscriptions.xlsx", result.skipped_sources)
        self.assertEqual(result.columns, ["user_id", "country"])
        self.assertEqual(result.row_count, 4)
        self.assertEqual(result.returned_count, 4)
        self.assertFalse(result.truncated)

    def test_applies_preview_limit_and_reports_truncation(self) -> None:
        adapter = LocalPreviewAdapter.from_demo_dir(ROOT / "examples" / "demo_data", max_rows=2)

        result = adapter.preview("SELECT payment_id, amount FROM payments ORDER BY payment_id")

        self.assertEqual(result.applied_limit, 2)
        self.assertEqual(result.row_count, 4)
        self.assertEqual(result.returned_count, 2)
        self.assertTrue(result.truncated)
        self.assertEqual([row["payment_id"] for row in result.rows], ["p001", "p002"])


    def test_empty_result_preserves_column_metadata(self) -> None:
        adapter = LocalPreviewAdapter.from_demo_dir(ROOT / "examples" / "demo_data", max_rows=10)

        result = adapter.preview("SELECT user_id, country FROM users WHERE country = 'ZZ'")

        self.assertEqual(result.columns, ["user_id", "country"])
        self.assertEqual(result.row_count, 0)
        self.assertEqual(result.returned_count, 0)
        self.assertFalse(result.truncated)

    def test_respects_smaller_sql_limit(self) -> None:
        adapter = LocalPreviewAdapter.from_demo_dir(ROOT / "examples" / "demo_data", max_rows=10)

        result = adapter.preview("SELECT user_id FROM users ORDER BY user_id LIMIT 1")

        self.assertEqual(result.applied_limit, 1)
        self.assertEqual(result.row_count, 1)
        self.assertEqual(result.returned_count, 1)
        self.assertFalse(result.truncated)
        self.assertEqual(result.rows, [{"user_id": "u001"}])

    def test_rejects_non_select_and_multi_statement_preview_sql(self) -> None:
        adapter = LocalPreviewAdapter.from_demo_dir(ROOT / "examples" / "demo_data")

        with self.assertRaisesRegex(ValueError, "SELECT/WITH"):
            adapter.preview("DELETE FROM users")
        with self.assertRaisesRegex(ValueError, "single statement"):
            adapter.preview("SELECT user_id FROM users; SELECT payment_id FROM payments")


if __name__ == "__main__":
    unittest.main()
