from __future__ import annotations

from semantic_builder.connectors.db import ColumnMetadata, SafeScanConfig, TableMetadata
from semantic_builder.inference.reverse_questions import generate_reverse_questions
from semantic_builder.metadata import TEST_ONLY_SYNTHETIC_METADATA_MARKER
from semantic_builder.scanner.mysql import MySQLScanner, scan_mysql_database


class _MySQLCommentConnector:
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
            ColumnMetadata(schema_name, table_name, "status", "varchar", False, 1, comment=self.column_comments.get("status")),
            ColumnMetadata(schema_name, table_name, "amount", "decimal", True, 2, comment=self.column_comments.get("amount")),
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


def _scan(table_comment: str | None, column_comments: dict[str, str | None]):
    connector = _MySQLCommentConnector(table_comment=table_comment, column_comments=column_comments)
    return MySQLScanner(connector, SafeScanConfig(max_tables=5, max_columns=10)).scan()["tables"][0]


def test_mysql_scanner_emits_real_db_comment_provenance_from_catalog_comments() -> None:
    table = _scan("Real MySQL orders table", {"amount": "Net payment amount from MySQL"})

    assert table["metadata_provenance"][0]["metadata_source"] == "real_db_comment"
    assert table["metadata_provenance"][0]["source_detail"] == "mysql.table_comment:semantic_fixture_sales.orders"
    assert table["metadata_provenance"][0]["can_use_for_text2sql"] is True

    amount = next(col for col in table["columns"] if col["column_name"] == "amount")
    assert amount["metadata_provenance"][0]["metadata_source"] == "real_db_comment"
    assert amount["metadata_provenance"][0]["source_detail"] == "mysql.column_comment:semantic_fixture_sales.orders.amount"
    assert amount["metadata_provenance"][0]["can_use_for_text2sql"] is True
    assert amount["metadata_provenance"][0]["is_test_only"] is False


def test_mysql_scanner_emits_no_comment_gaps_and_reverse_questions() -> None:
    table = _scan(None, {})

    assert table["metadata_provenance"][0]["metadata_source"] == "no_comment"
    assert table["metadata_provenance"][0]["metadata_gap_reason"] == "missing_db_comment"
    status = next(col for col in table["columns"] if col["column_name"] == "status")
    assert status["metadata_provenance"][0]["metadata_source"] == "no_comment"
    assert status["metadata_provenance"][0]["can_use_for_text2sql"] is False
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


def test_mysql_scanner_keeps_test_only_synthetic_comments_out_of_text2sql_context() -> None:
    marker = TEST_ONLY_SYNTHETIC_METADATA_MARKER
    table = _scan(
        f"{marker}: synthetic MySQL fixture table",
        {"amount": f"{marker}: synthetic MySQL amount"},
    )

    assert table["metadata_provenance"][0]["metadata_source"] == "test_only_synthetic_comment"
    assert table["metadata_provenance"][0]["is_test_only"] is True
    assert table["metadata_provenance"][0]["can_use_for_text2sql"] is False

    amount = next(col for col in table["columns"] if col["column_name"] == "amount")
    assert amount["metadata_provenance"][0]["metadata_source"] == "test_only_synthetic_comment"
    assert amount["metadata_provenance"][0]["is_test_only"] is True
    assert amount["metadata_provenance"][0]["can_use_for_text2sql"] is False


def test_scan_mysql_database_uses_mysql_connector_label() -> None:
    connector = _MySQLCommentConnector(table_comment="Real MySQL table", column_comments={})
    report = scan_mysql_database(connector, config=SafeScanConfig(max_tables=5, max_columns=10))

    assert report["connector"] == "mysql"
