# Production Risk Register

## Scope

This register compares the current implementation against the chosen production target:

- clone-ready package
- local MCP surface
- optional local HTTP adapter

It intentionally does **not** treat SaaS/BI/runtime SQL as the target. It also does not claim production readiness.

## Required ADR alternatives considered

- **MCP-only, no HTTP adapter** — rejected for the production target because n8n and other HTTP-native consumers need a stable adapter boundary.
- **Full SaaS/BI/runtime SQL product** — rejected because it expands scope into production execution, multi-tenant product behavior, and unsafe SQL responsibilities that are out of scope.
- **Docker-first production app** — rejected as the primary target because the repo is designed around clone-ready packages with local validation and optional adapter mounting.
- **Live DB/VDB mandatory evidence** — rejected as a product baseline because live evidence is a gate for verification, not the definition of the product itself.
- **Chosen: clone-ready package + MCP + optional local HTTP adapter** — accepted because it preserves local-first safety, keeps execution out of scope, and still allows a minimal adapter for orchestration consumers.

## Current implementation summary

Evidence currently present in the repo shows:

- installable package surfaces for contracts, registry, and MCP
- an MCP stdio server with deterministic tool/resource registration
- a pure Python Product API contract with route-level tests
- docs and demos that explicitly mark SQL execution as out of scope

Missing or incomplete evidence:

- no actual HTTP adapter / ASGI / WSGI entrypoint was found
- no `/healthz`, `/readyz`, OpenAPI server, typed HTTP error surface, or correlation-ID middleware was found
- no production execution path exists, which is correct for scope but blocks any claim of runtime deployability

## Risk register

| ID | Risk | Severity | Likelihood | Mitigation | Verification evidence | Owner lane |
|---|---|---:|---:|---|---|---|
| R1 | The repo looks “package complete” but still has no deployable HTTP adapter. | High | High | Add a minimal local adapter that mounts `semantic_registry.product.api.handle_product_api` without adding product SQL execution. Require `/healthz`, `/readyz`, OpenAPI, typed errors, and correlation IDs. | `docs/api/PRODUCT_API.md`; `docs/api/OPENAPI_LIKE.yaml`; `tests/product/test_phase16_answer_ui.py`; `tests/product/test_phase19_product_api_contract.py` prove route contracts exist, but no adapter file or server entrypoint was found. | web-adapter lane |
| R2 | MCP coverage can be mistaken for production readiness even though it is stdio-only and validation-first. | High | Medium | Keep MCP, package, and HTTP-adapter readiness separate; treat the MCP server as local orchestration only. | `packages/semantic_mcp/src/semantic_mcp/server.py`; `packages/semantic_mcp/pyproject.toml`; `tests/mcp/test_tools.py`; `tests/mcp/test_resources.py`; `tests/mcp/test_preview_query.py` show a local stdio MCP surface with no execution tool. | MCP lane |
| R3 | A reviewer may assume `execute_query` or general SQL execution exists because preview/query-planning surfaces are present. | Critical | Medium | Preserve explicit bans on production execution; keep `preview_query` validation-gated and local/demo only. | `packages/semantic_mcp/src/semantic_mcp/server.py`; `packages/semantic_mcp/src/semantic_mcp/tools/preview_query.py`; `docs/execution/SECURITY_CHECKLIST.md`; `tests/mcp/test_preview_query.py` all reinforce no production execution. | security/verifier lane |
| R4 | Readiness can be overstated if package and MCP tests are treated as end-to-end deploy evidence. | High | Medium | Separate package/unit evidence from adapter/runtime evidence and keep the readiness matrix gated by phase checks. | `reports/productization/phase20_n8n_readiness_report.md` states a web adapter is still required; `reports/productization/n8n_readiness_after_comment_rule_correction.md` marks the API/adapters as partial. | readiness-risk-docs lane |
| R5 | Live DB/VDB evidence may be assumed even though current evidence is fixture/demo oriented. | High | High | Keep live DB/VDB as an explicit verification gate, not a hidden fallback; require separate live-readonly proof when promoted. | `docs/product/N8N_PRECONDITIONS.md`; `docs/demo/N8N_WORKFLOW_REQUIREMENTS.md`; `docs/execution/SECURITY_CHECKLIST.md` all keep demo/local boundaries explicit. | verifier lane |
| R6 | Optional backend selection can silently degrade if unavailable backends are treated as acceptable fallbacks. | Medium | Medium | Preserve fail-closed backend errors and do not fallback from Weaviate to keyword or another backend without explicit labeling. | `tests/mcp/test_search_context.py` asserts explicit error behavior and no fallback for missing Weaviate/keyword adapters; `packages/semantic_registry/semantic_registry/retrieval/backends.py` documents explicit backend selection. | registry/MCP lane |
| R7 | The local Product UI/demo surface may be mistaken for a production product UI. | Medium | Medium | Keep UI/demos labeled as local/demo evidence only and keep orchestration wrappers from becoming the source of truth. | `apps/product_ui/index.html`; `apps/product_ui/app.js`; `docs/demo/N8N_WORKFLOW_REQUIREMENTS.md`; `docs/product/N8N_PRECONDITIONS.md` all present the UI and n8n layers as wrappers/demos. | docs/product lane |
| R8 | Environment drift can cause verification to read temp dependency bundles instead of repo packages. | Medium | Medium | Require repo package paths first and keep clean-venv verification explicit before any readiness claim. | The repository’s productization docs and prior verification notes reference local package paths plus `/tmp/semantic-data-context-deps` as a verification detail, not a product dependency. | verifier lane |

## Control gates

- **PR-1**: environment and import-path hygiene must be proven before any readiness claim.
- **PR-2**: HTTP adapter must be adapter-only and expose operational endpoints without SQL execution.
- **PR-3**: MCP surface must remain local, deterministic, and non-executing.
- **PR-4**: DB scope must stay read-only / fixture-scoped until live evidence exists.
- **PR-5**: Weaviate must fail closed when unavailable.
- **PR-6**: n8n workflows must call repository APIs and never duplicate product logic.
- **PR-7**: release/observability proof must exist before any production-style handoff.

## Residual risk

The biggest remaining gap is the missing HTTP adapter. Until that is added and verified, the repo has strong package-, MCP-, and contract-level coverage, but it does not yet provide a deployable HTTP surface for orchestration consumers.

