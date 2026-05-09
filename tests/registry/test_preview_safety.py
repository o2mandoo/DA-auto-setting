from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "semantic_contracts"))
sys.path.insert(0, str(ROOT / "packages" / "semantic_registry"))

from semantic_registry.execution import InMemoryPreviewAuditLog, PreviewRequest, SafePreviewEngine  # noqa: E402


class PreviewSafetyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.audit_log = InMemoryPreviewAuditLog()
        self.engine = SafePreviewEngine(audit_log=self.audit_log)

    def _request(self, sql: str, *, max_rows: int = 2) -> PreviewRequest:
        return PreviewRequest(
            sql=sql,
            space_id="demo_company.revenue",
            user_role="marketing_analyst",
            pack_root=ROOT / "semantic_packs",
            data_root=ROOT / "examples" / "demo_data",
            max_rows=max_rows,
        )

    def test_multi_statement_sql_is_blocked_before_local_preview(self) -> None:
        result = self.engine.preview(self._request("SELECT payment_id FROM payments; SELECT user_id FROM users"))

        self.assertFalse(result.ok)
        self.assertIn("Multiple SQL statements", result.error or "")
        self.assertEqual(len(self.audit_log.records), 1)
        self.assertFalse(self.audit_log.records[0].ok)
        self.assertIn("Multiple SQL statements", self.audit_log.records[0].failure_reason or "")
        self.assertEqual([], result.rows)


    def test_dml_and_ddl_failures_are_audited_before_execution(self) -> None:
        for sql in ["DELETE FROM users", "DROP TABLE payments"]:
            with self.subTest(sql=sql):
                audit_log = InMemoryPreviewAuditLog()
                engine = SafePreviewEngine(audit_log=audit_log)

                result = engine.preview(self._request(sql))

                self.assertFalse(result.ok)
                self.assertIn("Non-SELECT SQL keywords are blocked", result.error or "")
                self.assertEqual(len(audit_log.records), 1)
                self.assertFalse(audit_log.records[0].ok)
                self.assertIn("Non-SELECT SQL keywords are blocked", audit_log.records[0].failure_reason or "")

    def test_invalid_max_rows_failure_is_audited(self) -> None:
        result = self.engine.preview(self._request("SELECT payment_id FROM payments", max_rows=0))

        self.assertFalse(result.ok)
        self.assertIn("max_rows must be at least 1", result.error or "")
        self.assertEqual(len(self.audit_log.records), 1)
        self.assertFalse(self.audit_log.records[0].ok)
        self.assertIn("max_rows must be at least 1", self.audit_log.records[0].failure_reason or "")

    def test_missing_data_root_failure_is_audited_after_validation(self) -> None:
        request = PreviewRequest(
            sql="SELECT payment_id FROM payments",
            space_id="demo_company.revenue",
            user_role="marketing_analyst",
            pack_root=ROOT / "semantic_packs",
            data_root=ROOT / "examples" / "demo_data" / "missing",
            max_rows=2,
        )

        result = self.engine.preview(request)

        self.assertFalse(result.ok)
        self.assertIn("Local preview data root does not exist", result.error or "")
        self.assertEqual(len(self.audit_log.records), 1)
        record = self.audit_log.records[0]
        self.assertFalse(record.ok)
        self.assertIn("Local preview data root does not exist", record.failure_reason or "")
        self.assertIn("payments", record.referenced_tables)

    def test_audit_fingerprints_sql_without_storing_raw_sql(self) -> None:
        sql = "SELECT payment_id, amount FROM payments ORDER BY payment_id"
        result = self.engine.preview(self._request(sql, max_rows=2))

        self.assertTrue(result.ok, result.error)
        record = self.audit_log.records[0]
        self.assertFalse(hasattr(record, "sql"))
        self.assertNotEqual(sql, record.sql_fingerprint)
        self.assertRegex(record.sql_fingerprint, r"^[0-9a-f]{64}$")
        self.assertNotIn(sql, record.__dict__.values())

    def test_successful_preview_writes_audit_record(self) -> None:
        result = self.engine.preview(self._request("SELECT payment_id, amount FROM payments ORDER BY payment_id", max_rows=2))

        self.assertTrue(result.ok, result.error)
        self.assertEqual(["payment_id", "amount"], result.columns)
        self.assertEqual(2, result.row_count)
        self.assertTrue(result.truncated)
        self.assertEqual(len(self.audit_log.records), 1)
        record = self.audit_log.records[0]
        self.assertTrue(record.ok)
        self.assertEqual(result.audit_id, record.audit_id)
        self.assertEqual(2, record.row_count)
        self.assertTrue(record.truncated)
        self.assertIsNone(record.failure_reason)
        self.assertEqual("demo_company.revenue", record.space_id)
        self.assertEqual("marketing_analyst", record.user_role)

    def test_failed_preview_writes_failure_reason_to_audit(self) -> None:
        result = self.engine.preview(self._request("SELECT users.email FROM users"))

        self.assertFalse(result.ok)
        self.assertIn("Blocked columns referenced: users.email", result.error or "")
        self.assertEqual(len(self.audit_log.records), 1)
        record = self.audit_log.records[0]
        self.assertFalse(record.ok)
        self.assertEqual(result.audit_id, record.audit_id)
        self.assertIn("Blocked columns referenced: users.email", record.failure_reason or "")
        self.assertEqual(0, record.row_count)
        self.assertIn("users.email", record.referenced_columns)


if __name__ == "__main__":
    unittest.main()
