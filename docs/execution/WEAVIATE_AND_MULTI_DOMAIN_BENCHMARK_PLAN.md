# Weaviate Optional Integration + Multi-domain Benchmark Expansion Plan

Date: 2026-05-09 KST

## Goal

Extend the current local-demo-ready Semantic Data Context System so benchmarks are no longer centered on only `demo_company.revenue` or Superstore. The next iteration should support:

1. optional live Weaviate indexing/search verification;
2. executable benchmark mappings for Tableau Superstore;
3. executable benchmark mappings for the Sinagong Tableau 2026 workbook corpus under:

```text
docs/reference/test_datasets/sinagong_tableau_2026/
```

The work remains validation-first: no production `execute_query`, no dashboard UI, no SaaS, no production DB credentials, no raw PII storage.

## Current repo facts

Relevant current surfaces:

- Weaviate / retrieval seam:
  - `packages/semantic_registry/semantic_registry/retrieval/backends.py`
  - `packages/semantic_registry/semantic_registry/retrieval/embeddings.py`
  - `packages/semantic_mcp/src/semantic_mcp/tools/search_context.py`
  - `tests/registry/test_vdb_backend.py`
  - `tests/mcp/test_search_context.py`
  - `docs/execution/RETRIEVAL_LAYER.md`
- Evaluation harness:
  - `packages/semantic_builder/src/semantic_builder/eval/runner.py`
  - `packages/semantic_builder/src/semantic_builder/eval/cli.py`
  - `packages/semantic_contracts/semantic_contracts/eval_contracts.py`
  - `eval/datasets/*.yaml`
  - `tests/eval/*`
- Data documentation:
  - `docs/execution/VALIDATION_DATASETS.md`
  - `docs/execution/DATASET_BENCHMARKS.md`
  - `docs/reference/test_datasets/DATASET_MANIFEST.md`
- Final limitation already recorded:
  - `reports/final/final_integration_report.md` says live Weaviate and non-demo benchmark mappings remain next work.

Observed dataset inventory from the repo:

- Superstore: `docs/reference/test_datasets/tableau_superstore/Sample - Superstore.xls`
- Sinagong: 20 `.xlsx` files under `docs/reference/test_datasets/sinagong_tableau_2026/`
  when counted recursively:
  - 16 top-level `.xlsx` workbooks
  - 4 nested yearly `.xlsx` workbooks under `와일드카드유니온실습/`
- Sinagong examples include HR, sales/customer, population/demographics, weather, subway ridership, Starbucks stores/purchase logs, online shopping transaction amounts, amusement park visitors, stock-like time series, delivery app usage.

Current benchmark mapping state:

| Surface | Current status | Required alignment before implementation |
|---|---|---|
| `eval/datasets/demo_company_revenue.yaml` | executable deterministic benchmark baseline | keep as Tier 0 regression |
| `eval/datasets/tableau_superstore.yaml` | validation-style manifest exists | promote to runnable file-corpus benchmark |
| `eval/datasets/sinagong_tableau_2026.yaml` | broad validation-style manifest exists | split into domain-specific manifests under `eval/datasets/sinagong/*.yaml` |
| `eval/datasets/sinagong/*.yaml` | not present yet | create at least five domain manifests |
| `tests/integration/test_weaviate_live_optional.py` | not present yet | add env-gated live Weaviate integration test |
| live Weaviate service | optional external service | skip only when env is absent; fail explicitly when env is set but service is unavailable |

## Design principles

1. **Benchmark by domain, not by one giant corpus.**
   - The Sinagong corpus should be split into domain benchmark manifests so failures are interpretable.
2. **Separate scanner benchmarks from semantic gold benchmarks.**
   - Some datasets can prove scan/profile/draft/retrieval safety before they have hand-authored golden semantic questions.
3. **Weaviate must be explicit.**
   - `backend=weaviate` must either use Weaviate or return a typed explicit error. It must never silently fall back to keyword search.
4. **Fallbacks must be remediated when in scope.**
   - If a fallback trigger is fixable within the current task boundary, fix it
     and rerun the preferred path. Only fallback/skip after recording the
     attempted remediation, reason, fallback/skip path, and evidence.
5. **Generated draft packs stay draft.**
   - Benchmark generation can create draft packs under `runtime/benchmarks/**`; it must not mutate approved demo packs.
6. **PII safety is a first-class benchmark result.**
   - HR/customer/person-like files must prove raw value suppression in profiles, draft packs, retrieval documents, eval reports, and Weaviate payloads.
7. **Optional live services are opt-in.**
   - Default test suite must pass without a live Weaviate server. Live tests run only when explicit env config is present.

## Proposed benchmark tiers

### Tier 0 — Existing fast demo baseline

Keep existing:

- `eval/datasets/demo_company_revenue.yaml`
- `scripts/demo/run_local_demo.py`

Purpose:

- fast regression baseline
- MCP/query/runtime/preview/eval smoke

### Tier 1 — Superstore executable benchmark

Promote Superstore from validation-style manifest to runnable benchmark mapping.

Proposed manifest:

```text
eval/datasets/tableau_superstore.yaml
```

Expected coverage:

- `.xls` connector and per-sheet table split: `Orders`, `People`, `Returns`
- sales/profit/order/customer/product/region/cardinality profiles
- draft pack generation from workbook profiles
- reverse questions for ambiguous date basis, return handling, profit definition, region/person mapping
- retrieval search over generated draft cards
- SQL guard/red-team: mutating SQL blocked, raw customer fields blocked when detected

Do not require a perfect SQL planner for Superstore yet. The first runnable benchmark should be a builder/retrieval/safety benchmark, not a verified-query benchmark.

### Tier 2 — Sinagong representative domain benchmark set

Split the Sinagong corpus into multiple executable manifests. Recommended first set:

1. `sinagong_seil_sales`
   - file: `SEILOneCompany_Sales데이터.xlsx`
   - sheets: `결제내역`, `고객정보`
   - focus: sales/payment metrics, customer join key, customer PII blocking
2. `sinagong_seil_hr`
   - file: `SEILOneCompany_HR데이터.xlsx`
   - sheet: `직원현황`
   - focus: HR/person PII, employment status/date semantics, strict raw-value suppression
3. `sinagong_population_demographics`
   - files: `우리나라인구수_2021_2024.xlsx`, `시도별연간인구수.xlsx`, or `2008_2024_연령별인구현황.xlsx`
   - focus: public demographic time series, year/month sheet splitting, wide/narrow table shapes
4. `sinagong_weather_timeseries`
   - file: `서울날씨_최고기온.xlsx`
   - focus: year sheets, month/day matrix, time-series profiling
5. `sinagong_subway_ridership`
   - file: `서울지하철승하차인원.xlsx`
   - focus: large row count, station/line categories, ridership metrics
6. `sinagong_starbucks_stores`
   - file: `스타벅스매장데이터.xlsx`
   - focus: multi-region sheets, geo columns, store/address PII-like boundary
7. `sinagong_online_shopping`
   - file: `온라인쇼핑몰_판매매체별_상품군별거래액_2017_2024.xlsx`
   - focus: wide monthly transaction matrix, product/category/media dimensions

Optional later additions:

- `sinagong_delivery_app_usage`
- `sinagong_everland_visitors`
- `sinagong_starbucks_purchase`
- `sinagong_stock_like_appliance_series`

## Benchmark runner changes

### A. Add generic file-corpus benchmark mapping

Current gap: `semantic_builder.eval.runner._benchmark_manifest_from_contract_payload()` only maps `demo_company.revenue` into executable benchmark cases.

Add a generic path for dataset manifests with file inputs:

- Load manifest YAML.
- Verify every referenced file exists.
- Scan files using Builder connector.
- Profile columns.
- Generate deterministic hypotheses/questions with mock provider.
- Build a draft Semantic Pack under `runtime/benchmarks/<dataset_id>/semantic_pack.draft.yaml`.
- Validate the draft pack with `semantic_contracts`.
- Build retrieval documents from the draft pack.
- Run manifest-defined expectations:
  - expected sheet/table names present
  - expected semantic findings appear in hypotheses/cards/questions
  - expected PII-block columns are detected
  - no raw PII-like strings appear in generated artifacts
  - red-team mutating SQL cases fail closed

Recommended new internal concepts:

- `FileCorpusBenchmarkCase`
- `BenchmarkArtifactSet`
- `run_file_corpus_benchmark(manifest)`
- `write_benchmark_artifacts(dataset_id, artifacts)`

### B. Keep semantic-gold cases separate

Not every dataset has a verified query or curated Semantic Pack yet. Split checks into:

- `connector_profile_checks`
- `draft_pack_checks`
- `retrieval_checks`
- `question_generation_checks`
- `semantic_gold_checks`
- `red_team_safety_checks`

A dataset may pass connector/profile/retrieval/safety while semantic-gold is marked `not_applicable` or `pending_curated_pack`.

### C. Add benchmark corpus CLI

Extend `semantic-eval` with commands like:

```bash
semantic-eval run --manifest eval/datasets/tableau_superstore.yaml --out runtime/benchmarks/tableau_superstore
semantic-eval run --manifest eval/datasets/sinagong/seil_sales.yaml --out runtime/benchmarks/sinagong_seil_sales
semantic-eval run-corpus --manifest-dir eval/datasets/sinagong --out runtime/benchmarks/sinagong
```

Default should be bounded and deterministic. It must not scan every large workbook unless requested.

## Weaviate optional live integration plan

### A. Configuration contract

Add an explicit config object/env contract:

```text
SEMANTIC_WEAVIATE_ENABLED=1
SEMANTIC_WEAVIATE_URL=http://localhost:8080
SEMANTIC_WEAVIATE_API_KEY=optional
SEMANTIC_WEAVIATE_COLLECTION=SemanticCards
SEMANTIC_WEAVIATE_QUERY_MODE=bm25|hybrid|near_vector
```

Rules:

- If `backend=weaviate` and config is missing: return explicit `backend_configuration_error`.
- If enabled but server is unreachable: fail explicit `WeaviateUnavailableError`.
- Never auto-switch to keyword after Weaviate failure.
- Keyword parity tests are separate and must be labeled `backend=keyword`.

### B. Query mode hardening

Current fake tests exercise `collection.query.hybrid`. For live Weaviate, add a backend option:

- `query_mode="bm25"` for no-vectorizer text search smoke
- `query_mode="hybrid"` only when the collection has vectorizer or vectors
- `query_mode="near_vector"` only when an embedding provider is explicitly configured

This prevents a live Weaviate check from failing just because the collection is configured with `vectorizer=none`.

### C. PII-safe object schema

Index only `SearchDocument` fields:

- `doc_id`
- `title`
- `text`
- `card_type`
- `pack_id`
- `space_id`
- `status`
- `source_uri`
- safe role/category metadata

Never index:

- source rows
- raw values
- email/phone/name literals
- `raw_value`, `sample_value`, `top_value` metadata keys
- SQL text from user prompts unless fingerprinted/sanitized

### D. Live test strategy

Default tests:

- fake collection unit tests continue to run always
- explicit no-config error tests run always
- PII-safe projection tests run always

Optional live tests:

```bash
SEMANTIC_WEAVIATE_ENABLED=1 \
SEMANTIC_WEAVIATE_URL=http://localhost:8080 \
SEMANTIC_WEAVIATE_COLLECTION=SemanticCardsTest \
python3 -m unittest tests/integration/test_weaviate_live_optional.py -v
```

Expected behavior:

- if env is absent: skip with explicit message
- if env is present and service fails: test fails with explicit Weaviate error
- if service succeeds: index generated benchmark cards and retrieve expected cards across at least demo + one Superstore/Sinagong draft pack

## Work phases

### Phase A — Benchmark manifest expansion

Files:

- `eval/datasets/tableau_superstore.yaml`
- `eval/datasets/sinagong/*.yaml`
- `docs/execution/DATASET_BENCHMARKS.md`
- `docs/execution/VALIDATION_DATASETS.md`
- `tests/eval/test_dataset_manifests.py`

Acceptance:

- Manifests exist for Superstore and at least 5 Sinagong domain families.
- Every listed source file exists.
- No raw PII-like values in manifests.
- Manifests include golden/red-team/safety expectations where applicable.

### Phase B — Generic file-corpus benchmark runner

Files:

- `packages/semantic_builder/src/semantic_builder/eval/runner.py`
- `packages/semantic_builder/src/semantic_builder/eval/cli.py`
- `tests/eval/test_eval_runner.py`
- `tests/eval/test_file_corpus_benchmarks.py`

Acceptance:

- Superstore runnable benchmark passes.
- At least 3 Sinagong benchmarks pass connector/profile/draft/retrieval/safety checks.
- Artifacts written under `runtime/benchmarks/**`.
- No raw PII in generated benchmark reports.

### Phase C — Full Sinagong corpus bounded benchmark

Files:

- `eval/datasets/sinagong/*.yaml`
- `scripts/benchmarks/run_dataset_benchmarks.py`
- `tests/e2e/test_multi_domain_benchmarks.py`
- `reports/benchmarks/*`

Acceptance:

- Bounded corpus run covers at least:
  - HR
  - sales/customer
  - public population/demographics
  - weather/time series
  - subway/store/location or online shopping
- Each run reports included/excluded files and skip reasons.
- Large workbook scans are bounded by explicit config, not silent truncation.

### Phase D — Weaviate optional live integration

Files:

- `packages/semantic_registry/semantic_registry/retrieval/backends.py`
- `packages/semantic_registry/semantic_registry/retrieval/config.py` if needed
- `packages/semantic_mcp/src/semantic_mcp/tools/search_context.py`
- `tests/registry/test_vdb_backend.py`
- `tests/integration/test_weaviate_live_optional.py`
- `docs/execution/RETRIEVAL_LAYER.md`
- `docs/demo/WEAVIATE_OPTIONAL.md`

Acceptance:

- Existing fake/no-config tests pass.
- Live test skips only when env is absent.
- Live test fails explicitly if env is present but Weaviate is unreachable.
- Live test indexes demo + one generated multi-domain pack and retrieves expected cards.
- No keyword fallback occurs after Weaviate failure.
- No raw PII payload is sent to Weaviate.

### Phase E — Final multi-domain report

Files:

- `reports/benchmarks/multi_domain_benchmark_report.md`
- `reports/benchmarks/weaviate_optional_report.md`
- `reports/final/final_integration_report.md` update

Acceptance:

- Report shows per-dataset pass/fail/skip.
- Report distinguishes keyword, fake-Weaviate, and live-Weaviate evidence.
- Known limitations are explicit.

## Suggested team execution prompt

```bash
$team 5:executor "Execute the next expansion only: live Weaviate optional integration plus multi-domain benchmark mappings.

Read:
- docs/execution/WEAVIATE_AND_MULTI_DOMAIN_BENCHMARK_PLAN.md
- docs/execution/VALIDATION_DATASETS.md
- docs/execution/DATASET_BENCHMARKS.md
- docs/execution/RETRIEVAL_LAYER.md
- reports/final/final_integration_report.md
- packages/semantic_builder/src/semantic_builder/eval/**
- packages/semantic_registry/semantic_registry/retrieval/**
- packages/semantic_mcp/src/semantic_mcp/tools/search_context.py
- eval/datasets/**
- docs/reference/test_datasets/sinagong_tableau_2026/**

Global rules:
- Code workers use gpt-5.4-mini medium.
- Orchestrator/verifier uses gpt-5.5 high.
- No production execute_query.
- No dashboard UI or SaaS.
- No raw PII storage/indexing.
- Weaviate must be explicit; no silent keyword fallback.
- If fallback is triggered and the cause is fixable within scope, fix it and
  rerun the preferred path; otherwise log attempt/remediation decision/reason/
  fallback or skip/evidence.
- Generated artifacts go under runtime/benchmarks/** or reports/benchmarks/** only.

Worker 1 — manifest-dev
Allowed paths:
- eval/datasets/**
- docs/execution/DATASET_BENCHMARKS.md
- docs/execution/VALIDATION_DATASETS.md
- tests/eval/test_dataset_manifests.py
Responsibilities:
- Split Sinagong into domain benchmark manifests.
- Promote Superstore manifest to runnable expectations.
- Validate file existence and PII-safe manifest content.

Worker 2 — benchmark-runner-dev
Allowed paths:
- packages/semantic_builder/src/semantic_builder/eval/**
- tests/eval/**
- scripts/benchmarks/**
Responsibilities:
- Add generic file-corpus benchmark runner.
- Support artifact output under runtime/benchmarks/**.
- Add semantic-eval run/run-corpus commands.

Worker 3 — weaviate-dev
Allowed paths:
- packages/semantic_registry/semantic_registry/retrieval/**
- packages/semantic_mcp/src/semantic_mcp/tools/search_context.py
- tests/registry/test_vdb_backend.py
- tests/integration/test_weaviate_live_optional.py
Responsibilities:
- Harden optional live Weaviate config/query modes.
- Add env-gated live integration test.
- Preserve no-silent-fallback behavior.

Worker 4 — corpus-e2e-dev
Allowed paths:
- tests/e2e/**
- scripts/benchmarks/**
- reports/benchmarks/**
Responsibilities:
- Run bounded Superstore + Sinagong benchmark corpus.
- Produce per-domain report with pass/fail/skip and artifact paths.

Worker 5 — verifier/security-docs
Allowed paths:
- docs/**
- reports/**
- tests/security/**
Responsibilities:
- Verify no execute_query/UI/SaaS/PII leakage.
- Verify Weaviate errors are explicit.
- Run explicit per-suite tests, not root unittest discover.
- Update final report and docs.

Final report must include:
- changed files
- benchmark datasets covered
- Weaviate mode tested: fake/no-config/live or skipped
- test results
- PII/indexing safety result
- fallback log
- remaining limitations
"
```

## Evaluation command after execution

```text
ooo evaluate
Evaluate the Weaviate + multi-domain benchmark expansion.

Must pass:
1. Superstore has an executable benchmark mapping.
2. At least 5 Sinagong domain manifests exist and validate.
3. At least 3 Sinagong domains run through scan/profile/draft/retrieval/safety benchmark.
4. Generated benchmark artifacts are under runtime/benchmarks/** and reports/benchmarks/**.
5. No raw PII is stored in profiles, packs, eval reports, or Weaviate payloads.
6. Weaviate backend is explicit: no silent keyword fallback.
7. Live Weaviate test is optional/env-gated and reports explicit skip/failure/success.
8. Keyword backend remains deterministic and separately labeled.
9. No production execute_query.
10. No dashboard UI or SaaS.
11. Tests pass using explicit test subdirectories.

Return:
- pass/fail
- missing dataset coverage
- failed tests
- scope violations
- required fixes
- whether the system is multi-domain benchmark-ready
```
