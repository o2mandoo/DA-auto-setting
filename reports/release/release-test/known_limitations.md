## Structured known limitations

| Limitation | Impact | Evidence | Status |
|---|---|---|---|
| Release status is dry-run/local validation, not production ready. | Hosted CI pass evidence is attached; production promotion still requires release approval and signed candidate evidence. | reports/productization/PRODUCTION_READINESS_MATRIX.md | `open` |
| Production SQL execution is forbidden. | No production execute_query route, MCP tool, n8n node, or handler is included in v1 scope. | docs/product/PRODUCTION_MODE_ADR.md | `contract_boundary` |
| Live external services are optional and evidence-gated. | Missing live DB/VDB/n8n runs remain visible gaps or skips instead of pass claims. | reports/productization/PRODUCTION_READINESS_MATRIX.md | `evidence_gated` |
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

- This is an internal release-candidate state, not a production release approval.
- Signed or promoted release-candidate approval is still missing.
- PostgreSQL/MySQL support remains fixture/read-only metadata validation only.
- Weaviate remains optional and evidence-gated.
- n8n remains orchestration/demo wrapper only.
- Oracle remains unsupported.
- Production SQL execution remains forbidden.
