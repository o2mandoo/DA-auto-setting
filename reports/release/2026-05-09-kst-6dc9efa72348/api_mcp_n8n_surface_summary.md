# API / MCP / n8n Surface Summary

## API surface

- Adapter routes: `GET /healthz`, `GET /readyz`, `GET /openapi.json`
- Product routes:
  - `POST /api/onboarding/run`
  - `POST /api/confirmation/session`
  - `POST /api/confirmation/answer`
  - `POST /api/pack/promote`
  - `POST /api/product/answer`
  - `POST /api/product/compare-sql`
  - `POST /api/eval/run`
  - `POST /api/failure-review/run`
- Safety: local/demo only, typed errors/correlation IDs, no production SQL execution, no `execute_query`.

## MCP surface

- Transport: stdio
- Registered tools:
  - `list_semantic_spaces`
  - `search_semantic_context`
  - `resolve_business_terms`
  - `plan_data_query`
  - `validate_sql`
  - `preview_query`
  - `record_feedback`
  - `compare_baseline_vs_system_sql`
- Registered resources:
  - `semantic://packs`
  - `semantic://packs/{pack_id}`
  - `semantic://packs/{pack_id}/terms`
  - `semantic://packs/{pack_id}/metrics`
  - `semantic://packs/{pack_id}/policies`
  - `semantic://packs/{pack_id}/verified-queries`
- Registered prompt:
  - `answer_with_semantic_pack`

## n8n surface

- Required env: `SDC_PRODUCT_API_BASE_URL`, `SDC_DEMO_KEY`
- Workflow templates:
  - `n8n/workflows/01_onboarding_demo.json`
  - `n8n/workflows/02_confirmation_pack_promotion.json`
  - `n8n/workflows/03_query_runtime_comparison_demo.json`
  - `n8n/workflows/04_20_domain_benchmark_runner.json`
  - `n8n/workflows/05_failure_review_loop.json`
- Safety: call documented Product API routes only; show failures explicitly; no hidden fallback or SQL execution.
