# Phase 12 Security and Scope Checklist

Required checks before treating the local package as demo-ready:

- `execute_query` must not exist as a product function or MCP tool.
- `preview_query` is local/demo only, validation-gated, row-limited, and audited.
- SQL guard blocks non-SELECT, multi-statement SQL, unknown/disallowed tables, and blocked PII columns.
- PII candidates must not emit raw values into value dictionaries, embeddings, feedback, eval reports, demo summaries, or indexed search payloads.
- Generated benchmark and final-report artifacts under `reports/**` must stay free of raw PII literals.
- Weaviate is the intended VDB backend. If Weaviate is requested but unavailable or unconfigured, the system must return an explicit backend/config error and must not silently fall back to keyword search.
- Feedback and confirmation records must not mutate an approved pack directly.
- PostgreSQL and explicit MySQL fixture/demo scanning are read-only and credential-free in tests/docs; no production credentials are stored in this repo.
- Dashboard UI and SaaS multi-tenancy are non-goals for this local package.

Verification commands:

```bash
PYTHONPATH=packages/semantic_contracts:packages/semantic_builder/src:packages/semantic_registry:packages/semantic_mcp/src:/tmp/semantic-data-context-deps python3 -m unittest discover -s tests/security -v
PYTHONPATH=packages/semantic_contracts:packages/semantic_builder/src:packages/semantic_registry:packages/semantic_mcp/src:/tmp/semantic-data-context-deps python3 -m unittest discover -s tests/registry -v
PYTHONPATH=packages/semantic_contracts:packages/semantic_builder/src:packages/semantic_registry:packages/semantic_mcp/src:/tmp/semantic-data-context-deps python3 -m unittest discover -s tests/mcp -v
```
