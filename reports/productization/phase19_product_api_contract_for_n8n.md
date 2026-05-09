# Phase 19 — Product API Contract for n8n

## Summary

Implemented stable local product API route handlers and API documentation for n8n orchestration.

## Routes

- `POST /api/onboarding/run`
- `POST /api/confirmation/session`
- `POST /api/confirmation/answer`
- `POST /api/pack/promote`
- `POST /api/product/answer`
- `POST /api/product/compare-sql`
- `POST /api/eval/run`
- `POST /api/failure-review/run`

## Safety

- Product handlers never expose a production SQL execution surface.
- Audit payloads redact raw PII-like text.
- Pack promotion remains explicit and versioned; approved packs are not mutated in place.
- n8n is treated as orchestration only.

## Evaluation

Targeted tests: `tests/product/test_phase19_product_api_contract.py`.
