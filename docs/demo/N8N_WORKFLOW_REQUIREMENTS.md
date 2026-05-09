# n8n Workflow Requirements

n8n workflows are demo/orchestration wrappers around the Product API. They must not become the source of truth or implement their own safety logic.

## Workflow 01 — Onboarding Demo

- Calls `POST /api/onboarding/run`.
- Accepts dataset id and source root placeholders.
- Shows scan/profile/build-pack commands as next actions.
- Does not connect to production data sources.

## Workflow 02 — Comment-aware Reverse Question Demo + Pack Promotion

- Calls `POST /api/confirmation/session`.
- Presents reverse questions to a human reviewer.
- Calls `POST /api/confirmation/answer`.
- Calls `POST /api/pack/promote` only with explicit approval metadata.
- Must not mutate approved packs in place.

## Workflow 03 — Query Runtime + Baseline/System Comparison

- Calls `POST /api/product/answer`.
- Optionally calls `POST /api/product/compare-sql` for direct SQL comparison demos.
- Displays baseline not-executed status, semantic definitions, verification, failure state, and suggested actions.
- Must not run SQL directly.

## Workflow 04 — 20-Domain Benchmark Runner

- Calls `POST /api/eval/run`.
- Reads generated evidence reports.
- Shows missing evidence explicitly.
- Must not invent per-domain pass rates.

## Workflow 05 — Failure-safe Demo

- Calls `POST /api/failure-review/run`.
- Routes failures to review/remediation.
- Keeps red-team cases and failure states auditable.

## Safety gates every workflow must preserve

- Use placeholder demo header only; no checked-in credentials.
- No raw PII in sample payloads.
- No production SQL execution.
- No silent fallback routing.
- If an API reports failure, n8n must display it rather than branching to an unlabelled substitute.
