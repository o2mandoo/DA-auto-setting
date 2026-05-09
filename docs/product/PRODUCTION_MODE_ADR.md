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

## Decision

Production mode is a stricter operating boundary over the existing product
modes, not a new SQL execution engine or dashboard product.

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

## Production-mode invariants

Any deployment-like use of this repo must preserve these invariants:

- No production SQL execution route exists.
- `preview_query` remains local/demo-only, validation-gated, row-limited, and
  audited; it is not a general production query runner.
- SQL validation is SELECT-only and blocks multi-statement SQL, unknown or
  disallowed tables, and blocked PII columns.
- Raw PII values must not be emitted into prompts, logs, profiles, Semantic
  Packs, vector payloads, feedback, eval reports, or generated readiness
  summaries.
- Approved packs are immutable through feedback/confirmation flows; promotion
  must be explicit, validated, versioned, and auditable.
- Explicit Weaviate/VDB selection must not silently fall back to keyword search.
- Production credentials must not be stored in this repo, docs examples,
  workflow JSON, tests, or runtime artifacts.
- Dashboard UI, SaaS multi-tenancy, billing, seats, and production auth are
  outside this repository's current product scope.

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

## Verification expectations

Production-mode changes should be verified with the smallest relevant checks:

```bash
PYTHONPATH=packages/semantic_contracts:packages/semantic_builder/src:packages/semantic_registry:packages/semantic_mcp/src:/tmp/semantic-data-context-deps python3 -m unittest discover -s tests/security -v
PYTHONPATH=packages/semantic_contracts:packages/semantic_builder/src:packages/semantic_registry:packages/semantic_mcp/src:/tmp/semantic-data-context-deps python3 -m unittest discover -s tests/registry -v
PYTHONPATH=packages/semantic_contracts:packages/semantic_builder/src:packages/semantic_registry:packages/semantic_mcp/src:/tmp/semantic-data-context-deps python3 -m unittest discover -s tests/mcp -v
```

Docs-only changes may additionally run `make env-check` to prove local package
imports still resolve with the documented path order.
