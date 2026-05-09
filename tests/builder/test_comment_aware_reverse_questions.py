from __future__ import annotations

from semantic_builder.inference.reverse_questions import generate_reverse_questions


def test_no_comment_status_column_generates_gap_question_with_evidence() -> None:
    questions = generate_reverse_questions([
        {
            "table_name": "orders",
            "columns": [
                {
                    "name": "status",
                    "type_guess": "string",
                    "metadata_provenance": [{"metadata_source": "no_comment"}],
                    "metadata_gaps": [{"target": "column.orders.status", "metadata_gap_reason": "abstract_column_without_comment", "severity": "high", "expected_answer_type": "value_dictionary"}],
                    "pii": {"is_pii": False},
                }
            ],
        }
    ])
    gap = next(q for q in questions if q["category"] == "metadata_gap")
    assert gap["metadata_gap_reason"] == "abstract_column_without_comment"
    assert gap["evidence_source"] == "no_comment"
    assert gap["candidate_options"]
    assert gap["risk_if_unanswered"]


def test_informative_real_comment_reduces_generic_missing_question() -> None:
    questions = generate_reverse_questions([
        {
            "table_name": "orders",
            "columns": [
                {
                    "name": "status",
                    "type_guess": "string",
                    "metadata_provenance": [{"metadata_source": "real_db_comment"}],
                    "description": "Lifecycle state of the payment order",
                    "null_ratio": 0.0,
                    "cardinality_estimate": 2000,
                    "pii": {"is_pii": False},
                }
            ],
        }
    ])
    assert not [q for q in questions if q["category"] == "missing_evidence" and q["target"] == "column.orders.status"]


def test_vague_and_conflicting_comments_generate_clarification() -> None:
    questions = generate_reverse_questions([
        {
            "table_name": "orders",
            "columns": [
                {"name": "code", "type_guess": "string", "metadata_provenance": [{"metadata_source": "real_db_comment"}], "description": "code", "pii": {"is_pii": False}},
                {"name": "amount", "type_guess": "number", "metadata_provenance": [{"metadata_source": "real_db_comment"}], "description": "Customer name identifier", "pii": {"is_pii": False}},
            ],
        }
    ])
    categories = {q["category"] for q in questions}
    assert "comment_clarification" in categories
    assert "comment_profile_conflict" in categories
