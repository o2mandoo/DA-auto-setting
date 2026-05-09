# Product API Contract

These contracts are stable local/demo HTTP-style routes for UI and n8n orchestration. The current implementation is pure Python handlers in `semantic_registry.product.api`; a web adapter can mount the same route names later.

## Safety rules

- No production SQL execution route exists.
- SQL preview is validation-gated and local/test only.
- Product API handlers write audit JSONL records under `runtime/product_api/`.
- Raw PII-like text is redacted before audit writes.
- Missing providers/backends are reported explicitly; workflow templates must not hide failures.

## Demo auth/header strategy

For local demos, workflows should send a placeholder header such as `x-sdc-demo-key: <SDC_DEMO_KEY>`. This repository does not store real secrets. A deployment adapter may reject requests when the configured demo key is absent or mismatched.

## Routes

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/onboarding/run` | Start or record an onboarding scan request for approved local files/test fixtures. |
| POST | `/api/confirmation/session` | Open a reverse-question / confirmation session. |
| POST | `/api/confirmation/answer` | Record a human answer without mutating the approved pack. |
| POST | `/api/pack/promote` | Validate promotion preconditions; versioned promotion remains explicit. |
| POST | `/api/product/answer` | Return side-by-side baseline/system answer UI model. |
| POST | `/api/product/compare-sql` | Compare baseline and system SQL text without running either. |
| POST | `/api/eval/run` | Produce product readiness/evidence summary. |
| POST | `/api/failure-review/run` | Run red-team failure scenario review. |

See `docs/api/OPENAPI_LIKE.yaml` and `docs/api/examples/` for payloads.
