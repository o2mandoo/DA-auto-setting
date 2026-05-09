from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "semantic_contracts"))
sys.path.insert(0, str(ROOT / "packages" / "semantic_registry"))

from semantic_contracts import SqlCheckName, SqlCheckStatus  # noqa: E402
from semantic_registry.sql_guard import SQLGuard, validate_sql, validate_sql_dict  # noqa: E402


class SQLGuardTests(unittest.TestCase):
    def test_valid_select_against_allowed_tables_passes_without_execution(self) -> None:
        result = validate_sql(
            """
            SELECT users.user_id, SUM(payments.amount) AS total_amount
            FROM users
            JOIN payments ON users.user_id = payments.user_id
            WHERE payments.status = 'PAID'
            GROUP BY users.user_id;
            """,
            role="marketing_analyst",
            pack_root=ROOT / "semantic_packs",
        )

        self.assertTrue(result.valid, result.errors)
        self.assertFalse(result.execution_allowed)
        self.assertEqual(result.checks[SqlCheckName.SELECT_ONLY], SqlCheckStatus.PASS)
        self.assertEqual(result.checks[SqlCheckName.MULTI_STATEMENT], SqlCheckStatus.PASS)
        self.assertIn("users", result.referenced_tables)
        self.assertIn("payments", result.referenced_tables)
        self.assertIn("payments.amount", result.referenced_columns)

    def test_blocks_dml_and_ddl_keywords(self) -> None:
        cases = [
            "DELETE FROM users",
            "INSERT INTO users (user_id) VALUES (1)",
            "UPDATE users SET segment = 'x'",
            "DROP TABLE users",
            "ALTER TABLE users ADD COLUMN x INT",
            "TRUNCATE TABLE users",
        ]

        for sql in cases:
            with self.subTest(sql=sql):
                result = validate_sql(sql, role="marketing_analyst", pack_root=ROOT / "semantic_packs")
                self.assertFalse(result.valid)
                self.assertEqual(result.checks[SqlCheckName.SELECT_ONLY], SqlCheckStatus.FAIL)

    def test_blocks_multi_statement_sql(self) -> None:
        result = validate_sql(
            "SELECT users.user_id FROM users; DROP TABLE users;",
            role="marketing_analyst",
            pack_root=ROOT / "semantic_packs",
        )

        self.assertFalse(result.valid)
        self.assertEqual(result.checks[SqlCheckName.MULTI_STATEMENT], SqlCheckStatus.FAIL)
        self.assertTrue(any("Multiple SQL statements" in error for error in result.errors))

    def test_blocks_unknown_table_outside_role_policy(self) -> None:
        result = validate_sql(
            "SELECT orders.order_id FROM orders",
            role="marketing_analyst",
            pack_root=ROOT / "semantic_packs",
        )

        self.assertFalse(result.valid)
        self.assertEqual(result.checks[SqlCheckName.ALLOWED_TABLES], SqlCheckStatus.FAIL)
        self.assertTrue(any("orders" in error for error in result.errors))

    def test_blocks_qualified_unqualified_alias_and_star_pii_columns(self) -> None:
        cases = [
            "SELECT users.email FROM users",
            "SELECT email FROM users",
            "SELECT u.phone FROM users AS u",
            "SELECT name FROM users",
            "SELECT * FROM users",
        ]

        for sql in cases:
            with self.subTest(sql=sql):
                result = validate_sql(sql, role="marketing_analyst", pack_root=ROOT / "semantic_packs")
                self.assertFalse(result.valid)
                self.assertEqual(result.checks[SqlCheckName.BLOCKED_COLUMNS], SqlCheckStatus.FAIL)
                self.assertTrue(any("users." in error for error in result.errors))

    def test_unknown_explicit_role_does_not_silently_widen_policy(self) -> None:
        result = validate_sql(
            "SELECT payments.amount FROM payments",
            role="unknown_role",
            pack_root=ROOT / "semantic_packs",
        )

        self.assertFalse(result.valid)
        self.assertEqual(result.checks[SqlCheckName.ALLOWED_TABLES], SqlCheckStatus.FAIL)
        self.assertTrue(any("No Semantic Pack table policy matched role" in error for error in result.errors))

    def test_guard_can_validate_loaded_pack_and_dump_json_compatible_result(self) -> None:
        guard = SQLGuard.from_pack_root("demo_company.revenue", ROOT / "semantic_packs")
        result = guard.validate("SELECT payments.amount FROM payments", role="marketing_analyst")
        dumped = validate_sql_dict(
            "SELECT payments.amount FROM payments",
            role="marketing_analyst",
            pack_root=ROOT / "semantic_packs",
        )

        self.assertTrue(result.valid, result.errors)
        self.assertEqual(dumped["checks"]["select_only"], "pass")
        self.assertFalse(dumped["execution_allowed"])


if __name__ == "__main__":
    unittest.main()
