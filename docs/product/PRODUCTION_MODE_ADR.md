# ADR: Production Mode Boundary

## Status

Accepted for the local validation-first MVP.

## Context

The product now has local onboarding, registry/confirmation, answer comparison,
and benchmark/evidence modes. Those modes are useful for demos and readiness
checks, but they can be confused with a deployable production analytics service.

This ADR defines what "production mode" means for this repository before any
deployment adapter, hosted UI, or operational database path is added.

Related contracts:

- `docs/product/PRODUCT_MODES.md`
- `docs/product/FAILURE_SAFE_UX_SPEC.md`
- `docs/api/PRODUCT_API.md`
- `docs/execution/SECURITY_CHECKLIST.md`
- `docs/execution/RETRIEVAL_LAYER.md`
- `docs/setup/README.md`

## Drivers

- Make the v1 production target clone-ready and verifiable from a fresh local
  checkout.
- Preserve the current validation-first architecture: Semantic Pack source of
  truth, MCP tool surface, planner/guard checks, and local/demo preview only.
- Keep the product safe for demos without implying production DB execution,
  dashboard/BI ownership, SaaS operations, or production credential handling.
- Require visible evidence for missing capabilities; no silent fallback is
  allowed after a concrete backend, provider, workflow step, or adapter is
  selected.
- Leave room for a thin local HTTP adapter so n8n or UI prototypes can call the
  same contracts without moving business rules out of the repo.

## Decision

Production mode is a stricter operating boundary over the existing product
modes, not a new SQL execution engine or dashboard product.

Chosen v1 target: clone-ready package + MCP + optional local HTTP adapter.
The package remains the source of product behavior, MCP remains the agent-facing
interface, and any HTTP adapter is a thin transport layer with
health/readiness/OpenAPI/error/correlation-ID behavior only. The adapter must
not add `execute_query`, BI/SaaS behavior, or hidden fallback behavior.
The core product packages also must not introduce production web-framework or
dashboard runtime imports such as FastAPI, Flask, Django, Streamlit, Gradio, or
similar SaaS-style UI shells.

The system remains validation-first:

1. Semantic Packs are the source of truth for business meaning.
2. Builder and confirmation flows may create proposals or audit records, but
   they do not silently mutate approved packs.
3. Query runtime produces plans, comparisons, validation verdicts, and local
   preview status only when explicitly allowed by the safe preview contract.
4. Benchmark/evidence mode reports missing or unavailable evidence as missing,
   not as inferred readiness.
5. Every selected backend/provider must either run as selected or fail with an
   explicit component-level error.

## Alternatives considered

| Alternative | Decision | Reason |
|---|---|---|
| MCP-only, no HTTP adapter | Rejected for v1 target | Too narrow for clone-ready demos that need n8n or simple HTTP orchestration, even though MCP remains the core interface. |
| Full SaaS/BI/runtime SQL product | Rejected | Conflicts with current non-goals: no BI/SaaS, no production SQL execution, no production auth/billing/tenant operations. |
| Docker-first production app | Rejected as the primary target | Useful later, but it would hide clone-readiness and local package correctness behind container packaging before the contracts are stable. |
| Live DB/VDB mandatory evidence | Rejected as a hard requirement | PostgreSQL/MySQL/Weaviate evidence can be explicit and optional; production readiness must not be faked when live services are unavailable. |
| Clone-ready package + MCP + optional local HTTP adapter | Chosen | Preserves current safety contracts while giving demos and workflow tools a realistic integration surface. |

## Why chosen

The chosen target keeps the smallest production-like surface that can be
verified today. It supports local clone readiness, MCP-based agent workflows,
and optional HTTP orchestration without turning this repository into a BI/SaaS
platform or a production database execution runtime.

This also keeps ownership clear:

- Packages own contracts, planning, validation, registry state, builder outputs,
  retrieval seams, and evidence generation.
- MCP exposes those contracts to agents and tools.
- The optional local HTTP adapter can expose the same contracts to n8n or demos
  without changing the business logic.
- Missing production-grade capabilities remain explicit follow-ups, not hidden
  behavior.

## Production-mode invariants

Any deployment-like use of this repo must preserve these invariants:

- No production SQL execution route exists, including no production
  `execute_query` function, API route, or MCP tool.
- `preview_query` remains local/demo-only, validation-gated, row-limited, and
  audited; it is not a general production query runner.
- SQL validation is SELECT-only and blocks multi-statement SQL, unknown or
  disallowed tables, and blocked PII columns.
- Raw PII values must not be emitted into prompts, logs, profiles, Semantic
  Packs, vector payloads, feedback, eval reports, or generated readiness
  summaries.
- Approved packs are immutable through feedback/confirmation flows; promotion
  must be explicit, validated, versioned, and auditable.
- Explicit Weaviate/VDB selection must not silently fall back to keyword search;
  no silent fallback is allowed after any explicit backend/provider selection.
- Production credentials must not be stored in this repo, docs examples,
  workflow JSON, tests, or runtime artifacts.
- Dashboard UI, BI/SaaS ownership, SaaS multi-tenancy, billing, seats, and
  production auth are outside this repository's current product scope.
- Core product packages must stay free of production web-framework runtime
  dependencies unless a separate ADR explicitly approves them for a thin local
  adapter surface.

## Production-mode gate

A caller, workflow, or adapter may describe itself as production-like only when
all gates below are satisfied:

| Gate | Required behavior |
|---|---|
| Source of truth | Use an approved Semantic Pack version, not draft inference as business truth. |
| Configuration | Select backends/providers explicitly; missing config fails closed. |
| Credentials | Load secrets from the deployment environment only; never commit or echo them. |
| SQL safety | Run planner/guard validation before any preview-like operation. |
| PII safety | Redact or suppress raw PII before persistence, prompts, indexing, or reports. |
| Pack mutation | Record feedback/confirmation as audit data; do not mutate approved packs in place. |
| Retrieval | If Weaviate is selected, return an explicit Weaviate/config error on failure. |
| Evidence | Record the exact unsupported capability or failing component instead of masking it. |

If any gate fails, the user-facing state must be a failure-safe state such as
`policy_blocked`, `pii_blocked`, `unsafe_sql_blocked`,
`missing_semantic_context`, `retrieval_miss`, `preview_unavailable`, or another
explicit error with the component and recovery action.

## Non-goals

Production mode does not authorize adding:

- `execute_query` as a product function, API route, or MCP tool.
- A production database connection runtime.
- A hosted dashboard or standalone BI portal.
- SaaS multi-tenancy or account administration.
- Silent offline mocks after a concrete backend/provider was requested.
- Automatic promotion from draft/proposed cards into approved packs.
- Credential-bearing workflow exports.

Those capabilities require a separate ADR, threat model, tests, and explicit
leader/product approval.

## Consequences

- Product demos can remain realistic without pretending to be production data
  execution.
- n8n or HTTP-style adapters may orchestrate the local product contracts, but
  they inherit the same fail-closed behavior.
- Readiness reports must distinguish validated capabilities from missing,
  skipped, or unavailable production evidence.
- Future deployment work can add adapters around these contracts, but cannot
  weaken the no-execution, no-PII, no-silent-fallback, and approved-pack
  immutability rules without superseding this ADR.

## Support levels

| Surface | v1 support level | Boundary |
|---|---|---|
| Clone-ready package install/import | Required | Must work from a clean local checkout without production credentials. |
| Semantic Pack validation/registry/planner/guard | Required | Source-of-truth and validation-first behavior must remain in packages. |
| MCP server/tools | Required | Tooling surface remains validation/planning/preview-only; no production `execute_query`. |
| Optional local HTTP adapter | Supported target | Thin transport over package contracts; no independent product logic, no BI/SaaS, no SQL execution. |
| Weaviate/VDB | Optional explicit backend | If selected and unavailable, return explicit configuration/backend errors; no silent fallback. |
| PostgreSQL/MySQL evidence | Fixture/demo/read-only validation only | Missing live evidence must be reported as pending/unavailable, not treated as production readiness. |
| Oracle connector | Unsupported for v1 | Requires separate scope, evidence, and safety review. |
| Dashboard, SaaS, auth, billing, observability, release ops | Out of scope | Requires separate ADRs and production threat model. |

## Follow-ups

- PR-1: prove clean-venv clone readiness with repo-native editable installs
  and no dependency on a temporary `/tmp` cache.
- PR-2: add the optional local HTTP adapter with `/healthz`, `/readyz`, OpenAPI,
  typed errors, correlation IDs, and no `execute_query`.
- PR-3: keep product/evidence docs synchronized with the ADR support levels.
- PR-4: make DB evidence explicit: PostgreSQL remains metadata/profile/demo
  validation, and MySQL remains fixture/demo until live read-only evidence
  exists.
- PR-5: keep Weaviate evidence optional and explicit; backend failures must not
  become keyword fallback success.
- PR-6: add production-style observability/release/security planning only after
  the no-BI/SaaS and no-production-execution boundary is preserved.
- PR-7: re-run productization verification across ADR, readiness matrix, risk
  register, and test evidence before claiming any broader readiness.

## Verification expectations

Production-mode changes should be verified with the smallest relevant checks:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e packages/semantic_contracts -e packages/semantic_registry -e packages/semantic_mcp -e 'packages/semantic_builder[test]'
make env-check
make test
python3 -m unittest discover -s tests/security -v
python3 -m unittest discover -s tests/registry -v
python3 -m unittest discover -s tests/mcp -v
```

Docs-only changes may additionally run `make env-check` to prove local package
imports still resolve with the documented path order.

When the optional HTTP adapter is available, a deterministic local smoke check
should also be used:

```bash
python -m semantic_registry.product.http_adapter --check
```

That check must remain local, non-networked, and fail closed if required
contracts or imports are missing.
