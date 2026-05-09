# n8n Workflow Templates

## Created templates

- `n8n/workflows/01_onboarding_demo.json`
- `n8n/workflows/02_confirmation_pack_promotion.json`
- `n8n/workflows/03_query_runtime_comparison_demo.json`
- `n8n/workflows/04_20_domain_benchmark_runner.json`
- `n8n/workflows/05_failure_review_loop.json`

## Safety evidence

Templates call only documented Product API routes, use placeholder environment variables for base URL/demo header, and mark no-silent-fallback/no-SQL-run metadata.

## Remaining operational step

Import the templates into a local n8n instance after a lightweight HTTP adapter is started for `semantic_registry.product.api`.
