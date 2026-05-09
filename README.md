# Semantic Data Context System

A local, shareable **Semantic Data Context System** that turns data-source knowledge into versioned Semantic Packs and exposes that context to LLMs, agents, and apps through a Registry and Local MCP Server.

It is not a dashboard, SaaS BI platform, or production SQL execution engine.

## What is included

- **Semantic Builder**: scans CSV/JSON/XLS/XLSX and safe PostgreSQL metadata/profiles, profiles columns, detects PII candidates, generates draft hypotheses/questions, and writes draft Semantic Packs.
- **PostgreSQL scanner/profiler**: read-only, fixture-safe metadata/profile path for PostgreSQL sources.
- **MySQL fixture/scanner path**: explicit MySQL fixture DDL/comment planner plus read-only scanner surface that preserves the same comment provenance contract; live MySQL evidence remains opt-in and is not claimed unless the gated local fixture run is executed.
- **Semantic Registry**: loads Semantic Packs as source of truth, lists spaces, searches/resolve cards, stores feedback, handles proposal/confirmation/promotion guards.
- **Local MCP Server**: exposes deterministic tool/resource/prompt functions over the Registry.
- **Retrieval layer**: keyword backend plus explicit Weaviate backend configuration path. No silent fallback when Weaviate is requested and unavailable.
- **Domain-aware runtime**: plans questions, detects ambiguity, prefers verified queries, validates SQL with policy/semantic guards.
- **Safe preview**: local/demo fixture preview only; no production execution.
- **Evaluation harness**: dataset manifests, golden questions, red-team cases, and benchmark report generation.

## Package entrypoints

Declared console scripts:

- `semantic-builder`
- `semantic-registry`
- `semantic-mcp`
- `semantic-eval`

Use `--help` on each command for the reproducible local CLI flow. The exact local-demo path lives in `docs/demo/LOCAL_DEMO.md`, and the optional Weaviate configuration notes live in `docs/demo/WEAVIATE_OPTIONAL.md`.

For source checkout usage, set:

```bash
export PYTHONPATH=packages/semantic_contracts:packages/semantic_builder/src:packages/semantic_registry:packages/semantic_mcp/src
```

## Local demo

```bash
PYTHONPATH=packages/semantic_contracts:packages/semantic_builder/src:packages/semantic_registry:packages/semantic_mcp/src \
python3 scripts/demo/run_local_demo.py
```

Outputs are written to `runtime/phase12_demo/` and include a scan report, profiles, semantic hypotheses, onboarding questions, a draft pack, preview audit, eval report, and demo summary.

See `docs/demo/LOCAL_DEMO.md` for the exact path.
For clone-ready install/provider/test instructions, see `docs/setup/DEVELOPMENT.md`.

## Safety rules

- `execute_query` is forbidden.
- `preview_query` is allowed only for local/demo data after validation.
- PII raw values must not be stored or embedded.
- Feedback cannot mutate approved packs.
- Weaviate backend requests must fail explicitly if not configured; no silent keyword fallback.
- PostgreSQL support is read-only scanner/profiler scope unless separately approved.
- MySQL support is explicit and no-fallback: fixture/schema names must stay under `semantic_fixture_*`; `synthetic_comments` stay test-only; missing live MySQL config/dependency evidence must be reported as pending or an explicit error, never rerouted to PostgreSQL, DuckDB, or SQLite.
- Dashboard UI and SaaS multi-tenancy are non-goals.


## DB fixture and MySQL readiness

DB-backed fixture work is product-external and safety-gated. See `docs/dev/DB_FIXTURE_GUIDE.md` and `docs/product/METADATA_PROVENANCE_RULES.md` for the source-of-truth rules. Current code-level coverage includes:

- `no_comments`, `real_comments`, and `synthetic_comments` fixture modes.
- PostgreSQL and MySQL fixture DDL/comment planners with backend-specific syntax.
- MySQL scanner exports that label connector and provenance evidence as `mysql` rather than silently using PostgreSQL evidence.

Readiness is **PARTIAL** until live DB evidence is collected under explicit local fixture gates. A MySQL run requires `SEMANTIC_CONTEXT_FIXTURE_DB=1` plus target-specific MySQL opt-in/config such as `SEMANTIC_MYSQL_ENABLED=1`, `SEMANTIC_MYSQL_DSN`, `SEMANTIC_MYSQL_DATABASE`, and `SEMANTIC_MYSQL_TABLES`. Without that live run, reports should say `live_mysql_evidence_pending` or show the exact configuration/dependency error.

## Source-of-truth docs

- `docs/setup/DEVELOPMENT.md`
- `docs/execution/PROJECT_BRIEF.md`
- `docs/execution/MVP_SCOPE.md`
- `docs/execution/MODULES.md`
- `docs/execution/SEMANTIC_PACK_SPEC.md`
- `docs/execution/FINAL_PHASE_ROADMAP.md`
- `docs/execution/RETRIEVAL_LAYER.md`
- `docs/execution/VALIDATION_DATASETS.md`
- `docs/execution/DATASET_BENCHMARKS.md`
- `docs/execution/SECURITY_CHECKLIST.md`
