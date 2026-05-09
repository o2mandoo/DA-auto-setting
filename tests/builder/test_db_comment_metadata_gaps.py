from __future__ import annotations

from semantic_builder.connectors.db import ColumnMetadata, SafeScanConfig, TableMetadata
from semantic_builder.inference.reverse_questions import generate_reverse_questions
from semantic_builder.metadata import TEST_ONLY_SYNTHETIC_METADATA_MARKER
from semantic_builder.scanner import MySQLScanner, PostgresScanner


class _CommentConnector:
    read_only = True

    def __init__(self, *, table_comment: str | None, column_comments: dict[str, str | None]) -> None:
        self.table_comment = table_comment
        self.column_comments = column_comments

    def connect(self):
        return self

    def close(self) -> None:
        return None

    def list_schemas(self, config=None):
        return []

    def list_tables(self, config=None):
        return [TableMetadata("semantic_fixture_sales", "orders", "BASE TABLE", comment=self.table_comment)]

    def list_columns(self, schema_name, table_name, config=None):
        return [
            ColumnMetadata(schema_name, table_name, "status", "text", False, 1, comment=self.column_comments.get("status")),
            ColumnMetadata(schema_name, table_name, "amount", "numeric", False, 2, comment=self.column_comments.get("amount")),
            ColumnMetadata(schema_name, table_name, "created_at", "timestamp", False, 3, comment=self.column_comments.get("created_at")),
            ColumnMetadata(schema_name, table_name, "paid_at", "timestamp", True, 4, comment=self.column_comments.get("paid_at")),
        ]

    def sample_rows(self, *args, **kwargs):
        return []

    def profile_column(self, schema_name, table_name, column_name, config=None):
        type_guess = "number" if column_name == "amount" else "date" if column_name.endswith("_at") else "string"
        return {
            "name": column_name,
            "type_guess": type_guess,
            "row_count": 10,
            "null_count": 0,
            "null_ratio": 0.0,
            "cardinality_estimate": 3,
            "pii": {"is_pii": False},
        }


def _scan(connector: _CommentConnector):
    return PostgresScanner(connector, SafeScanConfig(max_tables=5, max_columns=10)).scan()["tables"][0]


def _scan_mysql(connector: _CommentConnector):
    return MySQLScanner(connector, SafeScanConfig(max_tables=5, max_columns=10)).scan()["tables"][0]


def test_real_db_comments_are_scanned_as_product_usable_provenance() -> None:
    table = _scan(_CommentConnector(table_comment="Real sales orders", column_comments={"amount": "Net payment amount"}))
    assert table["metadata_provenance"][0]["metadata_source"] == "real_db_comment"
    amount = next(col for col in table["columns"] if col["column_name"] == "amount")
    assert amount["metadata_provenance"][0]["metadata_source"] == "real_db_comment"
    assert amount["metadata_provenance"][0]["can_use_for_text2sql"] is True


def test_real_mysql_comments_are_product_usable_draft_provenance() -> None:
    table = _scan_mysql(_CommentConnector(table_comment="Real MySQL sales orders", column_comments={"amount": "Net payment amount from MySQL"}))
    table_provenance = table["metadata_provenance"][0]
    assert table_provenance["metadata_source"] == "real_db_comment"
    assert table_provenance["source_detail"] == "mysql.table_comment:semantic_fixture_sales.orders"
    assert table_provenance["can_use_for_text2sql"] is True

    amount = next(col for col in table["columns"] if col["column_name"] == "amount")
    column_provenance = amount["metadata_provenance"][0]
    assert column_provenance["metadata_source"] == "real_db_comment"
    assert column_provenance["source_detail"] == "mysql.column_comment:semantic_fixture_sales.orders.amount"
    assert column_provenance["can_use_for_text2sql"] is True
    assert column_provenance["is_test_only"] is False


def test_missing_comments_are_no_comment_gaps_without_scanner_failure() -> None:
    table = _scan(_CommentConnector(table_comment=None, column_comments={}))
    assert table["metadata_provenance"][0]["metadata_source"] == "no_comment"
    status = next(col for col in table["columns"] if col["column_name"] == "status")
    reasons = {gap["metadata_gap_reason"] for gap in status["metadata_gaps"]}
    assert "missing_column_comment" in reasons
    assert "abstract_column_without_comment" in reasons
    table_reasons = {gap["metadata_gap_reason"] for gap in table["metadata_gaps"]}
    assert "missing_table_comment" in table_reasons
    assert "multiple_candidate_date_columns" in table_reasons


def test_missing_mysql_comments_create_no_comment_reverse_question_inputs() -> None:
    table = _scan_mysql(_CommentConnector(table_comment=None, column_comments={}))
    assert table["metadata_provenance"][0]["metadata_source"] == "no_comment"
    assert table["metadata_provenance"][0]["metadata_gap_reason"] == "missing_db_comment"

    status = next(col for col in table["columns"] if col["column_name"] == "status")
    status_provenance = status["metadata_provenance"][0]
    assert status_provenance["metadata_source"] == "no_comment"
    assert status_provenance["metadata_gap_reason"] == "missing_db_comment"
    assert status_provenance["can_use_for_text2sql"] is False
    assert {gap["metadata_gap_reason"] for gap in status["metadata_gaps"]} >= {
        "missing_column_comment",
        "abstract_column_without_comment",
    }

    questions = generate_reverse_questions([table])
    gap_question = next(
        question
        for question in questions
        if question["category"] == "metadata_gap"
        and question["target"] == "column.orders.status"
        and question["metadata_gap_reason"] == "abstract_column_without_comment"
    )
    assert gap_question["evidence_source"] == "no_comment"
    assert gap_question["expected_answer_type"] == "value_dictionary"
    assert gap_question["candidate_options"]


def test_synthetic_comments_are_detected_as_test_only() -> None:
    table = _scan(_CommentConnector(table_comment=f"{TEST_ONLY_SYNTHETIC_METADATA_MARKER}: fixture table", column_comments={"amount": f"{TEST_ONLY_SYNTHETIC_METADATA_MARKER}: generated amount"}))
    assert table["metadata_provenance"][0]["metadata_source"] == "test_only_synthetic_comment"
    amount = next(col for col in table["columns"] if col["column_name"] == "amount")
    assert amount["metadata_provenance"][0]["is_test_only"] is True
    assert amount["metadata_provenance"][0]["can_use_for_text2sql"] is False
