# MVP SCOPE

## 1. MVP Goal

Build the smallest local system that proves a **Semantic Pack** can act as the source of truth for external LLM/Agent/App usage through a local Registry and stdio MCP server.

The MVP should demonstrate:

- one shared Semantic Pack schema
- one demo semantic pack
- local registry loading/search/validation
- local stdio MCP tools
- SQL guard validation
- feedback JSONL persistence
- basic tests

## 2. Included in 1st MVP

## 2.0 Phase 0 Implementation Slice

Phase 0 is the first executable implementation slice. It must remain smaller than the full MVP.

Phase 0 includes only:

- `semantic_contracts` schema/types/validators
- one demo Semantic Pack YAML
- tests for pack validation, schema validation, and SQL guard contract behavior

Phase 0 excludes:

- Registry runtime implementation
- MCP server runtime implementation
- Builder scanner implementation
- feedback runtime persistence beyond contract/test fixtures
- SQL execution
- UI of any kind

The rest of this document describes the full 1st MVP target. Registry, MCP, and Builder should be attached sequentially after Phase 0 passes.

### 2.1 Packages

- `packages/semantic_contracts`
  - shared schema/contracts
  - pack validation types
  - MCP tool input/output schemas
  - SQL guard result schema

- `packages/semantic_registry`
  - local pack loader
  - validation entrypoint
  - semantic space listing
  - local search over pack cards
  - version metadata handling
  - feedback JSONL writer

- `packages/semantic_mcp`
  - local MCP stdio server
  - exposes Registry resources/tools/prompts
  - deterministic JSON-compatible tool responses

- `packages/semantic_builder`
  - minimal file-source scanner/draft builder
  - CSV/XLSX/JSON metadata and profiling direction
  - PostgreSQL connector interface can be specified before full implementation
  - MySQL read-only fixture/demo scanner support is now allowed as an explicit, opt-in DB-backed validation target; production MySQL operations remain out of scope.
  - emits `semantic_pack.draft.yaml`

### 2.2 Demo Semantic Pack

- `semantic_packs/demo_company/revenue.v0_1.yaml`
- primary example dataset: `/Users/jtm427/Documents/내 Tableau 리포지토리/데이터 원본/2025.2/ko_KR-APAC/Sample - Superstore.xls`
- source workbook sheets:
  - `Orders` — 10,194 rows; sales/profit/order/customer/product fields
  - `People` — 4 rows; regional manager by region
  - `Returns` — 296 rows; returned order IDs
- domain: demo company sales/revenue/profit/customer-segment/product/category/returns analysis
- should use safe sample values only
- should model:
  - tables
  - columns
  - value dictionaries
  - metrics
  - business terms
  - join recipes
  - policies
  - verified queries


### 2.2.1 Secondary Builder Test Fixtures

Additional copied workbook fixtures live under:

```text
docs/reference/test_datasets/sinagong_tableau_2026/
```

Index file:

```text
docs/reference/test_datasets/DATASET_MANIFEST.md
```

Use these after the canonical Sample Superstore path to test broader workbook scanning and profiling behavior across weather, HR, sales, population, retail, transport, and public-statistics style examples.

### 2.3 MCP Tools

Required tools:

1. `list_semantic_spaces`
2. `search_semantic_context`
3. `resolve_business_terms`
4. `plan_data_query`
5. `validate_sql`
6. `record_feedback`

### 2.4 SQL Guard

MVP SQL guard must support:

- SELECT-only validation
- multi-statement blocking
- allowed table check
- blocked column detection
- basic policy explanation in validation output

The guard does **not** execute SQL.

### 2.5 Feedback Store

- local JSONL file
- append-only
- records tool feedback, validation feedback, missing context, and incorrect mapping reports
- must avoid storing raw PII values

### 2.6 Tests

Basic tests should cover:

- demo pack validation
- registry load/list/search
- business term resolution
- SQL guard pass/fail cases
- MCP tool schema shape
- feedback JSONL append behavior

### 2.7 Context Retrieval / VDB Boundary

The MVP must support context retrieval through local Registry search over Semantic Pack cards. This can be lexical or structured search.

The MVP must not require:

- production VDB
- embedding pipeline
- vector index service
- semantic similarity infrastructure

VDB/domain-memory concepts from the original plan are preserved as a future-compatible direction, but the MVP contract is local Semantic Pack retrieval.

### 2.8 Human-in-the-loop Boundary

Human-in-the-loop is preserved in the data contract, not as a UI requirement.

The MVP should represent human confirmation through fields such as:

- card `status`
- `confidence`
- `reverse_questions.status`
- `reverse_questions.answer`
- `source: profiler | llm | human | verified_query`

The MVP must not implement a Human confirmation UI.

## 3. Explicit Non-Goals for 1st MVP

The following are intentionally excluded:

- dashboard UI
- independent BI platform UI
- customer-facing analytics portal
- SaaS multi-tenancy
- authentication/authorization system beyond local policy metadata
- `execute_query`
- real operational DB execution
- production DB connection runtime
- full vector database
- embedding pipeline as a hard dependency
- Human confirmation UI
- Oracle connector
- Production MySQL connector usage beyond the explicit local fixture/demo read-only path
- complex ontology graph
- production audit logging
- cloud deployment
- billing, seats, plans, or enterprise packaging

## 4. MVP Flow

```text
Semantic Pack YAML
      ↓
semantic_contracts validation
      ↓
semantic_registry local load/search
      ↓
semantic_mcp stdio tools
      ↓
external LLM/Agent/App
      ↓
validate_sql + record_feedback
```

Builder enters after contracts are stable:

```text
CSV/XLSX/JSON/PostgreSQL/MySQL fixture metadata
      ↓
profile schema/columns/values safely
      ↓
LLM meaning hypotheses + reverse questions
      ↓
semantic_pack.draft.yaml
      ↓
Registry validation
```

## 5. Acceptance Criteria

The MVP scope is valid when:

- all required packages have defined responsibilities
- all required MCP tools have input/output schemas
- demo semantic pack can be validated by contracts
- SQL guard behavior is deterministic and validation-only
- feedback is persisted locally as JSONL
- no UI or SQL execution work is included in the first milestone
