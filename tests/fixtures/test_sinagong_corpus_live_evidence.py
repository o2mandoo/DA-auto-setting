from __future__ import annotations

import json
from pathlib import Path

from experiments.db_fixtures.scripts.fixture_modes import TEST_ONLY_MARKER
from experiments.db_fixtures.scripts.sinagong_corpus_live_evidence import (
    DEFAULT_DATASET_ROOT,
    collect_corpus_evidence,
    discover_workbook_plans,
    write_corpus_evidence,
)


def test_discovery_covers_twenty_workbooks_without_row_values() -> None:
    plans, datasets = discover_workbook_plans(DEFAULT_DATASET_ROOT)

    assert len(datasets) == 20
    assert len(plans) == 89
    assert sum(plan.row_count for plan in plans) == 103980
    assert all(TEST_ONLY_MARKER in plan.table_comment for plan in plans)
    assert all(TEST_ONLY_MARKER in comment for plan in plans for comment in plan.column_comments.values())
    # Evidence plans include structural metadata only; source row values are loaded
    # into local fixture DBs but not serialized into reports.
    assert all("rows" not in plan.to_safe_dict() for plan in plans)


def test_collect_without_dsns_is_explicit_pending_no_fallback(tmp_path: Path) -> None:
    evidence = collect_corpus_evidence(dataset_root=DEFAULT_DATASET_ROOT, env={})
    output = write_corpus_evidence(tmp_path / "evidence.json", evidence)
    payload = json.loads(output.read_text(encoding="utf-8"))

    assert payload["source_dataset_count"] == 20
    assert payload["source_sheet_count"] == 89
    assert payload["metadata_mode"] == "test_only_synthetic_comments"
    assert payload["synthetic_truth_blocked"] is True
    assert payload["postgres"]["status"] == "pending"
    assert payload["mysql"]["status"] == "pending"
    assert payload["postgres"]["fallback_used"] is False
    assert payload["mysql"]["fallback_used"] is False
    assert any("no fallback backend" in reason for reason in payload["postgres"]["reasons"])
    assert any("no fallback backend" in reason for reason in payload["mysql"]["reasons"])
