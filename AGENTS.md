# AGENTS.md — semantic-data-context

This file applies to this repository tree.

## Phase 0 boundary

Phase 0 is limited to:

- `packages/semantic_contracts/**`
- `semantic_packs/demo_company/**`
- `tests/contracts/**`
- documentation needed to explain the Phase 0 boundary

Do **not** implement Registry, MCP runtime, Builder runtime, UI, database execution, or an `execute_query` capability in Phase 0.

## Semantic Pack fixture requirements

The demo pack at `semantic_packs/demo_company/revenue.v0_1.yaml` must represent the required Phase 0 revenue fixture entities:

- `table.users`
- `table.payments`
- `term.new_customer`
- `metric.net_revenue`
- `join.users_payments`
- a policy for `marketing_analyst`
- `verified_query.monthly_new_customer_revenue`

PII-like user fields such as `users.email`, `users.phone`, and `users.name` must be represented as blocked columns and must not have raw value dictionaries.

## Verification

Before claiming completion, run the contract tests with dependencies available, for example:

```bash
PYTHONDONTWRITEBYTECODE=1 \
PYTHONPATH=/tmp/semantic-data-context-deps:packages/semantic_contracts \
python3 -m unittest discover -s tests/contracts -v
```

If local dependencies are missing, install them outside the repository working tree (for example under `/tmp`) rather than vendoring generated dependency files into this repo.

## Global execution rules

### No silent fallback

Do not perform a fallback silently. If a preferred path, command, dependency, tool, file location, or runtime is unavailable and a fallback is used, record it explicitly in the worker report, final report, or a relevant project log.

Before accepting a fallback, check whether the blocker is resolvable within the
current scope and environment. If it is safe and in scope to fix the blocker,
fix or improve it first, then rerun the preferred path. Use a fallback only when
the preferred path cannot be restored safely within the current task boundary.

A fallback note must include:

- what was attempted first
- why it could not be used
- whether an in-scope remediation was attempted, applied, or rejected
- what fallback path was used instead
- what evidence confirms the fallback result

Examples:

- If pytest is unavailable and `unittest` is used, report that switch and the command output.
- If dependencies are installed under `/tmp`, report the temp path and why repo vendoring was avoided.
- If an OMX/team canonical state path is used instead of a local `.omx/state` path, report the canonical path used.
- If a validation script must use a different import path or environment variable, report the exact `PYTHONPATH`/command.

Examples of required remediation before fallback:

- If a missing documentation path or dataset count is wrong, align the markdown
  and rerun the inventory check before launching implementation work.
- If an optional dependency is needed for a declared fixture and can be installed
  outside the repository, install it in a temp dependency path and report that
  path instead of silently skipping the fixture.
- If a command failed because the CLI syntax changed, retry with the corrected
  syntax and record both the failed command and the corrected command.
- If Weaviate is explicitly selected but unavailable, do not keyword-fallback.
  Return an explicit Weaviate/config error; only run keyword checks when the
  caller explicitly selects the keyword backend.

### Required comments and rationale notes

Add comments or short rationale notes when code contains non-obvious decisions, safety boundaries, or intentional limitations. Prefer concise comments near the relevant code over broad explanatory prose.

Comments are required for:

- safety boundaries such as no SQL execution, no raw PII storage, no VDB, no MCP runtime, or no external database
- fallback branches or compatibility shims
- deliberately simple MVP logic that might otherwise look incomplete
- validation rules that encode product policy, especially PII and blocked-column behavior

Do not add noisy comments that merely restate obvious Python syntax. Comments should explain why the code exists or why a safer/simple path was chosen.

### Dataset-aware verification

When a phase changes Builder, profiling, semantic draft generation, retrieval, or
validation behavior, do not rely only on tiny synthetic fixtures if broader
local datasets are available. Add a bounded verification pass using one or more
repo/reference datasets when it materially improves confidence.

Known local dataset sources include:

- `examples/demo_data/**` for minimal deterministic smoke tests
- `docs/reference/test_datasets/**` for copied/local reference datasets
- `/Users/jtm427/Documents/내 Tableau 리포지토리/데이터 원본/2025.2/ko_KR-APAC/Sample - Superstore.xls`
- `/Users/jtm427/Desktop/경영정보시각화 능력/2026 시나공_경영정보시각화능력_실기_태블로_실습 및 예제파일/**`

Dataset verification must stay non-destructive and PII-safe:

- read source files only; do not mutate external source dataset locations
- write generated scan/profile/draft artifacts under `runtime/**` or an
  explicitly assigned output path
- never store or embed raw PII values
- report which dataset was used, why it was selected, and whether any connector
  limitation prevented using it

### Weaviate/VDB planning boundary

The intended VDB baseline is Weaviate, but VDB implementation is not assumed by
earlier phases. Before adding Weaviate code, define and verify:

- the semantic text projection format to index
- which fields are explicitly excluded from indexing because of PII/policy
- local/offline test strategy and fallback behavior when Weaviate is unavailable
- how keyword search remains available without silently pretending VDB coverage
