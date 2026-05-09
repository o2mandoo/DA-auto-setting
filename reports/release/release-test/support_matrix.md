## Support matrix

| Surface | v1 support level | Current evidence | Production caveat |
|---|---|---|---|
| Packages (`semantic_contracts`, `semantic_builder`, `semantic_registry`, `semantic_mcp`) | **Supported for local validation** | Package pyprojects, Makefile, PR-1 clean-clone evidence, dependency snapshot, and PR-7 `make ci` evidence. | Still requires external CI logs before production release claims. |
| MCP stdio | **Supported with official SDK installed** | `semantic_mcp.server` registration surface and tests. | Missing SDK must fail explicitly; no fake stdio runtime. |
| HTTP adapter | **Partial local adapter** | PR-2 API docs, route inventory, product handler tests, typed errors, and audit evidence. | Local/demo scoped; not a production server distribution. |
| Weaviate | **Optional explicit backend** | Backend seam, docs, deterministic tests, optional live test path. | Live service not mandatory; selected backend must fail explicitly if unavailable. |
| PostgreSQL | **Read-only fixture/demo metadata validation** | Scanner/docs/tests and `reports/reality/postgres_live_fixture_evidence.json`. | No production execution; fixture schema/environment gated. |
| MySQL | **Read-only fixture/demo metadata validation** | Connector/docs/tests and `reports/reality/mysql_live_fixture_evidence.json`. | No fallback to other DBs; production MySQL execution is not supported. |
| Oracle | **Unsupported** | Docs state unsupported/no fake behavior. | Must fail explicitly until real connector and tests exist. |
| n8n | **Demo orchestration only** | Requirements/templates/product tests and PR-6 live Docker n8n smoke. | Not source of truth; must not execute SQL or hide failures. |
| CI | **Local CI-equivalent present; external CI pending** | `.github/workflows/packaging-clean-clone.yml`, `make ci`, `make test`, release/security/product tests. | External CI run URL/log and release approval remain missing gate evidence. |
| Observability | **Local audit/sample evidence only** | Product API audit writes, correlation IDs, structured error samples, and `docs/observability/product_api_audit_sample.jsonl`. | No Prometheus/Grafana/Jaeger/OTel production stack claim. |
| Release | **Dry-run release packet only** | `reports/release/release-test/**`, readiness matrix, risk register, support matrix, known limitations. | Needs signed/promoted release candidate and external CI evidence before production release. |

## Structured support levels

| Surface | Support level | Evidence status | Evidence | Limitation |
|---|---|---|---|---|
| Semantic Pack contracts | `supported_local_validation` | present | reports/productization/PRODUCTION_READINESS_MATRIX.md | Schema freeze and external-adapter versioning remain release-gated. |
| Local Registry and MCP interface | `supported_local_validation` | present | reports/productization/PR3_MCP_SAFE_RUNTIME_EVIDENCE.md | MCP requires the official SDK/runtime; no production SQL execution surface is supported. |
| Optional local HTTP adapter | `partial_local_adapter` | present | reports/productization/PR2_HTTP_ADAPTER_EVIDENCE.md | Adapter is local/demo scoped and does not make the repo production-server ready. |
| PostgreSQL fixture/read-only metadata | `fixture_readonly_validation` | present | reports/productization/PR4_DB_FIXTURE_READONLY_EVIDENCE.md | Metadata scan/profile/demo validation only; no production execution claim. |
| MySQL fixture/read-only metadata | `fixture_readonly_validation` | present | reports/productization/PR4_DB_FIXTURE_READONLY_EVIDENCE.md | No fallback to PostgreSQL/DuckDB/SQLite/cached JSON/synthetic comments. |
| Weaviate retrieval backend | `optional_evidence_gated` | present_or_explicit_skip | reports/productization/PR5_SEMANTIC_RETRIEVAL_EVIDENCE.md | Selected Weaviate must fail visibly if unavailable; keyword fallback is not allowed after explicit selection. |
| n8n orchestration | `demo_orchestration_only` | present | reports/productization/pr6_n8n_live_runtime_smoke.md | n8n is not source of truth, must not execute SQL, and must keep backend/comment warnings visible. |
| Oracle | `unsupported` | no_release_evidence | reports/productization/PRODUCTION_READINESS_MATRIX.md | Unsupported backends must fail explicitly; no fake Oracle fixture behavior is allowed. |
| Production execute_query | `forbidden` | prohibited_by_contract | docs/product/PRODUCTION_MODE_ADR.md | No route, MCP tool, handler, workflow, or documentation may promote production SQL execution. |

## Non-negotiable safety gates

- No production `execute_query` route, MCP tool, handler, or documented requirement.
- No BI/SaaS/dashboard claim for v1.
- No silent fallback after an explicit backend/provider/DB is selected.
- Missing live DB/VDB evidence is a visible gap, not a pass.
- PostgreSQL is metadata scan/profile/demo validation only.
- MySQL is fixture/read-only metadata validation only; live local fixture evidence does not imply production MySQL execution support.
- Oracle remains unsupported.
