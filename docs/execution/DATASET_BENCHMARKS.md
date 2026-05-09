# Dataset Benchmarks for Phase 11

This document defines the repository-local benchmark dataset surface used by
the Phase 11 evaluation harness and dataset-manifest follow-up.

## Available local datasets

The current deterministic executable benchmark baseline is the demo revenue
fixture under `examples/demo_data`:

- `examples/demo_data/users.csv`
- `examples/demo_data/payments.json`
- `examples/demo_data/subscriptions.xlsx`

The benchmark manifest in `eval/datasets/demo_company_revenue.yaml` binds those
files to the semantic pack:

- `semantic_packs/demo_company/revenue.v0_1.yaml`

Additional repo-local reference datasets now run through the generic
file-corpus benchmark path. Semantic-gold question coverage is still explicit
and can be skipped when a curated pack mapping is unavailable, but the
manifests themselves are runnable:

- `eval/datasets/tableau_superstore.yaml`
  - source: `docs/reference/test_datasets/tableau_superstore/Sample - Superstore.xls`
  - current role: runnable legacy `.xls` file-corpus benchmark target
- `eval/datasets/sinagong_tableau_2026.yaml`
  - source: `docs/reference/test_datasets/sinagong_tableau_2026/**`
  - current role: runnable broad Korean file-corpus benchmark manifest

Template-only manifests, such as `eval/datasets/postgresql_fixture_template.yaml`,
remain explicit skips instead of pretending to execute a live database.

The planned domain split remains documented in
`docs/execution/WEAVIATE_AND_MULTI_DOMAIN_BENCHMARK_PLAN.md` and
`docs/execution/VALIDATION_DATASETS.md`.

## Manifest policy

- `dataset_id`, `domain`, `tables`, `files`, `expected_semantic_findings`,
  `must_generate_questions`, `must_block`, `golden_questions`, and
  `red_team_cases` must be present in each manifest.
- Manifests must reference only files that actually exist in the repository.
- Do not invent external datasets or placeholder files as if they were local
  benchmark assets.
- PII-like values must not be embedded in benchmark manifests or docs.

## Explicit fallback policy

If an external dataset is requested but not available in the repository, the
correct fallback is to document the required path/template explicitly and stop.
Do not silently substitute a different dataset.

If the missing or failing path is resolvable within the current scope, fix the
cause before falling back. Examples:

- copy an approved missing fixture into `docs/reference/test_datasets/**`;
- correct a stale manifest path;
- install an optional parser dependency outside the repository working tree;
- retry a failed CLI invocation with the corrected syntax.

Only use a fallback/skip after recording the attempted remediation, the reason
it could not be completed safely, the fallback/skip chosen, and the evidence.

## Current benchmark coverage

Executable today:

- Column profiling: safe top-N, null ratio, cardinality, and PII candidate detection
- Reverse-question generation: ambiguous terms, joins, metrics, and policy/PII confirmations
- Golden question: monthly new customer revenue
- Red-team safety: blocked PII request
- Red-team safety: destructive SQL request
- Retrieval/search: keyword lookup over demo pack and generated draft pack

Planned before multi-domain-ready status:

- Superstore file-corpus benchmark that scans `Orders`, `People`, and `Returns`
  as separate workbook tables while preserving explicit semantic-gold skips
  when no curated pack mapping exists.
- At least five Sinagong domain manifests, with at least three domains running
  through scan/profile/draft/retrieval/safety checks.
- Optional live Weaviate verification that is environment-gated and clearly
  distinguished from fake/no-config tests.

## Validation notes

- Dataset manifest tests should verify that every listed file exists.
- Reported benchmark results must stay transport-free unless a separate task
  explicitly adds execution transport.
- Benchmark artifacts must not capture raw PII values, even when a red-team case
  intentionally asks for them.
