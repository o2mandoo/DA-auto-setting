# Phase 14 — Baseline Generic LLM SQL Runner

## Summary

Implemented a physical-schema-only baseline SQL runner under `semantic_registry.product.baseline`.

## Key properties

- Baseline receives only table/column/data-type schema snapshots.
- Baseline output is always `not_executed=true`.
- Mock provider is deterministic for offline tests.
- Explicit non-mock provider configuration errors are raised instead of silently falling back.
- JSONL storage is append-only under a caller-selected runtime directory.

## Evaluation

Targeted tests: `tests/product/test_phase14_baseline_sql_runner.py`.
