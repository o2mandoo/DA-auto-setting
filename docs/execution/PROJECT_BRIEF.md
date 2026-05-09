# PROJECT BRIEF — Semantic Data Context System

## 1. Purpose

This repository builds a **Semantic Data Context System**.

The system scans data sources, converts domain knowledge into a reusable **Semantic Pack**, stores that pack in a local **Semantic Registry**, and exposes the pack through a **Local MCP Server** so external LLMs, agents, and applications can safely use the same semantic context.

## 2. Reference Boundary

Primary execution 기준 are the documents in `docs/execution/`:

- `PROJECT_BRIEF.md`
- `MVP_SCOPE.md`
- `MODULES.md`
- `SEMANTIC_PACK_SPEC.md`

Original reference:

- `docs/reference/original-service-plan.pdf`

The original PDF should be used for background ideas such as:

- physical schema alone is insufficient for domain-aware data analysis
- business terms often differ from database column names
- low-cardinality value dictionaries are useful for interpreting coded values
- LLMs should generate reverse questions instead of silently guessing ambiguous domain rules
- verified queries, metrics, policies, and feedback loops improve reliability
- PII and sensitive raw values require strict handling

However, the current repository **does not adopt the original plan's positioning as a customer-dedicated BI/data-analysis platform**.

## 3. Current Product Definition

> Semantic Data Context System: a shareable context layer for data-aware LLMs, agents, and apps.

It is not an end-user BI product. The product provides semantic context and validation interfaces that other systems can consume.

The system has three major capabilities:

1. **Semantic Builder**
   - scans CSV/XLSX/JSON/PostgreSQL sources
   - profiles schemas, columns, values, PII candidates, and join candidates
   - uses LLMs to create meaning hypotheses and reverse questions
   - emits `semantic_pack.draft.yaml`

2. **Semantic Registry / Control Plane**
   - stores Semantic Packs as source of truth
   - manages cards and rules such as Table Card, Column Card, Value Dictionary, Metric, Business Term, Join Recipe, Policy, and Verified Query
   - provides validation, versioning, search, and feedback storage

3. **Local MCP Server**
   - exposes Semantic Pack context through MCP resources/tools/prompts
   - starts with stdio transport
   - lets external LLMs/agents/apps call context search, term resolution, query planning, SQL validation, and feedback recording tools


## 3.1 Canonical Example Dataset

Use the local Tableau sample workbook as the first concrete example dataset:

```text
/Users/jtm427/Documents/내 Tableau 리포지토리/데이터 원본/2025.2/ko_KR-APAC/Sample - Superstore.xls
```

Verified workbook structure:

| Sheet | Rows | Key columns |
|---|---:|---|
| `Orders` | 10,194 | `Order ID`, `Order Date`, `Ship Date`, `Ship Mode`, `Customer ID`, `Segment`, `Region`, `Category`, `Sub-Category`, `Sales`, `Quantity`, `Discount`, `Profit` |
| `People` | 4 | `Regional Manager`, `Region` |
| `Returns` | 296 | `Order ID`, `Returned` |

This dataset should be used for the first demo Semantic Pack and Builder profiling examples. It represents a safe local sample domain for sales, profit, customer segment, regional manager, product category, and return-status semantics.


Additional Builder test dataset folder:

```text
docs/reference/test_datasets/sinagong_tableau_2026/
```

Manifest:

```text
docs/reference/test_datasets/DATASET_MANIFEST.md
```

This folder contains 20 copied `.xlsx` practice/source datasets from the Sinagong Tableau 2026 example-file directory. Use it as a broader scanner/profiler fixture set after the Sample Superstore canonical demo path is stable.

## 4. Primary Users

### First users

- AI/agent developers who need domain context for Text-to-SQL or data agents
- Data platform engineers building internal semantic layers
- Analytics engineers who want explicit metric and term definitions
- Solution engineers packaging context for customer or team-specific agents

### External consumers

- LLM agents
- local developer tools
- IDE or notebook assistants
- BI copilots
- data quality or SQL validation workflows

## 5. Product Principles

1. **Semantic Pack is the source of truth.**
2. **Builder, Registry, and MCP share one schema.**
3. **MCP is the safe external interface.**
4. **SQL validation comes before SQL execution.**
5. **PII raw values must not be stored or embedded.**
6. **Every MCP tool must have explicit input/output schema.**
7. **Contracts first, Registry second, MCP third, Builder fourth.**
8. **Human confirmation is modeled in the pack, but UI is not in MVP.**

## 6. What This Repo Should Produce First

The first milestone is not product code. It is the executable seed/spec baseline:

- `specs/seeds/semantic-data-context.seed.yaml`
- `docs/execution/PROJECT_BRIEF.md`
- `docs/execution/MVP_SCOPE.md`
- `docs/execution/MODULES.md`
- `docs/execution/SEMANTIC_PACK_SPEC.md`

After these are stable, implementation should start with `semantic_contracts`.


## 6.1 Phase 0 Boundary

The first implementation slice is intentionally smaller than the full MVP.

Phase 0 includes only:

- shared Semantic Pack contracts
- one demo Semantic Pack
- tests for pack validation and SQL guard contract behavior

Phase 0 does not implement Registry runtime, MCP runtime, Builder scanner runtime, SQL execution, or any UI.

Human-in-the-loop from the original plan is preserved as pack status/source/reverse-question fields. VDB/domain-memory from the original plan is preserved as a retrieval direction, but MVP retrieval starts as local Semantic Pack card search.

## 7. Success Criteria for the MVP Direction

The MVP is successful if an external agent can:

1. discover available semantic spaces
2. search semantic context from a demo pack
3. resolve business terms such as “net revenue” or “new customer”
4. plan a data query without executing it
5. validate SQL against table/column/policy rules
6. record feedback to local JSONL

The MVP is not required to run real queries, render dashboards, or provide a human confirmation UI.
