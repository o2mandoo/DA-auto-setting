# Phase 15 — SQL Comparison / Diff / Scoring Engine

## Summary

Implemented deterministic SQL text profiling and baseline-vs-system comparison under `semantic_registry.product.comparison`.

## Covered checks

- single SELECT/WITH safety profiling,
- multi-statement and non-SELECT detection,
- table/column/join/filter/aggregation extraction,
- blocked PII column detection through pack policies,
- Semantic Pack differences for date basis, metric basis, join recipe, paid-status filter, and missing system SQL,
- MCP-facing tool `compare_baseline_vs_system_sql`.

## Execution boundary

The comparison engine and MCP tool profile SQL text only. Baseline and system candidates remain `not_executed` / `execution_allowed=false`.

## Evaluation

Targeted tests: `tests/product/test_phase15_sql_comparison_engine.py`.
