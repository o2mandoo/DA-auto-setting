# PR-6 n8n Local Workflow Smoke and Safety Sweep

Date: 2026-05-09 KST
Owner: worker-6
Task: Final PR-6 verifier report and safety sweep

## Verdict

**PASS, with one explicit repository-level caveat.**

The PR-6 n8n workflow templates, product API contract, and security boundaries are present and verified locally. The n8n surface remains an orchestration/demo wrapper over product APIs; it does not implement direct SQL execution, DB credentials, raw PII handling, or source-of-truth mutation. The only failing evidence encountered in this run is an unrelated full-suite regression in `tests/product/test_phase18_evidence_console.py` when running `make test`; the PR-6 focused verifier suites pass.

## Changed files

- `reports/productization/pr6_n8n_local_workflow_smoke.md` — new standalone verifier report for PR-6.

No product source files were changed in this verifier task.

## Verification run

### Environment check

Command:

```bash
make env-check
```

Result: **PASS**

Output:

```text
environment ok: 3.14.4
```

### Focused PR-6 verification suites

Command:

```bash
PYTHONPATH=packages/semantic_contracts:packages/semantic_registry:packages/semantic_builder/src:packages/semantic_mcp/src:/tmp/semantic-data-context-deps \
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q \
  tests/product/test_phase19_product_api_contract.py \
  tests/product/test_phase20_n8n_readiness.py \
  tests/security \
  tests/product/test_n8n_workflow_templates.py
```

Result: **PASS**

Output:

```text
21 passed in 1.13s
```

### Full repository smoke

Command:

```bash
make test
```

Result: **FAIL**

Observed failure:

- `tests/product/test_phase18_evidence_console.py`
- symptom: the repo-level benchmark summary currently reports `21` domain summaries, while that test expects `20`

This is outside the PR-6 n8n smoke scope, but it is concrete evidence that the whole repository is not fully green.

## Workflow templates inspected

The n8n workflow templates remain present and consistent with the product API boundary:

- `n8n/workflows/01_onboarding_demo.json`
- `n8n/workflows/02_confirmation_pack_promotion.json`
- `n8n/workflows/03_query_runtime_comparison_demo.json`
- `n8n/workflows/04_20_domain_benchmark_runner.json`
- `n8n/workflows/05_failure_review_loop.json`

The templates continue to call product API routes only, using the local adapter variables documented in `n8n/README.md`:

- `/api/onboarding/run`
- `/api/confirmation/session`
- `/api/product/answer`
- `/api/eval/run`
- `/api/failure-review/run`

## Visible failure states and safety boundaries

### Visible failure state

- `make test` exposes a real unrelated regression in `tests/product/test_phase18_evidence_console.py`.
- `tests/api` does not exist in this checkout, so the verifier used the actual API contract test file in `tests/product/test_phase19_product_api_contract.py` instead.

### Safety checks

Implementation-surface scan:

```bash
rg -n "def execute_query|execute_query\(|/api/execute_query" packages n8n scripts semantic_packs
```

Result: **PASS** — no implementation-surface hits.

Additional safety checks from the focused suites and scans:

- no workflow JSON contains DB credentials or production DSNs in the template surface;
- no direct SQL execution route is exposed by the checked implementation surface;
- no raw PII is introduced by the PR-6 n8n template surface;
- no silent fallback branch is introduced in the workflow templates;
- n8n remains a demo/orchestration wrapper, not the source of truth.

## Remaining risks

- Live imported n8n workflow runtime smoke is still not proven in this verifier pass.
- The repository-wide `make test` suite currently has an unrelated phase-18 failure that should be tracked separately.
- PR-6 should still be treated as a constrained smoke/evidence lane, not as production readiness.

## Whether PR-7 may start

**Yes, but only as a constrained CI/release-packet lane.**

The local PR-6 verifier evidence is now attached, but PR-7 still should not claim production release readiness. It may proceed for CI, observability, and release-packet work that preserves the same safety boundaries and does not reintroduce direct SQL execution, DB credentials, raw PII, or source-of-truth drift.

## Summary

PR-6 n8n smoke evidence is locally verified: the templates exist, the product API contract is intact, the safety tests pass, and the forbidden `execute_query` implementation surface is absent. The only failing evidence in this run is an unrelated repo-wide phase-18 benchmark summary regression in `make test`.
