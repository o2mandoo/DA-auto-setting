# Phase 9 Safe Preview Query Execution — verifier report

Status: **PASS — Phase 9 acceptance is green for the local preview flow.**

Verifier lane: `worker-1`, explicit task `15`.

## Scope and boundary checked

- `preview_query` is allowed only for local/demo validation-gated preview.
- Production `execute_query` remains forbidden.
- SQL is validation-gated, SELECT-only, single-statement, role/table policy constrained, row-limited, audited, and PII-safe.
- This report records fallback paths explicitly; no fallback is silent.

## Current PASS evidence

| Check | Result | Evidence |
| --- | --- | --- |
| PII columns represented as blocked contract fields | PASS | `semantic_packs/demo_company/revenue.v0_1.yaml` marks `users.email`, `users.phone`, `users.name` as `pii.is_candidate=true`, `raw_value_storage=blocked`, and policy `blocked_columns` includes all three. |
| PII value dictionaries absent | PASS | `tests/contracts/test_pii_policy_contract.py` and `tests/contracts/test_demo_pack_loading_validation.py` both pass. |
| SQLGuard blocks blocked PII projections | PASS | `tests/registry/test_preview_safety.py` and `tests/registry/test_sql_guard.py` cover blocked-column validation; current targeted run passed. |
| Registry preview blocks PII before row exposure | PASS | Direct smoke probe against `SafePreviewEngine` returned `ok=False`, `validation_present=True`, `validation.valid=False`, `error=Blocked columns referenced: users.email`, and no preview rows. |
| Valid non-PII preview works and truncates | PASS | Direct smoke probe on `SELECT payment_id, amount FROM payments ORDER BY payment_id` returned `ok=True`, `row_count=2`, `truncated=True`, `validation_valid=True`, `audit_records=1`. |
| SQL without LIMIT is limited automatically | PASS | `tests.registry.test_preview_safety` and `tests.registry.test_duckdb_preview` both pass; direct probe showed `row_count=2`, `truncated=True`, and an audit record was written. |
| Preview without caller validation internally validates first | PASS | Direct smoke probe with `validation_id=None` returned internal SQLGuard validation (`validation_valid=True`) and blocked PII SQL before row exposure. |
| Local preview adapter registers demo CSV/JSON and limits rows | PASS | `tests.registry.test_duckdb_preview` passes. |
| Preview safety/audit tests pass | PASS | `tests.registry.test_preview_models`, `tests.registry.test_preview_safety`, and `tests.registry.test_duckdb_preview` all passed in the latest run. |
| MCP preview tool contract stays validation-gated | PASS | `tests.mcp.test_preview_query` passed in the latest run, including registration and explicit row-limit assertions. |
| No production `execute_query` definitions/calls | PASS | `grep -RIn "def execute_query\|execute_query[[:space:]]*=\|execute_query(" packages semantic_packs tests` returned no hits. |
| Syntax/type-shape smoke | PASS | `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m compileall -q packages/semantic_contracts/semantic_contracts/execution_contracts.py packages/semantic_registry/semantic_registry/execution packages/semantic_mcp/src/semantic_mcp tests/registry/test_preview_models.py tests/registry/test_preview_safety.py tests/registry/test_duckdb_preview.py tests/mcp/test_preview_query.py` completed successfully. |
| Lint on modified / relevant files | PASS | `/tmp/semantic-data-context-deps/bin/ruff check ...` completed with `All checks passed!`. |

## Commands run

### Targeted Phase 9 verification suite

```bash
PYTHONDONTWRITEBYTECODE=1 \
.venv/bin/python -m unittest \
  tests.registry.test_preview_models \
  tests.registry.test_preview_safety \
  tests.registry.test_duckdb_preview \
  tests.mcp.test_preview_query -v
```

Result: PASS, 21 tests OK.

### Contract suite

```bash
PYTHONDONTWRITEBYTECODE=1 \
.venv/bin/python -m unittest discover -s tests/contracts -v
```

Result: PASS, 20 tests OK.

### Lint

```bash
/tmp/semantic-data-context-deps/bin/ruff check \
  packages/semantic_contracts/semantic_contracts/execution_contracts.py \
  packages/semantic_registry/semantic_registry/execution/__init__.py \
  packages/semantic_registry/semantic_registry/execution/local_preview.py \
  packages/semantic_registry/semantic_registry/execution/models.py \
  packages/semantic_registry/semantic_registry/execution/preview.py \
  tests/registry/test_preview_models.py \
  tests/registry/test_preview_safety.py \
  tests/registry/test_duckdb_preview.py \
  tests/mcp/test_preview_query.py \
  reports/phases/phase9_safe_preview_query_execution.md
```

Result: PASS, `All checks passed!`.

### Compile / syntax smoke

```bash
PYTHONDONTWRITEBYTECODE=1 \
.venv/bin/python -m compileall -q \
  packages/semantic_contracts/semantic_contracts/execution_contracts.py \
  packages/semantic_registry/semantic_registry/execution \
  packages/semantic_mcp/src/semantic_mcp \
  tests/registry/test_preview_models.py \
  tests/registry/test_preview_safety.py \
  tests/registry/test_duckdb_preview.py \
  tests/mcp/test_preview_query.py
```

Result: PASS.

### End-to-end smoke

```python
from semantic_registry.execution import InMemoryPreviewAuditLog, PreviewRequest, SafePreviewEngine
```

Result: PASS. Safe preview returned 2 rows for approved demo payments data, truncated to the limit, and a blocked PII preview returned no rows with a validation error.

## Explicit fallback notes

1. Attempted first: repository-local mailbox path `.omx/state/team/execute-phase-9-only-63d0350b/workers/worker-1/inbox.md`.
   - Why unavailable: the durable mailbox lives under the canonical OMX team state root, not the repo-local mirror.
   - Fallback used: `/Users/jtm427/.omx-runs/run-20260508104302-7a25/.omx/state/team/execute-phase-9-only-63d0350b/workers/worker-1/inbox.md` and `omx team api mailbox-list`.
   - Evidence: inbox was read successfully from the canonical path and team APIs confirmed no pending mailbox work.
2. Attempted first: plain `python3` / repo-local import path.
   - Why unavailable in earlier verifier history: missing `pydantic` / path masking issues.
   - Fallback used: `.venv/bin/python` with local package paths and `/tmp/semantic-data-context-deps` for lint.
   - Evidence: latest tests, compileall, and ruff all passed.
3. Attempted first: git commit per worker protocol.
   - Why unavailable: this workspace is not a git repository (`fatal: not a git repository`).
   - Fallback used: durable team task state plus this report and runtime evidence.
   - Evidence: current task state is completed via `omx team api transition-task-status` and the report is stored in repo.

## Phase 9 acceptance conclusion

- **Task 8 PII behavior:** PASS. PII is explicit as block-not-mask: blocked PII columns fail validation and preview, no rows are returned, and audit stores failure reason plus SQL fingerprint rather than raw SQL.
- **Overall Phase 9:** PASS. The local preview path is validation-gated, row-limited, auditable, and production `execute_query` remains absent.
- **Phase 10 may start:** Yes, from the verifier perspective Phase 9 acceptance is now green.
