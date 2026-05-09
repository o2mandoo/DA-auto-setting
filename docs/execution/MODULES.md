# MODULES

## 1. Module Overview

This repo is organized around four packages that share one Semantic Pack schema.

```text
semantic_builder  →  semantic_pack.draft.yaml
                         ↓
semantic_contracts  →  validation and shared schemas
                         ↓
semantic_registry   →  source-of-truth local store/search/feedback
                         ↓
semantic_mcp        →  external interface for LLMs/agents/apps
```

Implementation order:

0. Phase 0: `semantic_contracts` + demo Semantic Pack + tests only
1. `semantic_registry`
2. `semantic_mcp`
3. `semantic_builder`

Registry, MCP, and Builder are part of the full MVP path, but they must not be implemented inside Phase 0.

## 2. `semantic_contracts`

### Responsibility

Defines the shared schema and typed contracts used by Builder, Registry, and MCP.

### Owns

- Semantic Pack schema
- card schemas:
  - Table Card
  - Column Card
  - Value Dictionary
  - Metric
  - Business Term
  - Join Recipe
  - Policy
  - Verified Query
- MCP tool input/output schemas
- SQL guard result schema
- validation error schema
- version metadata schema

### Should expose

- `validate_semantic_pack(pack) -> ValidationResult`
- `load_pack_yaml(path) -> SemanticPack`
- schema constants or JSON schema export
- shared error codes

### Must not own

- filesystem registry state
- MCP server runtime
- source scanning logic
- LLM prompts

## 3. `semantic_registry`

### Responsibility

Stores and queries Semantic Packs as local source of truth.

### Owns

- local pack discovery
- semantic space listing
- pack version lookup
- pack validation orchestration
- local search over pack cards
- card indexing / retrieval-document projection
- business term lookup
- table/column/policy lookup
- feedback JSONL store
- retrieval document projection and backend seams under `semantic_registry/retrieval/`

### Should expose

- `list_semantic_spaces() -> list[SemanticSpaceSummary]`
- `get_pack(space_id, version=None) -> SemanticPack`
- `search_context(query, filters) -> SearchResult`
- `resolve_terms(terms, space_id) -> TermResolutionResult`
- `validate_sql(sql, context) -> SqlValidationResult`
- `record_feedback(feedback) -> FeedbackReceipt`

### Retrieval layer

See `docs/execution/RETRIEVAL_LAYER.md` for the Phase 7 retrieval contract.

The retrieval layer stays under the registry package and must remain:

- PII-safe
- local-first by default
- explicit about Weaviate availability/errors
- free of silent keyword fallback after a backend failure

### Storage

MVP storage is local files:

```text
semantic_packs/{space_id}/{pack}.yaml
.runtime/feedback/{space_id}.jsonl
```

If `.runtime/` is not desired in source control, it should be gitignored during implementation.

### Must not own

- MCP protocol handling
- product UI
- DB query execution

## 4. `semantic_mcp`

### Responsibility

Exposes Registry capabilities through a local MCP server.

### Transport

MVP transport:

- stdio

Future transports may be added later, but are not part of MVP.

### Required tools

- `list_semantic_spaces`
- `search_semantic_context`
- `resolve_business_terms`
- `plan_data_query`
- `validate_sql`
- `record_feedback`

### Required resources/prompts direction

Potential MCP resources:

- semantic pack metadata
- business glossary
- metric catalog
- table/column cards
- policy summary

Potential MCP prompts:

- domain-aware SQL planning prompt
- ambiguity/reverse-question prompt
- SQL validation explanation prompt

### Must not own

- Semantic Pack schema definition
- local pack persistence rules
- SQL execution
- UI

## 5. `semantic_builder`

### Responsibility

Builds draft Semantic Packs from source metadata/profiles.

### Supported source direction

MVP target sources:

- CSV
- XLSX
- JSON
- PostgreSQL

Implementation can start with local files and stub/contract PostgreSQL scanning before full connector behavior.


### First Example Dataset

Use this workbook as the first Builder/Registry demo fixture:

```text
/Users/jtm427/Documents/내 Tableau 리포지토리/데이터 원본/2025.2/ko_KR-APAC/Sample - Superstore.xls
```

Initial sheet mapping:

- `Orders` → fact-like order line table candidate
- `People` → region manager dimension candidate
- `Returns` → return status lookup/fact candidate keyed by `Order ID`


Additional fixture collection:

```text
docs/reference/test_datasets/sinagong_tableau_2026/
docs/reference/test_datasets/DATASET_MANIFEST.md
```

This collection should be used to test generic workbook scanning beyond the canonical Sample Superstore domain.

Name-like fields in sample workbooks, such as customer or manager names, should be treated as PII candidates in Builder/contract tests. They must not become value dictionary entries or embedding payloads.

Likely first metrics/business terms:

- `Sales` → sales amount
- `Profit` → profit amount
- `Discount` → discount rate
- `Returned` → return flag
- `Segment`, `Region`, `Category`, `Sub-Category`, `Ship Mode` → safe categorical value dictionaries

### Collects

- schema/table/column metadata
- data type
- nullable
- null ratio
- cardinality estimate
- column profile summaries for safe search and draft inference
- top-N values for safe low-cardinality fields
- min/max for numeric/date fields
- date column candidates
- ID/join key candidates
- PII candidates
- metric/fact table candidates

### LLM-assisted outputs

- table meaning hypotheses
- column meaning hypotheses
- metric hypotheses
- business term hypotheses
- reverse questions for domain owners

### Emits

- `semantic_pack.draft.yaml`

### Safety constraints

- do not store raw PII values
- do not collect full distinct values for high-cardinality columns
- do not run heavy production queries by default
- do not execute analytical SQL for users
- mark unconfirmed LLM outputs as `status: draft` or `confidence`

## 6. Cross-Module Contracts

All modules must agree on:

- `space_id`
- pack `version`
- card IDs
- table/column identifiers
- metric IDs
- business term IDs
- policy IDs
- validation error format
- feedback record format

## 7. Build Order Rationale

0. **Phase 0: Contracts + demo pack + tests only** because the repo needs a stable executable baseline before runtime modules exist.
1. **Registry second** because MCP and Builder both need a source-of-truth store.
2. **MCP third** because external agents need stable Registry-backed tools.
3. **Builder fourth** because draft generation is less valuable before validation and Registry behavior are stable.

Phase 0 may define contracts for Registry/MCP/Builder, but must not implement their runtimes.
