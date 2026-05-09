from __future__ import annotations

import pytest

from semantic_contracts import (
    BusinessTerm,
    CardStatus,
    ColumnCard,
    MetadataProvenance,
    MetadataSource,
    MetadataStatus,
    TableCard,
)


def test_real_db_comment_is_draft_text2sql_context() -> None:
    provenance = MetadataProvenance(metadata_source=MetadataSource.REAL_DB_COMMENT, source_detail="pg:orders.amount")
    assert provenance.can_use_for_text2sql is True
    assert provenance.requires_human_confirmation is True
    assert provenance.status == MetadataStatus.DRAFT


def test_no_comment_requires_gap_and_is_not_context_truth() -> None:
    with pytest.raises(ValueError):
        MetadataProvenance(metadata_source=MetadataSource.NO_COMMENT)
    provenance = MetadataProvenance(metadata_source=MetadataSource.NO_COMMENT, metadata_gap_reason="missing_column_comment")
    assert provenance.can_use_for_text2sql is False
    assert provenance.requires_human_confirmation is True


def test_synthetic_metadata_cannot_be_approved_product_truth() -> None:
    with pytest.raises(ValueError):
        MetadataProvenance(
            metadata_source=MetadataSource.TEST_ONLY_SYNTHETIC_COMMENT,
            status=MetadataStatus.APPROVED,
        )
    provenance = MetadataProvenance(metadata_source=MetadataSource.TEST_ONLY_SYNTHETIC_COMMENT)
    assert provenance.is_test_only is True
    assert provenance.can_use_for_text2sql is False


def test_human_confirmed_can_be_approved_context() -> None:
    provenance = MetadataProvenance(
        metadata_source=MetadataSource.HUMAN_CONFIRMED,
        status=MetadataStatus.APPROVED,
    )
    assert provenance.can_use_for_text2sql is True
    assert provenance.requires_human_confirmation is False


def test_cards_preserve_metadata_provenance() -> None:
    provenance = MetadataProvenance(metadata_source=MetadataSource.REAL_DB_COMMENT, source_detail="pg:table.orders")
    table = TableCard(id="table.orders", space_id="s", physical_name="orders", title="Orders", metadata_provenance=[provenance])
    column = ColumnCard(id="column.orders.amount", table="orders", name="amount", data_type="numeric", metadata_provenance=[provenance])
    term = BusinessTerm(id="term.revenue", term="revenue", definition="Revenue", status=CardStatus.DRAFT, metadata_provenance=[provenance])
    assert table.metadata_provenance[0].metadata_source == MetadataSource.REAL_DB_COMMENT
    assert column.metadata_provenance[0].can_use_for_text2sql is True
    assert term.metadata_provenance[0].status == MetadataStatus.DRAFT
