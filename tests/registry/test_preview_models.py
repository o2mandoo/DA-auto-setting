from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "semantic_contracts"))
sys.path.insert(0, str(ROOT / "packages" / "semantic_registry"))

from pydantic import ValidationError  # noqa: E402
from semantic_contracts import (  # noqa: E402
    ExecutionError,
    ExecutionPolicy,
    PreviewExecutionTarget,
    PreviewRequest,
    PreviewResult,
    PreviewStatus,
    QueryAuditRecord,
    load_pack_yaml,
)
from semantic_registry.execution import execution_policy_from_packs  # noqa: E402


class PreviewExecutionModelTests(unittest.TestCase):
    def test_preview_request_is_read_only_and_never_execution_grant(self) -> None:
        request = PreviewRequest(
            space_id="demo_company.revenue",
            sql="SELECT payment_id FROM payments",
            role="marketing_analyst",
            requested_limit=5,
        )

        self.assertEqual(request.execution_target, PreviewExecutionTarget.LOCAL_FIXTURE)
        self.assertFalse(request.execution_allowed)

        with self.assertRaises(ValidationError):
            PreviewRequest(space_id="demo_company.revenue", sql="DELETE FROM users", role="marketing_analyst")
        with self.assertRaises(ValidationError):
            PreviewRequest(space_id="demo_company.revenue", sql="SELECT 1; SELECT 2", role="marketing_analyst")

    def test_execution_policy_normalizes_tables_and_blocks_production_targets(self) -> None:
        policy = ExecutionPolicy(
            role="marketing_analyst",
            allowed_tables=["Users", "payments"],
            blocked_columns=["Users.Email"],
            max_preview_rows=25,
        )

        self.assertEqual(policy.allowed_tables, ["users", "payments"])
        self.assertEqual(policy.blocked_columns, ["users.email"])
        self.assertEqual(policy.max_preview_rows, 25)
        self.assertFalse(policy.allow_production_connections)
        self.assertTrue(policy.require_validation)

        with self.assertRaises(ValidationError):
            ExecutionPolicy(blocked_columns=["email"])

    def test_preview_result_and_audit_keep_blocked_payloads_empty(self) -> None:
        request = PreviewRequest(space_id="demo_company.revenue", sql="SELECT payment_id FROM payments")
        allowed = PreviewResult(
            request=request,
            status=PreviewStatus.ALLOWED,
            columns=["payment_id"],
            rows=[{"payment_id": "p001"}],
            row_count=1,
            applied_limit=1,
            truncated=True,
            audit_id="audit-1",
        )
        self.assertFalse(allowed.execution_allowed)

        with self.assertRaises(ValidationError):
            PreviewResult(
                request=request,
                status=PreviewStatus.BLOCKED,
                columns=["payment_id"],
                rows=[{"payment_id": "p001"}],
                row_count=1,
                applied_limit=0,
                errors=[ExecutionError(code="blocked", message="blocked")],
            )

        audit = QueryAuditRecord(
            audit_id="audit-1",
            request=request,
            policy=ExecutionPolicy(allowed_tables=["payments"]),
            status=PreviewStatus.ALLOWED,
            guard_valid=True,
            preview_allowed=True,
            row_count=1,
        )
        self.assertFalse(audit.execution_allowed)

        with self.assertRaises(ValidationError):
            QueryAuditRecord(
                audit_id="audit-2",
                request=request,
                policy=ExecutionPolicy(),
                status=PreviewStatus.BLOCKED,
                guard_valid=False,
                preview_allowed=True,
            )

    def test_registry_execution_policy_is_pack_backed(self) -> None:
        pack = load_pack_yaml(ROOT / "semantic_packs" / "demo_company" / "revenue.v0_1.yaml")
        policy = execution_policy_from_packs([pack], role="marketing_analyst", default_max_preview_rows=10)

        self.assertEqual(policy.max_preview_rows, 10)
        self.assertIn("payments", policy.allowed_tables)
        self.assertIn("users.email", policy.blocked_columns)
        self.assertTrue(policy.require_validation)

        no_role_policy = execution_policy_from_packs([pack], role="unknown_role", default_max_preview_rows=10)
        self.assertEqual(no_role_policy.allowed_tables, [])
        self.assertEqual(no_role_policy.max_preview_rows, 1)


if __name__ == "__main__":
    unittest.main()
