# Final Phase Roadmap — Phase 5 to Phase 12

Generated: 2026-05-08

## Run-level directives fixed by the user

1. **Weaviate replaces LanceDB.** Any source prompt mention of LanceDB or generic VDB backend is interpreted as Weaviate for this run.
2. **PostgreSQL-connected datasets are in scope.** The product must work when validation datasets are preloaded into PostgreSQL and scanned/connected as relational data sources, not only from original CSV/JSON/XLS/XLSX files. Full PostgreSQL connector implementation starts in Phase 10, but earlier phases must keep the contract seams compatible.
3. **No silent fallback.** If fallback occurs and is resolvable within the phase, resolve it. If it cannot be resolved safely, record attempt, reason, fallback behavior, and evidence in the phase report.

## Current state summary

Completed and verified before this roadmap:

- Phase 0: `semantic_contracts`, demo pack, validation tests.
- Phase 1: local `semantic_registry` store/search/feedback.
- Phase 2: local stdio `semantic_mcp` tools/resources/prompts.
- Phase 3: deterministic `QueryPlanner` and `SQLGuard` with `execution_allowed=false`.
- Phase 4: file-based Builder for CSV/JSON/JSONL/XLS/XLSX, including Excel sheet-level extraction.
- Supplemental Phase 4: `.xls`/`.xlsx` multi-sheet scanning, sheet metadata propagation, and PII extrema suppression.

Regression baseline at roadmap creation:

- Builder: 23 tests pass.
- Contracts: 20 tests pass.
- Registry: 28 tests pass.
- MCP: 19 tests pass.

## Schema audit

| Requirement | Current support | Gap / action |
|---|---:|---|
| Pack `draft/reviewed/approved` | Yes | No action. |
| Card `draft/reviewed/approved/confirmed` | Yes | Phase 6 should use statuses for promotion. |
| Metric `date_basis` | Yes | Add `grain` in Phase 5/6 if hypothesis/runtime needs it. |
| BusinessTerm `sql_condition` | Yes | No action. |
| BusinessTerm ambiguity rules | Yes | Phase 5 should generate rule/proposal-compatible uncertainty. |
| Policy `blocked_columns` | Yes | Add `max_preview_rows` in Phase 9 before safe preview. |
| VerifiedQuery `required_terms` | Partial | MCP contract has it; Semantic Pack `VerifiedQuery` model lacks it. Add in Phase 8 or 9 before runtime/preview relies on it. |
| PII raw storage prohibited | Yes | Must be enforced in every new provider/index/runtime payload. |
| Feedback direct mutation | Not present | Phase 6 must introduce proposal workflow, not silent mutation. |
| PostgreSQL source kind | Yes | Connector scanner not yet implemented. Phase 10 owns implementation. |
| Weaviate baseline | Documented only | Phase 7 owns interface and explicit config behavior. |

## Global stop conditions for every phase

Stop and write a failure report if any of these occur:

- Product code introduces dashboard UI, SaaS multi-tenancy, production SQL execution, or raw PII persistence.
- A worker edits outside its lane and the conflict cannot be isolated.
- Tests still fail after two phase-local repair attempts.
- A required external service or credential is needed and no deterministic/mock/local fallback exists.
- A fallback is used without an explicit log/report entry.

## Phase 5 — LLM Semantic Hypothesis + Reverse Question Generator

### Objective
Create a cautious, testable LLM-assisted inference pipeline that turns scan/profile outputs into draft semantic hypotheses and reverse questions without pretending uncertain business meaning is confirmed.

### Files to create/modify
- `packages/semantic_contracts/**` for hypothesis/proposal models if needed.
- `packages/semantic_builder/src/semantic_builder/inference/**`.
- `packages/semantic_builder/src/semantic_builder/cli.py` for CLI commands if needed.
- `tests/builder/test_semantic_hypothesis_models.py`.
- `tests/builder/test_semantic_inference_pipeline.py`.
- `reports/phases/phase5_semantic_hypothesis_reverse_questions.md`.

### Forbidden
- MCP runtime changes unless only import compatibility is required.
- Registry promotion workflow.
- VDB/Weaviate.
- Query execution or preview.
- External network calls by default.

### Agent lanes
1. Hypothesis contract/models lane.
2. Provider abstraction + deterministic mock lane.
3. Reverse question generator lane.
4. CLI/artifact lane.
5. Verifier lane.

### Acceptance criteria
- Deterministic mock provider produces `semantic_hypotheses.jsonl` and `onboarding_questions.jsonl`.
- Every hypothesis has evidence, confidence, status=`draft`, uncertainties, and source references.
- PII raw values are absent from prompts, logs, hypotheses, and questions.
- Optional local provider is config-gated and never default.
- Reverse questions are generated for low confidence, missing date basis, ambiguous metrics, joins, and policy concerns.

### Edge cases
- Empty profiles create questions, not fabricated terms.
- High-cardinality and PII columns are summarized/redacted.
- PostgreSQL-origin scan records should be accepted as source references even before Phase 10 implementation.

### Tests
- Unit tests for hypothesis models.
- Unit tests for deterministic provider.
- Pipeline test from demo profiles and at least one real dataset profile.
- PII redaction tests.
- Scope grep for no network-by-default/no VDB/no execution.

### Exact team launch prompt summary
`omx team 5:executor "Execute Phase 5 only: LLM Semantic Hypothesis + Reverse Question Generator. Read FINAL_PHASE_ROADMAP, SEMANTIC_PACK_SPEC, builder/contracts, semantic_packs, and validation datasets. Implement deterministic/mock provider, config-gated local provider seam, hypothesis artifacts, reverse questions, PII-safe prompt payloads, tests, and phase report. No VDB, no UI, no query execution, no external network by default."`

## Phase 6 — Human Confirmation + Pack Promotion Workflow

### Objective
Turn draft hypotheses/questions/feedback into explicit confirmation records and pack update proposals, then allow deterministic promotion to reviewed/approved only through auditable local workflow.

### Files to create/modify
- `packages/semantic_registry/semantic_registry/promotion.py`.
- `packages/semantic_registry/semantic_registry/proposals.py`.
- `packages/semantic_contracts/**` for confirmation/proposal models if needed.
- `tests/registry/test_pack_promotion.py`.
- `tests/registry/test_pack_proposals.py`.
- `reports/phases/phase6_human_confirmation_pack_promotion.md`.

### Forbidden
- UI.
- Direct mutation of approved packs from feedback.
- VDB.
- Query execution/preview.

### Agent lanes
1. Confirmation/proposal contract lane.
2. Registry proposal store lane.
3. Promotion workflow lane.
4. Pack diff/versioning lane.
5. Verifier lane.

### Acceptance criteria
- Feedback/hypothesis answers create proposals, not silent pack mutation.
- Promotion requires explicit confirmation records.
- Approved pack mutation is blocked unless a new version/proposal path is used.
- Rejected/dismissed questions remain auditable.

### Tests
- Proposal creation tests.
- Promotion status transition tests.
- Approved pack mutation block test.
- JSONL/audit artifact tests.

### Exact team launch prompt summary
`omx team 5:executor "Execute Phase 6 only: Human Confirmation + Pack Promotion Workflow. Implement confirmation records, proposal store, safe pack promotion/versioning, and tests. Feedback must not silently mutate approved packs. No UI, no VDB, no query execution."`

## Phase 7 — Weaviate / Card Index / Retrieval Layer

### Objective
Implement a retrieval layer that projects Semantic Pack cards into PII-safe retrieval documents and supports deterministic retrieval plus explicit Weaviate backend configuration.

See `docs/execution/RETRIEVAL_LAYER.md` for the current retrieval boundary and safety contract.

### Files to create/modify
- `packages/semantic_registry/semantic_registry/retrieval/**`.
- `packages/semantic_mcp/src/semantic_mcp/tools/**` only for retrieval integration if prompt requires.
- `tests/registry/test_retrieval_documents.py`.
- `tests/registry/test_embedding_provider.py`.
- `tests/registry/test_weaviate_backend.py`.
- `tests/mcp/test_retrieval_tools.py` if MCP surface changes.
- `reports/phases/phase7_vdb_card_index_retrieval.md`.

### Forbidden
- LanceDB implementation for this run.
- Silent fallback from Weaviate to keyword search.
- Embedding or indexing raw PII values.
- Query execution/preview.

### Agent lanes
1. Retrieval document projection lane.
2. Embedding provider lane.
3. Weaviate backend/config lane.
4. Registry/MCP integration lane.
5. Verifier lane.

### Acceptance criteria
- PII-safe retrieval documents are generated for tables, columns, terms, metrics, policies, value dictionaries, ambiguity rules.
- Deterministic embedding provider passes tests.
- Weaviate backend is config-gated and returns explicit configuration/dependency errors if unavailable.
- Keyword fallback is available only when explicitly selected, never silently after Weaviate failure.
- Retrieval results preserve draft/reviewed/approved/deprecated/confirmed status and source references.

### Tests
- Projection safety tests.
- Deterministic retrieval tests.
- Weaviate explicit-error tests.
- No PII vector payload tests.

### Exact team launch prompt summary
`omx team 5:executor "Execute Phase 7 only: Weaviate / Card Index / Retrieval Layer. Replace LanceDB instructions with Weaviate. Implement PII-safe retrieval documents, deterministic embeddings, config-gated Weaviate backend with explicit errors, keyword backend parity, tests, and phase report. No silent fallback, no raw PII indexing, no query execution."`

## Phase 8 — Domain-Aware Query Runtime

### Objective
Use registry/retrieval/planner/guard outputs to produce domain-aware, validation-only query plans and warnings for user questions.

### Files to create/modify
- `packages/semantic_registry/semantic_registry/runtime/**`.
- `packages/semantic_registry/semantic_registry/query_planner.py` if needed.
- `packages/semantic_mcp/src/semantic_mcp/tools/plan_query.py`.
- `tests/registry/test_domain_query_runtime.py`.
- `tests/mcp/test_domain_query_runtime_tool.py`.
- `reports/phases/phase8_domain_aware_query_runtime.md`.

### Forbidden
- `preview_query`.
- SQL execution.
- DB connections.
- UI.

### Agent lanes
1. Runtime context assembly lane.
2. Ambiguity/warning policy lane.
3. MCP integration lane.
4. PostgreSQL-source compatibility test lane.
5. Verifier lane.

### Acceptance criteria
- Runtime uses Semantic Pack + retrieval/search context.
- Draft metrics/terms produce warnings, not confirmed truth.
- Ambiguous questions return reverse questions/ambiguities.
- `execution_allowed` remains false.
- PostgreSQL-origin tables/source_refs are accepted in planning inputs.

### Tests
- Korean/English domain query plans.
- Ambiguity warning tests.
- Draft status warning tests.
- No preview/execute grep.

### Exact team launch prompt summary
`omx team 6:executor "Execute Phase 8 only: Domain-Aware Query Runtime. Implement validation-only runtime context assembly over Registry/Retrieval/Planner, with ambiguity warnings, draft status warnings, MCP plan tool wiring, PostgreSQL-source compatibility tests, and phase report. No preview_query, no SQL execution, no DB connections."`

## Phase 9 — Safe Preview Query Execution

### Objective
Add bounded local safe preview execution for approved local fixtures only, behind SQLGuard and policy limits.

### Files to create/modify
- `packages/semantic_registry/semantic_registry/preview/**`.
- `packages/semantic_contracts/**` for preview contracts and `max_preview_rows`.
- `packages/semantic_mcp/src/semantic_mcp/tools/preview_query.py` if explicitly introduced.
- `tests/registry/test_safe_preview.py`.
- `tests/mcp/test_preview_query.py`.
- `reports/phases/phase9_safe_preview_query_execution.md`.

### Forbidden
- Production DB execution.
- Mutating SQL.
- Preview without SQLGuard pass.
- Preview over PII blocked columns.

### Agent lanes
1. Preview contract lane.
2. Local fixture execution lane.
3. SQLGuard/policy integration lane.
4. MCP tool lane.
5. Verifier lane.

### Acceptance criteria
- Preview only runs SELECT after SQLGuard pass.
- Max rows enforced from policy/config.
- Blocked columns and multi-statement SQL blocked.
- Execution target is local fixture or explicit safe test DB only.
- `execute_query` production path still absent.

### Tests
- Valid preview against local fixture.
- DML/multi-statement/PII block tests.
- Max rows tests.
- No production credential tests.

### Exact team launch prompt summary
`omx team 5:executor "Execute Phase 9 only: Safe Preview Query Execution. Add bounded local preview_query over local fixtures/test DB only, guarded by SQLGuard and policy max_preview_rows. No production execute_query, no mutating SQL, no PII preview. Include tests and phase report."`

## Phase 10 — DB Connector + Safe Scanner Extension

### Objective
Implement PostgreSQL-safe scanner/profiler extension so datasets already loaded in PostgreSQL can produce the same scan/profile/draft artifacts as file sources.

### Files to create/modify
- `packages/semantic_builder/src/semantic_builder/connectors/postgresql.py`.
- `packages/semantic_builder/src/semantic_builder/connectors/**` integration.
- `packages/semantic_builder/src/semantic_builder/cli.py` for config-driven scan if needed.
- `tests/builder/test_postgresql_connector.py`.
- `tests/builder/test_postgresql_profile_pipeline.py`.
- `docs/execution/POSTGRESQL_VALIDATION.md`.
- `reports/phases/phase10_db_connector_safe_scanner.md`.

### Forbidden
- Oracle/MySQL.
- Production credentials in repo.
- Unbounded value sampling.
- Raw PII storage.
- SQL execution beyond scanner metadata/profile queries required for safe scanning.

### Agent lanes
1. PostgreSQL connector contract lane.
2. Safe metadata scanner lane.
3. Safe profiler/sample lane.
4. Dataset preload/manifest lane.
5. Verifier lane.
6. Docs/report lane.

### Acceptance criteria
- Connector can scan table/schema/column metadata.
- Optional test PostgreSQL fixture path is config-gated and skipped loudly when unavailable.
- No silent fallback to file scanner when PostgreSQL config fails.
- Profiles match shared builder contract.
- PII redaction and top-N restrictions match file pipeline.

### Tests
- Unit tests with mocked DB metadata/cursors.
- Integration test conditional on local PostgreSQL fixture.
- Explicit config error tests.
- PII safety tests.

### Exact team launch prompt summary
`omx team 6:executor "Execute Phase 10 only: DB Connector + Safe Scanner Extension. Implement PostgreSQL scanner/profiler contracts and safe config-gated connector, with mocked tests and optional local fixture tests. No Oracle/MySQL, no production credentials, no raw PII, no silent fallback. Include docs/report."`

## Phase 11 — Evaluation Harness + Benchmark Runner

### Objective
Create evaluation schemas and runners for golden questions, red-team cases, retrieval, SQL guard, builder safety, preview, and dataset manifests.

### Files to create/modify
- `eval/**`.
- `packages/semantic_registry/semantic_registry/eval/**`.
- `packages/semantic_builder/src/semantic_builder/eval/**`.
- `tests/eval/**`.
- `docs/execution/DATASET_BENCHMARKS.md`.
- `reports/phases/phase11_evaluation_harness_benchmark_runner.md`.

### Forbidden
- Production DB execution.
- External paid API dependency.
- Benchmark results that hide skipped cases.

### Agent lanes
1. Eval contract lane.
2. Eval runner lane.
3. Dataset manifest lane.
4. MCP/eval helper lane.
5. Verifier lane.

### Acceptance criteria
- Machine-readable and markdown-readable eval report generated.
- Dataset manifests cover demo, Superstore, Sinagong, and PostgreSQL fixture template.
- Red-team cases cover PII, dangerous SQL, ambiguous terms, draft metric warnings.
- Weaviate retrieval eval uses deterministic backend by default and explicit Weaviate config path when available.

### Tests
- Eval schema tests.
- Runner tests.
- Dataset manifest tests.
- Example eval report test.

### Exact team launch prompt summary
`omx team 5:executor "Execute Phase 11 only: Evaluation Harness + Benchmark Runner. Implement eval schemas/runners/manifests for golden, red-team, retrieval, SQL guard, builder safety, preview if available, and dataset benchmarks including PostgreSQL templates. Deterministic providers by default. Include tests/report."`

## Phase 12 — Final Integration + Packaging + Demo

### Objective
Finalize the local shareable Semantic Data Context System with documented CLI flows, package entry points, demo scripts, and end-to-end proof.

### Files to create/modify
- `README.md`.
- `AGENTS.md` if workflow rules need updates.
- package `pyproject.toml` entry points.
- `scripts/**` or `examples/**` for local demos.
- `eval/**` report/demo fixtures if needed.
- `reports/phases/phase12_final_integration_packaging_demo.md`.

### Forbidden
- Dashboard UI.
- SaaS multi-tenancy.
- Production credentials.
- Silent Weaviate/PostgreSQL fallback.
- Raw PII payloads.

### Agent lanes
1. Packaging/CLI lane.
2. README/docs lane.
3. Demo script lane.
4. Eval/demo evidence lane.
5. Scope/safety verifier lane.
6. Release report lane.

### Acceptance criteria
- Clean local demo path works from scan/profile/build to confirmation/proposal/promotion to registry/MCP retrieval/runtime/preview/eval where available.
- README explains Builder, Registry, MCP, Weaviate retrieval, PostgreSQL scanner, preview, eval, and safety boundaries.
- CLI commands are reproducible.
- Final eval report passes.
- Scope audit passes.

### Tests
- Full unit suite.
- Demo script smoke test.
- Eval runner smoke test.
- Packaging/import smoke tests.

### Exact team launch prompt summary
`omx team 6:executor "Execute Phase 12 only: Final Integration + Packaging + Demo. Finalize local packaging, CLI entry points, README, demo scripts, eval/demo evidence, and final safety audit. Use Weaviate config rules and PostgreSQL fixture docs. No UI/SaaS/production credentials/silent fallback/raw PII. Include final report."`

## Immediate next action

Start Phase 5 with the exact team prompt from this roadmap, then run the Phase 5 evaluation. Do not start Phase 6 until Phase 5 passes or a repair report says it is blocked.

## Risks

- Phase 5 optional local LLM adapter may depend on local MLX model naming; tests must use deterministic mock provider and log local-provider availability separately.
- Phase 7 Weaviate may not be installed/running; implementation must provide explicit config/dependency errors and deterministic backend tests.
- Phase 10 PostgreSQL fixture may not be running; mocked connector tests must pass and local integration must skip loudly with evidence if unavailable.
- Phase 9 preview introduces limited execution semantics; strict SQLGuard and local-only boundaries are required.
- Long multi-phase execution can accumulate worker conflicts; use lane contracts and `reports/conflicts/` for any overlap.
