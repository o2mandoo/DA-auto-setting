# Observability samples

This repository intentionally keeps observability local and demo-safe. The
sample artifact below mirrors the product HTTP adapter audit JSONL shape used by
local checks; it is not a production logging stack and it does not contain real
credentials, connection strings, or raw PII fixtures.

## Product API audit JSONL

- Sample: `docs/observability/product_api_audit_sample.jsonl`
- Runtime writer: `semantic_registry.product.http_adapter`
- Runtime default area: `runtime/product_api/` or the explicit `--audit-root`
  passed to `python -m semantic_registry.product.http_adapter --check`
- Correlation field: `correlation_id`
- Safety invariant: `execution_allowed` remains `false`; production
  `execute_query` is not present in route names or audit payloads.

Each line is a standalone JSON object so local demos can tail or parse the file
without loading an external service. The included success and validation-error
records cover the two most common support paths: a traceable read-only product
answer response and an explicit typed failure.

## Local verification

```bash
python -m pytest -q tests/product/test_observability_samples.py
```
