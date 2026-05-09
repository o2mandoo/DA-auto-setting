# Product API Contract

These are the stable local/demo HTTP-style routes used by the UI and n8n
orchestration flows. The current implementation is pure Python handlers in
`semantic_registry.product.api`; a thin web adapter can mount the same route
names later without changing the product logic.

## Contract scope

- The API is local/demo only.
- No production SQL execution route exists.
- SQL preview remains validation-gated and local/test only.
- Product API handlers write audit JSONL records under `runtime/product_api/`.
- Raw PII-like text is redacted before audit writes.
- Missing providers/backends are reported explicitly; workflow templates must
  not hide failures behind unlabeled fallbacks.

## Demo auth/header strategy

For local demos, workflows should send a placeholder header such as
`x-sdc-demo-key: <SDC_DEMO_KEY>`. This repository does not store real secrets.
A deployment adapter may reject requests when the configured demo key is absent
or mismatched.

## Shared response conventions

- `POST /api/product/answer` and `POST /api/product/compare-sql` are read-only
  view-model endpoints. They return comparison data and never execute SQL.
- `POST /api/onboarding/run`, `POST /api/confirmation/session`,
  `POST /api/confirmation/answer`, `POST /api/pack/promote`,
  `POST /api/eval/run`, and `POST /api/failure-review/run` all emit an
  `audit_id`.
- Confirmation and promotion routes are explicit about non-mutation:
  confirmation answers return `pack_mutated: false`, and promotion is either
  `blocked` or `dry_run_ready` with `mutation_mode: versioned_proposal_only`.
- Product answer responses expose the side-by-side baseline/system model, a
  verification panel, a failure state panel, and suggested next actions.
- Missing or unsupported inputs fail fast with explicit errors instead of
  silently selecting a substitute route.

## Routes

| Method | Path | Purpose | Key response notes |
|---|---|---|---|
| POST | `/api/onboarding/run` | Start or record an onboarding scan request for approved local files/test fixtures. | Returns `status: accepted`, `scan_allowed: true`, `production_connections_allowed: false`, and `audit_id`. |
| POST | `/api/confirmation/session` | Open a reverse-question / confirmation session. | Returns `session_id`, the active reverse questions, and `audit_id`. |
| POST | `/api/confirmation/answer` | Record a human answer without mutating the approved pack. | Returns `status: recorded`, `pack_mutated: false`, `promotion_required: true`, and `audit_id`. |
| POST | `/api/pack/promote` | Validate promotion preconditions; versioned promotion remains explicit. | Returns `blocked` when approval is missing; otherwise `dry_run_ready` with `mutation_mode: versioned_proposal_only` and `audit_id`. |
| POST | `/api/product/answer` | Return side-by-side baseline/system answer UI model. | Returns the answer comparison view model, including baseline/system panels, verification, failure state, and `execution_allowed: false`. |
| POST | `/api/product/compare-sql` | Compare baseline and system SQL text without running either. | Returns the SQL comparison model and keeps execution disabled. |
| POST | `/api/eval/run` | Produce product readiness/evidence summary. | Returns `status: completed`, `domain_targets`, `missing_evidence`, `execution_allowed: false`, and `audit_id`. |
| POST | `/api/failure-review/run` | Run red-team failure scenario review. | Returns `status: completed`, pass/fail counts, failure details, `execution_allowed: false`, and `audit_id`. |

## Payload examples

See `docs/api/OPENAPI_LIKE.yaml` and `docs/api/examples/` for request payload
shapes and example bodies.
