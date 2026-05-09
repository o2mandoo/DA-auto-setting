from __future__ import annotations

from pathlib import Path
import unittest

from semantic_contracts import PackStatus, load_pack_yaml
from semantic_registry import PackStore
from semantic_registry.retrieval import documents_from_pack
from semantic_registry import FeedbackStore
from semantic_registry.promotion import PromotionError, assert_approved_pack_update_allowed
from semantic_registry.retrieval import WeaviateSearchBackend, WeaviateUnavailableError
from semantic_registry.sql_guard import validate_sql


ROOT = Path(__file__).resolve().parents[2]
PACK_ROOT = ROOT / "semantic_packs"
PACKAGE_ROOTS = (ROOT / "packages" / "semantic_contracts", ROOT / "packages" / "semantic_registry", ROOT / "packages" / "semantic_mcp", ROOT / "packages" / "semantic_builder")
FORBIDDEN_RUNTIME_IMPORTS = (
    # This lane is hardening-only: no dashboard or SaaS runtime surfaces belong
    # in the product codebase.
    "streamlit",
    "gradio",
    "dash",
    "flask",
    "fastapi",
    "django",
)
FORBIDDEN_PROD_CREDENTIAL_MARKERS = (
    "postgresql://",
    "mysql://",
    "oracle://",
    "snowflake://",
    "aws_access_key",
    "aws_secret_access_key",
    "password=",
)
FORBIDDEN_PII_LITERALS = (
    "alice@example.com",
    "ada@example.com",
    "grace@example.com",
    "+821012345678",
    "kim example",
)


class Phase12HardeningTests(unittest.TestCase):
    def test_no_exec_query_or_dashboard_runtime_surfaces(self) -> None:
        runtime_hits: list[tuple[Path, str]] = []
        execute_query_token = "execute" + "_query"
        for package_root in PACKAGE_ROOTS:
            if not package_root.exists():
                continue
            for path in package_root.rglob("*.py"):
                text = path.read_text(encoding="utf-8")
                if f"def {execute_query_token}" in text or f"{execute_query_token}(" in text:
                    runtime_hits.append((path, execute_query_token))
                for marker in FORBIDDEN_RUNTIME_IMPORTS:
                    if f"import {marker}" in text or f"from {marker}" in text:
                        runtime_hits.append((path, marker))

        self.assertEqual(
            runtime_hits,
            [],
            "Product code must not introduce execute query or dashboard/SaaS runtime imports",
        )

    def test_no_production_credentials_literals_in_package_code(self) -> None:
        credential_hits: list[tuple[Path, str]] = []
        for package_root in PACKAGE_ROOTS:
            if not package_root.exists():
                continue
            for path in package_root.rglob("*.py"):
                text = path.read_text(encoding="utf-8").casefold()
                for marker in FORBIDDEN_PROD_CREDENTIAL_MARKERS:
                    if marker in text:
                        credential_hits.append((path, marker))

        self.assertEqual(
            credential_hits,
            [],
            "Package code must not embed production credential strings or obvious secret markers",
        )

    def test_retrieval_and_preview_surfaces_fail_closed_without_silent_vdb_fallback(self) -> None:
        with self.assertRaisesRegex(WeaviateUnavailableError, "keyword fallback is not performed"):
            WeaviateSearchBackend()

        result = validate_sql(
            "SELECT payment_id FROM payments",
            space_id="demo_company.revenue",
            role="marketing_analyst",
            pack_root=PACK_ROOT,
        )
        self.assertTrue(result.valid, result.errors)

        blocked = validate_sql(
            "DELETE FROM users",
            space_id="demo_company.revenue",
            role="marketing_analyst",
            pack_root=PACK_ROOT,
        )
        self.assertFalse(blocked.valid)
        self.assertTrue(blocked.errors)

    def test_feedback_and_promotion_guards_block_raw_pii_and_approved_pack_mutation(self) -> None:
        with self.assertRaises(ValueError):
            FeedbackStore(ROOT / "runtime" / "hardening_feedback").save_feedback(
                {"space_id": "revenue", "feedback": "contact user@example.com"}
            )

        pack = load_pack_yaml(PACK_ROOT / "demo_company" / "revenue.v0_1.yaml")
        approved_pack = pack.model_copy(update={"status": PackStatus.APPROVED})
        mutated_candidate = approved_pack.model_copy(deep=True, update={"metadata": {**approved_pack.metadata, "note": "changed"}})

        with self.assertRaises(PromotionError):
            assert_approved_pack_update_allowed(
                approved_pack,
                mutated_candidate,
                confirmations=[{"confirmation_id": "c1", "target_id": "proposal-1", "status": "approved", "source_ref": "phase5"}],
                proposal_id="proposal-1",
            )

    def test_generated_search_payloads_remain_pii_safe(self) -> None:
        pack = PackStore(PACK_ROOT).load_pack("demo_company.revenue")
        documents = documents_from_pack(pack)

        # Safety boundary: blocked PII columns may be discoverable by safe
        # identifiers, but their raw values must never be projected into the
        # searchable text or metadata that VDB/keyword backends index.
        blocked_columns = {"users.email", "users.phone", "users.name"}
        blocked_value_dictionary_docs = [
            doc for doc in documents if doc.metadata.get("card_type") == "value_dictionary" and doc.metadata.get("column") in {"email", "phone", "name"}
        ]
        self.assertEqual(blocked_value_dictionary_docs, [])

        blocked_column_docs = [
            doc
            for doc in documents
            if doc.metadata.get("card_type") == "column"
            and f"{doc.metadata.get('table')}.{doc.metadata.get('column')}" in blocked_columns
        ]
        self.assertEqual({f"{doc.metadata.get('table')}.{doc.metadata.get('column')}" for doc in blocked_column_docs}, blocked_columns)
        for document in blocked_column_docs:
            text = f"{document.title} {document.text} {dict(document.metadata)}"
            for literal in FORBIDDEN_PII_LITERALS:
                self.assertNotIn(literal, text)

        for document in documents:
            text = f"{document.title} {document.text} {dict(document.metadata)}"
            for literal in FORBIDDEN_PII_LITERALS:
                self.assertNotIn(literal, text)

    def test_generated_reports_remain_free_of_raw_pii_literals(self) -> None:
        report_roots = [ROOT / "reports" / "benchmarks", ROOT / "reports" / "final"]
        offenders: list[tuple[Path, str]] = []

        for report_root in report_roots:
            if not report_root.exists():
                continue
            for path in report_root.rglob("*"):
                if not path.is_file() or path.suffix.lower() not in {".md", ".json", ".yaml", ".yml", ".txt"}:
                    continue
                text = path.read_text(encoding="utf-8", errors="ignore")
                for literal in FORBIDDEN_PII_LITERALS:
                    if literal in text:
                        offenders.append((path, literal))

        self.assertEqual(
            offenders,
            [],
            "Generated benchmark/final-report artifacts must not contain raw PII literals",
        )

    def test_sql_red_team_cases_remain_blocked(self) -> None:
        for sql in [
            "DELETE FROM users",
            "DROP TABLE payments",
            "SELECT payment_id FROM payments; SELECT user_id FROM users",
        ]:
            with self.subTest(sql=sql):
                result = validate_sql(
                    sql,
                    space_id="demo_company.revenue",
                    role="marketing_analyst",
                    pack_root=PACK_ROOT,
                )
                self.assertFalse(result.valid)
                self.assertTrue(result.errors)


if __name__ == "__main__":
    unittest.main()
