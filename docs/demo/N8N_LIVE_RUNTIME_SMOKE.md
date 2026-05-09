# n8n Live Runtime Smoke

This repo supports a real n8n runtime smoke using Docker. It is intentionally separate from product features: the smoke proves that imported n8n workflows call the product HTTP adapter and do not become a source of truth.

## Command

```bash
make n8n-live-smoke
```

Equivalent direct command:

```bash
.venv/bin/python scripts/n8n/live_runtime_smoke.py \
  --image n8nio/n8n:2.19.5 \
  --out runtime/n8n_live_smoke/latest
```

## What it does

1. Starts the local stdlib product HTTP adapter on `0.0.0.0:8765`.
2. Runs the official `n8nio/n8n:2.19.5` Docker image.
3. Imports all workflow JSON files from `n8n/workflows/` into n8n.
4. Executes each imported workflow with `n8n execute --id=...`.
5. Reads the product adapter audit log to prove the live n8n runtime called these routes:
   - `POST /api/onboarding/run`
   - `POST /api/confirmation/session`
   - `POST /api/confirmation/answer`
   - `POST /api/pack/promote`
   - `POST /api/product/answer`
   - `POST /api/product/compare-sql`
   - `POST /api/eval/run`
   - `POST /api/failure-review/run`
6. Fails closed if an expected route is missing or if any workflow execution fails.

## Safety boundary

The smoke verifies:

- n8n calls product API/adapter routes only;
- n8n workflow JSON contains no DB connector nodes;
- n8n workflow JSON contains no DB credentials or production DSNs;
- n8n workflow JSON contains no raw PII examples;
- product adapter audit records `execution_allowed=false`;
- no raw email-like PII is present in the product adapter audit;
- n8n does not mutate Semantic Pack source of truth directly.

## Non-silent environment notes

- `npx n8n@2.19.5` was probed on the local Node v25 environment and failed during native dependency installation (`isolated-vm`). The supported live path in this repo is therefore Docker-based.
- n8n 2.x blocks environment-variable access inside nodes by default. The Docker smoke sets `N8N_BLOCK_ENV_ACCESS_IN_NODE=false` explicitly so workflow expressions can read `SDC_PRODUCT_API_BASE_URL` and `SDC_DEMO_KEY`. This is a documented smoke-run setting, not a hidden fallback.
- The container reaches the host adapter through `http://host.docker.internal:8765`.

## Artifacts

By default the smoke writes:

- `runtime/n8n_live_smoke/latest/live_smoke_report.json`
- `runtime/n8n_live_smoke/latest/live_smoke_report.md`
- `runtime/n8n_live_smoke/latest/product_api_audit/audit.jsonl`
- `runtime/n8n_live_smoke/latest/logs/*`

These runtime artifacts are evidence outputs and are not product source of truth.
