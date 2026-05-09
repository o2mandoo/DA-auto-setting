## Structured known limitations

| Limitation | Impact | Evidence | Status |
|---|---|---|---|
| Release status is dry-run/local validation, not production ready. | Production promotion still requires CI logs, release approval, and signed candidate evidence. | reports/productization/PRODUCTION_READINESS_MATRIX.md | `open` |
| Production SQL execution is forbidden. | No production execute_query route, MCP tool, n8n node, or handler is included in v1 scope. | docs/product/PRODUCTION_MODE_ADR.md | `contract_boundary` |
| Live external services are optional and evidence-gated. | Missing live DB/VDB/n8n/CI runs remain visible gaps or skips instead of pass claims. | reports/productization/PRODUCTION_READINESS_MATRIX.md | `evidence_gated` |
| Oracle is unsupported. | Unsupported backends must fail explicitly and must not be represented by fake fixture success. | reports/productization/PRODUCTION_READINESS_MATRIX.md | `unsupported` |
| Synthetic comments are fixture-only. | Generated comments may support lab/debug comparisons but cannot become approved product truth automatically. | docs/product/METADATA_PROVENANCE_RULES.md | `contract_boundary` |
| n8n remains demo orchestration only. | n8n must call product APIs, display backend/comment warnings, and avoid duplicating Semantic Pack logic. | reports/productization/pr6_n8n_live_runtime_smoke.md | `demo_only` |

## Known limitations

- Live Weaviate service benchmarking is not included; current tests verify explicit backend behavior and no silent keyword fallback.
- PostgreSQL support remains safe scan/profile scope with credential-free tests; no production DB execution is included.
- The demo pack was promoted to `approved` for final local package demo purposes, while generated Builder output remains draft/proposal-based.
- MCP stdio server creation is smoke-tested; complete client/server transport integration is still a later integration hardening item.
- Root `unittest discover -s tests` does not discover all tests; run per-suite commands listed above.
- Released evidence uses redacted fixture passwords in docs and reports; this packet intentionally avoids publishing credential-like DSN literals.

## Current known limitations

- `.xlsx` is supported and verified with `openpyxl`.
- legacy `.xls` is supported and verified with `xlrd` against Tableau Sample
  Superstore.
- Large workbook validation should be bounded and reported; do not turn every
  local development test into a full corpus scan unless the phase explicitly
  requires it.
