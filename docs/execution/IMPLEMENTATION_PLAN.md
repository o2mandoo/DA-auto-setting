# IMPLEMENTATION PLAN — Semantic Data Context System

## 0. Planning Status

This plan is generated from the approved seed/spec baseline:

- `specs/seeds/semantic-data-context.seed.yaml`
- `docs/execution/PROJECT_BRIEF.md`
- `docs/execution/MVP_SCOPE.md`
- `docs/execution/MODULES.md`
- `docs/execution/SEMANTIC_PACK_SPEC.md`
- `docs/reference/original-service-plan.pdf` as original reference only

This document is a plan only. It does not authorize code implementation until the user explicitly approves a phase execution.

## 0.1 Consensus Revision Notes

Architect review found one important tension: the user-requested phases list places Query Planner + SQL Guard in Phase 3, while the source architecture says MCP should expose stable Registry-backed capabilities. To satisfy both constraints, this plan keeps the requested Phase 0-5 list but defines a two-step ownership rule:

- **Phase 1 owns the Registry planner/guard core API boundary** so MCP Phase 2 never ships placeholder `plan_data_query` or `validate_sql` behavior.
- **Phase 3 hardens and expands Query Planner + SQL Guard** after MCP integration, without changing ownership or adding SQL execution.

Therefore Phase 2 may expose all six tools only by calling real Registry APIs. If Phase 1 planner/guard core is not ready, Phase 2 must stop rather than register placeholder tools.

## 1. RALPLAN-DR Summary

### 1.1 Principles

1. **Contracts first**: stabilize Semantic Pack and tool I/O contracts before runtime modules.
2. **Semantic Pack as source of truth**: Builder, Registry, and MCP must converge on one schema.
3. **Validation before execution**: SQL validation is in scope; SQL execution is explicitly out of scope.
4. **Local-first MVP**: use local files, local registry, stdio MCP, JSONL feedback, and lexical/card search before production infrastructure.
5. **Safety by default**: no PII raw-value storage, no UI, no SaaS tenancy, no full VDB requirement.

### 1.2 Decision Drivers

1. Phase 0 must be small enough to approve and verify independently.
2. Multi-agent execution must avoid overlapping file edits through lane contracts.
3. Every team run needs a verifier lane with explicit evidence requirements.

### 1.3 Viable Options Considered

| Option | Summary | Pros | Cons | Decision |
|---|---|---|---|---|
| A. Contract-first sequential phases | Phase 0 contracts/demo/tests, then Registry with planner/guard core, MCP, SQL guard hardening, Builder, LLM hypothesis | Lowest scope risk; matches approved docs; easy to verify | Slower visible product surface | **Chosen** |
| B. Build MCP first | Expose tools early, backfill contracts and Registry | Faster demo of agent interface | High schema churn; weak validation; risks tool contract breakage | Rejected |
| C. Builder first | Scan files and generate draft pack early | Immediate use of datasets | Produces unstable pack output before schema/validation exists | Rejected |
| D. BI/demo app first | Build visible dashboard or chat UI | Easy stakeholder demo | Violates non-goals: UI and BI platform scope | Rejected |

## 2. Architecture Target

```text
semantic_builder
  scans CSV/JSON/XLSX first, PostgreSQL later
  emits semantic_pack.draft.yaml
        ↓
semantic_contracts
  Pydantic models, SemanticPack schema, validation, SQL guard contracts
        ↓
semantic_registry
  local pack store, card registry, keyword search, feedback JSONL
        ↓
semantic_mcp
  local stdio MCP server exposing resources/tools/prompts, no execute_query
        ↓
external LLM / Agent / App
```

## 3. Global Guardrails

These constraints apply to every phase and every `$team` run.

- Do not build dashboard UI.
- Do not build independent BI platform UI.
- Do not implement `execute_query`.
- Do not connect to or execute against operational databases.
- Do not implement SaaS multi-tenancy.
- Do not require a production VDB or embedding pipeline.
- Do not store or embed PII raw values.
- Do not let multiple workers edit the same file.
- Every team run must include a verifier lane.
- Workers must not modify files outside their assigned lane.
- If a worker discovers required cross-lane changes, it must report the need instead of editing another lane's files.

## 4. Available Agent Types and Staffing Guidance

Use `omx team N:executor` for all coordinated implementation phases unless a later OMX install exposes more specialized role prompts.

Recommended lane types inside the team prompt:

- **Contract lane**: schemas, Pydantic models, validation contracts.
- **Fixture lane**: demo Semantic Pack and sample data fixture mapping.
- **Registry lane**: local store/search/feedback behavior.
- **MCP lane**: stdio server/resources/tools/prompts.
- **Planner/Guard lane**: query planning and SQL guard rules.
- **Builder lane**: file scanner/profiler and draft pack generation.
- **Verifier lane**: tests, acceptance evidence, scope/guardrail audit.

Suggested reasoning:

- Contract, MCP, SQL guard, Builder: high.
- Registry and fixture: medium/high.
- Verifier: high.

## 5. Repository File Ownership Rules

### 5.1 Shared files requiring strict single-owner edits

Only one lane may edit these in a given phase:

- `pyproject.toml`
- lock files, if any
- root README or global config
- `docs/execution/*.md`
- `semantic_packs/demo_company/revenue.v0_1.yaml`
- shared test fixtures under `tests/fixtures/`

### 5.2 Package ownership

| Package | Owning lane |
|---|---|
| `packages/semantic_contracts/` | Contract lane |
| `packages/semantic_registry/` | Registry lane |
| `packages/semantic_mcp/` | MCP lane |
| `packages/semantic_builder/` | Builder lane |

### 5.3 Test ownership

Tests should be split by package or feature:

- `tests/semantic_contracts/` — Contract/verifier lanes only by agreement.
- `tests/semantic_registry/` — Registry lane owns, verifier may add separate verifier test file if non-overlapping.
- `tests/semantic_mcp/` — MCP lane owns, verifier may add separate verifier test file if non-overlapping.
- `tests/semantic_builder/` — Builder lane owns, verifier may add separate verifier test file if non-overlapping.
- `tests/integration/` — verifier lane owns unless a phase prompt explicitly assigns it elsewhere.

## 5.4 Contract Change Governance

After Phase 0, `packages/semantic_contracts/**` is a protected shared package. Only an explicitly named **contract-maintainer lane** may edit it in a later team run. Other lanes must report contract gaps rather than editing contracts directly.

If a phase needs a contract change, the team must either:

1. assign exactly one contract-maintainer worker and list the exact contract files it may edit, or
2. stop and write the required contract change to `.omx/team-notes/contract-gaps.md`.

Root config ownership is also single-lane only. `pyproject.toml`, `pytest.ini`, lock files, and shared package config may be edited only by the worker explicitly named as config owner in that phase prompt.

## 6. Phase 0 — Contract + Demo Semantic Pack + Validation Tests

### Objective

Create the minimum executable baseline: common Pydantic contracts, Semantic Pack schema, validation rules, one demo Semantic Pack, and validation tests. This is the first code-bearing phase and requires explicit approval before execution.

### Files to create

Contract lane:

- `packages/semantic_contracts/pyproject.toml` or package config chosen by the repo
- `packages/semantic_contracts/semantic_contracts/__init__.py`
- `packages/semantic_contracts/semantic_contracts/models.py`
- `packages/semantic_contracts/semantic_contracts/validators.py`
- `packages/semantic_contracts/semantic_contracts/sql_guard_contracts.py`
- `packages/semantic_contracts/semantic_contracts/mcp_tool_contracts.py`
- `packages/semantic_contracts/semantic_contracts/errors.py`

Fixture lane:

- `semantic_packs/demo_company/revenue.v0_1.yaml`
- optional `tests/fixtures/semantic_packs/demo_company/revenue.v0_1.yaml` if tests need immutable copy

Verifier lane:

- `tests/semantic_contracts/test_pack_validation.py`
- `tests/semantic_contracts/test_sql_guard_contracts.py`
- `tests/semantic_contracts/test_demo_pack.py`

### Files allowed to modify

- `packages/semantic_contracts/**`
- `semantic_packs/demo_company/revenue.v0_1.yaml`
- `tests/semantic_contracts/**`
- package/test config only if necessary: `pyproject.toml`, `pytest.ini`, or equivalent

### Files forbidden to modify

- `packages/semantic_registry/**`
- `packages/semantic_mcp/**`
- `packages/semantic_builder/**`
- `docs/reference/**`
- `docs/execution/**` except implementation notes explicitly requested by the user
- any UI, dashboard, or application runtime files

### Agent lanes

| Lane | Worker | Write scope | Responsibility |
|---|---:|---|---|
| Contract lane | worker-1 | `packages/semantic_contracts/**` | Pydantic models, schema enums, validation result/error models |
| Fixture lane | worker-2 | `semantic_packs/demo_company/revenue.v0_1.yaml` | Demo pack based on Sample Superstore and approved spec |
| Verifier lane | worker-3 | `tests/semantic_contracts/**` | Tests and scope audit; verify no runtime modules implemented |

### Acceptance criteria

- Demo Semantic Pack validates successfully.
- Required card types are represented: tables, columns, value dictionaries, metrics, business terms, join recipes, policies, verified queries, reverse questions.
- PII raw-value rules are enforced or testable.
- Name-like sample columns are flagged as PII candidates and not used as value dictionaries.
- SQL guard contract can represent SELECT-only, multi-statement, allowed table, and blocked column checks.
- Six MCP tool request/response contract models exist for `list_semantic_spaces`, `search_semantic_context`, `resolve_business_terms`, `plan_data_query`, `validate_sql`, and `record_feedback`; no MCP runtime exists.
- No Registry, MCP, Builder runtime implementation exists in Phase 0.

### Tests

- Unit: model parsing and required fields.
- Unit: unique IDs and reference resolution.
- Unit: PII candidate cannot have raw value dictionary.
- Unit: SQL guard contract pass/fail result shapes.
- Unit: MCP tool request/response contract shapes.
- Fixture: `semantic_packs/demo_company/revenue.v0_1.yaml` validates.
- Scope test/manual check: no `execute_query`, no UI, no Registry/MCP/Builder runtime code.

### Risks

- Schema may become too large in Phase 0.
- Demo pack may overfit Sample Superstore.
- Pydantic version/tooling choice may be unresolved.

### Exact `$team` launch prompt

```bash
$team 3:executor "Phase 0 only for semantic-data-context. Do not implement Registry, MCP, Builder runtime, UI, or execute_query. Use lane contracts and do not edit another lane's files. worker-1 Contract lane: create packages/semantic_contracts Pydantic models, validators, errors, SQL guard contract models, and MCP tool contract models only. worker-2 Fixture lane: populate/replace the existing semantic_packs/demo_company/revenue.v0_1.yaml placeholder from SEMANTIC_PACK_SPEC and Sample Superstore, with PII-safe handling of name-like fields. worker-3 Verifier lane: create tests/semantic_contracts only, verify demo pack validation and SQL guard and MCP tool contract shapes, and audit that no forbidden runtime/UI/query execution files were added. Report evidence and failing tests if any."
```

## 7. Phase 1 — Registry Local File Store + Search + Feedback + Planner/Guard Core

### Objective

Implement a local Semantic Registry that loads validated packs, indexes cards, supports keyword/structured search, resolves business terms, appends feedback JSONL, and owns the minimal planner/SQL-guard core APIs required by MCP Phase 2. This prevents MCP from exposing placeholder `plan_data_query` or `validate_sql` tools.

### Files to create

Registry lane:

- `packages/semantic_registry/pyproject.toml` or package config
- `packages/semantic_registry/semantic_registry/__init__.py`
- `packages/semantic_registry/semantic_registry/store.py`
- `packages/semantic_registry/semantic_registry/cards.py`
- `packages/semantic_registry/semantic_registry/search.py`
- `packages/semantic_registry/semantic_registry/feedback.py`
- `packages/semantic_registry/semantic_registry/query_planner.py`
- `packages/semantic_registry/semantic_registry/sql_guard.py`

Verifier lane:

- `tests/semantic_registry/test_store.py`
- `tests/semantic_registry/test_search.py`
- `tests/semantic_registry/test_feedback.py`
- `tests/semantic_registry/test_query_planner_core.py`
- `tests/semantic_registry/test_sql_guard_core.py`
- `tests/integration/test_registry_with_demo_pack.py`

### Files allowed to modify

- `packages/semantic_registry/**`
- `tests/semantic_registry/**`
- `tests/integration/test_registry_with_demo_pack.py`
- `packages/semantic_contracts/**` only if a single named contract-maintainer lane is assigned; otherwise report contract gaps without editing

### Files forbidden to modify

- `packages/semantic_mcp/**`
- `packages/semantic_builder/**`
- `semantic_packs/demo_company/revenue.v0_1.yaml` unless a validation bug is explicitly assigned
- UI files
- any SQL execution implementation

### Agent lanes

| Lane | Worker | Write scope | Responsibility |
|---|---:|---|---|
| Registry store lane | worker-1 | `packages/semantic_registry/store.py`, package init/config | Load packs from local files, version lookup, semantic space listing |
| Registry search/feedback/planner lane | worker-2 | `packages/semantic_registry/search.py`, `cards.py`, `feedback.py`, `query_planner.py`, `sql_guard.py` | Card registry, keyword search, term resolution, JSONL feedback append, minimal planner/guard core APIs |
| Verifier lane | worker-3 | `tests/semantic_registry/**`, `tests/integration/test_registry_with_demo_pack.py` | Tests and guardrail audit |

### Acceptance criteria

- Registry loads the demo pack through `semantic_contracts` validation.
- `list_semantic_spaces`-equivalent function returns demo pack metadata.
- Keyword/card search can find metrics, terms, tables, columns, policies, and verified queries.
- Feedback JSONL append works and avoids raw PII storage.
- Minimal `plan_data_query` core returns semantic terms/metrics/tables/joins/ambiguities with `execution_allowed: false`.
- Minimal `validate_sql` core supports SELECT-only, multi-statement blocking, allowed table checks, and blocked column checks.
- Registry exposes no SQL execution behavior.

### Tests

- Unit: load valid pack and reject invalid pack.
- Unit: list semantic spaces.
- Unit: search by Korean and English terms where present.
- Unit: resolve business terms.
- Unit: feedback JSONL append and schema validation.
- Integration: demo pack loads and searches successfully.
- Unit: planner core returns deterministic planning object without SQL execution.
- Unit: SQL guard core blocks non-SELECT, multi-statement, unknown table, and blocked column cases.

### Risks

- Keyword search may be too weak without normalization.
- Feedback messages may accidentally store sensitive text unless constrained.
- Contract changes may be needed; avoid uncoordinated edits.

### Exact `$team` launch prompt

```bash
$team 3:executor "Phase 1 only for semantic-data-context Registry. Do not edit MCP, Builder, UI, or execute_query. Use lane contracts and do not overlap files. worker-1 Registry store lane: implement packages/semantic_registry store/load/version/list behavior using semantic_contracts validation. worker-2 Registry search-feedback-planner lane: implement card registry, keyword search, business-term lookup helpers, feedback JSONL append, minimal query_planner.py and sql_guard.py core APIs with PII-safe constraints and execution_allowed=false. worker-3 Verifier lane: write tests/semantic_registry and integration test against demo pack; verify no SQL execution and no forbidden file edits. Report test commands and evidence."
```

## 8. Phase 2 — Local MCP Server + Tools/Resources/Prompts

### Objective

Expose Registry capabilities through a local stdio MCP server with deterministic tools/resources/prompts and no query execution.

### Files to create

MCP lane:

- `packages/semantic_mcp/pyproject.toml` or package config
- `packages/semantic_mcp/semantic_mcp/__init__.py`
- `packages/semantic_mcp/semantic_mcp/server.py`
- `packages/semantic_mcp/semantic_mcp/tools.py`
- `packages/semantic_mcp/semantic_mcp/resources.py`
- `packages/semantic_mcp/semantic_mcp/prompts.py`
- `packages/semantic_mcp/semantic_mcp/schemas.py`

Verifier lane:

- `tests/semantic_mcp/test_tool_schemas.py`
- `tests/semantic_mcp/test_tools_with_registry.py`
- `tests/semantic_mcp/test_no_execute_query.py`

### Files allowed to modify

- `packages/semantic_mcp/**`
- `tests/semantic_mcp/**`
- `packages/semantic_registry/**` only for additive read-only API adjustments assigned to one registry-support worker
- `packages/semantic_contracts/**` only for additive MCP tool schema contracts assigned to one contract-support worker

### Files forbidden to modify

- `packages/semantic_builder/**`
- UI files
- SQL execution code
- production DB connector code

### Agent lanes

| Lane | Worker | Write scope | Responsibility |
|---|---:|---|---|
| MCP tool lane | worker-1 | `packages/semantic_mcp/tools.py`, `schemas.py` | Implement six required tools over Registry APIs |
| MCP resource/prompt lane | worker-2 | `server.py`, `resources.py`, `prompts.py`, package init/config | stdio server, resources, prompt templates |
| Verifier lane | worker-3 | `tests/semantic_mcp/**` | Tool schema tests, no `execute_query` audit, stdio smoke path if practical |

### Acceptance criteria

Required tools exist and return deterministic JSON-compatible responses:

- `list_semantic_spaces`
- `search_semantic_context`
- `resolve_business_terms`
- `plan_data_query`
- `validate_sql`
- `record_feedback`

Required properties:

- stdio transport is supported.
- MCP resources expose pack metadata/card summaries.
- MCP prompts are context/validation oriented.
- No `execute_query` tool exists.
- `plan_data_query` and `validate_sql` call real Registry planner/guard APIs created in Phase 1; placeholder or fake success behavior is forbidden.
- If Registry planner/guard APIs are not ready, Phase 2 must fail fast rather than registering incomplete tools.
- Tool outputs match `SEMANTIC_PACK_SPEC.md` contracts or documented compatible equivalents.

### Tests

- Unit: tool input/output schema validation.
- Unit: tools call Registry and return expected demo pack results.
- Unit: no `execute_query` symbol/tool is registered.
- Smoke: server can initialize in stdio-compatible mode if framework permits.

### Risks

- MCP SDK choice may affect shape of server tests.
- Tool contracts may drift from spec if not centralized.
- Prompt text may become too product/UI oriented; keep it interface-focused.

### Exact `$team` launch prompt

```bash
$team 3:executor "Phase 2 only for semantic-data-context local MCP. Do not edit Builder, UI, production DB connectors, or implement execute_query. Use lane contracts and no overlapping file edits. worker-1 MCP tool lane: implement packages/semantic_mcp tools.py and schemas.py for list_semantic_spaces, search_semantic_context, resolve_business_terms, plan_data_query, validate_sql, record_feedback over real Registry APIs only; do not ship placeholder plan/validate tools. worker-2 MCP resource-prompt lane: implement server.py, resources.py, prompts.py, stdio server wiring, and package init/config. worker-3 Verifier lane: write tests/semantic_mcp, verify tool schemas, demo registry integration, stdio smoke if practical, and assert no execute_query. Report evidence."
```

## 9. Phase 3 — Query Planner + SQL Guard Hardening

### Objective

Harden and expand the Registry-owned planning and SQL validation behavior created in Phase 1. This phase improves correctness and MCP integration but does not change ownership: Registry remains the source of planner/guard semantics, and MCP remains a thin interface.

### Files to create

Planner/guard hardening lane:

- `packages/semantic_registry/semantic_registry/query_planner.py`
- `packages/semantic_registry/semantic_registry/sql_guard.py`

MCP integration lane:

- updates to `packages/semantic_mcp/semantic_mcp/tools.py` only for `plan_data_query` and `validate_sql` integration

Verifier lane:

- `tests/semantic_registry/test_query_planner.py`
- `tests/semantic_registry/test_sql_guard.py`
- `tests/semantic_mcp/test_query_planner_tools.py`

### Files allowed to modify

- `packages/semantic_registry/semantic_registry/query_planner.py`
- `packages/semantic_registry/semantic_registry/sql_guard.py`
- `packages/semantic_mcp/semantic_mcp/tools.py` only by MCP integration lane
- `tests/semantic_registry/**`
- `tests/semantic_mcp/test_query_planner_tools.py`
- `packages/semantic_contracts/**` only for additive SQL guard schema updates assigned to a single contract-maintainer lane

### Files forbidden to modify

- `packages/semantic_builder/**`
- UI files
- any actual SQL execution function
- any DB connector runtime

### Agent lanes

| Lane | Worker | Write scope | Responsibility |
|---|---:|---|---|
| Planner/guard hardening lane | worker-1 | `query_planner.py`, `sql_guard.py` | Improve planner output and SQL guard logic without changing ownership |
| MCP integration lane | worker-2 | `packages/semantic_mcp/semantic_mcp/tools.py` only | Wire planner/guard into MCP tools without changing server/resources |
| Verifier lane | worker-3 | Phase 3 tests only | Positive/negative SQL guard tests and no-execution audit |

### Acceptance criteria

- `plan_data_query` returns required terms, metrics, tables, joins, filters, policy notes, ambiguities, and `execution_allowed: false`.
- `validate_sql` blocks non-SELECT statements.
- `validate_sql` blocks multi-statement SQL.
- `validate_sql` checks allowed tables.
- `validate_sql` checks blocked columns.
- SQL validation never executes SQL.

### Tests

- Unit: valid SELECT against allowed table passes validation.
- Unit: `DROP`, `INSERT`, `UPDATE`, `DELETE` fail.
- Unit: semicolon multi-statement fails.
- Unit: unknown table fails.
- Unit: blocked PII column fails.
- Integration: MCP `validate_sql` returns same decision shape as Registry guard.

### Risks

- SQL parsing may be naive; document limitations and prefer conservative blocking.
- `SELECT *` policy needs an explicit decision. Recommended: allow only if expanded columns can be proven safe; otherwise warn or fail.
- Planner may appear to generate SQL; keep it to planning/validation unless future phase explicitly approves SQL generation.

### Exact `$team` launch prompt

```bash
$team 3:executor "Phase 3 only for semantic-data-context query planner and SQL guard. Do not implement SQL execution, DB connectors, Builder, or UI. Use lane contracts and no overlapping file edits. worker-1 Planner/guard hardening lane: harden Registry query_planner.py and sql_guard.py with stronger term/metric/join planning, SELECT-only, multi-statement block, allowed table, blocked column checks, and execution_allowed=false. worker-2 MCP integration lane: modify only packages/semantic_mcp/semantic_mcp/tools.py to route plan_data_query and validate_sql to Registry planner/guard. worker-3 Verifier lane: write Phase 3 tests for positive/negative SQL guard cases, MCP integration, and no execute_query/no DB execution audit. Report evidence."
```

## 10. Phase 4 — File-Based Builder MVP

### Objective

Implement a file-based scanner/profiler MVP for CSV, JSON, and XLSX. It should profile schema/columns safely and emit `semantic_pack.draft.yaml` without requiring LLM calls.

### Files to create

Builder lane:

- `packages/semantic_builder/pyproject.toml` or package config
- `packages/semantic_builder/semantic_builder/__init__.py`
- `packages/semantic_builder/semantic_builder/scanner.py`
- `packages/semantic_builder/semantic_builder/profiler.py`
- `packages/semantic_builder/semantic_builder/draft_pack.py`
- `packages/semantic_builder/semantic_builder/sources/csv_source.py`
- `packages/semantic_builder/semantic_builder/sources/json_source.py`
- `packages/semantic_builder/semantic_builder/sources/xlsx_source.py`

Fixture/test lane:

- `tests/semantic_builder/test_csv_source.py`
- `tests/semantic_builder/test_json_source.py`
- `tests/semantic_builder/test_xlsx_source.py`
- `tests/semantic_builder/test_draft_pack.py`

### Files allowed to modify

- `packages/semantic_builder/**`
- `tests/semantic_builder/**`
- `docs/reference/test_datasets/**` only for non-destructive manifest additions if needed
- `packages/semantic_contracts/**` only for additive draft status/profile schema support assigned to one contract-support lane

### Files forbidden to modify

- `packages/semantic_mcp/**` unless explicitly assigned in a later integration phase
- UI files
- runtime DB connector implementation
- SQL execution code
- raw source dataset files except read-only use

### Agent lanes

| Lane | Worker | Write scope | Responsibility |
|---|---:|---|---|
| Builder source lane | worker-1 | `sources/*.py`, `scanner.py` | CSV/JSON/XLSX source reading and sheet/table detection |
| Builder profile/draft lane | worker-2 | `profiler.py`, `draft_pack.py` | Safe profiling, PII candidates, draft pack emission |
| Verifier lane | worker-3 | `tests/semantic_builder/**` | Tests with Sample Superstore and copied xlsx fixtures; safety audit |

### Acceptance criteria

- CSV, JSON, and XLSX files can be scanned locally.
- XLSX scanner handles multi-sheet workbooks.
- Profiler captures schema, column types, null ratio, cardinality estimate, safe top-N/category candidates, numeric/date min-max where practical, join key candidates, and PII candidates.
- Name-like columns are not emitted as value dictionaries.
- Draft pack output validates or produces actionable validation errors through `semantic_contracts`.
- No PostgreSQL runtime connector is implemented in this phase.

### Tests

- Unit: CSV schema/profile.
- Unit: JSON schema/profile.
- Unit: XLSX workbook sheet detection.
- Unit: PII candidate detection for name/email/phone-like columns.
- Unit: high-cardinality values do not become full dictionaries.
- Integration: draft pack generated from Sample Superstore validates or returns expected draft validation messages.

### Risks

- Data type inference can become complex; keep MVP simple and transparent.
- Large workbook handling may be slow; tests should use bounded samples where needed.
- Profiling rules may accidentally preserve sensitive values; verifier must inspect outputs.

### Exact `$team` launch prompt

```bash
$team 3:executor "Phase 4 only for semantic-data-context file-based Builder MVP. Do not implement PostgreSQL runtime, MCP changes, UI, or execute_query. Use lane contracts and no overlapping file edits. worker-1 Builder source lane: implement scanner.py and sources/csv_source.py, json_source.py, xlsx_source.py for local file/sheet detection. worker-2 Builder profile-draft lane: implement profiler.py and draft_pack.py with safe top-N, cardinality/null stats, join candidates, PII candidates, and semantic_pack.draft.yaml emission. worker-3 Verifier lane: write tests/semantic_builder using Sample Superstore and docs/reference/test_datasets fixtures; verify no raw PII value dictionaries and no forbidden runtime. Report evidence."
```

## 11. Phase 5 — LLM Semantic Hypothesis + Reverse Question Generator

### Objective

Add optional LLM-assisted hypothesis generation and reverse-question generation on top of Builder profiles. Outputs must be marked as draft/hypothesis and must not be treated as confirmed business truth.

### Files to create

LLM hypothesis lane:

- `packages/semantic_builder/semantic_builder/hypothesis.py`
- `packages/semantic_builder/semantic_builder/reverse_questions.py`
- `packages/semantic_builder/semantic_builder/prompts.py`

Verifier lane:

- `tests/semantic_builder/test_hypothesis.py`
- `tests/semantic_builder/test_reverse_questions.py`
- `tests/semantic_builder/test_hypothesis_safety.py`

### Files allowed to modify

- `packages/semantic_builder/semantic_builder/hypothesis.py`
- `packages/semantic_builder/semantic_builder/reverse_questions.py`
- `packages/semantic_builder/semantic_builder/prompts.py`
- `packages/semantic_builder/semantic_builder/draft_pack.py` only for integrating hypothesis fields
- `tests/semantic_builder/**`
- `packages/semantic_contracts/**` only for additive hypothesis/reverse-question schema fixes assigned to a single contract-support lane

### Files forbidden to modify

- `packages/semantic_mcp/**` unless a later integration phase explicitly allows it
- UI files
- SQL execution code
- feedback store runtime beyond existing Registry contract
- production LLM credential/config files

### Agent lanes

| Lane | Worker | Write scope | Responsibility |
|---|---:|---|---|
| Hypothesis lane | worker-1 | `hypothesis.py`, `prompts.py` | Meaning/metric/business-term hypothesis generation contract and prompt scaffolds |
| Reverse-question lane | worker-2 | `reverse_questions.py`, `draft_pack.py` integration only | Generate domain-owner questions from uncertainties |
| Verifier lane | worker-3 | `tests/semantic_builder/test_hypothesis*.py`, `test_reverse_questions.py` | Deterministic tests with fake LLM/stubbed responses and safety audit |

### Acceptance criteria

- LLM calls are optional and mockable.
- Offline tests pass without real credentials.
- All generated semantic meanings are marked `draft` with confidence/source.
- Reverse questions include target, question, reason, status, and optional answer fields.
- No generated hypothesis stores raw PII values.
- Human confirmation remains a contract/status concept; no UI is built.

### Tests

- Unit: fake LLM response maps to draft hypotheses.
- Unit: uncertainties generate reverse questions.
- Unit: PII-like columns are redacted or excluded from prompt payloads.
- Unit: generated draft pack still validates.
- Scope audit: no UI, no execute_query, no production credential requirement.

### Risks

- LLM output can be unstable; tests must use deterministic fake responses.
- Prompt payload may leak sample values; restrict payload to safe profiles.
- Users may confuse hypotheses with confirmed truth; status/source fields must be visible.

### Exact `$team` launch prompt

```bash
$team 3:executor "Phase 5 only for semantic-data-context LLM hypothesis and reverse-question generator. Do not build UI, execute_query, production credentials, or MCP changes. Use lane contracts and no overlapping file edits. worker-1 Hypothesis lane: implement hypothesis.py and prompts.py with optional/mockable LLM hypothesis contracts, draft status, confidence, source, and PII-safe prompt payloads. worker-2 Reverse-question lane: implement reverse_questions.py and only the minimal draft_pack.py integration needed to include reverse questions. worker-3 Verifier lane: write deterministic tests with fake LLM responses, safety tests for PII redaction, and audit no UI/no execute_query/no credential dependency. Report evidence."
```

## 12. Team Verification Path

Every `$team` run must finish with verifier evidence:

1. List files changed by each lane.
2. Run the phase's targeted tests.
3. Run guardrail searches that distinguish implementation from negative tests:

```bash
# Forbidden runtime/API/UI implementation search. Tests may contain negative SQL strings, so scan packages first.
rg -n "def execute_query|execute_query\s*=|execute_query\(|dashboard|streamlit|gradio|flask|fastapi" packages semantic_packs || true

# SQL mutation strings are allowed in negative tests, but forbidden in runtime implementation paths.
rg -n "CREATE TABLE|DROP TABLE|INSERT INTO|UPDATE .* SET|DELETE FROM" packages || true
```

The verifier must classify hits as either expected contract/test text or forbidden implementation.

4. Confirm no worker edited another lane's files.
5. Confirm no raw PII values were added to Semantic Pack value dictionaries.
6. Confirm package imports or validation commands used by the phase.

## 13. First Recommended `$team` Prompt

Use this first, only after explicitly approving Phase 0 execution:

```bash
$team 3:executor "Phase 0 only for semantic-data-context. Do not implement Registry, MCP, Builder runtime, UI, or execute_query. Use lane contracts and do not edit another lane's files. worker-1 Contract lane: create packages/semantic_contracts Pydantic models, validators, errors, SQL guard contract models, and MCP tool contract models only. worker-2 Fixture lane: populate/replace the existing semantic_packs/demo_company/revenue.v0_1.yaml placeholder from SEMANTIC_PACK_SPEC and Sample Superstore, with PII-safe handling of name-like fields. worker-3 Verifier lane: create tests/semantic_contracts only, verify demo pack validation and SQL guard and MCP tool contract shapes, and audit that no forbidden runtime/UI/query execution files were added. Report evidence and failing tests if any."
```

## 14. Remaining Risks

- Python packaging convention is not fixed; Phase 0 may need a small tooling decision.
- Pydantic version should be selected before implementing contracts.
- MCP SDK behavior may change exact server/test structure in Phase 2.
- SQL parsing quality in Phase 3 can be deceptively hard; start conservative.
- Builder profiling may leak sample values if safety filters are weak.
- Team workers can conflict if they ignore lane ownership; verifier must audit changed files.

## 15. Stop Rules

Stop and ask the user before proceeding if:

- a phase requires editing files outside its allowed scope
- workers need to modify shared package config from multiple lanes
- any design requires SQL execution
- any design requires dashboard/UI work
- any implementation needs real credentials or production database access
- tests require installing a major framework not already agreed
