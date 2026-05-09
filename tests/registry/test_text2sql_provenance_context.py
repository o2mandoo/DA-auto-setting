from __future__ import annotations

from semantic_contracts import (
    BusinessTerm,
    ColumnCard,
    MetadataProvenance,
    MetadataSource,
    MetadataStatus,
    Metric,
    Owner,
    SemanticPack,
    SemanticSpace,
    TableCard,
)
from semantic_registry.cards import iter_pack_card_documents
from semantic_registry.query_planner import QueryPlanner
from semantic_registry.search import SearchIndex


def _pack() -> SemanticPack:
    real = MetadataProvenance(metadata_source=MetadataSource.REAL_DB_COMMENT, source_detail="pg.comment")
    human = MetadataProvenance(metadata_source=MetadataSource.HUMAN_CONFIRMED, status=MetadataStatus.APPROVED)
    synthetic = MetadataProvenance(metadata_source=MetadataSource.TEST_ONLY_SYNTHETIC_COMMENT)
    return SemanticPack(
        id="test.pack",
        version="0.1.0",
        title="Test Pack",
        owners=[Owner(role="owner", name="test")],
        spaces=[SemanticSpace(id="s", title="S")],
        tables=[TableCard(id="table.orders", space_id="s", physical_name="orders", title="Orders", description="Sales orders from DB comment", metadata_provenance=[real])],
        columns=[
            ColumnCard(id="column.orders.amount", table="orders", name="amount", data_type="numeric", description="Net amount from DB comment", metadata_provenance=[real]),
            ColumnCard(id="column.orders.synthetic", table="orders", name="synthetic", data_type="string", description="Synthetic fixture only", metadata_provenance=[synthetic]),
        ],
        metrics=[Metric(id="metric.net_revenue", name="net_revenue", label="순매출", formula_sql="SUM(orders.amount)", required_tables=["orders"], metadata_provenance=[human])],
        business_terms=[BusinessTerm(id="term.net_revenue", term="순매출", definition="Confirmed net revenue", related_tables=["orders"], related_metrics=["metric.net_revenue"], metadata_provenance=[human])],
    )


def test_real_db_comment_is_retrievable_as_column_context() -> None:
    results = SearchIndex(_pack()).search_cards("Net amount", card_types=["column"])
    assert results
    assert results[0].metadata["metadata_source"] == "real_db_comment"
    assert results[0].metadata["can_use_for_text2sql"] is True


def test_synthetic_comment_is_not_indexed_as_approved_text2sql_truth() -> None:
    results = SearchIndex(_pack()).search_cards("Synthetic fixture only", card_types=["column"])
    assert results == []


def test_human_confirmed_definition_out_ranks_comment_in_runtime_context() -> None:
    plan = QueryPlanner.from_pack(_pack()).plan("순매출")
    assert "human_confirmed" in plan.used_context_sources
    assert plan.source_status["human_confirmed"] == "approved"
    assert "metric.net_revenue" in plan.required_metrics


def test_card_documents_disclose_comment_only_warning() -> None:
    docs = list(iter_pack_card_documents(_pack()))
    amount_doc = next(doc for doc in docs if doc.card_id == "column.orders.amount")
    assert "comment_only_draft_context" in amount_doc.metadata["context_warnings"]
