# Phase 20 — n8n Readiness Report

## Readiness verdict

PASS for workflow-template implementation. The Product API contracts, examples, failure states, and local UI/evidence surfaces now exist. A separate web adapter is still required to expose these pure Python handlers over HTTP in a running environment.

## Preconditions satisfied

- Product modes and answer UI contracts are documented in `docs/product/`.
- Product API routes are documented in `docs/api/PRODUCT_API.md` and `docs/api/OPENAPI_LIKE.yaml`.
- Example payloads exist under `docs/api/examples/`.
- Failure-safe red-team scenarios exist under `eval/product_scenarios/`.
- Evidence reports exist under `reports/final/`.

## Workflows to create next

1. Onboarding Demo.
2. Confirmation + Pack Promotion.
3. Query Runtime + Baseline/System Comparison.
4. 20-Domain Benchmark Runner.
5. Failure Review Loop.

## Safety gates

- n8n must call repo Product API routes and must not duplicate Semantic Pack logic.
- Workflows must keep baseline SQL and system SQL not executed.
- Workflows must show API failure states explicitly.
- Workflow JSON must not contain credentials, raw PII, production DSNs, or hidden fallback branches.

## Remaining adapter work

- A lightweight HTTP adapter can be added around `semantic_registry.product.api.handle_product_api`.
- Import n8n workflow templates into a local n8n instance and configure the base URL and demo header placeholder.
