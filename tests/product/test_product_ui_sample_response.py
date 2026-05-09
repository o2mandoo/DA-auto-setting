from __future__ import annotations

import json
from pathlib import Path


def test_product_ui_sample_response_exposes_comment_mode_comparison_panel() -> None:
    payload = json.loads(Path("apps/product_ui/sample_response.json").read_text(encoding="utf-8"))
    panel = payload["comment_mode_comparison_panel"]
    assert panel["selected_comment_mode"] == "no_comments"
    assert [item["mode"] for item in panel["comparisons"]] == [
        "no_comments",
        "real_comments",
        "synthetic_comments",
    ]
    assert panel["comparisons"][0]["runtime_warnings"] == ["metadata_gap_not_context_truth"]
    assert panel["comparisons"][1]["runtime_warnings"] == ["comment_only_draft_context"]
    assert panel["comparisons"][2]["runtime_warnings"] == ["test_only_synthetic_metadata_excluded"]
