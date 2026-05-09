# Semantic Data Context System

A local, shareable **Semantic Data Context System** that turns data-source knowledge into versioned Semantic Packs and exposes that context to LLMs, agents, and apps through a Registry and Local MCP Server.

It is not a dashboard, SaaS BI platform, or production SQL execution engine.

## What is included

- **Semantic Builder**: scans CSV/JSON/XLS/XLSX and safe PostgreSQL metadata/profiles, profiles columns, detects PII candidates, generates draft hypotheses/questions, and writes draft Semantic Packs.
- **PostgreSQL scanner/profiler**: read-only, fixture-safe metadata/profile path for PostgreSQL sources.
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
export PYTHONPATH=packages/semantic_contracts:packages/semantic_builder/src:packages/semantic_registry:packages/semantic_mcp/src:/tmp/semantic-data-context-deps
```

## Local demo

```bash
PYTHONPATH=packages/semantic_contracts:packages/semantic_builder/src:packages/semantic_registry:packages/semantic_mcp/src:/tmp/semantic-data-context-deps \
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
- Dashboard UI and SaaS multi-tenancy are non-goals.

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
