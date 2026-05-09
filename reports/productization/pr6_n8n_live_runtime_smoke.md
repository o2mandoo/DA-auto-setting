# PR-6 n8n Live Runtime Smoke Evidence

Date: 2026-05-10 KST
Status: PASS
Runner: Docker `n8nio/n8n:2.19.5`

## Summary

A real n8n runtime smoke was executed with Docker. The smoke started the local product HTTP adapter, imported all five n8n workflow JSON templates, executed each imported workflow with `n8n execute --id=...`, and verified the product adapter audit log.

This is live n8n runtime evidence, not a Python-only simulation.

## Command run

```bash
make n8n-live-smoke N8N_LIVE_OUT=runtime/n8n_live_smoke/final_check
```

## Live runtime result

```text
status: passed
workflows imported: 5
workflows executed: 5
errors: []
missing_routes: []
```

Executed workflow IDs from the live n8n database:

```text
UDfvUq97I1aqftEb
E1LMHjVTyXgXI7lS
leEO1OYojinxzR8k
b8eX6uax536Sbdko
VeN4frOzpAv6f53a
```

## Observed product API routes from live n8n execution

The product adapter audit log recorded:

```text
GET /readyz
POST /api/confirmation/answer
POST /api/confirmation/session
POST /api/eval/run
POST /api/failure-review/run
POST /api/onboarding/run
POST /api/pack/promote
POST /api/product/answer
POST /api/product/compare-sql
```

`POST /api/product/answer` appeared multiple times because the failure-safe workflow intentionally covers multiple answer/failure scenarios.

## Safety checks

The live smoke report recorded all of these as true:

```text
execution_allowed_false_in_audit: true
expected_product_api_routes_called: true
no_db_credentials_or_raw_pii_literals: true
no_direct_sql_connector_nodes: true
no_raw_pii_in_audit: true
product_adapter_live: true
workflow_json_safe: true
```

Additional static scans:

```text
rg -n -i "postgres://|mysql://|mongodb://|password|secret|token|api_key|apikey|authorization|bearer |n8n-nodes-base\.(postgres|mysql|mssql|sqlite|mariadb|oracledb|snowflake)" n8n/workflows
=> no credential-like or direct SQL connector hits

rg -n "execute_query|/api/execute" packages n8n scripts tests
=> no implementation-surface hits; only guard/report/test references
```

## Non-silent fallback / environment notes

- Local `npx n8n@2.19.5 --version` was attempted and failed under Node v25 during native dependency installation (`isolated-vm`). This failure is not hidden.
- Docker was available and used as the explicit live n8n runtime path.
- n8n 2.x denied workflow expression access to environment variables on the first smoke attempt. The smoke runner now sets `N8N_BLOCK_ENV_ACCESS_IN_NODE=false` explicitly. The first failure was observed during live debugging and is documented in `docs/demo/N8N_LIVE_RUNTIME_SMOKE.md`; the current live artifact is under `runtime/n8n_live_smoke/final_check`.
- The Docker container calls the host adapter through `http://host.docker.internal:8765`.

## PR-6 evaluation

- n8n is an orchestration/demo wrapper only: PASS.
- n8n calls product API/adapter routes: PASS, proven by live adapter audit.
- n8n does not duplicate semantic logic: PASS, workflow templates contain HTTP orchestration only.
- n8n does not execute SQL directly: PASS.
- n8n contains no DB credentials: PASS.
- n8n contains no raw PII examples: PASS.
- n8n does not mutate Semantic Pack source of truth: PASS; pack promotion remains a product API dry-run/versioned proposal path.
- API failure visibility: PASS, failure-safe workflow executed through product API routes and preserves visible failure-state surfaces.
- backend/comment mode/source status/warnings visibility: PASS at template/API contract level; live runtime route execution is proven.
- real/no/synthetic comment distinction: PASS at workflow/API contract level.
- baseline SQL vs system SQL comparison: PASS, live route `/api/product/compare-sql` observed.
- safe failure states: PASS, live routes `/api/product/answer` and `/api/failure-review/run` observed.
- no production `execute_query` route: PASS.

## Remaining risk

This smoke proves local live n8n runtime execution through Docker. It does not prove a long-running production n8n deployment, user login flow, external credential storage, or production webhook exposure.

## Whether PR-7 may start

Yes. PR-7 may start as CI/release-packet work with this live n8n runtime evidence included. Production release claims still require the final release packet to preserve the evidence/limitation distinction.
