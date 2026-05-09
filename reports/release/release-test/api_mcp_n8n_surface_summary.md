# API / MCP / n8n Surface Summary

This summary is assembled from current repo evidence and keeps explicit source references.

## Source references
- docs/product/PRODUCT_MODES.md
- docs/product/BASELINE_COMPARISON_SPEC.md
- docs/product/METADATA_PROVENANCE_RULES.md
- docs/api/PRODUCT_API.md
- reports/productization/PR2_HTTP_ADAPTER_EVIDENCE.md
- reports/productization/PR3_MCP_SAFE_RUNTIME_EVIDENCE.md
- reports/productization/phase20_n8n_readiness_report.md

## Summary

- Product API and MCP surfaces remain validation-first and do not expose production execute_query.
- Baseline versus system SQL comparison is profile-only and non-executing.
- n8n workflow evidence remains orchestration-only and must surface backend/comment warnings explicitly.

## DB comment-mode rules

| Comment mode | Metadata source | Product rule | Fallback rule |
|---|---|---|---|
| `real_comments` | `real_db_comment` | Usable only as draft Text-to-SQL context with provenance/status and comment-only warnings. | If real catalog or manifest comments are absent, mark the mode unavailable; do not synthesize replacements. |
| `no_comments` | `no_comment` | Represents an explicit metadata gap and reverse-question input, not context truth. | Do not fabricate comments or replace missing semantics with generated text. |
| `synthetic_comments` | `test_only_synthetic_comment` | Fixture/lab evidence only; excluded from approved product context and human truth by default. | Never promote generated comments to real comments or approved truth automatically. |
