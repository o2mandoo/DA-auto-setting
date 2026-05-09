# n8n Workflow Templates

These workflow JSON files are importable demo templates for the Semantic Data Context Product API.

## Required environment values in n8n

- `SDC_PRODUCT_API_BASE_URL`: base URL of a local HTTP adapter for `semantic_registry.product.api`.
- `SDC_DEMO_KEY`: placeholder demo header value agreed with the local adapter.

## Workflows

1. `01_onboarding_demo.json` — calls `POST /api/onboarding/run`.
2. `02_confirmation_pack_promotion.json` — comment-aware reverse-question demo; starts confirmation and keeps promotion as a separate explicit approval step.
3. `03_query_runtime_comparison_demo.json` — main baseline vs Semantic Pack comparison demo.
4. `04_20_domain_benchmark_runner.json` — calls evidence summary route.
5. `05_failure_review_loop.json` — failure-safe demo; calls red-team failure review route and keeps blocked states visible.

## Safety notes

- Workflow JSON contains no credentials.
- SQL text is passed only to product comparison/validation APIs.
- n8n must display API failure states directly.
- n8n must not implement a hidden substitute branch when a provider/backend fails.
