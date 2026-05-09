# PR-6 n8n / Local Workflow Smoke

Date: 2026-05-09 KST
Team: execute-pr-6-n8n-loca-634f3d99
Status: PASS, with explicit remaining live-n8n limitation

## Verdict

PR-6 local workflow smoke passes for the repository-local product API / n8n template surface.

The n8n workflows remain orchestration/demo wrappers over product API routes. They do not own Semantic Pack truth, do not include direct DB connectors, do not include DB credentials, do not execute SQL, and do not include raw PII examples.

PR-7 may start only as a constrained CI/release-packet lane. Production release readiness is still not proven because live imported n8n runtime execution was not performed in this phase.

## Changed files

```text
M docs/demo/N8N_WORKFLOW_REQUIREMENTS.md
M docs/product/BASELINE_COMPARISON_SPEC.md
M experiments/db_fixtures/scripts/fixture_modes.py
M n8n/README.md
M n8n/workflows/01_onboarding_demo.json
M n8n/workflows/02_confirmation_pack_promotion.json
M n8n/workflows/03_query_runtime_comparison_demo.json
M n8n/workflows/05_failure_review_loop.json
M packages/semantic_registry/semantic_registry/product/baseline.py
M packages/semantic_registry/semantic_registry/product/comparison.py
M packages/semantic_registry/semantic_registry/product/evidence.py
M packages/semantic_registry/semantic_registry/product/scenarios.py
M reports/final/20_domain_benchmark_summary.json
M reports/final/20_domain_benchmark_summary.md
M reports/final/final_capability_matrix.md
M reports/final/known_failure_patterns.md
A reports/productization/pr6_n8n_local_workflow_smoke.md
M tests/fixtures/test_db_fixture_comment_modes.py
M tests/product/test_n8n_workflow_templates.py
M tests/product/test_phase19_product_api_contract.py
```

Scope repair performed by leader after team completion:
- reverted out-of-scope product UI / local demo / e2e changes that were not required for PR-6;
- fixed the phase-18 evidence console so the benchmark-only `semantic_gold.v0_1.yaml` support pack is not counted as a 21st domain target;
- regenerated final evidence reports with 20 domain targets.

## Workflow templates

The PR-6 n8n workflow set is:

1. `n8n/workflows/01_onboarding_demo.json` — DB-backed onboarding demo.
2. `n8n/workflows/02_confirmation_pack_promotion.json` — comment-aware reverse-question and human confirmation / pack promotion demo.
3. `n8n/workflows/03_query_runtime_comparison_demo.json` — query runtime with baseline vs system SQL comparison.
4. `n8n/workflows/04_20_domain_benchmark_runner.json` — 20-domain/fixture benchmark runner.
5. `n8n/workflows/05_failure_review_loop.json` — failure-safe demo.

All workflow JSON files validate with `python -m json.tool`.

## Product API routes used by n8n

The templates call product API / adapter routes only:

- `POST /api/onboarding/run`
- `POST /api/confirmation/session`
- `POST /api/confirmation/answer`
- `POST /api/pack/promote`
- `POST /api/product/answer`
- `POST /api/product/compare-sql`
- `POST /api/eval/run`
- `POST /api/failure-review/run`

No n8n workflow owns semantic logic or mutates Semantic Pack truth directly. Promotion is represented as a product API call after human confirmation.

## Visible semantic context and failure states

The local template/API/test surface demonstrates:

- DB-backed onboarding flow.
- `real_db_comment` available as draft semantic context when present.
- `no_comment` represented as metadata gaps / reverse questions.
- `test_only_synthetic_comment` visibly marked fixture-only and not approved product truth.
- baseline generic SQL vs system SQL comparison with `not_executed` semantics.
- visible failure states:
  - ambiguity clarification;
  - PII blocked;
  - unsafe SQL blocked;
  - missing context;
  - draft/comment-only warning.

## Safety checks

Static/template safety checks passed:

- no direct SQL connector node in n8n workflow JSON;
- no workflow DB credentials or production DSNs;
- no raw PII examples in workflow JSON;
- no `/api/execute_query`, `def execute_query`, or `execute_query(` implementation surface in checked packages/n8n/scripts/semantic_packs;
- n8n does not bypass SQL Guard;
- baseline SQL is compared/profiled, not executed;
- source-of-truth remains product API / Registry, not n8n.

## Tests run

Environment:

```text
make env-check
=> environment ok: 3.14.4
```

Focused n8n/API/security verification:

```text
.venv/bin/python -m pytest -q \
  tests/product/test_n8n_workflow_templates.py \
  tests/product/test_phase19_product_api_contract.py \
  tests/product/test_phase20_n8n_readiness.py \
  tests/security
=> 25 passed in 1.03s
```

Requested product/security suite with explicit fallback because `tests/api` is absent in this checkout:

```text
tests/api directory absent; running tests/product tests/security instead (logged fallback).
.venv/bin/python -m pytest -q tests/product tests/security
=> 55 passed in 6.35s
```

Phase-18 evidence-console repair verification:

```text
.venv/bin/python -m pytest -q tests/product/test_phase18_evidence_console.py
=> 3 passed in 0.08s
```

Full repository tests:

```text
make test
=> 376 passed, 2 skipped in 72.72s
```

Template / forbidden-surface scans:

```text
python -m json.tool n8n/workflows/*.json
=> json-templates-ok

rg -n "def execute_query|execute_query\(|/api/execute_query" packages n8n scripts semantic_packs
=> no-execute-query-hit

rg -n "postgres://|mysql://|password|secret|token|api_key|Authorization" n8n/workflows
=> no-credential-hit
```

## Non-silent fallback / process notes

- Team launch used a detached 240x80 tmux session because the active 209x51 pane was likely too small for six worker panes. This was logged before launch.
- `omx team api send-message` used `hook_timeout_fallback_confirmed:tmux_send_keys_sent` for one leader-to-worker dispatch. This was visible in command output.
- `tests/api` does not exist in this checkout. The verifier did not pretend it ran; it ran `tests/product tests/security` and the product API contract tests instead.
- Worker-5 spawned native child probes despite the leader's no-subagent instruction; one child probe hit a spark-model usage limit. The final leader verification did not rely on that probe as proof.
- After team completion, leader removed out-of-scope UI/local-demo/e2e changes and fixed the evidence-console 20-domain counting issue before final validation.

## Remaining risks

- Live imported n8n runtime execution is still not proven; this phase proves repository-local workflow template/API smoke only.
- No external n8n server, webhook execution transcript, or screenshot artifact is attached yet.
- PR-7 must preserve the no-production-`execute_query`, no-raw-PII, no-silent-fallback, and source-of-truth boundaries.

## Whether PR-7 may start

Yes, with gates.

PR-7 may start as a CI/release-packet lane only. It must not claim production readiness until live n8n import/runtime smoke and release evidence are attached.
