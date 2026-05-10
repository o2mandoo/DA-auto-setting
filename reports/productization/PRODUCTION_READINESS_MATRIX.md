# Production Readiness Matrix

Date: 2026-05-09 KST  
Lane contract: worker-2 edits only `reports/productization/PRODUCTION_READINESS_MATRIX.md` and `reports/productization/PRODUCTION_RISK_REGISTER.md`.

## Executive verdict

This repository is **clone-ready for local validation and demo operation**, but it is **not production ready**. The v1 production target is a clone-ready package with the existing local Semantic Builder, Registry, MCP surface, and an optional local HTTP adapter. The target explicitly excludes a BI/SaaS product, production SQL execution, hidden fallback, production credentials, and mandatory live DB/VDB dependencies.

## Source evidence used

| Evidence | What it proves |
|---|---|
| `Makefile` | Canonical local commands: `make setup`, `make env-check`, `make test`, `make demo`; repo-first `PYTHONPATH` with `/tmp/semantic-data-context-deps` last. |
| `docs/setup/CLONE_READY_USAGE_SUMMARY.md` | Clone-ready setup, local editable package install, recommended verification, no production `execute_query`, no silent fallback. |
| `docs/demo/LOCAL_DEMO.md` | End-to-end local demo path and generated `runtime/phase12_demo/**` artifacts. |
| `docs/api/PRODUCT_API.md` and `packages/semantic_registry/semantic_registry/product/api.py` | Product API is currently pure Python handler functions; a web adapter is future work. |
| `packages/semantic_mcp/src/semantic_mcp/server.py` | MCP stdio registration surface exists and intentionally omits SQL execution / DB connectors / hidden LLM calls. |
| `docs/execution/SECURITY_CHECKLIST.md` | Scope and safety invariants: no production SQL execution, no raw PII, explicit Weaviate errors, read-only DB fixture scope. |
| `docs/demo/WEAVIATE_OPTIONAL.md`, `docs/demo/N8N_DB_BACKED_DEMO_REQUIREMENTS.md`, `docs/dev/DB_FIXTURE_GUIDE.md` | Optional live Weaviate and DB-backed demo evidence must be explicit and environment-gated. |
| `reports/final/final_integration_report.md` | Prior local demo-ready evidence: package install, targeted test suites, demo/eval/security results, known limitations. |

## Current implementation vs v1 production target

| Area | Current implementation | v1 production target | Readiness | Required before promoting |
|---|---|---|---|---|
| Local packages | Four editable packages: `semantic_contracts`, `semantic_builder`, `semantic_registry`, `semantic_mcp`. | Reproducible package install from a clean clone/venv. | **Partial** | PR-1 clean-venv install without relying on `/tmp/semantic-data-context-deps`; package metadata and dependency pins verified. |
| Semantic Pack contracts | Pydantic contracts and approved demo pack exist. | Contract schemas are stable and documented for external adapter users. | **Near** | Freeze v1 schema notes and run contract/registry suites in clean environment. |
| Builder | Local file scan/profile/infer/build-pack path exists. | Local files and safe fixture DB metadata produce auditable draft packs. | **Partial** | Prove clean environment path, artifact schemas, and PII suppression on current fixtures. |
| Registry | Pack store/search/planner/guard/retrieval/product facades exist. | Registry is source of truth for semantic context, validation, product handlers. | **Partial** | PR-1/PR-3 evidence plus release-level docs for data paths and audit output. |
| MCP | Stdio server and deterministic tool functions exist; official SDK is required for stdio. | MCP remains the primary automation interface, with no SQL execution tool. | **Partial** | PR-2/PR-3 stdio smoke with official SDK and registration-surface evidence. |
| HTTP adapter | Only pure Python local handlers and API docs exist; no web server adapter is implemented. | Optional local HTTP adapter mounting repo-owned handlers. | **Not started** | PR-2 adapter-only app with `/healthz`, `/readyz`, OpenAPI, typed errors, correlation ID, and no `execute_query`. |
| Safe preview | Local/demo `preview_query` exists and stays validation-gated. | Preview remains local/test only; production execution remains absent. | **Partial** | PR-3 evidence that preview cannot be mistaken for production query execution. |
| Weaviate | Explicit backend seam and optional live test docs; default suite does not require live service. | Optional explicit backend; no keyword fallback after explicit Weaviate failure. | **Partial** | PR-5 optional live evidence or explicit skip/failure artifact; fake/backend tests remain deterministic. |
| PostgreSQL | Read-only fixture scan/profile/demo validation scope. | Metadata scan/profile/demo validation only; no production execution. | **Partial** | PR-4 environment-gated fixture evidence and visible unavailable state when absent. |
| MySQL | Explicit fixture/demo validation requirements and tests; live evidence may be pending. | Fixture/demo validation only until live read-only evidence exists. | **Early** | PR-4 live-read-only evidence or explicit `live_mysql_not_run`; no reroute to other DBs. |
| Oracle | Documented unsupported / no fake fixture behavior. | Unsupported until real connector and evidence exist. | **Not supported** | Keep fail-explicit stance; do not ship fake Oracle readiness. |
| n8n | Requirements/templates and demo wrapper boundaries exist. | n8n calls stable product APIs and displays failures; it is not source of truth. | **Partial** | PR-6 import/smoke evidence against local HTTP adapter; explicit backend/mode fields visible. |
| CI | Local `make` commands exist; CI status not proven here. | CI runs clean setup, tests, docs checks, and release checks. | **Not proven** | PR-7 add/verify CI jobs and artifact uploads. |
| Observability | Audit JSONL paths exist in product handlers; no production observability stack. | Local audit/log artifacts, correlation IDs, error taxonomy, and run evidence. | **Early** | PR-2/PR-7 correlation ID propagation and structured evidence artifacts. |
| Release | Clone-ready docs exist; no versioned release packet. | Versioned release bundle with verification matrix and known limits. | **Not ready** | PR-7 release checklist, tag/version policy, and support matrix sign-off. |

## Phase gates PR-1 through PR-7

### PR-1 — Clean clone package baseline

**Goal:** prove the repo installs and verifies from a clean clone/venv without hidden local state.  
**Acceptance commands:**

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e packages/semantic_contracts -e packages/semantic_registry -e packages/semantic_mcp -e 'packages/semantic_builder[test]'
make env-check
make test
```

**Artifact evidence required:**
- `make env-check` output.
- `make test` output with pass/fail count.
- `pip freeze` or dependency lock snapshot.
- Explicit note that the run did **not** depend on `/tmp/semantic-data-context-deps`.

**Exit criteria:** packages, tests, and local imports pass from the venv; any missing dependency is explicit.

### PR-2 — Optional local HTTP adapter

**Goal:** expose existing product handlers over a local adapter without moving safety logic out of the repo modules.  
**Acceptance commands:**

```bash
make env-check
python -m pytest -q tests/product tests/packaging
# adapter-specific smoke command to add in PR-2, for example:
# python -m semantic_registry.product.http_adapter --check
```

**Artifact evidence required:**
- `/healthz` returns process health.
- `/readyz` verifies pack root/config readiness and reports missing dependencies explicitly.
- OpenAPI document generated from handler contracts.
- Typed error payloads for validation/config failures.
- Correlation ID appears in response headers and audit logs.
- Audit proving no production `execute_query` route or handler exists.

**Exit criteria:** adapter is adapter-only; core planning/validation remains in `semantic_registry`/`semantic_mcp`.

### PR-3 — MCP + safe query runtime hardening

**Goal:** prove MCP stdio and local preview are safe automation surfaces.  
**Acceptance commands:**

```bash
make env-check
python -m pytest -q tests/mcp tests/registry tests/security
python - <<'PY'
from semantic_mcp.server import inspect_registration_surface
print(inspect_registration_surface())
PY
```

**Artifact evidence required:**
- Registered tools list includes metadata/planning/validation/preview tools only.
- `execution_allowed` remains false for validation and preview surfaces.
- Local preview artifacts are under `runtime/**` and are clearly demo/test scoped.
- SQL red-team blocking output for mutating, multi-statement, blocked-column, and PII cases.

**Exit criteria:** no production query execution path is introduced; MCP registration fails explicitly if SDK/runtime is missing.

### PR-4 — DB fixture/read-only evidence

**Goal:** prove DB-backed evidence remains fixture/demo/read-only and never silently reroutes.  
**Acceptance commands:**

```bash
make env-check
python -m pytest -q tests/builder/test_postgres_scanner.py tests/builder/test_mysql_comment_scanner.py tests/fixtures tests/e2e/test_mysql_db_fixture_comparison.py
```

**Artifact evidence required:**
- PostgreSQL status: metadata scan/profile/demo validation only.
- MySQL status: fixture/demo until live read-only evidence exists.
- If live services are absent, record explicit unavailable/skip reason.
- No fallback from MySQL to PostgreSQL/DuckDB/SQLite/cached JSON/synthetic comments.
- Oracle remains unsupported and fails explicitly.

**Exit criteria:** all DB claims are scoped to evidence actually run; no production credentials or SQL execution.

### PR-5 — Retrieval / Weaviate optional evidence

**Goal:** prove retrieval uses explicit backend selection and never silently falls back after Weaviate failure.  
**Acceptance commands:**

```bash
make env-check
python -m pytest -q tests/registry/test_vdb_backend.py tests/mcp/test_search_context.py tests/integration/test_weaviate_live_optional.py
```

**Artifact evidence required:**
- Deterministic keyword/fake-Weaviate tests.
- Optional live Weaviate result: pass, explicit skip, or explicit failure.
- Evidence that raw PII payloads are not indexed.
- Evidence that Weaviate unavailable/config errors are typed and visible.

**Exit criteria:** live Weaviate is optional, but selected Weaviate cannot degrade silently to keyword.

**Current evidence:** PASS as of `reports/productization/PR5_SEMANTIC_RETRIEVAL_EVIDENCE.md`.
Reconfirmed on 2026-05-09 with the focused regression set
`tests/registry/test_semantic_query.py`, `tests/registry/test_search_index.py`,
`tests/registry/test_vdb_backend.py`, and `tests/mcp/test_search_context.py`
(`35 passed, 1 skipped`), plus a direct `search_semantic_context("휴면 고객")`
runtime smoke that returned `fallback_used=false`, `unknown_terms=['휴면 고객']`,
`recommended_card_types=['reverse_question', 'business_term']`, and
`results=[]`.
The run also verified the PostgreSQL/MySQL 20-dataset fixture precondition in
`reports/reality/sinagong_20_live_db_fixture_evidence.json` and added
deterministic Semantic Pack query-understanding evidence for aliases,
question-patterns, reverse questions, ambiguity rules, unknown terms, and
semantic-gold retrieval metrics.

### PR-6 — n8n/local workflow smoke

**Goal:** prove n8n is only an orchestration/demo wrapper over product APIs.  
**Acceptance commands:**

```bash
make env-check
python -m pytest -q tests/product/test_n8n_workflow_templates.py tests/product/test_phase19_product_api_contract.py tests/product/test_phase20_n8n_readiness.py
```

**Artifact evidence required:**
- Workflow payloads call product API/adapter routes, not internal duplicated logic.
- Backend/comment mode/source status/warnings are displayed.
- API failures remain visible; no hidden replacement branch.
- No workflow executes SQL directly.

**Exit criteria:** n8n can be demoed against local APIs while Semantic Pack/Registry remain source of truth.

### PR-7 — CI, observability, release packet

**Goal:** make the production-readiness proof repeatable outside one developer machine.  
**Acceptance commands:**

```bash
make env-check
make test
python -m pytest -q tests/security tests/packaging tests/e2e
# CI job URLs and release artifact checks to be attached by PR-7.
```

**Artifact evidence required:**
- CI logs for setup/test/security/packaging jobs.
- Structured run artifact directory with matrix, risk register, release notes, and known limitations.
- Correlation ID/audit-log sample for HTTP/API work.
- Version/tag or release-candidate identifier.

**Exit criteria:** release packet states supported, partial, optional, and unsupported surfaces without claiming full production readiness.

## Support matrix

| Surface | v1 support level | Current evidence | Production caveat |
|---|---|---|---|
| Packages (`semantic_contracts`, `semantic_builder`, `semantic_registry`, `semantic_mcp`) | **Supported for local validation** | Package pyprojects, Makefile, PR-1 clean-clone evidence, dependency snapshot, and PR-7 `make ci` evidence. | Hosted CI pass evidence is attached; production release claims still require signed/promoted release approval. |
| MCP stdio | **Supported with official SDK installed** | `semantic_mcp.server` registration surface and tests. | Missing SDK must fail explicitly; no fake stdio runtime. |
| HTTP adapter | **Partial local adapter** | PR-2 API docs, route inventory, product handler tests, typed errors, and audit evidence. | Local/demo scoped; not a production server distribution. |
| Weaviate | **Optional explicit backend** | Backend seam, docs, deterministic tests, optional live test path. | Live service not mandatory; selected backend must fail explicitly if unavailable. |
| PostgreSQL | **Read-only fixture/demo metadata validation** | Scanner/docs/tests and `reports/reality/postgres_live_fixture_evidence.json`. | No production execution; fixture schema/environment gated. |
| MySQL | **Read-only fixture/demo metadata validation** | Connector/docs/tests and `reports/reality/mysql_live_fixture_evidence.json`. | No fallback to other DBs; production MySQL execution is not supported. |
| Oracle | **Unsupported** | Docs state unsupported/no fake behavior. | Must fail explicitly until real connector and tests exist. |
| n8n | **Demo orchestration only** | Requirements/templates/product tests and PR-6 live Docker n8n smoke. | Not source of truth; must not execute SQL or hide failures. |
| CI | **Hosted CI pass evidence attached** | `.github/workflows/packaging-clean-clone.yml`, `make ci`, `make test`, release/security/product tests, `reports/productization/hosted_ci_evidence.*`, run `25621898578`. | Signed/promoted release approval remains missing gate evidence. |
| Observability | **Local audit/sample evidence only** | Product API audit writes, correlation IDs, structured error samples, and `docs/observability/product_api_audit_sample.jsonl`. | No Prometheus/Grafana/Jaeger/OTel production stack claim. |
| Release | **Dry-run release packet only** | `reports/release/release-test/**`, readiness matrix, risk register, support matrix, known limitations. | Needs signed/promoted release candidate approval before production release. |

## Non-negotiable safety gates

- No production `execute_query` route, MCP tool, handler, or documented requirement.
- No BI/SaaS/dashboard claim for v1.
- No silent fallback after an explicit backend/provider/DB is selected.
- Missing live DB/VDB evidence is a visible gap, not a pass.
- PostgreSQL is metadata scan/profile/demo validation only.
- MySQL is fixture/read-only metadata validation only; live local fixture evidence does not imply production MySQL execution support.
- Oracle remains unsupported.
