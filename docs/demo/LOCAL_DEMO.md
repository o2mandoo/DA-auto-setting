# Local Demo: Semantic Data Context System

This demo runs the complete local path without external services or production database credentials.

```bash
PYTHONPATH=packages/semantic_contracts:packages/semantic_builder/src:packages/semantic_registry:packages/semantic_mcp/src:/tmp/semantic-data-context-deps \
python3 scripts/demo/run_local_demo.py
```

Run this from the repository root. If you already have a virtualenv active, keep the repository package paths ahead of `/tmp/semantic-data-context-deps` so the checkout code wins over any temporary dependency cache.

The script performs:

1. scan `examples/demo_data`
2. profile columns
3. infer deterministic draft semantic hypotheses
4. generate onboarding/reverse questions
5. build `runtime/phase12_demo/semantic_pack.draft.yaml`
6. create a safe confirmation/proposal object
7. promote a copy of the demo pack in memory
8. list/search/resolve via MCP-like tool functions
9. plan and validate a golden revenue question
10. run local/demo `preview_query`
11. run the Phase 11 eval benchmark

Outputs are written under `runtime/phase12_demo/` and include the scan report, profiles, semantic hypotheses, onboarding questions, draft pack, preview audit, eval report, and demo summary.

Safety boundaries:

- no production `execute_query`
- no dashboard UI
- no SaaS multi-tenancy
- no raw PII in generated summary output
- preview is local fixture only and validation-gated
- Weaviate is the intended VDB backend; if unavailable, callers must receive an explicit backend/config error instead of silent keyword fallback
