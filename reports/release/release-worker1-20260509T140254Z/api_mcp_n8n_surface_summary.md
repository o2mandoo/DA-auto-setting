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
